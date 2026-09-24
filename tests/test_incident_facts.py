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

    def test_chp_closure_wrappers_are_bookkeeping_but_mixed_facts_survive(self):
        facts = self.facts(
            '[5:03 PM] [1] NEG 1125',
            '[5:18 PM] [23] [CHP] has closed their incident [260923IC0278] [Shared]',
            '[5:19 PM] [24] Unit At Scene [Shared]',
            '[5:20 PM] [25] Unit At Scene; ROAD NOT CLOSED',
        )
        self.assertEqual(facts['reports_oldest_first'], ['NEG 1125', 'Unit At Scene; ROAD NOT CLOSED'])

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

    def test_location_metadata_is_not_a_cross_street_or_physical_city(self):
        for note in ('0530', 'NB AT SHELL STATION', 'TIL 0530'):
            with self.subTest(note=note):
                facts = incident_facts({'Source': 'CHP', 'Type': 'Assist with Construction',
                    'Location': 'Sr94 W / I5 N', 'Location Desc.': note,
                    'Area': 'El Cajon', 'City': 'San Diego'})
                self.assertEqual(facts['location_note'], note)
                self.assertEqual(facts['reporting_area'], 'El Cajon')
                self.assertNotIn('cross_street', facts)
                self.assertNotIn('area', facts)
                self.assertEqual(facts['city'], 'San Diego')
        stored = incident_facts({'source': 'CHP', 'location_desc': '0530', 'area': 'Oceanside'})
        self.assertEqual(stored['location_note'], '0530')
        self.assertEqual(stored['reporting_area'], 'Oceanside')
        self.assertEqual(incident_facts({'Source': 'SDPD', 'Neighborhood': 'Downtown'})['area'], 'Downtown')

    def test_category_only_assistance_templates_preserve_neutral_notes(self):
        cases = [
            ('Assist with Construction', '0530', 'Construction assistance at Sr94 W / I5 N. Location note: 0530.'),
            ('Traffic Escort', '', 'A traffic escort call at Sr94 W / I5 N.'),
            ('Escort', 'NB AT SHELL STATION', 'An escort call at Sr94 W / I5 N. Location note: NB AT SHELL STATION.'),
        ]
        for kind, note, expected in cases:
            with self.subTest(kind=kind):
                facts = incident_facts({'Source': 'CHP', 'Type': kind, 'Location': 'Sr94 W / I5 N',
                    'Location Desc.': note, 'Area': 'El Cajon', 'Details': ['[1] Unit Assigned']})
                self.assertEqual(template_description(facts), expected)
        self.assertIsNone(template_description(self.facts('CALLER REPORTS COW IN ROAD')))

    def test_explicit_until_time_is_a_note_not_a_reopening_promise(self):
        for note, expected in [('TIL 0530', 'Until 05:30 noted.'), ('TILL 2359', 'Until 23:59 noted.'),
                               ('0530', 'Location note: 0530.'), ('TIL 2560', 'Location note: TIL 2560.'),
                               ('NB TIL 0530', 'Location note: NB TIL 0530.')]:
            with self.subTest(note=note):
                facts = incident_facts({'Type': 'Assist with Construction', 'Location Desc.': note})
                summary = template_description(facts)
                assert summary is not None
                self.assertTrue(summary.endswith(expected))
                self.assertEqual(facts['location_note'], note)
                self.assertNotIn('reopen', summary.lower())

    def test_reviewed_translation_keeps_the_original_report_as_evidence(self):
        facts = self.facts('[1] NEG VEHS PULLED OVER', 'POSS NEG VEHS PULLED OVER', 'NEG 9999')
        compact = compact_input(facts)
        self.assertEqual(compact.get('reviewed_report_phrases'), {
            'NEG VEHS PULLED OVER': 'No vehicles reported pulled over'})
        self.assertEqual(compact['reports_oldest_first'], facts['reports_oldest_first'])
        from backend.incident_facts import reviewed_report_phrase
        self.assertEqual(reviewed_report_phrase('NEG VEHS PULLED OVER'), 'No vehicles reported pulled over')
        for line in ('POSS NEG VEHS PULLED OVER', 'NEG 9999', 'NEG VEHS PULLED OVER / ROAD CLOSED'):
            self.assertIsNone(reviewed_report_phrase(line))

    def test_road_conditions_escort_is_a_category_not_an_active_operation(self):
        facts = incident_facts({'Source': 'CHP', 'Type': 'ESCORT for Road Conditions',
            'Location': '1722 E Main St', 'Location Desc.': 'El Cajon CHP Office', 'Area': 'El Cajon'})
        self.assertEqual(template_description(facts),
            'An escort call for road conditions at 1722 E Main St. Location note: El Cajon CHP Office.')

    def test_policy_refreshes_even_unchanged_source_facts(self):
        import hashlib
        import json
        facts = self.facts('ROAD NOT CLOSED')
        old_payload = json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        old_hash = hashlib.sha256(('facts-v1' + old_payload.casefold()).encode()).hexdigest()
        self.assertNotEqual(fact_hash(facts), old_hash)

    def test_caller_attribution_and_ambiguous_location_remain_source_evidence(self):
        details = [
            '[8:04 PM] [9] [Notification] [CHP]-RP CB // 1022 CHP - THEY LOCATED THE COW OWNER AND ITS OFF THE RDWY [Shared]',
            '[8:52 PM] [5] 10B APPEARS FIRE IS ON TRANS TO 5 O/SHOT',
        ]
        facts = self.facts(*details)
        compact = compact_input(facts)
        self.assertEqual(compact['reports_oldest_first'], [
            '-RP CB // 1022 CHP - THEY LOCATED THE COW OWNER AND ITS OFF THE RDWY',
            '10B APPEARS FIRE IS ON TRANS TO 5 O/SHOT'])
        self.assertNotIn('reviewed_report_phrases', compact)
        self.assertIsNone(template_description(facts))
        self.assertEqual(len(details), 2)

    def test_sigalert_category_alone_does_not_force_critical(self):
        self.assertIsNone(severity_for(incident_facts({'Type': 'SIGALERT'})))


if __name__ == '__main__':
    unittest.main()
