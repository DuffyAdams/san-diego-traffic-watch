import unittest
from backend.descriptions import source_description, incident_description
from backend.incident_facts import template_description

class NoAgencyPrefixTests(unittest.TestCase):
    def test_templates_omit_agency(self):
        self.assertEqual(source_description({'Source':'SDPD','Type':'Welfare check','Location':'Main St'}), 'Welfare check at Main St.')
        self.assertEqual(template_description({'source':'CHP','type':'Traffic hazard','location':'I-5'}), 'Traffic hazard at I-5.')
    def test_existing_prefixes_removed_without_removing_actions(self):
        for prefix in ['CHP reports ', 'SDPD report: ', 'SDSO reported ', 'SDFD reports ']:
            self.assertEqual(incident_description({'description':prefix+'a hazard on I-5.'}), 'A hazard on I-5.')
        self.assertEqual(incident_description({'description':'CHP closed lane 2.'}), 'CHP closed lane 2.')
