import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from backend import db
from backend.chp_identity import resolve_chp_identities
from backend.scrapers import ScraperError
from backend.scrapers import chp
from backend.sqlite_utils import sqlite_connection

FIXTURE = (Path(__file__).parent / 'fixtures/chp/snapshot.xml').read_bytes()


class CHPParsingTests(unittest.TestCase):
    def test_full_identity_dates_coordinates_and_chronology(self):
        records = chp.parse_chp_xml(FIXTURE)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record['NativeID'], '260923BC0007')
        self.assertEqual(record['Date'], '2026-09-23')
        self.assertEqual(record['Type'], 'Trfc Collision-Unkn Inj')
        self.assertAlmostEqual(record['Latitude'], 32.712902)
        self.assertAlmostEqual(record['Longitude'], -117.118422)
        self.assertIn('TWO VEHICLES', record['Details'][0])
        self.assertIn('EVERYTHING ON RHS', record['Details'][-1])
        self.assertEqual(len(record['SourceEvents']), 4)
        self.assertFalse(any('Unit' in line for line in record['Details']))

    def test_explicit_empty_dispatch_is_valid_but_missing_dispatch_is_not(self):
        self.assertEqual(chp.parse_chp_xml(b'<State><Center><Dispatch ID="BCCC"/></Center></State>'), [])
        for invalid in (b'<State/>', b'<html/>', FIXTURE[:-10], FIXTURE.replace(b'<State>', b'<!DOCTYPE State><State>')):
            with self.subTest(invalid=invalid[:30]), self.assertRaises(ScraperError):
                chp.parse_chp_xml(invalid)

    def test_empty_detail_element_is_valid_not_a_partial_response(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring(FIXTURE)
        log = root.find(".//Log")
        log.find("LogDetails").clear()
        ET.SubElement(log.find("LogDetails"), "details")
        self.assertEqual(chp.parse_chp_xml(ET.tostring(root))[0]["Details"], [])

    def test_partial_details_fail_entire_snapshot(self):
        with self.assertRaises(ScraperError):
            chp.parse_chp_xml(FIXTURE.replace(b'<LogDetails>', b'<NoDetails>').replace(b'</LogDetails>', b'</NoDetails>'))
        with self.assertRaises(ScraperError):
            chp.parse_chp_xml(FIXTURE.replace(b'Sep 23 2026 12:02PM', b'bad time'))

    def test_missing_coords_do_not_reject_narrative(self):
        record = chp.parse_chp_xml(FIXTURE.replace(b'32712902:117118422', b'0:0'))[0]
        self.assertNotIn('Latitude', record)
        self.assertEqual(len(record['Details']), 3)

    def test_html_selection_overrides_hidden_postback_values(self):
        state = {'__VIEWSTATE': 'saved', '__EVENTTARGET': '', '__EVENTARGUMENT': '',
                 '__VIEWSTATEGENERATOR': 'dynamic', '__EVENTVALIDATION': 'validation'}
        response = Mock(text='<html/>')
        with patch.object(chp.requests, 'post', return_value=response) as post:
            chp._get_incident_details(2, state)
        sent = post.call_args.kwargs['data']
        self.assertEqual(sent['__EVENTTARGET'], 'gvIncidents')
        self.assertEqual(sent['__EVENTARGUMENT'], 'Select$2')
        self.assertEqual(sent['__VIEWSTATEGENERATOR'], 'dynamic')
        self.assertEqual(sent['__EVENTVALIDATION'], 'validation')

    def test_missing_html_details_are_unavailable_not_empty(self):
        self.assertEqual(chp._extract_traffic_info('<html/>'), {'DetailsAvailable': False})

    def test_local_cache_is_not_a_new_disappearance_observation(self):
        with patch.object(chp, '_cached', []), patch.object(chp, '_last_poll', 100), patch.object(chp.time, 'monotonic', return_value=101), patch.object(chp, 'scrape_chp_xml') as scrape:
            result = chp.scrape_chp_incidents()
        self.assertFalse(result.fresh)
        scrape.assert_not_called()

    def test_conditional_get_keeps_xml_cache_separate_from_html(self):
        response = Mock(status_code=304)
        with patch.object(chp, '_xml_cached', [{'No.': 'xml'}]), patch.object(chp, '_cached', [{'No.': 'html'}]), patch.object(chp._session, 'get', return_value=response):
            self.assertEqual(chp.scrape_chp_xml(), [{'No.': 'xml'}])

    def test_xml_failure_uses_html_only_when_enabled(self):
        with patch.object(chp, '_cached', None), patch.object(chp, 'CHP_COLLECTOR', 'xml'), patch.object(chp, 'CHP_HTML_FALLBACK', True), patch.object(chp, 'scrape_chp_xml', side_effect=ScraperError('bad')), patch.object(chp, 'scrape_chp_html', return_value=[]) as html:
            self.assertEqual(chp.scrape_chp_incidents(), [])
            html.assert_called_once()


class CHPIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, 'test.db')
        db.init_db(self.path)
        self.record = chp.parse_chp_xml(FIXTURE)[0]

    def tearDown(self):
        self.temp.cleanup()

    def test_migration_preserves_public_id_likes_and_comments(self):
        legacy = {**self.record, 'NativeID': None}
        with patch.object(db, 'DB_FILE', self.path):
            db.save_or_update_incident(legacy, generate_description_on_insert=False)
            with sqlite_connection(self.path) as conn:
                conn.execute("INSERT INTO likes VALUES ('device', '0007', '2026-09-23')")
                conn.execute("INSERT INTO comments (incident_no, comment) VALUES ('0007', 'Keep me')")
            mapped = resolve_chp_identities([self.record], self.path)[0]
            self.assertEqual(mapped['No.'], '0007')
            db.save_or_update_incident(mapped, generate_description_on_insert=False)
        with sqlite_connection(self.path) as conn:
            self.assertEqual(conn.execute('SELECT native_id FROM incidents').fetchone()[0], self.record['NativeID'])
            self.assertEqual(conn.execute('SELECT incident_no FROM comments').fetchone()[0], '0007')
            self.assertEqual(conn.execute('SELECT incident_no FROM likes').fetchone()[0], '0007')

    def test_new_ids_keep_native_namespace_and_fsp_collision_is_distinct(self):
        fsp = {**self.record, 'NativeID': '260923BCFSP0007'}
        mapped = resolve_chp_identities([self.record, fsp], self.path)
        self.assertEqual({r['No.'] for r in mapped}, {'260923BC0007', '260923BCFSP0007'})
        self.assertEqual(mapped[1]['RelatedIncidentID'], mapped[0]['No.'])

    def test_correlated_fsp_preserves_row_but_skips_duplicate_feed_and_ai(self):
        fsp = {**self.record, 'NativeID': '260923BCFSP0007'}
        mapped = resolve_chp_identities([self.record, fsp], self.path)
        with patch.object(db, 'DB_FILE', self.path):
            for record in mapped:
                db.save_or_update_incident(record, generate_description_on_insert=False)
            self.assertEqual(len(db.read_incidents()), 1)
        with sqlite_connection(self.path) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM incidents').fetchone()[0], 2)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM description_jobs').fetchone()[0], 1)

    def test_same_location_alone_never_merges_fsp(self):
        fsp = {**self.record, 'NativeID': '260923BCFSP0007', 'Details': ['Different incident']}
        mapped = resolve_chp_identities([self.record, fsp], self.path)
        self.assertIsNone(mapped[1]['RelatedIncidentID'])

    def test_ambiguous_legacy_identity_does_not_overwrite_existing(self):
        with patch.object(db, 'DB_FILE', self.path):
            db.save_or_update_incident({**self.record, 'NativeID': None, 'Location': 'Other road'}, generate_description_on_insert=False)
        with self.assertRaises(ScraperError):
            resolve_chp_identities([self.record], self.path)

    def test_html_fallback_reuses_mapped_native_public_id(self):
        mapped = resolve_chp_identities([self.record], self.path)[0]
        with patch.object(db, 'DB_FILE', self.path):
            db.save_or_update_incident(mapped, generate_description_on_insert=False)
        html = {**self.record}
        del html['NativeID']
        self.assertEqual(resolve_chp_identities([html], self.path)[0]['No.'], mapped['No.'])


if __name__ == '__main__':
    unittest.main()
