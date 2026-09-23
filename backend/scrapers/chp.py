"""
California Highway Patrol (CHP) incident scraper.
Fetches live incidents from the CAD dispatch feed.
"""

import copy
import re
import time
import threading
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from ..config import (
    CHP_SCRAPE_URL, HEADERS, PARAMS, HTTP_TIMEOUT_SECONDS, CHP_XML_URL,
    CHP_COLLECTOR, CHP_HTML_FALLBACK, CHP_POLL_SECONDS,
)
from ..config import ensure_pst, now_pst
from ..logging_utils import safe_print
from . import ScraperError
from ..incident_facts import narrative_lines

# ── Pre-compiled patterns ──────────────────────────────────────────────────
_LAT_LON_PATTERN  = re.compile(r"(\d+\.\d+ -\d+\.\d+)")
_EXCLUDED_DETAILS = {"Unit At Scene", "Unit Enroute", "Unit Assigned"}


def scrape_chp_html():
    """Return a list of incident dicts from the CHP live CAD feed."""
    try:
        response = requests.get(CHP_SCRAPE_URL, headers=HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        soup     = BeautifulSoup(response.text, "html.parser")
        table    = soup.find("table", id="gvIncidents")
        if not table:
            raise ScraperError("CHP incident table was not present")

        headers   = [th.get_text(strip=True) for th in table.find_all("th")]
        rows      = table.find_all("tr")[1:]  # Skip header
        viewstate = _get_viewstate(response.text)
        if not viewstate:
            raise ScraperError("CHP response did not contain __VIEWSTATE")

        incidents_list = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(_process_row, idx, row, headers, viewstate)
                for idx, row in enumerate(rows)
            ]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    incidents_list.append(result)

        return incidents_list
    except ScraperError:
        raise
    except Exception as exc:
        raise ScraperError(f"CHP scrape failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_viewstate(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    values = {field.get("name"): field.get("value", "") for field in soup.select('input[type="hidden"][name]')}
    return values if values.get("__VIEWSTATE") else None


def _get_incident_details(row_index, viewstate):
    """POST to CHP site to retrieve lat/lon and timeline details for one row."""
    try:
        data = {
            **viewstate,
            "__LASTFOCUS":          "",
            "__EVENTTARGET":        "gvIncidents",
            "__EVENTARGUMENT":      f"Select${row_index}",
            "ddlComCenter":         "BCCC",
            "ddlSearches":          "Choose One",
            "ddlResources":         "Choose One",
        }
        post = requests.post(
            CHP_SCRAPE_URL,
            params=PARAMS,
            headers=HEADERS,
            data=data,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        post.raise_for_status()
        return _extract_traffic_info(post.text)
    except requests.exceptions.RequestException as e:
        safe_print(f"CHP: Network error for row {row_index}: {e}")
        return {"DetailsAvailable": False}
    except Exception as e:
        safe_print(f"CHP: Unexpected error for row {row_index}: {e}")
        return {"DetailsAvailable": False}


def _extract_traffic_info(response_text):
    """Parse lat/lon and detail timeline from CHP HTML response."""
    matches = _LAT_LON_PATTERN.findall(response_text)
    soup    = BeautifulSoup(response_text, "html.parser")
    details_table = soup.find("table", id="tblDetails")
    details = []
    if details_table is None:
        return {"DetailsAvailable": False}

    if details_table:
        for row in details_table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 3:
                time_cell   = cells[0].get_text(strip=True)
                detail_cell = cells[-1].get_text(strip=True) if cells[-1].get("colspan") else ""
                if detail_cell and detail_cell not in _EXCLUDED_DETAILS:
                    details.append(f"[{time_cell}] {detail_cell}" if time_cell else detail_cell)

    # CHP displays newest first; the rest of the pipeline uses oldest first.
    payload = {"Details": list(reversed(details)), "DetailsAvailable": True}
    if matches:
        for match in matches:
            lat_str, lon_str = match.split()
            if 32 <= float(lat_str) <= 43 and -125 <= float(lon_str) <= -114:
                payload["Latitude"] = float(lat_str)
                payload["Longitude"] = float(lon_str)
                break
    return payload


def _process_row(idx, row, headers, viewstate):
    row_data = [cell.get_text(strip=True) for cell in row.find_all("td")]
    if len(row_data) != len(headers):
        raise ScraperError("CHP incident row does not match its headers")
    if "Location" in headers and row_data[headers.index("Location")] == "Media Log":
        return None

    table_data         = dict(zip(headers, row_data))
    table_data.pop("Details", None)
    additional_details = _get_incident_details(idx, viewstate)
    if not additional_details:
        safe_print(f"CHP WARNING: No extra details for row {idx}; keeping row without coords.")

    merged   = {**table_data, **additional_details}
    chp_time = table_data.get("Time", "")

    if chp_time:
        try:
            now       = now_pst()
            today_str = now.strftime("%Y-%m-%d")
            try:
                dt_obj = datetime.strptime(f"{today_str} {chp_time}", "%Y-%m-%d %I:%M %p")
            except ValueError:
                dt_obj = datetime.strptime(f"{today_str} {chp_time}", "%Y-%m-%d %H:%M")
            dt_obj = ensure_pst(dt_obj)

            if dt_obj > now + timedelta(minutes=5):
                dt_obj -= timedelta(days=1)

            merged["Timestamp"] = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            merged["Date"]      = dt_obj.strftime("%Y-%m-%d")
        except Exception as e:
            safe_print(f"CHP: Time parse error '{chp_time}': {e}")
            now = now_pst()
            merged["Timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
            merged["Date"]      = now.strftime("%Y-%m-%d")
    else:
        now = now_pst()
        merged["Timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
        merged["Date"]      = now.strftime("%Y-%m-%d")

    merged["Source"] = "CHP"
    merged["RawType"] = merged.get("Type", "")
    return merged


class CHPSnapshot(list):
    """Cached snapshots must not count as additional missing-source observations."""
    def __init__(self, records, fresh=True):
        super().__init__(records)
        self.fresh = fresh


_session = requests.Session()
_collection_lock = threading.Lock()
_cached = None
_last_poll = 0.0
_validators = {}
_xml_cached = None


def _xml_text(element, name):
    value = (element.findtext(name) or "").strip()
    return value[1:-1].strip() if value.startswith('"') and value.endswith('"') else value


def parse_chp_xml(content):
    if len(content) > 5_000_000 or b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ScraperError("Invalid CHP XML envelope")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ScraperError("Malformed CHP XML") from exc
    dispatches = root.findall("./Center/Dispatch[@ID='BCCC']")
    if root.tag != "State" or len(dispatches) != 1:
        raise ScraperError("CHP XML is missing an unambiguous BCCC dispatch")
    result = []
    seen = set()
    for log in dispatches[0]:
        if log.tag != "Log":
            raise ScraperError("Unexpected BCCC record")
        native = log.get("ID", "")
        match = re.fullmatch(r"(\d{6})BC(?:FSP)?(\d+)", native)
        if not match or native in seen:
            raise ScraperError("Invalid or duplicate CHP native ID")
        seen.add(native)
        location = _xml_text(log, "Location")
        if location == "Media Log":
            continue
        try:
            timestamp = ensure_pst(datetime.strptime(" ".join(_xml_text(log, "LogTime").split()), "%b %d %Y %I:%M%p"))
            date = datetime.strptime(match[1], "%y%m%d").strftime("%Y-%m-%d")
        except ValueError as exc:
            raise ScraperError("Invalid CHP incident date") from exc
        raw_type = _xml_text(log, "LogType")
        if not raw_type or not location or log.find("LogDetails") is None:
            raise ScraperError("Incomplete CHP incident")
        events = []
        for event in log.find("LogDetails"):
            if event.tag not in {"details", "units"}:
                raise ScraperError("Unknown CHP detail shape")
            if len(event) == 0 and not (event.text or "").strip():
                continue  # CHP represents a valid empty timeline as <details />.
            time_key, detail_key = ("DetailTime", "IncidentDetail") if event.tag == "details" else ("UnitTime", "UnitDetail")
            body = _xml_text(event, detail_key)
            try:
                dt = ensure_pst(datetime.strptime(" ".join(_xml_text(event, time_key).split()), "%b %d %Y %I:%M%p"))
            except ValueError as exc:
                raise ScraperError("Invalid CHP detail timestamp") from exc
            if not body:
                raise ScraperError("Missing CHP event text")
            sequence = re.match(r"\[(\d+)\]", body)
            events.append({"time": dt.strftime("%Y-%m-%d %H:%M:%S"), "text": body,
                           "kind": event.tag, "sequence": int(sequence[1]) if sequence else 0})
        events.sort(key=lambda event: (event["time"], event["sequence"]))
        incident = {
            "No.": match[2], "NativeID": native, "Source": "CHP", "Date": date,
            "Timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"), "RawType": raw_type,
            "Type": re.sub(r"^[A-Za-z0-9]+-", "", raw_type), "Location": location,
            "Location Desc.": _xml_text(log, "LocationDesc"), "Area": _xml_text(log, "Area"),
            "Details": [f"[{event['time']}] {event['text']}" for event in events if event["kind"] == "details"],
            "DetailsAvailable": True, "SourceEvents": events,
        }
        coords = _xml_text(log, "LATLON").split(":")
        if len(coords) == 2:
            try:
                lat, lon = float(coords[0]) / 1_000_000, -abs(float(coords[1]) / 1_000_000)
                if 32 <= lat <= 43 and -125 <= lon <= -114:
                    incident.update({"Latitude": lat, "Longitude": lon, "precision": "source"})
            except ValueError:
                pass  # Invalid coordinates do not erase otherwise valid incident facts.
        result.append(incident)
    return result


def scrape_chp_xml():
    global _xml_cached, _validators
    response = _session.get(CHP_XML_URL, headers={"Accept": "*/*", "User-Agent": HEADERS["User-Agent"], **_validators}, timeout=HTTP_TIMEOUT_SECONDS)
    if response.status_code == 304:
        if _xml_cached is None:
            raise ScraperError("CHP returned 304 without a cached XML snapshot")
        return copy.deepcopy(_xml_cached)
    response.raise_for_status()
    modified = response.headers.get("Last-Modified")
    if modified:
        try:
            age = (now_pst() - parsedate_to_datetime(modified)).total_seconds()
        except (ValueError, TypeError):
            raise ScraperError("Invalid CHP freshness header")
        if age > 300:
            raise ScraperError("CHP XML response is stale")
    records = parse_chp_xml(response.content)
    _validators = {}
    if response.headers.get("ETag"):
        _validators["If-None-Match"] = response.headers["ETag"]
    if modified:
        _validators["If-Modified-Since"] = modified
    _xml_cached = copy.deepcopy(records)
    return records


def scrape_chp_incidents():
    global _cached, _last_poll
    with _collection_lock:
        now = time.monotonic()
        if _cached is not None and now - _last_poll < CHP_POLL_SECONDS:
            return CHPSnapshot(copy.deepcopy(_cached), fresh=False)
        if CHP_COLLECTOR == "html":
            records = scrape_chp_html()
        elif CHP_COLLECTOR == "compare":
            # Comparison mode serves HTML; it never sends an extra set of AI jobs.
            records = scrape_chp_html()
            try:
                xml = scrape_chp_xml()
                comparison = compare_snapshots(records, xml)
                safe_print(f"CHP XML comparison: {comparison}")
            except Exception as exc:
                safe_print(f"CHP XML comparison unavailable: {type(exc).__name__}")
        else:
            try:
                records = scrape_chp_xml()
            except Exception as exc:
                if not CHP_HTML_FALLBACK:
                    raise ScraperError(f"CHP XML failed: {type(exc).__name__}") from exc
                safe_print(f"CHP XML unavailable; trying HTML: {type(exc).__name__}")
                records = scrape_chp_html()
        _cached = copy.deepcopy(records)
        _last_poll = now
        return CHPSnapshot(records)


def compare_snapshots(html, xml):
    def key(record):
        return record.get("No."), record.get("Date"), record.get("Area")
    left, right = {key(r): r for r in html}, {key(r): r for r in xml}
    mismatches = 0
    for k in left.keys() & right.keys():
        if any(left[k].get(field) != right[k].get(field) for field in ("Location", "Type", "Timestamp")):
            mismatches += 1
    shared = left.keys() & right.keys()
    return {"html_count": len(html), "xml_count": len(xml), "only_html": len(left.keys() - right.keys()),
            "only_xml": len(right.keys() - left.keys()), "field_mismatches": mismatches,
            "narrative_mismatches": sum(narrative_lines(left[k].get("Details")) != narrative_lines(right[k].get("Details")) for k in shared),
            "coordinate_mismatches": sum(any(left[k].get(f) != right[k].get(f) for f in ("Latitude", "Longitude")) for k in shared),
            "unavailable_html_details": sum(r.get("DetailsAvailable") is False for r in html)}
