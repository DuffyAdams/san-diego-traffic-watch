import os
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from backend import db, llm
from backend.description_jobs import usage_metrics
from backend.sqlite_utils import sqlite_connection


def response(content='{"summary":"A collision is reported on I-5."}', finish='stop', usage=None):
    return NS(choices=[NS(message=NS(content=content), finish_reason=finish)], usage=usage, id='test-generation', provider='test-provider')


class LlmAccountingTests(unittest.TestCase):
    def test_request_bounds_reasoning_and_requires_schema_capability(self):
        create = Mock()
        client = NS(chat=NS(completions=NS(create=create)))
        with patch.object(llm, 'llm_client', client):
            llm._call_llm('system', 'input')
        args = create.call_args.kwargs
        self.assertEqual(args['extra_body']['reasoning'], {'effort': 'low'})
        self.assertTrue(args['extra_body']['provider']['require_parameters'])
        self.assertEqual(args['response_format']['type'], 'json_schema')
        self.assertEqual(args['max_tokens'], 2048)

    def test_truncated_empty_oversized_and_extra_field_outputs_rejected(self):
        for result in [response(finish='length'), response(content=''), response(content='{"summary":"' + 'x'*200 + '"}'), response(content='{"summary":"Hi","severity":5}'), response(content='```json\n{}\n```')]:
            with self.subTest(result=result), self.assertRaises(ValueError):
                llm._parse_response(result)

    def test_usage_preserves_unknowns_and_does_not_double_count_reasoning(self):
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, 'test.db')
            db.init_db(path)
            context = {'db_file': path, 'incident_no': 'TEST', 'trigger_reason': 'update'}
            usage = NS(prompt_tokens=120, completion_tokens=400, cost=0.001,
                       completion_tokens_details=NS(reasoning_tokens=350), prompt_tokens_details=NS(cached_tokens=20))
            result = response(usage=usage)
            with patch.object(llm, 'TESTMODE', False), patch.object(llm, 'LLM_API_CONFIGURED', True), patch.object(llm, '_call_llm', return_value=result):
                llm.generate_description({'Source': 'CHP', 'Type': 'SIGALERT'}, usage_context=context)
            llm.record_attempt(None, {'db_file': path}, 0.1, RuntimeError())
            metrics = usage_metrics(path)
            self.assertEqual(metrics['attempts'], 2)
            self.assertEqual(metrics['inputTokens'], 120)
            self.assertEqual(metrics['completionTokens'], 400)
            self.assertEqual(metrics['reasoningTokens'], 350)
            self.assertEqual(metrics['missingUsage'], 1)
            self.assertEqual(metrics['reportedCost'], 0.001)

    def test_fallback_and_mock_paths_do_not_record_paid_attempts(self):
        with patch.object(llm, 'record_attempt') as record:
            with patch.object(llm, 'TESTMODE', False), patch.object(llm, 'LLM_API_CONFIGURED', False):
                llm.generate_description({'Source': 'CHP', 'Type': 'Traffic Hazard'})
            with patch.object(llm, 'TESTMODE', True):
                llm.generate_description({'Location': 'Test'})
            record.assert_not_called()


if __name__ == '__main__':
    unittest.main()
