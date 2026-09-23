"""
Flask API routes for the traffic app.
Import this module to register all routes on the shared `app` instance.
"""

import ipaddress
import os
import queue
import sqlite3
import threading
import time
import uuid
from threading import Lock

import requests
from flask import abort, jsonify, request, send_from_directory

from .config import (
    app, DB_FILE, TARGET_DIR, COOKIE_NAME, COOKIE_MAX_AGE, COOKIE_SECURE, db_lock,
    API_READ_RATE_LIMIT, API_WRITE_RATE_LIMIT, TRUST_PROXY_HEADERS,
    HTTP_TIMEOUT_SECONDS, env_number, now_pst, pst_timestamp_str,
)
from .api_support import BoundedTTLCache, KeyedLockPool, RateLimiter
from .db import read_incidents, with_user_like_state
from .logging_utils import safe_print
from .runtime_metrics import get_runtime_metrics, record_api_request
from .description_jobs import usage_metrics
from .sqlite_utils import sqlite_connection
from .stats import (
    build_incident_stats_payload as _build_incident_stats_payload,
    date_clause as _date_clause,
    range_key as _range_key,
    range_label as _range_label,
    timestamp_clause as _timestamp_clause,
)


MAX_INCIDENT_LIMIT = 150
MAX_FILTER_VALUES = 25
MAX_FILTER_LENGTH = 80
MAX_COMMENT_LENGTH = 500
MAX_USERNAME_LENGTH = 40
READ_CACHE_TTL = 20
STATS_CACHE_TTL = 45
STATIC_ASSET_MAX_AGE_SECONDS = env_number(
    "STATIC_ASSET_MAX_AGE_SECONDS", 60 * 60 * 24 * 30, int, minimum=0
)
API_EVENT_BATCH_SIZE = env_number("API_EVENT_BATCH_SIZE", 50, int, minimum=1)
API_EVENT_FLUSH_SECONDS = env_number(
    "API_EVENT_FLUSH_SECONDS", 1.0, float, minimum=0.1
)
API_EVENT_QUEUE_SIZE = env_number("API_EVENT_QUEUE_SIZE", 10_000, int, minimum=1)
STATS_TYPE_BREAKDOWN_LIMIT = env_number(
    "STATS_TYPE_BREAKDOWN_LIMIT", 40, int, minimum=1
)
ALLOWED_DATE_FILTERS = {None, "day", "daily", "week", "month", "year"}
ALLOWED_SOURCES = {"CHP", "SDPD", "SDSO", "SDFD"}
TRAFFIC_APP_PUBLIC_URL = os.environ.get(
    "TRAFFIC_APP_PUBLIC_URL", "https://traffic-app.duffyadams.com"
)
METRICS_PUBLIC_URL = os.environ.get(
    "METRICS_PUBLIC_URL", "https://metrics.duffyadams.com"
)
TRAFFIC_APP_PUBLIC_HOST = TRAFFIC_APP_PUBLIC_URL.split("://", 1)[-1].split("/", 1)[0]
METRICS_PUBLIC_HOST = METRICS_PUBLIC_URL.split("://", 1)[-1].split("/", 1)[0]
RESPONSE_CACHE_MAX_ENTRIES = env_number(
    "RESPONSE_CACHE_MAX_ENTRIES", 256, int, minimum=1
)
RATE_LIMIT_MAX_BUCKETS = env_number(
    "RATE_LIMIT_MAX_BUCKETS", 4096, int, minimum=1
)
INCIDENT_CACHE_ARGS = {
    "limit",
    "cursor",
    "type",
    "location",
    "source",
    "active_only",
    "date_filter",
}
STATS_CACHE_ARGS = {"source", "date_filter"}

TRUSTED_PROXY_NETWORKS = []
for raw_network in os.environ.get(
    "TRUSTED_PROXY_CIDRS", "127.0.0.0/8,::1/128"
).split(","):
    raw_network = raw_network.strip()
    if not raw_network:
        continue
    try:
        TRUSTED_PROXY_NETWORKS.append(ipaddress.ip_network(raw_network, strict=False))
    except ValueError:
        safe_print(f"Ignoring invalid TRUSTED_PROXY_CIDRS entry: {raw_network}")

