"""
Background monitoring loop: orchestrates scraping, geocoding,
incident persistence, and description generation.
"""

import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .config import (
    DB_FILE,
    HEALTHCHECK_URL,
    HTTP_TIMEOUT_SECONDS,
    SDSO_API_URL,
    db_lock,
    geo_cache,
    now_pst,
    pst_date_str,
)
from .db import fetch_existing_incidents, save_or_update_incident
from .geocoding import geocode_location as geo_geocode_location
from .llm import generate_description
from .logging_utils import safe_print
from .runtime_metrics import record_scrape_success
from .sqlite_utils import sqlite_connection


_description_executor = ThreadPoolExecutor(max_workers=2)
_refresh_inflight = set()
_refresh_inflight_lock = threading.Lock()


def geocode_location(location_query):
    """Geocode using the shared module and cache."""
    return geo_geocode_location(location_query, cache=geo_cache, debug_print=safe_print)


# ---------------------------------------------------------------------------
# Per-incident processing
# ---------------------------------------------------------------------------

def process_and_save_incident(incident, existing_record=None):
    """Geocode and persist one incident. Return its ID, or ``None`` on failure."""
    try:
        incident_no = incident.get("No.") or incident.get("Incident No.")
        if not incident_no:
            safe_print("WARNING: No incident number found. Skipping.")
            return None

        inc_exists = existing_record is not None
        needs_geocoding = not inc_exists
        incoming_details = incident.get("Details", [])
        if isinstance(incoming_details, str):
            incoming_details = [incoming_details]
        details_changed = bool(
            inc_exists
            and json.dumps(incoming_details) != existing_record.get("details", "")
        )

        if not inc_exists:
            # Write the row immediately so the feed can surface it without waiting
            # for geocoding or description enrichment to finish.
            save_or_update_incident(
                incident,
                existing_record=None,
                generate_description_on_insert=False,
            )
            _schedule_description_refresh(dict(incident))

        if inc_exists and (
            existing_record.get("latitude") is None
            or existing_record.get("longitude") is None
        ):
            safe_print(f"Incident {incident_no} is missing coordinates; will geocode.")
            needs_geocoding = True

        if needs_geocoding:
            _geocode_incident(incident)

        save_or_update_incident(
            incident,
            existing_record=existing_record if inc_exists else None,
            generate_description_on_insert=False,
        )
        if details_changed:
            _schedule_description_refresh(dict(incident))
        return str(incident_no)
    except Exception as e:
        inc_id = incident.get("No.", "unknown") if isinstance(incident, dict) else "unknown"
        safe_print(f"Error processing incident {inc_id}: {e}")
        return None


def _geocode_incident(incident):
    """Attempt geocoding for sources that don't provide coordinates (SDPD/SDFD/SDSO)."""
    if (
        incident.get("Latitude") is not None
        and incident.get("Longitude") is not None
    ):
        return  # Already has coordinates (e.g. CHP)

    source       = incident.get("Source", "")
    location_str = incident.get("Location", "")

    if source == "SDPD":
        query = f"{location_str}, San Diego, CA"

    elif source == "SDFD":
        cross = incident.get("Location Desc.", "")
        if cross and cross != "N/A" and cross.lower() not in location_str.lower():
            query = f"{location_str} and {cross}, San Diego, CA"
        else:
            query = f"{location_str}, San Diego, CA"

    elif source == "SDSO":
        community = incident.get("Neighborhood", "")
        address   = location_str.replace("/", " & ")
        query = (
            f"{address}, {community}, CA"
            if community
            else f"{address}, San Diego County, CA"
        )

    elif source == "CHP":
        query = f"{location_str}, San Diego County, CA" if location_str else "San Diego County, CA"

    else:
        return

    safe_print(f"Geocoding {incident.get('No.')} ({source}): {query}")
    coords = geocode_location(query)
    if coords:
        incident.update(coords)


def _normalise_details(details):
    """Return details in the same list form persisted by ``db.py``."""
    if isinstance(details, str):
        return [details]
    return details if isinstance(details, list) else []


def _refresh_key(incident):
    incident_no = incident.get("No.") or incident.get("Incident No.")
    incident_date = incident.get("Date", pst_date_str())
    details_json = json.dumps(_normalise_details(incident.get("Details", [])))
    return str(incident_no or ""), incident_date, details_json


def _schedule_description_refresh(incident):
    """Schedule one LLM refresh while deduplicating in-flight work."""
    # Already-closed source records keep their immediate factual description.
    # The active-only worker cannot save enrichment for these records.
    if incident.get("active", 1) == 0:
        return False
    key = _refresh_key(incident)
    if not key[0]:
        return False

    with _refresh_inflight_lock:
        if key in _refresh_inflight:
            return False
        _refresh_inflight.add(key)

    try:
        future = _description_executor.submit(
            _refresh_incident_description, dict(incident)
        )
    except Exception:
        with _refresh_inflight_lock:
            _refresh_inflight.discard(key)
        raise

    def release(_future):
        with _refresh_inflight_lock:
            _refresh_inflight.discard(key)

    future.add_done_callback(release)
    return True


