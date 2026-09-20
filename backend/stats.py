"""Incident statistics queries and time-bucket construction."""

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from .runtime_metrics import get_runtime_metrics
from .sqlite_utils import sqlite_connection


def range_key(date_filter):
    return date_filter or "day"


def range_label(date_filter):
    return {
        "day": "Today",
        "daily": "Today",
        "week": "Last 7 days",
        "month": "Last 30 days",
        "year": "Last 12 months",
        None: "Today",
    }.get(date_filter, "Today")


def range_start(now, date_filter):
    selected = range_key(date_filter)
    if selected == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if selected == "week":
        return now - timedelta(days=7)
    if selected == "month":
        return now - timedelta(days=30)
    if selected == "year":
        return now - relativedelta(months=12)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def timestamp_clause(column, date_filter, now):
    start = range_start(now, date_filter)
    return f"{column} >= ?", [start.strftime("%Y-%m-%d %H:%M:%S")]


def date_clause(column, date_filter, now):
    if range_key(date_filter) == "day":
        return f"{column} = ?", [now.strftime("%Y-%m-%d")]
    start = range_start(now, date_filter)
    return f"{column} >= ?", [start.strftime("%Y-%m-%d")]


def build_incident_stats_payload(
    date_filter,
    sources,
    now,
    *,
    db_file,
    type_breakdown_limit,
):
    selected_range = range_key(date_filter)
    with sqlite_connection(db_file) as conn:
        cur = conn.cursor()
        where_clauses, query_params = _range_conditions(
            selected_range,
            sources,
            now,
        )

        def make_query(select_part, extra=None):
            clauses = list(where_clauses)
            if extra:
                clauses.append(extra)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            return f"{select_part}{where}", list(query_params)

        today = now.strftime("%Y-%m-%d")
        events_today = _count_with_source(cur, sources, "date = ?", [today])
        events_last_hour = _count_with_source(
            cur,
            sources,
            "timestamp >= ? AND timestamp < ?",
            [
                (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
                now.strftime("%Y-%m-%d %H:%M:%S"),
            ],
        )

        query, params = make_query("SELECT COUNT(*) FROM incidents", "active = 1")
        cur.execute(query, params)
        events_active = cur.fetchone()[0]

        query, params = make_query("SELECT COUNT(*) FROM incidents")
        cur.execute(query, params)
        total_incidents = cur.fetchone()[0]

        query, params = make_query(
            "SELECT type, COUNT(*) AS count FROM incidents",
            "type IS NOT NULL AND type != ''",
        )
        cur.execute(
            query + " GROUP BY type ORDER BY count DESC LIMIT ?",
            [*params, type_breakdown_limit],
        )
        incidents_by_type = dict(cur.fetchall())

        query, params = make_query(
            "SELECT location, COUNT(*) AS count FROM incidents",
            "location IS NOT NULL AND location != ''",
        )
        cur.execute(query + " GROUP BY location ORDER BY count DESC LIMIT 10", params)
        top_locations = dict(cur.fetchall())

        chart_data = _build_chart_data(cur, sources, selected_range, now)
        previous_week_data = (
            _previous_week_chart_data(cur, sources, now)
            if selected_range == "day" else None
        )
        historical_average, historical_samples = _historical_hour_average(cur, sources, now)

    runtime_snapshot = get_runtime_metrics()
    return {
        "rangeKey": selected_range,
        "rangeLabel": range_label(date_filter),
        "eventsToday": events_today,
        "eventsLastHour": events_last_hour,
        "eventsActive": events_active,
        "totalIncidents": total_incidents,
        "incidentsByType": incidents_by_type,
        "topLocations": top_locations,
        "hourlyData": chart_data,
        "previousWeekHourlyData": previous_week_data,
        "historicalCurrentHourAverage": historical_average,
        "historicalHourSampleCount": historical_samples,
        "generatedAt": now.isoformat(),
        "apiRequestsServed": runtime_snapshot["apiRequestsServed"],
        "averageScrapeTime": runtime_snapshot["averageScrapeTime"],
        "lastSuccessfulScrape": runtime_snapshot["lastSuccessfulScrape"],
        "lastSuccessfulScrapeAt": runtime_snapshot["lastSuccessfulScrapeAt"],
    }


def _range_conditions(selected_range, sources, now):
    clauses, params = _source_clause(sources)
    if selected_range == "day":
        clauses.append("date = ?")
        params.append(now.strftime("%Y-%m-%d"))
    elif selected_range in {"week", "month"}:
        days = 7 if selected_range == "week" else 30
        clauses.append("timestamp >= ?")
        params.append((now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S"))
    elif selected_range == "year":
        clauses.append("timestamp >= ?")
        params.append(
            (now - relativedelta(months=12)).strftime("%Y-%m-%d %H:%M:%S")
        )
    return clauses, params


def _count_with_source(cur, sources, condition, condition_params):
    clauses, params = _source_clause(sources)
    clauses.append(condition)
    params.extend(condition_params)
    cur.execute(
        f"SELECT COUNT(*) FROM incidents WHERE {' AND '.join(clauses)}",
        params,
    )
    return cur.fetchone()[0]


def _source_clause(sources):
    if not sources:
        return [], []
    placeholders = ",".join("?" for _ in sources)
    return [f"source IN ({placeholders})"], list(sources)


def _bucket_counts(cur, sources, start_dt, end_dt, bucket_format):
    clauses, params = _source_clause(sources)
    clauses.extend(("timestamp >= ?", "timestamp < ?"))
    params.extend(
        (
            start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        )
    )
    cur.execute(
        f"""
        SELECT strftime(?, timestamp) AS bucket, COUNT(*) AS count
        FROM incidents
        WHERE {' AND '.join(clauses)}
        GROUP BY bucket
        """,
        [bucket_format, *params],
    )
    return dict(cur.fetchall())


def _hour_offset_counts(cur, sources, start_dt, end_dt):
    clauses, params = _source_clause(sources)
    clauses.extend(("timestamp >= ?", "timestamp < ?"))
    params.extend(
        (
            start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        )
    )
    cur.execute(
        f"""
        SELECT CAST(
            (strftime('%s', timestamp) - strftime('%s', ?)) / 3600 AS INTEGER
        ) AS bucket,
        COUNT(*) AS count
        FROM incidents
        WHERE {' AND '.join(clauses)}
        GROUP BY bucket
        """,
        [start_dt.strftime("%Y-%m-%d %H:%M:%S"), *params],
    )
    return {row[0]: row[1] for row in cur.fetchall() if row[0] is not None}


def _build_chart_data(cur, sources, date_filter, now):
    if date_filter == "year":
        base = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        starts = [base - relativedelta(months=11 - index) for index in range(12)]
        counts = _bucket_counts(
            cur,
            sources,
            starts[0],
            base + relativedelta(months=1),
            "%Y-%m",
        )
        return [counts.get(start.strftime("%Y-%m"), 0) for start in starts]
    if date_filter == "month":
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
        starts = [base - timedelta(days=29 - index) for index in range(30)]
        counts = _bucket_counts(
            cur, sources, starts[0], base + timedelta(days=1), "%Y-%m-%d"
        )
        return [counts.get(start.strftime("%Y-%m-%d"), 0) for start in starts]
    if date_filter == "week":
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
        starts = [base - timedelta(days=6 - index) for index in range(7)]
        counts = _bucket_counts(
            cur, sources, starts[0], base + timedelta(days=1), "%Y-%m-%d"
        )
        return [counts.get(start.strftime("%Y-%m-%d"), 0) for start in starts]

    start = now - timedelta(hours=24)
    counts = _hour_offset_counts(cur, sources, start, now)
    return [counts.get(index, 0) for index in range(24)]


def _previous_week_chart_data(cur, sources, now):
    """Use the same rolling 24 hours, shifted back seven days.

    As with the historical average, records on each touched calendar day are
    our coverage proxy. Missing history must not appear as a zero-activity day.
    """
    end = now - timedelta(weeks=1)
    start = end - timedelta(hours=24)
    first_day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    last_day = (end - timedelta(seconds=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    clauses, params = _source_clause(sources)
    clauses.extend(("timestamp >= ?", "timestamp < ?"))
    params.extend((
        first_day.strftime("%Y-%m-%d %H:%M:%S"),
        (last_day + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
    ))
    cur.execute(
        f"SELECT COUNT(DISTINCT date(timestamp)) FROM incidents WHERE {' AND '.join(clauses)}",
        params,
    )
    if cur.fetchone()[0] != (last_day - first_day).days + 1:
        return None
    return _build_chart_data(cur, sources, "day", end)


def _historical_hour_average(cur, sources, now):
    """Compare the same rolling hour in the previous eight weeks.

    Days without any records for the selected sources are unknown, not zero.
    This is a coverage proxy until per-source ingestion history is available.
    A covered day with no incidents in the matching hour is a valid zero.
    """
    samples = []
    for weeks_ago in range(1, 9):
        end = now - timedelta(weeks=weeks_ago)
        start = end - timedelta(hours=1)
        first_day = start.replace(hour=0, minute=0, second=0, microsecond=0)
        last_day = (end - timedelta(seconds=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        clauses, params = _source_clause(sources)
        clauses.extend(("timestamp >= ?", "timestamp < ?"))
        params.extend((
            first_day.strftime("%Y-%m-%d %H:%M:%S"),
            (last_day + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
        ))
        cur.execute(
            f"""
            SELECT COUNT(DISTINCT date(timestamp)),
                   SUM(CASE WHEN timestamp >= ? AND timestamp < ? THEN 1 ELSE 0 END)
            FROM incidents WHERE {' AND '.join(clauses)}
            """,
            [start.strftime("%Y-%m-%d %H:%M:%S"),
             end.strftime("%Y-%m-%d %H:%M:%S"), *params],
        )
        covered_days, count = cur.fetchone()
        if covered_days == (last_day - first_day).days + 1:
            samples.append(count or 0)
    return (sum(samples) / len(samples), len(samples)) if samples else (0, 0)
