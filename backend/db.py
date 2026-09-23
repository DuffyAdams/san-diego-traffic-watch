# db.py
"""
Database initialisation and all CRUD operations for the traffic app.
"""

import json
import re
import sqlite3

from .config import DB_FILE, db_lock, pst_date_str, pst_timestamp_str
from .logging_utils import safe_print
from .llm import generate_description
from .descriptions import incident_description, source_description, usable_description
from .sqlite_utils import sqlite_connection
from .description_jobs import init_schema as init_description_schema, sync_job


TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_incidents_timestamp ON incidents(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_active ON incidents(active)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_date ON incidents(date)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_no_date ON incidents(incident_no, date)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_source_timestamp "
    "ON incidents(source, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_source_active "
    "ON incidents(source, active)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_source_date ON incidents(source, date)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_llm_pending "
    "ON incidents(active, llm_pending_at)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_pagination "
    "ON incidents(timestamp DESC, incident_no DESC)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_dow_hour "
    "ON incidents(strftime('%w', timestamp), strftime('%H', timestamp))",
    "CREATE INDEX IF NOT EXISTS idx_incidents_dow_date "
    "ON incidents(strftime('%w', timestamp), date(timestamp))",
    "CREATE INDEX IF NOT EXISTS idx_incidents_source_dow_hour "
    "ON incidents(source, strftime('%w', timestamp), strftime('%H', timestamp))",
    "CREATE INDEX IF NOT EXISTS idx_incidents_source_dow_date "
    "ON incidents(source, strftime('%w', timestamp), date(timestamp))",
    "CREATE INDEX IF NOT EXISTS idx_comments_incident_time "
    "ON comments(incident_no, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_likes_incident_device "
    "ON likes(incident_no, device_uuid)",
    "CREATE INDEX IF NOT EXISTS idx_api_events_timestamp ON api_events(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_api_events_host_timestamp "
    "ON api_events(host, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_api_events_device_time "
    "ON api_events(device_uuid, timestamp)",
)


# ---------------------------------------------------------------------------
# Schema & migrations
# ---------------------------------------------------------------------------

