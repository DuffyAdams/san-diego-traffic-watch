import os
import tempfile
import unittest
from unittest.mock import patch

from backend import db, monitor
from backend.scrapers.chp import CHPSnapshot
from backend.sqlite_utils import sqlite_connection


class MonitorCycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, 'test.db')
        db.init_db(self.path)
        self.patch = patch.object(monitor, 'DB_FILE', self.path)
        self.patch.start()
        self.db_patch = patch.object(db, 'DB_FILE', self.path)
        self.db_patch.start()
        self.schedule = patch.object(monitor, '_schedule_description_refresh')
        self.schedule.start()
        with sqlite_connection(self.path) as conn:
            conn.executemany("INSERT INTO incidents (incident_no, date, source, active, details, description) VALUES (?, '2026-09-23', ?, 1, '[]', 'Existing description')",
                             [('CHP-1', 'CHP'), ('SDPD-1', 'SDPD')])

    def tearDown(self):
        self.patch.stop()
        self.db_patch.stop()
        self.schedule.stop()
        self.temp.cleanup()

    def active(self):
        with sqlite_connection(self.path) as conn:
            return dict(conn.execute('SELECT incident_no, active FROM incidents'))

    def test_failed_source_is_not_deactivated(self):
        def fail():
            raise RuntimeError('unavailable')
        monitor.run_monitor_cycle({'CHP': fail, 'SDPD': lambda: []})
        self.assertEqual(self.active(), {'CHP-1': 1, 'SDPD-1': 0})

    def test_all_source_failure_preserves_active_records(self):
        def fail():
            raise RuntimeError('unavailable')
        with self.assertRaises(RuntimeError):
            monitor.run_monitor_cycle({'CHP': fail, 'SDPD': fail})
        self.assertEqual(self.active(), {'CHP-1': 1, 'SDPD-1': 1})

    def test_chp_disappearance_requires_two_fresh_polls_and_no_closing_ai(self):
        with patch.object(monitor, 'generate_description') as generate:
            monitor.run_monitor_cycle({'CHP': lambda: []})
            self.assertEqual(self.active()['CHP-1'], 1)
            monitor.run_monitor_cycle({'CHP': lambda: CHPSnapshot([], fresh=False)})
            self.assertEqual(self.active()['CHP-1'], 1)
            monitor.run_monitor_cycle({'CHP': lambda: []})
            self.assertEqual(self.active()['CHP-1'], 0)
            generate.assert_not_called()
        with sqlite_connection(self.path) as conn:
            self.assertEqual(conn.execute("SELECT description FROM incidents WHERE incident_no='CHP-1'").fetchone()[0], 'Existing description')

    def test_processing_failure_preserves_source_active_records(self):
        with patch.object(monitor, 'process_and_save_incident', return_value=None):
            for _ in range(2):
                monitor.run_monitor_cycle({'CHP': lambda: [{'No.': 'NEW', 'Date': '2026-09-23'}]})
        self.assertEqual(self.active()['CHP-1'], 1)


if __name__ == '__main__':
    unittest.main()