_response_cache = BoundedTTLCache(RESPONSE_CACHE_MAX_ENTRIES)
_singleflight_pool = KeyedLockPool()
_rate_limiter = RateLimiter(RATE_LIMIT_MAX_BUCKETS)
_api_event_queue = queue.Queue(maxsize=API_EVENT_QUEUE_SIZE)
_api_event_drop_count = 0
_api_event_thread_started = False
_api_event_thread_lock = Lock()


# ---------------------------------------------------------------------------
# Cookie helper
# ---------------------------------------------------------------------------

def _normalize_uuid(value):
    if not value:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        return None


def _get_or_create_uuid(req):
    device_uuid = _normalize_uuid(req.cookies.get(COOKIE_NAME))
    return device_uuid or str(uuid.uuid4())


def _set_uuid_cookie(response, device_uuid):
    """Attach UUID cookie to a response if missing or invalid."""
    if _normalize_uuid(request.cookies.get(COOKIE_NAME)) != device_uuid:
        response.set_cookie(
            COOKIE_NAME,
            device_uuid,
            max_age=COOKIE_MAX_AGE,
            secure=COOKIE_SECURE,
            httponly=True,
            samesite="Lax",
        )
    return response


def _parse_limit(default=20, max_value=MAX_INCIDENT_LIMIT):
    raw_limit = request.args.get("limit", str(default))
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        abort(400, description="Invalid limit")

    return max(1, min(limit, max_value))


def _clean_filter_values(name, allowed_values=None):
    values = []
    for raw_value in request.args.getlist(name)[:MAX_FILTER_VALUES]:
        value = raw_value.strip()
        if not value:
            continue
        if len(value) > MAX_FILTER_LENGTH:
            abort(400, description=f"{name} value is too long")
        if allowed_values and value not in allowed_values:
            abort(400, description=f"Invalid {name} value")
        values.append(value)
    return values


def _get_date_filter():
    date_filter = request.args.get("date_filter")
    if date_filter not in ALLOWED_DATE_FILTERS:
        abort(400, description="Invalid date_filter")
    return date_filter


def _cache_key(prefix, allowed_args=None, *extra_parts):
    args = tuple(
        sorted(
            (key, tuple(sorted(value.strip() for value in values)))
            for key, values in request.args.lists()
            if allowed_args is None or key in allowed_args
        )
    )
    return (prefix, args, extra_parts)


def _get_cached_response(key):
    return _response_cache.get(key)


def _set_cached_response(key, payload, ttl):
    _response_cache.set(key, payload, ttl)