def init_db(db_file=None):
    """Initialize a SQLite database schema and run pending migrations."""
    with sqlite_connection(db_file or DB_FILE) as conn:
        conn.execute("PRAGMA journal_mode=WAL")   # Better concurrent read/write
        conn.execute("PRAGMA synchronous=NORMAL")  # Balanced durability/speed
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()

        # ── Core tables ────────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_no       TEXT,
                date              TEXT,
                timestamp         TEXT,
                city              TEXT,
                neighborhood      TEXT,
                location          TEXT,
                location_desc     TEXT,
                type              TEXT,
                details           TEXT,
                description       TEXT,
                latitude          REAL,
                longitude         REAL,
                map_filename      TEXT,
                likes             INTEGER DEFAULT 0,
                comments          TEXT DEFAULT '[]',
                active            INTEGER DEFAULT 1,
                source            TEXT DEFAULT 'CHP',
                batch_queued_at   TEXT DEFAULT NULL,
                batch_enriched_at TEXT DEFAULT NULL,
                llm_pending_at    TEXT DEFAULT NULL,
                PRIMARY KEY (incident_no, date)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                device_uuid  TEXT,
                incident_no  TEXT,
                timestamp    TEXT,
                PRIMARY KEY (device_uuid, incident_no)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                device_uuid TEXT,
                incident_no TEXT,
                username    TEXT,
                comment     TEXT,
                timestamp   TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS api_events (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                device_uuid  TEXT,
                route        TEXT,
                request_type TEXT,
                host         TEXT,
                client_ip    TEXT,
                timestamp    TEXT
            )
        """)

        # ── Migrations (safe ALTER TABLE with fallback) ────────────────────
        _add_column(cur, "incidents", "source",           "TEXT DEFAULT 'CHP'")
        _add_column(cur, "incidents", "geocode_precision", "TEXT DEFAULT 'unknown'")
        _add_column(cur, "incidents", "severity",          "INTEGER DEFAULT NULL")
        _add_column(cur, "incidents", "batch_queued_at",   "TEXT DEFAULT NULL")
        _add_column(cur, "incidents", "batch_enriched_at", "TEXT DEFAULT NULL")
        _add_column(cur, "incidents", "llm_pending_at",    "TEXT DEFAULT NULL")

        # Carry unfinished work from the removed Gemini batch queue into the
        # provider-neutral per-incident LLM retry queue exactly once.
        cur.execute(
            """
            UPDATE incidents
            SET llm_pending_at = COALESCE(llm_pending_at, batch_queued_at)
            WHERE batch_queued_at IS NOT NULL
              AND batch_enriched_at IS NULL
              AND active = 1
            """
        )
        cur.execute(
            """
            UPDATE incidents
            SET batch_queued_at = NULL, batch_enriched_at = NULL
            WHERE batch_queued_at IS NOT NULL OR batch_enriched_at IS NOT NULL
            """
        )

        for name, definition in {
            "native_id": "TEXT", "raw_type": "TEXT", "area": "TEXT",
            "details_stale": "INTEGER DEFAULT 0", "description_origin": "TEXT DEFAULT 'legacy'",
            "missing_polls": "INTEGER DEFAULT 0", "related_incident": "TEXT",
        }.items():
            _add_column(cur, "incidents", name, definition)
        init_description_schema(conn)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_incidents_native ON incidents(source, native_id) WHERE native_id IS NOT NULL")
        cur.execute("""CREATE TABLE IF NOT EXISTS incident_source_events (
            source TEXT NOT NULL, native_id TEXT NOT NULL, event_hash TEXT NOT NULL,
            observed_at TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(source, native_id, event_hash))""")

        # ── Type normalisation ─────────────────────────────────────────────
        _normalise_types(cur)

        # ── Indexes ────────────────────────────────────────────────────────
        for statement in INDEX_STATEMENTS:
            cur.execute(statement)

        conn.row_factory = sqlite3.Row
        # Recover legacy pending work without re-summarizing completed history.
        for row in conn.execute("SELECT * FROM incidents WHERE active=1 AND llm_pending_at IS NOT NULL").fetchall():
            sync_job(conn, dict(row))
        conn.commit()


def _add_column(cur, table, column, definition):
    """Add a column when it is absent without masking migration failures."""
    existing_columns = {
        row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing_columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _normalise_types(cur):
    """Standardise legacy type names in the incidents table."""
    mappings = [
        ("type LIKE 'Trfc Collision%'",            "Traffic Collision"),
        ("type = 'Assist CT with Maintenance'",    "Maintenance"),
        ("type = 'Road/Weather Conditions'",       "Road Conditions"),
        ("type = 'Object Flying From Veh'",        "Debris from Vehicle"),
        ("type = 'Assist with Construction'",      "Construction"),
    ]
    for condition, new_type in mappings:
        cur.execute(f"UPDATE incidents SET type = ? WHERE {condition}", (new_type,))


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def read_incidents(
    limit=20,
    incident_types=None,
    locations=None,
    sources=None,
    active_only=False,
    cursor=None,
    date_filter=None,
    device_uuid=None,
):
    """Fetch incidents with optional filtering, cursor-based pagination, and embedded comments."""
    with sqlite_connection(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        conditions, params = ["related_incident IS NULL"], []

        if sources:
            _in(conditions, params, "source", sources)
        if incident_types:
            _in(conditions, params, "type", incident_types)
        if locations:
            _in(conditions, params, "location", locations)
        if active_only:
            conditions.append("active = 1")
        if date_filter in ("day", "daily"):
            conditions.append("date = ?")
            params.append(pst_date_str())
        if cursor:
            if "|" in cursor:
                ts_part, id_part = cursor.split("|", 1)
                conditions.append("(timestamp, incident_no) < (?, ?)")
                params.extend([ts_part, id_part])
            else:
                conditions.append("timestamp < ?")
                params.append(cursor)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT * FROM incidents{where} ORDER BY timestamp DESC, incident_no DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, tuple(params))
        incidents = [dict(row) for row in cur.fetchall()]
        for incident in incidents:
            incident["description"] = incident_description(incident)

        if incidents:
            _attach_comments(cur, incidents)
            _attach_user_like_state(cur, incidents, device_uuid)

        return incidents


def _in(conditions, params, column, values):
    placeholders = ",".join("?" for _ in values)
    conditions.append(f"{column} IN ({placeholders})")
    params.extend(values)


def _attach_comments(cur, incidents):
    """Join comments onto each incident dict in-place."""
    incident_nos = [inc["incident_no"] for inc in incidents]
    placeholders = ",".join("?" for _ in incident_nos)
    cur.execute(
        f"SELECT incident_no, username, comment, timestamp "
        f"FROM comments WHERE incident_no IN ({placeholders}) ORDER BY timestamp ASC",
        tuple(incident_nos),
    )
    by_incident = {}
    for row in cur.fetchall():
        by_incident.setdefault(row[0], []).append(
            {"username": row[1] or "Anonymous", "comment": row[2], "timestamp": row[3]}
        )
    for inc in incidents:
        inc["comments"] = by_incident.get(inc["incident_no"], [])
        try:
            inc["Details"] = json.loads(inc["details"]) if inc["details"] else []
        except (json.JSONDecodeError, TypeError):
            inc["Details"] = []


def _attach_user_like_state(cur, incidents, device_uuid):
    """Annotate incidents with whether the current device has liked them."""
    liked_incidents = set()

    if device_uuid:
        incident_nos = [inc["incident_no"] for inc in incidents]
        placeholders = ",".join("?" for _ in incident_nos)
        cur.execute(
            f"SELECT incident_no FROM likes WHERE device_uuid = ? "
            f"AND incident_no IN ({placeholders})",
            (device_uuid, *incident_nos),
        )
        liked_incidents = {row[0] for row in cur.fetchall()}

    for inc in incidents:
        inc["liked_by_user"] = inc["incident_no"] in liked_incidents


def with_user_like_state(incidents, device_uuid):
    """Return incident copies annotated with whether this device liked each one."""
    incident_copies = []
    for incident in incidents:
        copied = dict(incident)
        if isinstance(copied.get("comments"), list):
            copied["comments"] = [dict(comment) for comment in copied["comments"]]
        incident_copies.append(copied)

    if not incident_copies:
        return incident_copies

    with sqlite_connection(DB_FILE) as conn:
        cur = conn.cursor()
        _attach_user_like_state(cur, incident_copies, device_uuid)

    return incident_copies


def incident_exists(incident_no, date):
    """Return True if an incident already exists in the DB."""
    with sqlite_connection(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM incidents WHERE incident_no = ? AND date = ?",
            (str(incident_no), date),
        )
        return cur.fetchone() is not None


def fetch_existing_incidents(keys):
    """Fetch existing incidents for (incident_no, date) keys into a dict."""
    normalized_keys = [
        (str(incident_no), date)
        for incident_no, date in keys
        if incident_no and date
    ]
    if not normalized_keys:
        return {}

    existing = {}
    with db_lock:
        with sqlite_connection(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Keep comfortably under SQLite's common 999-parameter limit.
            chunk_size = 400
            for start in range(0, len(normalized_keys), chunk_size):
                chunk = normalized_keys[start : start + chunk_size]
                placeholders = ",".join(["(?, ?)"] * len(chunk))
                params = [value for key in chunk for value in key]
                cur.execute(
                    f"SELECT * FROM incidents WHERE (incident_no, date) IN ({placeholders})",
                    tuple(params),
                )
                for row in cur.fetchall():
                    record = dict(row)
                    existing[(record["incident_no"], record["date"])] = record

    return existing


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def save_or_update_incident(
    data,
    existing_record=None,
    log_unchanged=False,
    return_status=False,
    generate_description_on_insert=True,
):
    """Insert or update an incident.

    By default this preserves the historical bool return value. Callers that
    need accounting can pass return_status=True to receive inserted, updated,
    unchanged, or invalid.
    """
    if not data:
        return "invalid" if return_status else False

    incident_no = data.get("No.") or data.get("Incident No.")
    if not incident_no:
        safe_print("No incident number found in data.")
        return "invalid" if return_status else False

    date            = data.get("Date",      pst_date_str())
    new_timestamp   = data.get("Timestamp", pst_timestamp_str())
    city            = data.get("City", "")
    neighborhood    = data.get("Neighborhood", "")
    location        = data.get("Location", "")
    location_desc   = data.get("Location Desc.", "")
    source          = data.get("Source", "CHP")
    geocode_precision = data.get("precision", "unknown")
    latitude        = data.get("Latitude")
    longitude       = data.get("Longitude")
    new_map_filename = data.get("MapFilename", "")
    active_status   = data.get("active", 1)

    # Standardise type
    type_field = data.get("Type", "")
    if type_field and type_field.startswith("Trfc Collision"):
        type_field = "Traffic Collision"

    # SDPD sometimes shifts its table so the incident datetime lands in `Type`
    # and the actual label lands in `Location Desc.`. Recover that shape here.
    if (
        source == "SDPD"
        and isinstance(type_field, str)
        and TIMESTAMP_PATTERN.match(type_field)
        and location_desc
    ):
        new_timestamp = type_field
        date = type_field[:10]
        type_field = location_desc

    # A failed detail fetch is not evidence that the source erased its narrative.
    details_unavailable = data.get("DetailsAvailable") is False
    new_details = data.get("Details", [])
    if isinstance(new_details, str):
        new_details = [new_details]
    details_json = json.dumps(new_details)

    if existing_record is not None and not isinstance(existing_record, dict):
        existing_record = dict(existing_record)

    # ── Fetch existing record only when a caller did not prefetch it ───────
    if existing_record is None:
        with db_lock:
            with sqlite_connection(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT * FROM incidents WHERE incident_no = ? AND date = ?",
                    (str(incident_no), date),
                )
                row = cur.fetchone()
                existing_record = dict(row) if row else None

    if details_unavailable and existing_record:
        try:
            new_details = json.loads(existing_record.get("details") or "[]")
        except (ValueError, TypeError):
            new_details = []
        details_json = json.dumps(new_details)
        data = {**data, "Details": new_details}

    # Immediate source fallback; durable jobs own all network enrichment.
    if not existing_record:
        new_description = incident_description(data)
        new_severity = data.get("severity")
    else:
        new_description = existing_record.get("description")
        new_severity = existing_record.get("severity")
        if not usable_description(new_description) or new_description == source_description(existing_record):
            new_description = source_description(data)

    # ── Apply DB update/insert ─────────────────────────────────────────────
    with db_lock:
        with sqlite_connection(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            if existing_record:
                existing_data = existing_record
                updates, params = [], []

                if details_json != existing_data.get("details", ""):
                    updates.append("details = ?")
                    params.append(details_json)

                if new_description != existing_data.get("description"):
                    # A background AI summary may have arrived since prefetch.
                    updates.append(
                        "description = CASE WHEN description IS ? THEN ? ELSE description END"
                    )
                    params.extend([existing_data.get("description"), new_description])

                mutable_values = {
                    "timestamp": new_timestamp,
                    "city": city,
                    "neighborhood": neighborhood,
                    "location": location,
                    "location_desc": location_desc,
                    "type": type_field,
                    "active": active_status,
                    "source": source,
                    "raw_type": data.get("RawType") or data.get("Type", ""),
                    "area": data.get("Area", ""),
                    "details_stale": int(details_unavailable),
                    "missing_polls": 0,
                }
                if "RelatedIncidentID" in data:
                    mutable_values["related_incident"] = data["RelatedIncidentID"]
                for column, value in mutable_values.items():
                    if value != existing_data.get(column):
                        updates.append(f"{column} = ?")
                        params.append(value)

                optional_values = {
                    "native_id": data.get("NativeID"),
                    "latitude": latitude,
                    "longitude": longitude,
                    "map_filename": new_map_filename or None,
                    "geocode_precision": (
                        geocode_precision if geocode_precision != "unknown" else None
                    ),
                }
                for column, value in optional_values.items():
                    if value is not None and value != existing_data.get(column):
                        updates.append(f"{column} = ?")
                        params.append(value)

                if updates:
                    query = (
                        f"UPDATE incidents SET {', '.join(updates)} "
                        "WHERE incident_no = ? AND date = ?"
                    )
                    params.extend([str(incident_no), existing_data.get("date", date)])
                    cur.execute(query, tuple(params))
                    _sync_source_and_job(conn, str(incident_no), date, data)
                    conn.commit()
                    safe_print(f"Incident {incident_no} updated.")
                    return "updated" if return_status else True
                else:
                    _sync_source_and_job(conn, str(incident_no), date, data)
                    if log_unchanged:
                        safe_print(f"No changes for incident {incident_no}.")
                    return "unchanged" if return_status else False
            else:
                cur.execute(
                    """
                    UPDATE incidents
                    SET active = 0
                    WHERE incident_no = ? AND date != ? AND active = 1
                    """,
                    (str(incident_no), date),
                )
                cur.execute(
                    """
                    INSERT INTO incidents
                    (
                        incident_no, date, timestamp, city, neighborhood,
                        location, location_desc, type, details, description,
                        latitude, longitude, map_filename, likes, comments,
                        active, source, geocode_precision, severity,
                        batch_queued_at, batch_enriched_at, llm_pending_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(incident_no), date, new_timestamp, city, neighborhood,
                        location, location_desc, type_field, details_json, new_description,
                        latitude, longitude, new_map_filename, 0, "[]",
                        active_status, source, geocode_precision, new_severity,
                        None,
                        None,
                        pst_timestamp_str() if active_status else None,
                    ),
                )
                conn.execute("""UPDATE incidents SET native_id=?, raw_type=?, area=?, details_stale=?, related_incident=?, description_origin='source'
                    WHERE incident_no=? AND date=?""",
                    (data.get("NativeID"), data.get("RawType") or data.get("Type", ""), data.get("Area", ""),
                     int(details_unavailable), data.get("RelatedIncidentID"), str(incident_no), date))
                _sync_source_and_job(conn, str(incident_no), date, data)
                conn.commit()
                safe_print(f"Incident {incident_no} inserted.")
                return "inserted" if return_status else True


def _sync_source_and_job(conn, incident_no, date, data):
    # Preserve source snapshots only when they change, including administrative details.
    import hashlib
    if data.get("NativeID") and data.get("DetailsAvailable", True):
        payload = json.dumps({k: data.get(k) for k in ("RawType", "Details", "Location", "Location Desc.", "SourceEvents")}, sort_keys=True)
        conn.execute("INSERT OR IGNORE INTO incident_source_events VALUES (?, ?, ?, ?, ?)",
                     (data.get("Source", "CHP"), data["NativeID"], hashlib.sha256(payload.encode()).hexdigest(), pst_timestamp_str(), payload))
    row = conn.execute("SELECT * FROM incidents WHERE incident_no=? AND date=?", (incident_no, date)).fetchone()
    sync_job(conn, dict(row))
