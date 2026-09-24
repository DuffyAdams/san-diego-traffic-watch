import json
import os
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from backend import llm, description_jobs as jobs


def response(content, finish='stop'):
    return NS(choices=[NS(finish_reason=finish, message=NS(content=content))])


class ValidationDiagnosticsTests(unittest.TestCase):
    def test_oversized_summary_has_safe_specific_code(self):
        # Live saved job 1019 reproduced a valid JSON, stop response of 279 chars.
        with self.assertRaises(ValueError) as caught:
            llm._parse_response(response(json.dumps({'summary': 'x' * 279})))
        self.assertEqual(str(caught.exception), 'summary_too_long')

    def test_boundaries_and_normal_prose_keep_existing_safety_contract(self):
        for summary in ('x' * 199, 'A semi continued on; the car moved to the roadside.',
                        'A vehicle is reported on the I-15 connector to SR-56.'):
            self.assertEqual(llm._parse_response(response(json.dumps({'summary': summary})))[0], summary)
        with self.assertRaisesRegex(ValueError, '^summary_too_long$'):
            llm._parse_response(response(json.dumps({'summary': 'x' * 200})))
        from backend.summary_validation import SummaryValidationError, safe_error_code
        with self.assertRaisesRegex(ValueError, '^Unknown summary validation code$'):
            SummaryValidationError('private provider content')
        self.assertEqual(safe_error_code(RuntimeError('private provider content')), 'RuntimeError')

    def test_prompt_addresses_observed_accuracy_and_length_failures(self):
        # Contract tests: these guard the actual system instructions, not model quality.
        prompt = llm.SYSTEM_PROMPT.lower()
        for instruction in (
            'never infer the actor', 'caller', 'not proof that chp',
            'reporting_area', 'not the incident city', 'location_note',
            'trans', 'never movement or spread', 'neg vehs pulled over',
            'no vehicles reported pulled over', 'no further details',
            'prioritize concrete hazard', 'aim for 160', '199 characters',
        ):
            with self.subTest(instruction=instruction):
                self.assertIn(instruction, prompt)

    def test_validation_codes_reach_job_and_log_without_content(self):
        secret = 'PRIVATE RESPONSE DO NOT LOG'
        cases = [
            (NS(choices=[]), 'missing_choice'),
            (response('{}', 'length'), 'unfinished_response'),
            (response(None), 'empty_content'),
            (response(secret), 'invalid_json'),
            (response('[]'), 'unexpected_fields'),
            (response(json.dumps({'summary': 'ok', 'extra': secret})), 'unexpected_fields'),
            (response('{"summary":123}'), 'summary_type'),
            (response('{"summary":"unknown"}'), 'empty_summary'),
            (response(json.dumps({'summary': secret * 12})), 'summary_too_long'),
            (response('{"summary":"[5:04 PM] [4] Unit At Scene"}'), 'dispatch_log'),
        ]
        for result, code in cases:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                path = os.path.join(directory, 'test.db')
                with sqlite3.connect(path) as conn:
                    jobs.init_schema(conn)
                    conn.execute('''INSERT INTO description_jobs
                        (incident_no,date,desired_hash,facts_json,payload_json,trigger_reason,first_queued_at,due_at)
                        VALUES ('test','2026-09-23','hash','{}',?,'initial',0,0)''',
                        (json.dumps({'Source': 'CHP', 'Type': 'Collision', 'Location': 'Test Rd'}),))
                with patch.object(llm, 'TESTMODE', False), patch.object(llm, 'LLM_API_CONFIGURED', True), patch.object(jobs, 'LLM_API_CONFIGURED', True), patch.object(llm, '_call_llm', return_value=result), patch.object(llm, 'safe_print') as log, patch.object(jobs, 'DESCRIPTION_MAX_ATTEMPTS', 2):
                    self.assertTrue(jobs.run_one(path, llm.generate_description, now=1))
                    with sqlite3.connect(path) as conn:
                        row = conn.execute('SELECT last_error,attempts,status,lease_token FROM description_jobs').fetchone()
                        self.assertEqual(row, ('validation:' + code, 1, 'pending', None))
                        self.assertEqual(conn.execute('SELECT cost,outcome FROM llm_attempts').fetchone(), (None, 'failed'))
                    log.assert_called_once_with('Description generation failed: validation:' + code)
                    self.assertNotIn(secret, str(log.call_args_list))
                    self.assertTrue(jobs.run_one(path, llm.generate_description, now=10000))
                    with sqlite3.connect(path) as conn:
                        self.assertEqual(conn.execute('SELECT attempts,status FROM description_jobs').fetchone(), (2, 'failed'))
                        self.assertEqual(conn.execute('SELECT COUNT(*) FROM llm_attempts').fetchone()[0], 2)


if __name__ == '__main__':
    unittest.main()