def _api_event_worker():
    batch = []
    while True:
        try:
            item = _api_event_queue.get(timeout=API_EVENT_FLUSH_SECONDS)
            batch.append(item)
            while len(batch) < API_EVENT_BATCH_SIZE:
                try:
                    batch.append(_api_event_queue.get_nowait())
                except queue.Empty:
                    break
        except queue.Empty:
            pass

        if not batch:
            continue

        try:
            with db_lock:
                with sqlite_connection(DB_FILE) as conn:
                    conn.cursor().executemany(
                        """
                        INSERT INTO api_events
                            (device_uuid, route, request_type, host, client_ip, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        batch,
                    )
                    conn.commit()
        except Exception as exc:
            safe_print(f"Analytics batch insert failed: {exc}")
        finally:
            batch.clear()


def _ensure_api_event_worker():
    """Start the analytics writer once, on the first event."""
    global _api_event_thread_started

    if _api_event_thread_started:
        return
    with _api_event_thread_lock:
        if _api_event_thread_started:
            return
        threading.Thread(
            target=_api_event_worker,
            name="api-event-writer",
            daemon=True,
        ).start()
        _api_event_thread_started = True


@app.before_request
def _track_api_requests():
    if request.path.startswith("/api/"):
        record_api_request()


def _clear_response_cache():
    _response_cache.clear()


def _validate_incident_id(incident_id):
    if not incident_id or len(incident_id) > 80:
        abort(400, description="Invalid incident id")
    return incident_id


def _is_trusted_proxy(remote_addr):
    if not remote_addr or not TRUSTED_PROXY_NETWORKS:
        return False
    try:
        ip = ipaddress.ip_address(remote_addr)
    except ValueError:
        return False
    return any(ip in network for network in TRUSTED_PROXY_NETWORKS)


def _client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if TRUST_PROXY_HEADERS and forwarded_for and _is_trusted_proxy(request.remote_addr):
        candidate = forwarded_for.split(",", 1)[0].strip()
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            pass
    return request.remote_addr or "unknown"


def _enforce_rate_limit(bucket, limit_spec):
    if not _rate_limiter.allow(_client_ip(), bucket, limit_spec):
        abort(429, description="Too many requests")


def _record_api_event(device_uuid, route_name, request_type="read"):
    global _api_event_drop_count

    if not device_uuid:
        return

    _ensure_api_event_worker()

    host = (request.host or "").split(":", 1)[0]
    event = (
        device_uuid,
        route_name,
        request_type,
        host,
        _client_ip(),
        pst_timestamp_str(),
    )
    try:
        _api_event_queue.put_nowait(event)
    except queue.Full:
        _api_event_drop_count += 1
        if _api_event_drop_count % 100 == 1:
            safe_print(f"Analytics event queue full; dropped {_api_event_drop_count} events")


def _finalize_api_response(response, device_uuid, route_name, request_type="read"):
    _record_api_event(device_uuid, route_name, request_type=request_type)
    return _set_uuid_cookie(response, device_uuid)


def _count_query(cur, query, params=()):
    cur.execute(query, params)
    return cur.fetchone()[0] or 0


def _probe_url(url, timeout=HTTP_TIMEOUT_SECONDS):
    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=timeout)
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return {
            "ok": response.ok,
            "statusCode": response.status_code,
            "latencyMs": latency_ms,
            "url": url,
        }
    except Exception as exc:
        return {
            "ok": False,
            "statusCode": None,
            "latencyMs": None,
            "url": url,
            "error": str(exc),
        }


def _scrape_health_status(scrape_freshness_seconds):
    if scrape_freshness_seconds is None:
        return "Unknown"
    if scrape_freshness_seconds <= 90:
        return "Healthy"
    if scrape_freshness_seconds <= 300:
        return "Delayed"
    return "Stale"


# ---------------------------------------------------------------------------
# Incident list & stats
# ---------------------------------------------------------------------------

@app.route("/api/incidents")
def get_incidents():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    device_uuid = _get_or_create_uuid(request)
    limit = _parse_limit()
    cursor = request.args.get("cursor")
    if cursor and len(cursor) > 120:
        abort(400, description="Invalid cursor")
    incident_types = _clean_filter_values("type")
    locations = _clean_filter_values("location")
    sources = _clean_filter_values("source", ALLOWED_SOURCES)
    active_only = request.args.get("active_only", "false").lower() == "true"
    date_filter = _get_date_filter()

    cache_key = _cache_key("incidents", INCIDENT_CACHE_ARGS)
    incidents = _get_cached_response(cache_key)
    if incidents is None:
        incidents = read_incidents(
            limit=limit, cursor=cursor, incident_types=incident_types,
            locations=locations, sources=sources, active_only=active_only,
            date_filter=date_filter, device_uuid=None,
        )
        _set_cached_response(cache_key, incidents, READ_CACHE_TTL)

    incidents = with_user_like_state(incidents, device_uuid)

    response = jsonify(incidents)
    return _finalize_api_response(response, device_uuid, "incidents")


@app.route("/api/incident_stats")
def get_incident_stats():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    device_uuid = _get_or_create_uuid(request)
    date_filter = _get_date_filter()
    sources = _clean_filter_values("source", ALLOWED_SOURCES)
    now = now_pst()

    cache_key = _cache_key("incident_stats", STATS_CACHE_ARGS)
    cached_payload = _get_cached_response(cache_key)
    if cached_payload is not None:
        response = jsonify(cached_payload)
        return _finalize_api_response(response, device_uuid, "incident_stats")

    with _singleflight_pool.hold(cache_key):
        cached_payload = _get_cached_response(cache_key)
        if cached_payload is not None:
            response = jsonify(cached_payload)
            return _finalize_api_response(response, device_uuid, "incident_stats")

        payload = _build_incident_stats_payload(
            date_filter,
            sources,
            now,
            db_file=DB_FILE,
            type_breakdown_limit=STATS_TYPE_BREAKDOWN_LIMIT,
        )
        _set_cached_response(cache_key, payload, STATS_CACHE_TTL)

    response = jsonify(payload)
    return _finalize_api_response(response, device_uuid, "incident_stats")


@app.route("/api/dashboard_metrics")
def get_dashboard_metrics():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    device_uuid = _get_or_create_uuid(request)
    date_filter = _get_date_filter()
    now = now_pst()
    range_key = _range_key(date_filter)
    range_label = _range_label(date_filter)

    incident_clause, incident_params = _date_clause("date", range_key, now)
    event_clause, event_params = _timestamp_clause("timestamp", range_key, now)
    traffic_host = TRAFFIC_APP_PUBLIC_HOST
    metrics_host = METRICS_PUBLIC_HOST

    with sqlite_connection(DB_FILE) as conn:
        cur = conn.cursor()

        total_incidents = _count_query(cur, "SELECT COUNT(*) FROM incidents WHERE related_incident IS NULL")
        active_incidents = _count_query(cur, "SELECT COUNT(*) FROM incidents WHERE active = 1 AND related_incident IS NULL")
        incidents_in_range = _count_query(
            cur,
            f"SELECT COUNT(*) FROM incidents WHERE related_incident IS NULL AND {incident_clause}",
            tuple(incident_params),
        )
        tracked_days = _count_query(cur, "SELECT COUNT(DISTINCT date) FROM incidents WHERE related_incident IS NULL") or 0

        comments_in_range = _count_query(
            cur,
            f"SELECT COUNT(*) FROM comments WHERE {event_clause}",
            tuple(event_params),
        )
        likes_in_range = _count_query(
            cur,
            f"SELECT COUNT(*) FROM likes WHERE {event_clause}",
            tuple(event_params),
        )

        traffic_app_requests_in_range = _count_query(
            cur,
            f"SELECT COUNT(*) FROM api_events WHERE host = ? AND {event_clause}",
            (traffic_host, *event_params),
        )
        traffic_app_unique_visitors_in_range = _count_query(
            cur,
            f"""
            SELECT COUNT(DISTINCT device_uuid)
            FROM api_events
            WHERE host = ? AND {event_clause} AND device_uuid IS NOT NULL AND device_uuid != ''
            """,
            (traffic_host, *event_params),
        )
        metrics_page_requests_in_range = _count_query(
            cur,
            f"SELECT COUNT(*) FROM api_events WHERE host = ? AND {event_clause}",
            (metrics_host, *event_params),
        )
        metrics_page_unique_visitors_in_range = _count_query(
            cur,
            f"""
            SELECT COUNT(DISTINCT device_uuid)
            FROM api_events
            WHERE host = ? AND {event_clause} AND device_uuid IS NOT NULL AND device_uuid != ''
            """,
            (metrics_host, *event_params),
        )

    runtime_snapshot = get_runtime_metrics()
    average_incidents_per_day = (
        round(total_incidents / tracked_days, 1) if tracked_days else 0.0
    )
    scrape_health_status = _scrape_health_status(runtime_snapshot["scrapeFreshnessSeconds"])
    public_site_health = _probe_url(f"{TRAFFIC_APP_PUBLIC_URL}/")
    public_api_health = _probe_url(f"{TRAFFIC_APP_PUBLIC_URL}/api/healthz")

    payload = {
        "llmUsage": usage_metrics(DB_FILE),
        "rangeKey": range_key,
        "rangeLabel": range_label,
        "totalIncidentsIngested": total_incidents,
        "activeIncidents": active_incidents,
        "incidentsInRange": incidents_in_range,
        "averageIncidentsPerDay": average_incidents_per_day,
        "trafficAppRequestsInRange": traffic_app_requests_in_range,
        "trafficAppUniqueVisitorsInRange": traffic_app_unique_visitors_in_range,
        "metricsPageRequestsInRange": metrics_page_requests_in_range,
        "metricsPageUniqueVisitorsInRange": metrics_page_unique_visitors_in_range,
        "commentsInRange": comments_in_range,
        "likesInRange": likes_in_range,
        "engagementActionsInRange": comments_in_range + likes_in_range,
        "apiRequestsServed": runtime_snapshot["apiRequestsServed"],
        "averageScrapeTime": runtime_snapshot["averageScrapeTime"],
        "lastSuccessfulScrape": runtime_snapshot["lastSuccessfulScrape"],
        "lastSuccessfulScrapeAt": runtime_snapshot["lastSuccessfulScrapeAt"],
        "scrapeFreshnessSeconds": runtime_snapshot["scrapeFreshnessSeconds"],
        "scrapeHealthStatus": scrape_health_status,
        "requestsPerMinute": runtime_snapshot["requestsPerMinute"],
        "requestsLastMinute": runtime_snapshot["requestsLastMinute"],
        "requestsLastFiveMinutes": runtime_snapshot["requestsLastFiveMinutes"],
        "requestsLastHour": runtime_snapshot["requestsLastHour"],
        "processStartedAt": runtime_snapshot["processStartedAt"],
        "processUptimeSeconds": runtime_snapshot["processUptimeSeconds"],
        "publicSiteHealth": public_site_health,
        "publicApiHealth": public_api_health,
        "generatedAt": now.isoformat(),
    }
    response = jsonify(payload)
    return _finalize_api_response(response, device_uuid, "dashboard_metrics")


# ---------------------------------------------------------------------------
# Map files
# ---------------------------------------------------------------------------

@app.route("/maps/<filename>")
def get_map(filename):
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    return send_from_directory(TARGET_DIR, filename)


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------

@app.route("/api/incidents/<incident_id>/like", methods=["POST", "DELETE"])
def like_incident(incident_id):
    _enforce_rate_limit("write", API_WRITE_RATE_LIMIT)
    incident_id = _validate_incident_id(incident_id)
    device_uuid = _get_or_create_uuid(request)

    with db_lock:
        with sqlite_connection(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM incidents WHERE incident_no = ?", (incident_id,))
            if not cur.fetchone():
                abort(404, description="Incident not found")
            if request.method == "DELETE":
                cur.execute(
                    "DELETE FROM likes WHERE incident_no = ? AND device_uuid = ?",
                    (incident_id, device_uuid),
                )
                if cur.rowcount:
                    cur.execute(
                        """
                        UPDATE incidents
                        SET likes = MAX(likes - 1, 0)
                        WHERE incident_no = ?
                        """,
                        (incident_id,),
                    )
            else:
                cur.execute(
                    "SELECT 1 FROM likes WHERE incident_no = ? AND device_uuid = ?",
                    (incident_id, device_uuid),
                )
                if cur.fetchone():
                    return jsonify({"error": "You already liked this post."}), 400
                timestamp = pst_timestamp_str()
                cur.execute(
                    """
                    INSERT INTO likes (incident_no, device_uuid, timestamp)
                    VALUES (?, ?, ?)
                    """,
                    (incident_id, device_uuid, timestamp),
                )
                cur.execute(
                    "UPDATE incidents SET likes = likes + 1 WHERE incident_no = ?",
                    (incident_id,),
                )
            conn.commit()
            _clear_response_cache()

    with sqlite_connection(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT likes FROM incidents WHERE incident_no = ?", (incident_id,))
        result = cur.fetchone()
        likes_count = result[0] if result else 0

    response = jsonify(
        {
            "likes": likes_count,
            "liked_by_user": request.method != "DELETE",
        }
    )
    return _finalize_api_response(response, device_uuid, "incident_like", request_type="write")


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@app.route("/api/incidents/<incident_id>/comment", methods=["POST"])
def comment_incident(incident_id):
    _enforce_rate_limit("write", API_WRITE_RATE_LIMIT)
    incident_id = _validate_incident_id(incident_id)
    device_uuid  = _get_or_create_uuid(request)
    payload      = request.get_json(silent=True) or {}
    new_comment  = str(payload.get("comment", "")).strip()
    username     = str(payload.get("username", "Anonymous")).strip() or "Anonymous"
    timestamp    = pst_timestamp_str()

    if not new_comment:
        return jsonify({"error": "Empty comment"}), 400
    if len(new_comment) > MAX_COMMENT_LENGTH:
        return jsonify({"error": "Comment is too long"}), 400
    if len(username) > MAX_USERNAME_LENGTH:
        username = username[:MAX_USERNAME_LENGTH]

    with db_lock:
        with sqlite_connection(DB_FILE) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cur = conn.cursor()
            try:
                cur.execute("SELECT 1 FROM incidents WHERE incident_no = ?", (incident_id,))
                if not cur.fetchone():
                    abort(404, description="Incident not found")

                cur.execute(
                    "SELECT COUNT(*) FROM comments WHERE incident_no = ? AND device_uuid = ?",
                    (incident_id, device_uuid),
                )
                if cur.fetchone()[0] >= 2:
                    return jsonify({"error": "You can only leave 2 comments per post."}), 400

                cur.execute(
                    """
                    INSERT INTO comments
                        (incident_no, device_uuid, username, comment, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (incident_id, device_uuid, username, new_comment, timestamp),
                )
                conn.commit()
                _clear_response_cache()
                cur.execute(
                    """
                    SELECT username, comment, timestamp
                    FROM comments
                    WHERE incident_no = ?
                    ORDER BY timestamp ASC
                    """,
                    (incident_id,),
                )
                comments = [
                    {
                        "username": row[0] or "Anonymous",
                        "comment": row[1],
                        "timestamp": row[2],
                    }
                    for row in cur.fetchall()
                ]
            except sqlite3.IntegrityError:
                conn.rollback()
                return jsonify({"error": "Could not process comment."}), 400

    response = jsonify({"comments": comments})
    return _finalize_api_response(response, device_uuid, "incident_comment", request_type="write")


# ---------------------------------------------------------------------------
# User identity
# ---------------------------------------------------------------------------

@app.route("/api/user/check", methods=["GET"])
def check_user():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    device_uuid = _get_or_create_uuid(request)
    response = jsonify({"uuid": device_uuid})
    return _finalize_api_response(response, device_uuid, "user_check")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.route("/api/healthz", methods=["GET"])
def healthz():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    runtime_snapshot = get_runtime_metrics()
    return jsonify(
        {
            "ok": True,
            "generatedAt": now_pst().isoformat(),
            "lastSuccessfulScrapeAt": runtime_snapshot["lastSuccessfulScrapeAt"],
            "scrapeHealthStatus": _scrape_health_status(runtime_snapshot["scrapeFreshnessSeconds"]),
        }
    )


# ---------------------------------------------------------------------------
# SPA catch-all
# ---------------------------------------------------------------------------

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_app(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        cacheable_prefixes = ("assets/", "map_tiles/", "fonts/")
        max_age = (
            STATIC_ASSET_MAX_AGE_SECONDS
            if path.startswith(cacheable_prefixes)
            else None
        )
        return send_from_directory(app.static_folder, path, max_age=max_age)
    return send_from_directory(app.static_folder, "index.html", max_age=0)
