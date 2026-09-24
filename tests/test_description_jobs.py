import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from backend import db, description_jobs as jobs
from backend.sqlite_utils import sqlite_connection


class DescriptionJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, 'test.db')
        self.patch = patch.object(db, 'DB_FILE', self.path)
        self.patch.start()
        self.config = patch.object(jobs, 'LLM_API_CONFIGURED', True)
        self.config.start()
        db.init_db()
        self.incident = {'No.': '1234', 'Date': '2026-09-23', 'Timestamp': '2026-09-23 12:00:00',
                         'Source': 'CHP', 'Type': 'Traffic Collision', 'Location': 'I5 N / Test Rd',
                         'Details': ['Two cars reported; circumstances unknown']}

    def tearDown(self):
        self.patch.stop()
        self.config.stop()
        self.temp.cleanup()

    def save(self, **updates):
        self.incident.update(updates)
        db.save_or_update_incident(self.incident, generate_description_on_insert=False)

    def row(self, table='description_jobs'):
        with sqlite_connection(self.path, row_factory=sqlite3.Row) as conn:
            return dict(conn.execute('SELECT * FROM ' + table).fetchone())

    def due(self):
        with sqlite_connection(self.path) as conn:
            conn.execute('UPDATE description_jobs SET due_at=0')

    def test_public_read_repair_has_source_origin_and_keeps_raw_details(self):
        raw = '[5:04 PM] [4] Unit At Scene'
        self.save(Details=[raw])
        with sqlite_connection(self.path) as conn:
            conn.execute("UPDATE incidents SET description=?, description_origin='ai'", (raw,))
        public = db.read_incidents()[0]
        self.assertEqual(public['description'], 'Traffic collision reported at I5 N / Test Rd.')
        self.assertEqual(public['description_origin'], 'source')
        self.assertEqual(public['Details'], [raw])
        self.assertEqual(self.row('incidents')['description'], raw)

    def test_whitespace_only_cleanup_preserves_ai_origin(self):
        self.save()
        with sqlite_connection(self.path) as conn:
            conn.execute("UPDATE incidents SET description='  A collision is reported.  ', description_origin='ai'")
        public = db.read_incidents()[0]
        self.assertEqual(public['description'], 'A collision is reported.')
        self.assertEqual(public['description_origin'], 'ai')

    def test_pending_and_failed_jobs_keep_readable_fallback_without_fake_success(self):
        from types import SimpleNamespace as NS
        from backend import llm
        raw = ['[5:01 PM] [1] No injuries reported', '[5:04 PM] [4] Unit At Scene']
        self.save(Details=raw)
        pending = self.row('incidents')
        self.assertNotIn('[', pending['description'])
        self.assertIn('No injuries reported', pending['description'])
        self.assertEqual(pending['description_origin'], 'source')
        response = NS(choices=[NS(finish_reason='stop', message=NS(content='{"summary":"[5:04 PM] [4] Unit At Scene"}'))])
        with patch.object(llm, 'TESTMODE', False), patch.object(llm, 'LLM_API_CONFIGURED', True), patch.object(llm, '_call_llm', return_value=response), patch.object(jobs, 'DESCRIPTION_MAX_ATTEMPTS', 1):
            self.assertTrue(jobs.run_one(self.path, llm.generate_description))
        self.assertEqual(self.row()['status'], 'failed')
        self.assertIsNone(self.row()['completed_hash'])
        self.assertEqual(self.row('llm_attempts')['outcome'], 'failed')
        self.assertEqual(self.row('incidents')['description'], pending['description'])
        self.assertEqual(json.loads(self.row('incidents')['details']), raw)
        self.assertEqual(self.row('incidents')['description_origin'], 'source')

    def test_initial_then_unchanged_has_one_call_and_survives_restart(self):
        self.save()
        generate = Mock(return_value=('Reported collision on I-5.', None))
        self.assertTrue(jobs.run_one(self.path, generate))
        self.save()
        db.init_db()
        self.assertFalse(jobs.run_one(self.path, generate))
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(self.row()['status'], 'complete')

    def test_type_and_location_changes_queue_new_version(self):
        self.save()
        old = self.row()['desired_hash']
        self.save(Type='Hit and Run No Injuries', Location='I8 E / Test Rd')
        self.assertNotEqual(old, self.row()['desired_hash'])
        self.assertEqual(self.row()['trigger_reason'], 'urgent')

    def test_admin_and_formatting_changes_do_not_call_again(self):
        self.save()
        generate = Mock(return_value=('Reported collision.', None))
        jobs.run_one(self.path, generate)
        self.save(Details=['[12:01 PM] [1] Two cars reported; circumstances unknown [Shared]', 'Unit Assigned'])
        self.assertFalse(jobs.run_one(self.path, generate))
        self.assertIsNone(self.row('incidents')['llm_pending_at'])

    def test_newer_pending_version_replaces_old_payload(self):
        self.save()
        self.save(Details=['Vehicle now on its roof'])
        generate = Mock(return_value=('A vehicle is reported on its roof.', None))
        jobs.run_one(self.path, generate)
        self.assertEqual(generate.call_args.args[0]['Details'], json.dumps(['Vehicle now on its roof']))
        self.assertEqual(self.row()['status'], 'complete')

    def test_inflight_old_result_cannot_overwrite_new_facts(self):
        self.save()
        def generate(*args, **kwargs):
            self.save(Details=['ALL LANES OPEN'])
            return 'Old blocked lane report', 4
        jobs.run_one(self.path, generate)
        self.assertNotEqual(self.row('incidents')['description'], 'Old blocked lane report')
        self.assertEqual(self.row()['status'], 'pending')
        self.assertIsNone(self.row()['lease_token'])

    def test_only_one_worker_claims_same_incident_and_lease_recovers(self):
        self.save()
        self.assertIsNotNone(jobs.claim_job(self.path))
        self.assertIsNone(jobs.claim_job(self.path))
        with sqlite_connection(self.path) as conn:
            conn.execute('UPDATE description_jobs SET lease_until=0')
        self.assertIsNotNone(jobs.claim_job(self.path))

    def test_provider_failure_backoff_and_successful_retry(self):
        self.save()
        failed = Mock(side_effect=RuntimeError('offline'))
        jobs.run_one(self.path, failed)
        self.assertEqual(self.row()['attempts'], 1)
        self.assertFalse(jobs.run_one(self.path, failed))
        self.assertIsNotNone(self.row('incidents')['llm_pending_at'])
        self.due()
        jobs.run_one(self.path, Mock(return_value=('Reported collision.', None)))
        self.assertEqual(self.row()['status'], 'complete')
        self.assertIsNone(self.row('incidents')['llm_pending_at'])

    def test_failed_configuration_does_not_spin(self):
        self.save()
        with patch.object(jobs, 'LLM_API_CONFIGURED', False), patch.object(jobs, 'TESTMODE', False):
            generate = Mock()
            self.assertFalse(jobs.run_one(self.path, generate))
            generate.assert_not_called()

    def test_partial_details_do_not_erase_previous_facts(self):
        self.save()
        version = self.row()['desired_hash']
        self.save(Details=[], DetailsAvailable=False)
        self.assertEqual(self.row()['desired_hash'], version)
        self.assertEqual(json.loads(self.row('incidents')['details']), ['Two cars reported; circumstances unknown'])
        self.assertEqual(self.row('incidents')['details_stale'], 1)

    def test_simple_template_uses_no_ai_and_no_severity_guess(self):
        self.save(Type='Traffic Hazard', Details=[])
        generate = Mock()
        self.assertFalse(jobs.run_one(self.path, generate))
        generate.assert_not_called()
        self.assertEqual(self.row('incidents')['description_origin'], 'template')
        self.assertIsNone(self.row('incidents')['severity'])

    def test_material_update_immediately_replaces_stale_ai_claim(self):
        self.save(Details=['ALL LANES BLOCKED'])
        jobs.run_one(self.path, Mock(return_value=('All lanes are blocked.', 4)))
        self.save(Details=['ALL LANES BLOCKED', 'ALL LANES OPEN'])
        row = self.row('incidents')
        self.assertEqual(row['description_origin'], 'source')
        self.assertIn('All lanes open', row['description'])
        self.assertEqual(row['severity'], 1)

    def test_superseded_claim_is_skipped_before_provider_call(self):
        self.save()
        original = jobs.claim_job
        def claim(*args, **kwargs):
            job = original(*args, **kwargs)
            self.save(Details=['ALL LANES OPEN'])
            return job
        generate = Mock()
        with patch.object(jobs, 'claim_job', side_effect=claim):
            self.assertTrue(jobs.run_one(self.path, generate))
        generate.assert_not_called()
        self.assertIsNone(self.row()['lease_token'])

    def test_debounce_has_a_maximum_wait(self):
        self.save()
        with sqlite_connection(self.path, row_factory=sqlite3.Row) as conn:
            conn.execute("UPDATE description_jobs SET first_queued_at=100, due_at=100")
            row = dict(conn.execute('SELECT * FROM incidents').fetchone())
            for moment in (120, 145, 170, 185):
                row['details'] = json.dumps([f'New routine report {moment}'])
                jobs.sync_job(conn, row, now=moment)
            job = conn.execute('SELECT due_at FROM description_jobs').fetchone()
        self.assertLessEqual(job[0], 190)

    def test_pending_work_can_finish_after_source_disappears(self):
        self.save()
        with sqlite_connection(self.path) as conn:
            conn.execute('UPDATE incidents SET active=0')
        jobs.run_one(self.path, Mock(return_value=('Reported collision on I-5.', None)))
        row = self.row('incidents')
        self.assertEqual(row['active'], 0)
        self.assertEqual(row['description'], 'Reported collision on I-5.')

    def test_repeated_failures_stop_at_bound(self):
        self.save()
        with patch.object(jobs, 'DESCRIPTION_MAX_ATTEMPTS', 2):
            for _ in range(2):
                self.due()
                jobs.run_one(self.path, Mock(side_effect=ValueError('bad output')))
        self.assertEqual(self.row()['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
