"""Calendar alignment, coverage and partial-bucket checks for chart comparisons."""
import sqlite3
import unittest
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from backend.stats import _build_chart_data, _previous_period_chart_data


class StatsComparisonTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.cur = self.conn.cursor()
        self.cur.execute("CREATE TABLE incidents (timestamp TEXT, source TEXT, related_incident TEXT)")

    def insert(self, timestamp, count=1, source="CHP"):
        self.cur.executemany("INSERT INTO incidents (timestamp, source) VALUES (?, ?)",
                             [(timestamp.strftime("%Y-%m-%d %H:%M:%S"), source)] * count)

    def test_week_and_month_align_days_and_match_partial_final_day(self):
        now = datetime(2026, 9, 19, 14, 30)
        for period, days in (("week", 7), ("month", 30)):
            with self.subTest(period=period):
                self.cur.execute("DELETE FROM incidents")
                end = now - timedelta(days=days)
                start = end.replace(hour=0, minute=0) - timedelta(days=days - 1)
                for i in range(days):
                    self.insert(start + timedelta(days=i, hours=1))
                self.insert(start - timedelta(seconds=1), 99)
                self.insert(end - timedelta(seconds=1), 2)
                self.insert(end, 99)
                self.insert(end + timedelta(hours=1), 99)
                self.assertEqual(_previous_period_chart_data(self.cur, ["CHP"], period, now),
                                 [1] * (days - 1) + [3])
                self.assertIsNone(_previous_period_chart_data(self.cur, ["SDPD"], period, now))
                self.cur.execute("DELETE FROM incidents WHERE date(timestamp) = ?",
                                 [(start + timedelta(days=2)).strftime("%Y-%m-%d")])
                self.assertIsNone(_previous_period_chart_data(self.cur, ["CHP"], period, now))

    def test_year_aligns_matching_months_and_excludes_later_days(self):
        now = datetime(2026, 9, 19, 14, 30)
        end = now - relativedelta(years=1)
        start = datetime(2024, 10, 1)
        for i in range(12):
            self.insert(start + relativedelta(months=i), i + 1)
        self.insert(start - timedelta(seconds=1), 99)
        self.insert(end - timedelta(seconds=1), 2)
        self.insert(end, 99)
        self.insert(end + timedelta(days=1), 99)
        self.assertEqual(_previous_period_chart_data(self.cur, ["CHP"], "year", now),
                         list(range(1, 12)) + [14])
        self.cur.execute("DELETE FROM incidents WHERE strftime('%Y-%m', timestamp) = '2025-03'")
        self.assertIsNone(_previous_period_chart_data(self.cur, ["CHP"], "year", now))

    def test_leap_day_comparison_clamps_to_february_28(self):
        now = datetime(2024, 2, 29, 14, 30)
        for i in range(12):
            self.insert(datetime(2022, 3, 1) + relativedelta(months=i))
        self.insert(datetime(2023, 2, 28, 14, 29), 2)
        self.insert(datetime(2023, 2, 28, 14, 30), 99)
        self.insert(datetime(2023, 3, 1), 99)
        self.assertEqual(_previous_period_chart_data(self.cur, [], "year", now), [1] * 11 + [3])

    def test_all_current_periods_exclude_future_records(self):
        now = datetime(2026, 9, 19, 14, 30)
        self.insert(now - timedelta(seconds=1), 3)
        self.insert(now, 99)
        self.insert(now + timedelta(hours=1), 99)
        for period, length in (("day", 24), ("week", 7), ("month", 30), ("year", 12)):
            self.assertEqual(_build_chart_data(self.cur, [], period, now), [0] * (length - 1) + [3])


if __name__ == "__main__":
    unittest.main()
