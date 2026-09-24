import unittest
from backend.descriptions import incident_description, source_description

class CityContextTests(unittest.TestCase):
    def test_omit_redundant_city_context(self):
        for text in ['Debris on I-5 in San Diego.', 'Debris on I-5, San Diego.', 'Debris in San Diego, blocking lane 2.']:
            self.assertNotIn('San Diego', incident_description({'description': text}))
        self.assertEqual(source_description({'Source':'SDPD','Type':'Traffic hazard','Location':'I-5','City':'San Diego'}),'Traffic hazard at I-5.')
    def test_preserve_street_names_and_other_places(self):
        text='Collision at 11588 Via Rancho San Diego in El Cajon.'
        self.assertEqual(incident_description({'description':text}),text)
        self.assertEqual(incident_description({'description':'Collision on San Diego Ave.'}),'Collision on San Diego Ave.')
