"""Public fallbacks must not turn dispatch logs into purported AI prose."""
import copy
import unittest

from types import SimpleNamespace as NS
from backend import llm
from backend.descriptions import source_description, incident_description


class DispatchFallbackTests(unittest.TestCase):
    def test_chp_fallback_uses_plain_facts_not_raw_dispatch_entries(self):
        incident = {
            'Source': 'CHP', 'Type': 'Traffic Collision', 'Location': 'I-5',
            'Details': [
                '[5:01 PM] [1] No injuries reported',
                '[5:02 PM] [2] Road is NOT closed',
                '[5:03 PM] [3] B115-020 1039 1185 [Shared]',
                '[5:04 PM] [4] Unit At Scene',
                '[5:05 PM] [5] [FSP] has closed their incident [260923BCFSP0123]',
            ],
        }
        original = copy.deepcopy(incident)
        summary = source_description(incident)
        self.assertIn('Traffic collision reported at I-5.', summary)
        self.assertIn('No injuries reported', summary)
        self.assertIn('Road is not closed', summary)
        for raw in ('[', '5:01', 'B115', '1039', '1185', 'Unit At Scene', 'closed their incident'):
            self.assertNotIn(raw, summary)
        self.assertEqual(incident, original)


    def test_cached_dispatch_log_is_read_repaired_without_mutating_source(self):
        for origin in ('source', 'legacy', 'ai'):
            row = {'source': 'CHP', 'type': 'Traffic Collision', 'location': 'I-5',
                   'description_origin': origin,
                   'description': 'CHP report: Traffic Collision. Reported details: [5:04 PM] [4] Unit At Scene.',
                   'details': '["[5:04 PM] [4] Unit At Scene"]'}
            original = copy.deepcopy(row)
            self.assertEqual(incident_description(row), 'Traffic collision reported at I-5.')
            self.assertEqual(row, original)
        row['description'] = 'A collision is reported on I-5; no injuries reported.'
        row['description_origin'] = 'ai'
        self.assertEqual(incident_description(row), row['description'])

    def test_model_dispatch_log_is_rejected_not_recorded_as_success(self):
        import json
        for summary in ('[5:04 PM] [4] Unit At Scene',
                        'CHP has closed their incident [260923IC0278].',
                        'B115-020 1039 1185 [Shared]'):
            response = NS(choices=[NS(finish_reason='stop', message=NS(content=json.dumps({'summary': summary})))])
            with self.subTest(summary=summary), self.assertRaises(ValueError):
                llm._parse_response(response)


if __name__ == '__main__':
    unittest.main()
