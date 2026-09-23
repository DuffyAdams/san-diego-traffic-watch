import unittest
from backend.incident_facts import incident_facts, fact_hash, compact_input, severity_for, template_description


class IncidentFactTests(unittest.TestCase):
    def facts(self, *details):
        return incident_facts({'Source': 'CHP', 'Type': 'Traffic Collision', 'Details': list(details)})

    def test_negation_uncertainty_and_unknown_codes_survive(self):
        facts = self.facts('NO INJURIES', 'ROAD NOT CLOSED', 'POSS ROLL OVER', 'UNKNOWN 9999')
        self.assertEqual(len(facts['reports_oldest_first']), 4)
        self.assertIsNone(severity_for(facts))

    def test_new_shoulder_report_overrides_old_lane_impact(self):
        self.assertEqual(severity_for(self.facts('BLOCKING #1 LN', 'EVERYTHING ON RHS')), 1)
        self.assertEqual(severity_for(self.facts('ALL LANES OPEN', 'ALL LANES BLOCKED')), 4)

    def test_uncertain_or_negated_reopening_is_not_scored_as_open(self):
        for text in ('NOT ALL LANES OPEN', 'POSS ALL LANES OPEN', 'ALL LANES OPEN EXCEPT #1', 'ALL LANES OPEN / #2 BLOCKED'):
            with self.subTest(text=text):
                self.assertIsNone(severity_for(self.facts('ALL LANES BLOCKED', text)))

    def test_fsp_closure_is_administrative_and_never_road_resolution(self):
        facts = self.facts('BLOCKING #1 LN', '[3] [FSP] has closed their incident [260923BCFSP0123]')
        self.assertEqual(severity_for(facts), 2)
        self.assertEqual(len(facts['reports_oldest_first']), 1)

    def test_latest_repeated_state_is_retained(self):
        self.assertEqual(severity_for(self.facts('ALL LANES OPEN', 'ALL LANES BLOCKED', 'ALL LANES OPEN')), 1)

    def test_shared_wrappers_and_timestamps_do_not_change_hash(self):
        self.assertEqual(fact_hash(self.facts('[12:00 PM] [1] Vehicle on shoulder [Shared]')),
                         fact_hash(self.facts('Vehicle on shoulder')))

    def test_xml_and_html_category_have_same_meaning(self):
        xml = incident_facts({'RawType': '1183-Trfc Collision-Unkn Inj'})
        html = incident_facts({'RawType': 'Trfc Collision-Unkn Inj'})
        self.assertEqual(fact_hash(xml), fact_hash(html))

    def test_input_budget_prioritizes_impacts_and_marks_omissions(self):
        facts = self.facts(*[f'Other narrative {i}: ' + 'x' * 200 for i in range(20)], 'ALL LANES OPEN')
        compact = compact_input(facts)
        self.assertIn('ALL LANES OPEN', compact['reports_oldest_first'])
        self.assertGreater(compact['omitted_reports'], 0)
        self.assertLessEqual(sum(map(len, compact['reports_oldest_first'])), 2400)

    def test_sigalert_category_alone_does_not_force_critical(self):
        self.assertIsNone(severity_for(incident_facts({'Type': 'SIGALERT'})))


if __name__ == '__main__':
    unittest.main()
