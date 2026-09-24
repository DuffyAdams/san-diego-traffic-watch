import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import patch

from backend import db, llm, monitor
from backend.descriptions import incident_description, source_description
from scripts.backfill_descriptions import backfill


class DescriptionTests(unittest.TestCase):
    def setUp(self):
        accounting = patch.object(llm, "record_attempt")
        accounting.start()
        self.addCleanup(accounting.stop)
        self.incident = {
            "No.": "SDSO-TEST", "Date": "2026-09-18",
            "Timestamp": "2026-09-18 12:00:00", "Source": "SDSO",
            "Type": "1130 - INCOMPLETE PHONE CALL", "Location": "100 MAIN ST",
            "Neighborhood": "SPRING VALLEY", "City": "San Diego County",
            "Details": ["Service Area: RANCHO SAN DIEGO / LEMON GROVE"],
            "active": 0,
        }
        self.expected = "SDSO report: Incomplete phone call at 100 MAIN ST, Spring Valley."

    def test_closed_sheriff_call_uses_only_supplied_facts(self):
        self.assertEqual(source_description(self.incident), self.expected)
        with patch.object(monitor._description_executor, "submit") as submit:
            self.assertFalse(monitor._schedule_description_refresh(self.incident))
        submit.assert_not_called()

    def test_legacy_database_shape_and_placeholders(self):
        row = {
            "source": "SDSO", "type": self.incident["Type"],
            "location": "100 MAIN ST", "neighborhood": "SPRING VALLEY",
            "details": json.dumps(self.incident["Details"]),
        }
        for empty in (None, "", " \n ", "No description available", "Traffic incident reported."):
            with self.subTest(description=empty):
                self.assertEqual(incident_description({**row, "description": empty}), self.expected)
        self.assertEqual(incident_description({**row, "description": "Existing AI summary."}), "Existing AI summary.")

    def test_unknown_code_is_not_guessed(self):
        self.assertEqual(source_description({"Source": "SDSO", "Type": "9999"}), "SDSO report: 9999.")
        self.assertEqual(source_description({}), "Incident.")

    def test_details_preserve_negations_and_ignore_administrative_metadata(self):
        description = source_description({
            "Source": "CHP", "Type": "Traffic Collision", "Location": "I-5",
            "Details": '["No injuries reported", "Road is NOT closed"]',
        })
        self.assertIn("No injuries reported; Road is not closed.", description)
        self.assertEqual(source_description({"Details": {"unexpected": "data"}}), "Incident.")

    def test_ai_failure_or_empty_output_uses_specific_fallback(self):
        for response in (None, "", '{"summary": null}', '{"summary":""}', '{}', 'invalid'):
            with self.subTest(response=response):
                result = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=response))])
                with patch.object(llm, "TESTMODE", False), patch.object(llm, "LLM_API_CONFIGURED", True), patch.object(llm, "_call_llm", return_value=result):
                    self.assertEqual(llm.generate_description(self.incident), (self.expected, None))
                    with self.assertRaises((ValueError, TypeError)):
                        llm.generate_description(self.incident, raise_on_error=True)

    def test_valid_ai_summary_is_preserved(self):
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content='{"summary":"Reported collision on I-5."}'
        ))])
        self.assertEqual(llm._parse_response(response, False), ("Reported collision on I-5.", None))

    def test_unconfigured_ai_returns_source_facts(self):
        with patch.object(llm, "TESTMODE", False), patch.object(llm, "LLM_API_CONFIGURED", False):
            self.assertEqual(llm.generate_description(self.incident), (self.expected, None))

    def test_insert_read_repair_and_idempotent_backfill_preserve_other_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "incidents.db")
            with patch.object(db, "DB_FILE", path), patch.object(db, "generate_description") as generate:
                db.init_db()
                db.save_or_update_incident(self.incident, generate_description_on_insert=False)
                generate.assert_not_called()
                with closing(sqlite3.connect(path)) as conn:
                    row = conn.execute("SELECT description, active, llm_pending_at FROM incidents").fetchone()
                    self.assertEqual(row, (self.expected, 0, None))
                    conn.execute("UPDATE incidents SET description = '', severity = 3, likes = 4")
                    conn.execute("INSERT INTO incidents (incident_no, date, description) VALUES ('KEEP', '2026-01-01', 'Good summary')")
                    conn.commit()
                self.assertEqual(db.read_incidents()[0]["description"], self.expected)
                self.assertEqual(backfill(path), 1)
                with closing(sqlite3.connect(path)) as conn:
                    self.assertEqual(conn.execute("SELECT description FROM incidents WHERE incident_no = 'SDSO-TEST'").fetchone()[0], "")
                self.assertEqual(backfill(path, apply=True, batch_size=1), 1)
                self.assertEqual(backfill(path, apply=True), 0)
                with closing(sqlite3.connect(path)) as conn:
                    self.assertEqual(conn.execute("SELECT description, active, severity, likes FROM incidents WHERE incident_no = 'SDSO-TEST'").fetchone(), (self.expected, 0, 3, 4))
                    self.assertEqual(conn.execute("SELECT description FROM incidents WHERE incident_no = 'KEEP'").fetchone()[0], "Good summary")

    def test_source_update_refreshes_fallback_but_preserves_concurrent_ai_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "incidents.db")
            with patch.object(db, "DB_FILE", path):
                db.init_db()
                db.save_or_update_incident(self.incident, generate_description_on_insert=False)
                existing = db.fetch_existing_incidents([("SDSO-TEST", "2026-09-18")])[("SDSO-TEST", "2026-09-18")]
                changed = {**self.incident, "Location": "200 MAIN ST"}
                db.save_or_update_incident(changed, existing_record=existing, generate_description_on_insert=False)
                self.assertIn("200 MAIN ST", db.read_incidents()[0]["description"])
                with closing(sqlite3.connect(path)) as conn:
                    conn.execute("UPDATE incidents SET description = 'Fresh AI summary'")
                    conn.commit()
                db.save_or_update_incident(changed, existing_record=existing, generate_description_on_insert=False)
                self.assertEqual(db.read_incidents()[0]["description"], "Fresh AI summary")


if __name__ == "__main__":
    unittest.main()
