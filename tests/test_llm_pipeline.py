import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend import config, db, llm


class ImmediateLlmPipelineTests(unittest.TestCase):
    def test_new_incident_is_not_queued_for_deferred_refinement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "traffic-test.db")
            with patch.object(db, "DB_FILE", db_path):
                db.init_db()
                db.save_or_update_incident(
                    {
                        "No.": "TEST-1",
                        "Date": "2026-07-17",
                        "Timestamp": "2026-07-17 18:00:00",
                        "Location": "I-5 / Test Rd",
                        "Type": "Traffic Collision",
                        "Details": ["Two lanes blocked"],
                        "Source": "CHP",
                    },
                    generate_description_on_insert=False,
                )

            with closing(sqlite3.connect(db_path)) as conn:
                queued_at, enriched_at, pending_at = conn.execute(
                    """
                    SELECT batch_queued_at, batch_enriched_at, llm_pending_at
                    FROM incidents
                    """
                ).fetchone()

            self.assertIsNone(queued_at)
            self.assertIsNone(enriched_at)
            self.assertIsNotNone(pending_at)

    def test_glm_flash_summary_model_is_configured(self):
        self.assertEqual(config.DEFAULT_IMMEDIATE_LLM_MODEL, "z-ai/glm-5.3-flash")
        self.assertFalse(hasattr(config, "BATCH_LLM_MODEL"))
        self.assertFalse(hasattr(config, "DEFAULT_BATCH_LLM_MODEL"))

    def test_environment_model_override_is_ignored(self):
        env = os.environ.copy()
        env["IMMEDIATE_LLM_MODEL"] = "google/gemini-2.5-flash-lite"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from backend import config; "
                    "print(config.IMMEDIATE_LLM_MODEL)"
                ),
            ],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.stdout.strip(), "z-ai/glm-5.3-flash")

    def test_background_enrichment_can_surface_transient_provider_failures(self):
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=Mock(side_effect=RuntimeError("temporary provider failure"))
                )
            )
        )

        with (
            patch.object(llm, "TESTMODE", False),
            patch.object(llm, "LLM_API_CONFIGURED", True),
            patch.object(llm, "llm_client", client),
            self.assertRaisesRegex(RuntimeError, "temporary provider failure"),
        ):
            llm.generate_description(
                {"No.": "TEST-1", "Details": ["Lane blocked"]},
                raise_on_error=True,
            )

    def test_llm_call_uses_configured_glm_flash_model(self):
        create = Mock(return_value=SimpleNamespace())
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

        with patch.object(llm, "llm_client", client):
            llm._call_llm("system", "user")

        self.assertEqual(create.call_args.kwargs["model"], "z-ai/glm-5.3-flash")


if __name__ == "__main__":
    unittest.main()
