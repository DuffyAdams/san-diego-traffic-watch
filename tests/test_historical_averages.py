import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from unittest.mock import patch

from backend import db, routes


class HistoricalAverageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "traffic-test.db")
        db.init_db(self.db_path)
        self.patches = [
            patch.object(db, "DB_FILE", self.db_path),
            patch.object(routes, "DB_FILE", self.db_path),
        ]
        for active_patch in self.patches:
            active_patch.start()
        routes._clear_response_cache()
        self.client = routes.app.test_client()

    def tearDown(self):
        routes._clear_response_cache()
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temp_dir.cleanup()

    def _insert_incidents(self, timestamp, count, prefix, next_id):
        rows = []
        for offset in range(count):
            incident_id = next_id + offset
            rows.append(
                (
                    f"{prefix}-{incident_id}",
                    timestamp.strftime("%Y-%m-%d"),
                    timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "CHP",
                    0,
                )
            )
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executemany(
                """
                INSERT INTO incidents
                    (incident_no, date, timestamp, source, active)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
        return next_id + count

    def test_historical_average_uses_matching_weekday_and_hour(self):
        now = datetime(2026, 9, 19, 14, 30)
        next_id = 1
        for weeks_ago, count in ((1, 20), (2, 10), (3, 30)):
            next_id = self._insert_incidents(
                now - timedelta(days=7 * weeks_ago, minutes=30),
                count,
                "MATCH",
                next_id,
            )

        next_id = self._insert_incidents(
            now - timedelta(days=7, hours=2),
            15,
            "OTHER-HOUR",
            next_id,
        )
        self._insert_incidents(
            now - timedelta(days=6),
            25,
            "OTHER-DAY",
            next_id,
        )

        with (
            patch.object(routes, "now_pst", return_value=now),
            patch.object(routes, "_record_api_event"),
        ):
            response = self.client.get("/api/incident_stats?date_filter=day")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["historicalCurrentHourAverage"], 20.0)
        self.assertEqual(response.get_json()["historicalHourSampleCount"], 3)

    def _stats(self, now, source="CHP", date_filter="day"):
        with (
            patch.object(routes, "now_pst", return_value=now),
            patch.object(routes, "_record_api_event"),
        ):
            return self.client.get(
                f"/api/incident_stats?date_filter={date_filter}&source={source}"
            ).get_json()

    def test_rolling_window_excludes_today_future_and_old_history(self):
        now = datetime(2026, 9, 19, 14, 30)
        past = now - timedelta(weeks=1)
        next_id = 1
        for timestamp, count in (
            (past - timedelta(hours=1), 2),  # Included start, previous clock hour
            (past - timedelta(minutes=10), 3),
            (past, 9),  # Exclusive end
            (now - timedelta(minutes=10), 7),  # Current hour, not baseline
            (now, 8),  # Exclusive end of current hour
            (now + timedelta(hours=1), 9),  # Future
            (now - timedelta(weeks=9, minutes=10), 99),  # Too old
        ):
            next_id = self._insert_incidents(timestamp, count, "WINDOW", next_id)
        stats = self._stats(now)
        self.assertEqual(stats["historicalCurrentHourAverage"], 5)
        self.assertEqual(stats["historicalHourSampleCount"], 1)
        self.assertEqual(stats["eventsLastHour"], 7)
        self.assertEqual(stats["hourlyData"][-1], 7)

    def test_empty_days_are_unknown_but_covered_quiet_hours_count_as_zero(self):
        now = datetime(2026, 9, 19, 14, 30)
        self._insert_incidents(now - timedelta(weeks=1, minutes=10), 6, "BUSY", 1)
        self._insert_incidents(now - timedelta(weeks=2, hours=3), 1, "QUIET", 10)
        stats = self._stats(now)
        self.assertEqual(stats["historicalCurrentHourAverage"], 3)
        self.assertEqual(stats["historicalHourSampleCount"], 2)

    def test_no_history_and_other_sources_do_not_supply_baseline(self):
        now = datetime(2026, 9, 19, 14, 30)
        self._insert_incidents(now - timedelta(weeks=1, minutes=10), 6, "CHP", 1)
        stats = self._stats(now, "SDPD")
        self.assertEqual(stats["historicalCurrentHourAverage"], 0)
        self.assertEqual(stats["historicalHourSampleCount"], 0)

    def test_midnight_window_uses_both_calendar_days(self):
        now = datetime(2026, 9, 19, 0, 30)
        past = now - timedelta(weeks=1)
        self._insert_incidents(past - timedelta(minutes=45), 2, "BEFORE", 1)
        self._insert_incidents(past - timedelta(minutes=15), 3, "AFTER", 10)
        stats = self._stats(now)
        self.assertEqual(stats["historicalCurrentHourAverage"], 5)
        self.assertEqual(stats["historicalHourSampleCount"], 1)

    def test_exact_midnight_does_not_require_records_on_next_day(self):
        now = datetime(2026, 9, 19, 0, 0)
        self._insert_incidents(now - timedelta(weeks=1, minutes=15), 4, "BEFORE", 1)
        stats = self._stats(now)
        self.assertEqual(stats["historicalCurrentHourAverage"], 4)
        self.assertEqual(stats["historicalHourSampleCount"], 1)

    def test_previous_week_aligns_all_24_rolling_buckets_and_boundaries(self):
        now = datetime(2026, 9, 19, 14, 30)
        end = now - timedelta(weeks=1)
        start = end - timedelta(hours=24)
        next_id = 1
        for timestamp, count in (
            (start - timedelta(seconds=1), 9),
            (start, 2),
            (start + timedelta(hours=1), 3),
            (end - timedelta(seconds=1), 4),
            (end, 9),
            (now - timedelta(minutes=5), 7),
        ):
            next_id = self._insert_incidents(timestamp, count, "COMPARE", next_id)
        stats = self._stats(now)
        self.assertEqual(stats["previousWeekHourlyData"], [2, 3] + [0] * 21 + [4])
        self.assertEqual(stats["hourlyData"][-1], 7)

    def test_previous_week_missing_or_partial_history_is_unavailable(self):
        now = datetime(2026, 9, 19, 14, 30)
        self.assertIsNone(self._stats(now)["previousWeekHourlyData"])
        self._insert_incidents(now - timedelta(weeks=1, minutes=5), 2, "PARTIAL", 1)
        routes._clear_response_cache()
        self.assertIsNone(self._stats(now)["previousWeekHourlyData"])

    def test_previous_week_respects_source_and_preserves_covered_zero_activity(self):
        now = datetime(2026, 9, 19, 14, 30)
        end = now - timedelta(weeks=1)
        # Records cover both calendar days, but fall outside the compared hours.
        self._insert_incidents(end - timedelta(hours=25), 1, "BEFORE", 1)
        self._insert_incidents(end + timedelta(hours=1), 1, "AFTER", 2)
        self.assertEqual(self._stats(now)["previousWeekHourlyData"], [0] * 24)
        self.assertIsNone(self._stats(now, "SDPD")["previousWeekHourlyData"])

    def test_previous_week_midnight_needs_only_the_compared_calendar_day(self):
        now = datetime(2026, 9, 19)
        self._insert_incidents(now - timedelta(weeks=1, minutes=5), 2, "MIDNIGHT", 1)
        self.assertEqual(self._stats(now)["previousWeekHourlyData"], [0] * 23 + [2])

    def test_previous_week_is_only_returned_for_the_day_view(self):
        now = datetime(2026, 9, 19)
        self._insert_incidents(now - timedelta(weeks=1, minutes=5), 2, "HISTORY", 1)
        for period in ("week", "month", "year"):
            self.assertIsNone(self._stats(now, date_filter=period)["previousWeekHourlyData"])


if __name__ == "__main__":
    unittest.main()