def _recover_pending_mistral_refreshes(limit=100):
    """Resubmit persisted per-incident LLM work after failures/restarts."""
    with db_lock:
        with sqlite_connection(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT incident_no, date, timestamp, city, neighborhood, location, location_desc,
                       type, details, source
                FROM incidents
                WHERE active = 1 AND llm_pending_at IS NOT NULL
                ORDER BY llm_pending_at, timestamp, incident_no
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    for row in rows:
        record = dict(row)
        try:
            details = json.loads(record.get("details") or "[]")
        except (TypeError, json.JSONDecodeError):
            details = [str(record.get("details") or "")]
        _schedule_description_refresh(
            {
                "No.": record["incident_no"],
                "Date": record["date"],
                "Timestamp": record.get("timestamp") or "",
                "City": record.get("city") or "",
                "Neighborhood": record.get("neighborhood") or "",
                "Location": record.get("location") or "",
                "Location Desc.": record.get("location_desc") or "",
                "Type": record.get("type") or "",
                "Details": details,
                "Source": record.get("source") or "CHP",
            }
        )


def _refresh_incident_description(incident):
    """Generate a durable LLM summary without blocking incident ingest."""
    try:
        incident_no = incident.get("No.") or incident.get("Incident No.")
        if not incident_no:
            return

        details = _normalise_details(incident.get("Details", []))
        details_json = json.dumps(details)
        incident_snapshot = dict(incident)
        incident_snapshot["Details"] = json.loads(details_json)

        description, severity = generate_description(
            incident_snapshot, raise_on_error=True
        )
        incident_date = incident.get("Date", pst_date_str())

        with db_lock:
            with sqlite_connection(DB_FILE) as conn:
                conn.cursor().execute(
                    """
                    UPDATE incidents
                    SET description = ?, severity = ?, llm_pending_at = NULL
                    WHERE incident_no = ? AND date = ?
                        AND details = ? AND active = 1
                    """,
                    (
                        description,
                        severity,
                        str(incident_no),
                        incident_date,
                        details_json,
                    ),
                )
                conn.commit()
    except Exception as e:
        safe_print(
            f"Background description refresh failed for {incident.get('No.', 'unknown')}: {e}"
        )


# ---------------------------------------------------------------------------
# Monitoring loop
# ---------------------------------------------------------------------------

def _default_scrapers():
    """Build the source-to-scraper mapping for configured feeds."""
    from .scrapers.chp import scrape_chp_incidents
    from .scrapers.sdfd import scrape_sdfd_incidents
    from .scrapers.sdpd import scrape_sdpd_incidents
    from .scrapers.sdso import scrape_sdso_incidents

    scrapers = {
        "CHP": scrape_chp_incidents,
        "SDPD": scrape_sdpd_incidents,
        "SDFD": scrape_sdfd_incidents,
    }
    if SDSO_API_URL:
        scrapers["SDSO"] = scrape_sdso_incidents
    return scrapers


def run_monitor_cycle(scrapers=None):
    """Run one complete scrape cycle and return its elapsed time.

    Stale-incident cleanup only runs for a source when both its scrape and all
    of its incident-processing tasks succeeded. A transient failure therefore
    cannot incorrectly clear that source's live incidents.
    """
    cycle_start = time.perf_counter()
    safe_print(f"Checking updates... {now_pst().strftime('%Y-%m-%d %H:%M:%S')}")

    scrapers = scrapers or _default_scrapers()
    all_incidents = []
    successful_sources = set()

    with ThreadPoolExecutor(max_workers=max(1, len(scrapers))) as executor:
        futures = {executor.submit(scraper): source for source, scraper in scrapers.items()}
        for future in as_completed(futures):
            source = futures[future]
            try:
                incidents = future.result()
                if not isinstance(incidents, list):
                    raise TypeError("scraper returned a non-list result")
                for incident in incidents:
                    incident.setdefault("Source", source)
                all_incidents.extend(incidents)
                successful_sources.add(source)
                safe_print(f"{source}: {len(incidents)} incidents fetched")
            except Exception as exc:
                safe_print(f"Error scraping {source}: {exc}")

    if not successful_sources:
        raise RuntimeError("All configured traffic sources failed")

    active_ids_by_source = {source: set() for source in successful_sources}
    failed_processing_sources = set()

    if all_incidents:
        all_incidents.sort(key=lambda item: 0 if item.get("Source") == "CHP" else 1)
        incident_keys = [
            (
                incident.get("No.") or incident.get("Incident No."),
                incident.get("Date", pst_date_str()),
            )
            for incident in all_incidents
        ]
        existing_records = fetch_existing_incidents(incident_keys)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {}
            for incident in all_incidents:
                incident_no = incident.get("No.") or incident.get("Incident No.")
                incident_date = incident.get("Date", pst_date_str())
                existing_record = existing_records.get((str(incident_no), incident_date))
                future = executor.submit(
                    process_and_save_incident,
                    incident,
                    existing_record,
                )
                futures[future] = incident.get("Source", "CHP")

            for future in as_completed(futures):
                source = futures[future]
                try:
                    incident_id = future.result()
                except Exception as exc:
                    safe_print(f"Error processing {source} incident: {exc}")
                    incident_id = None
                if incident_id:
                    active_ids_by_source[source].add(incident_id)
                else:
                    failed_processing_sources.add(source)
    else:
        safe_print("All successful source feeds are currently empty.")

    for source in failed_processing_sources:
        active_ids_by_source.pop(source, None)

    _generate_final_descriptions(active_ids_by_source)
    _mark_inactive(active_ids_by_source)
    _recover_pending_mistral_refreshes()
    return time.perf_counter() - cycle_start


def monitor_traffic_data(interval=15):
    """Continuously run scrape cycles until the process is interrupted."""
    safe_print("Starting continuous traffic monitoring...")
    safe_print(f"DB: {DB_FILE}")
    safe_print("Press Ctrl+C to stop.")

    try:
        while True:
            try:
                elapsed = run_monitor_cycle()
                _ping_healthcheck(success=True)
                record_scrape_success(elapsed)
            except Exception as exc:
                safe_print(f"Error in monitoring loop: {exc}")
                _ping_healthcheck(success=False)
            time.sleep(interval)
    except KeyboardInterrupt:
        safe_print("Monitoring stopped by user.")


def _generate_final_descriptions(active_ids_by_source):
    """Generate closing LLM summaries for incidents that just went inactive."""
    if not active_ids_by_source:
        return

    with db_lock:
        with sqlite_connection(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            sources = tuple(active_ids_by_source)
            placeholders = ",".join("?" for _ in sources)
            rows = conn.execute(
                f"SELECT * FROM incidents WHERE active = 1 AND source IN ({placeholders})",
                sources,
            ).fetchall()

    newly_inactive = [
        dict(row)
        for row in rows
        if row["incident_no"] not in active_ids_by_source[row["source"]]
    ]

    if not newly_inactive:
        return

    safe_print(f"Generating final summaries for {len(newly_inactive)} newly inactive incidents...")

    def _process_final(record):
        try:
            details = json.loads(record.get("details", "[]") or "[]")
            if not details:
                return
            data = {
                "Neighborhood":  record.get("neighborhood"),
                "Location":      record.get("location"),
                "Location Desc.": record.get("location_desc"),
                "Type":          record.get("type"),
                "Details":       details,
            }
            final_desc, final_sev = generate_description(data)
            with db_lock:
                with sqlite_connection(DB_FILE) as conn:
                    conn.cursor().execute(
                        """
                        UPDATE incidents
                        SET description = ?, severity = ?, active = 0,
                            llm_pending_at = NULL
                        WHERE incident_no = ? AND date = ?
                        """,
                        (
                            final_desc,
                            final_sev,
                            record["incident_no"],
                            record["date"],
                        ),
                    )
                    conn.commit()
        except Exception as ex:
            safe_print(f"Error generating final description for {record.get('incident_no')}: {ex}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        for _ in as_completed([executor.submit(_process_final, r) for r in newly_inactive]):
            pass


def _mark_inactive(active_ids_by_source):
    """Deactivate stale incidents for sources with fully successful cycles."""
    if not active_ids_by_source:
        return

    with db_lock:
        with sqlite_connection(DB_FILE) as conn:
            cur = conn.cursor()
            for source, active_ids in active_ids_by_source.items():
                if active_ids:
                    placeholders = ",".join("?" for _ in active_ids)
                    cur.execute(
                        f"""
                        UPDATE incidents
                        SET active = 0
                        WHERE source = ? AND incident_no NOT IN ({placeholders})
                        """,
                        (source, *active_ids),
                    )
                else:
                    cur.execute(
                        "UPDATE incidents SET active = 0 WHERE source = ?",
                        (source,),
                    )
            conn.commit()


def _ping_healthcheck(success=True):
    if not HEALTHCHECK_URL:
        return
    url = HEALTHCHECK_URL + ("" if success else "/fail")
    try:
        requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
        safe_print(f"Healthcheck ping: {'success' if success else 'failure'}")
    except Exception as e:
        safe_print(f"Failed to ping healthcheck: {e}")
