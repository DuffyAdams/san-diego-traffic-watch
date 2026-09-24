"""One durable, leased description job per incident; updates supersede pending work."""

import json
import random
import sqlite3
import time
import uuid

from .config import (
    DESCRIPTION_DEBOUNCE_SECONDS, DESCRIPTION_MAX_WAIT_SECONDS,
    DESCRIPTION_MAX_ATTEMPTS, DESCRIPTION_TEMPLATES, LLM_TIMEOUT_SECONDS,
    LLM_API_CONFIGURED, TESTMODE,
)
from .incident_facts import incident_facts, fact_hash, template_description, severity_for, urgent_change
from .sqlite_utils import sqlite_connection
from .descriptions import source_description, uses_ai_description


def init_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS description_jobs (
            incident_no TEXT NOT NULL, date TEXT NOT NULL,
            desired_hash TEXT NOT NULL, completed_hash TEXT,
            facts_json TEXT NOT NULL, payload_json TEXT NOT NULL,
            trigger_reason TEXT NOT NULL, first_queued_at REAL NOT NULL,
            due_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            lease_token TEXT, lease_until REAL, last_error TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            PRIMARY KEY (incident_no, date)
        );
        CREATE INDEX IF NOT EXISTS idx_description_jobs_due ON description_jobs(status, due_at);
        CREATE TABLE IF NOT EXISTS llm_attempts (
            id INTEGER PRIMARY KEY, created_at REAL NOT NULL,
            incident_no TEXT, date TEXT, input_hash TEXT, trigger_reason TEXT,
            model TEXT, provider TEXT, prompt_version TEXT, reasoning_effort TEXT, max_tokens INTEGER,
            input_tokens INTEGER, completion_tokens INTEGER, reasoning_tokens INTEGER,
            cached_tokens INTEGER, cost REAL, duration_seconds REAL,
            finish_reason TEXT, outcome TEXT, generation_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_llm_attempts_created ON llm_attempts(created_at);
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(llm_attempts)")}
    for name, kind in (("reasoning_effort", "TEXT"), ("max_tokens", "INTEGER")):
        if name not in columns:
            conn.execute(f"ALTER TABLE llm_attempts ADD COLUMN {name} {kind}")


def snapshot(row):
    """Use persisted source fields so process restarts see identical inputs."""
    return {
        "No.": row["incident_no"], "Date": row["date"],
        "Source": row.get("source"), "Type": row.get("type"),
        "RawType": row.get("raw_type"), "Location": row.get("location"),
        "Location Desc.": row.get("location_desc"), "Neighborhood": row.get("neighborhood"),
        "Area": row.get("area"), "City": row.get("city"), "Details": row.get("details"),
    }


def sync_job(conn, row, now=None):
    """Called inside the source-write transaction; never contacts the provider."""
    now = time.time() if now is None else now
    key = row["incident_no"], row["date"]
    if not uses_ai_description(row):
        # Also retire legacy/retry jobs and invalidate any older worker's lease.
        conn.execute("""UPDATE description_jobs SET status='source',
            completed_hash=desired_hash, lease_token=NULL, lease_until=NULL, last_error=NULL
            WHERE incident_no=? AND date=?""", key)
        conn.execute("""UPDATE incidents SET description=?, severity=?,
            description_origin='source', llm_pending_at=NULL WHERE incident_no=? AND date=?""",
            (source_description(row), severity_for(incident_facts(row)), *key))
        return
    old = conn.execute("SELECT * FROM description_jobs WHERE incident_no = ? AND date = ?", key).fetchone()
    old = dict(old) if old else None
    if row.get("related_incident"):
        conn.execute("UPDATE description_jobs SET status='related' WHERE incident_no=? AND date=?", key)
        conn.execute("UPDATE incidents SET llm_pending_at=NULL WHERE incident_no=? AND date=?", key)
        return
    if not row.get("active", 1) and old is None:
        return
    payload = snapshot(row)
    facts = incident_facts(payload)
    version = fact_hash(facts)
    if old and old["desired_hash"] == version and old["status"] != "related":
        return
    simple = template_description(facts) if DESCRIPTION_TEMPLATES else None
    if simple:
        conn.execute("""UPDATE incidents SET description = ?, severity = ?, description_origin = 'template',
                     llm_pending_at = NULL WHERE incident_no = ? AND date = ?""",
                     (simple, severity_for(facts), *key))
    previous = json.loads(old["facts_json"]) if old else {}
    urgent = urgent_change(previous, facts)
    pending = old and old["status"] == "pending"
    first = old["first_queued_at"] if pending else now
    due = now if urgent or not old else min(now + DESCRIPTION_DEBOUNCE_SECONDS, first + DESCRIPTION_MAX_WAIT_SECONDS)
    # Keep an existing lease: a newer version waits for the old attempt to finish.
    conn.execute("""INSERT INTO description_jobs
        (incident_no, date, desired_hash, completed_hash, facts_json, payload_json,
         trigger_reason, first_queued_at, due_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(incident_no, date) DO UPDATE SET
            desired_hash=excluded.desired_hash, completed_hash=excluded.completed_hash,
            facts_json=excluded.facts_json, payload_json=excluded.payload_json,
            trigger_reason=excluded.trigger_reason, first_queued_at=excluded.first_queued_at,
            due_at=excluded.due_at, attempts=0, last_error=NULL, status=excluded.status""",
        (*key, version, version if simple else (old["completed_hash"] if old else None),
         json.dumps(facts), json.dumps(payload), "urgent" if urgent else ("update" if old else "initial"),
         first, due, "complete" if simple else "pending"))
    if not simple:
        # Material changes are visible even while the provider is slow or down.
        conn.execute("""UPDATE incidents SET description=?, severity=?, description_origin='source',
                     llm_pending_at = COALESCE(llm_pending_at, ?) WHERE incident_no = ? AND date = ?""",
                     (source_description(payload), severity_for(facts), row.get("timestamp") or str(now), *key))


def claim_job(db_file, now=None):
    now = time.time() if now is None else now
    with sqlite_connection(db_file, row_factory=sqlite3.Row) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""SELECT * FROM description_jobs
            WHERE status = 'pending' AND due_at <= ? AND (lease_until IS NULL OR lease_until <= ?)
              AND (completed_hash IS NULL OR completed_hash != desired_hash)
            ORDER BY due_at, first_queued_at LIMIT 1""", (now, now)).fetchone()
        if row is None:
            return None
        job = dict(row)
        job["lease_token"] = uuid.uuid4().hex
        conn.execute("""UPDATE description_jobs SET lease_token = ?, lease_until = ?
            WHERE incident_no = ? AND date = ?""",
            (job["lease_token"], now + max(120, LLM_TIMEOUT_SECONDS + 60), job["incident_no"], job["date"]))
        return job


def run_one(db_file, generate, now=None):
    """Return False when there is no due job. No lock is held during inference."""
    if not (LLM_API_CONFIGURED or TESTMODE):
        return False  # Configuration absence is not a repeatedly failing paid job.
    job = claim_job(db_file, now)
    if job is None:
        return False
    key = job["incident_no"], job["date"]
    token = job["lease_token"]
    version = job["desired_hash"]
    # Re-check after claim and immediately before spending tokens.
    with sqlite_connection(db_file, row_factory=sqlite3.Row) as conn:
        latest = conn.execute("SELECT * FROM description_jobs WHERE incident_no = ? AND date = ?", key).fetchone()
        if latest["desired_hash"] != version or latest["status"] != "pending":
            conn.execute("UPDATE description_jobs SET lease_token=NULL, lease_until=NULL WHERE incident_no=? AND date=? AND lease_token=?", (*key, token))
            return True
        incident = conn.execute("SELECT * FROM incidents WHERE incident_no=? AND date=?", key).fetchone()
        if incident is not None and not uses_ai_description(dict(incident)):
            sync_job(conn, dict(incident), now=now)
            return True
    context = {"db_file": db_file, "incident_no": key[0], "date": key[1],
               "input_hash": version, "trigger_reason": job["trigger_reason"]}
    try:
        description, severity = generate(json.loads(job["payload_json"]), raise_on_error=True, usage_context=context)
        with sqlite_connection(db_file) as conn:
            conn.execute("BEGIN IMMEDIATE")
            updated = conn.execute("""UPDATE description_jobs SET completed_hash=?, status='complete',
                lease_token=NULL, lease_until=NULL, last_error=NULL
                WHERE incident_no=? AND date=? AND desired_hash=? AND lease_token=? AND status='pending'""",
                (version, *key, version, token)).rowcount
            if updated:
                # Inactive is allowed: disappearance does not change the source facts.
                conn.execute("""UPDATE incidents SET description=?, severity=?, description_origin='ai',
                    llm_pending_at=NULL WHERE incident_no=? AND date=?""", (description, severity, *key))
            else:
                conn.execute("UPDATE description_jobs SET lease_token=NULL, lease_until=NULL WHERE incident_no=? AND date=? AND lease_token=?", (*key, token))
            if context.get("attempt_id"):
                conn.execute("UPDATE llm_attempts SET outcome=? WHERE id=?", ("saved" if updated else "stale", context["attempt_id"]))
    except Exception as exc:
        attempts = job["attempts"] + 1
        status_code = getattr(exc, "status_code", None)
        permanent = status_code in (400, 401, 403, 404, 422)
        exhausted = attempts >= DESCRIPTION_MAX_ATTEMPTS
        delay = min(3600, 30 * 2 ** min(attempts - 1, 7)) * random.uniform(1, 1.2)
        response = getattr(exc, "response", None)
        try:
            delay = max(delay, float(response.headers.get("retry-after", 0))) if response is not None else delay
        except (ValueError, TypeError):
            pass
        with sqlite_connection(db_file) as conn:
            conn.execute("""UPDATE description_jobs SET attempts=?, due_at=?, last_error=?, status=?
                WHERE incident_no=? AND date=? AND desired_hash=? AND lease_token=?""",
                (attempts, (time.time() if now is None else now) + delay, type(exc).__name__,
                 "failed" if permanent or exhausted else "pending", *key, version, token))
            conn.execute("UPDATE description_jobs SET lease_token=NULL, lease_until=NULL WHERE incident_no=? AND date=? AND lease_token=?", (*key, token))
    return True


def usage_metrics(db_file, since=None):
    """Last 24 hours by default; token totals explicitly report missing accounting."""
    since = time.time() - 86400 if since is None else since
    with sqlite_connection(db_file, row_factory=sqlite3.Row) as conn:
        row = conn.execute("""SELECT COUNT(*) AS attempts,
            SUM(CASE WHEN input_tokens IS NULL OR completion_tokens IS NULL THEN 1 ELSE 0 END) AS missingUsage,
            SUM(CASE WHEN cost IS NULL THEN 1 ELSE 0 END) AS missingCost,
            SUM(input_tokens) AS inputTokens, SUM(completion_tokens) AS completionTokens,
            SUM(reasoning_tokens) AS reasoningTokens, SUM(cached_tokens) AS cachedTokens,
            SUM(cost) AS reportedCost, SUM(CASE WHEN outcome='stale' THEN 1 ELSE 0 END) AS staleResults,
            SUM(CASE WHEN outcome='saved' THEN 1 ELSE 0 END) AS savedResults,
            SUM(CASE WHEN outcome='failed' THEN 1 ELSE 0 END) AS failures,
            AVG(duration_seconds) AS averageSeconds
            FROM llm_attempts WHERE created_at >= ?""", (since,)).fetchone()
        result = dict(row)
        result['windowHours'] = 24
        result['jobs'] = dict(conn.execute('SELECT status, COUNT(*) FROM description_jobs GROUP BY status'))
        result['templates'] = conn.execute("SELECT COUNT(*) FROM incidents WHERE description_origin='template'").fetchone()[0]
        return result
