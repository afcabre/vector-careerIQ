import os
import unittest

from app.core.settings import get_settings
from app.services import opportunity_store
from app.services.request_trace_store import reset_request_traces


def _reset_state() -> None:
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    reset_request_traces()


class OpportunityManualImportTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PERSISTENCE_BACKEND"] = "memory"
        get_settings.cache_clear()
        _reset_state()

    def tearDown(self) -> None:
        get_settings.cache_clear()
        _reset_state()

    def test_manual_text_creates_distinct_records_and_persists_source_label(self) -> None:
        first = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Vacante CTO",
            company="",
            location="",
            raw_text="Descripcion larga de vacante uno.",
            source_label="WhatsApp Ana",
        )
        second = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Vacante CTO",
            company="",
            location="",
            raw_text="Descripcion larga de vacante dos.",
            source_label="WhatsApp Ana",
        )

        self.assertNotEqual(first["opportunity_id"], second["opportunity_id"])
        self.assertEqual(first["source_label"], "WhatsApp Ana")
        self.assertEqual(second["source_label"], "WhatsApp Ana")

    def test_duplicate_url_can_enrich_source_label_without_creating_new_record(self) -> None:
        first, created = opportunity_store.import_url_opportunity(
            person_id="p-001",
            source_url="https://example.com/jobs/1",
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            raw_text="Descripcion suficiente de vacante.",
            source_label="",
        )
        self.assertTrue(created)
        self.assertEqual(first["source_label"], "")

        second, created_again = opportunity_store.import_url_opportunity(
            person_id="p-001",
            source_url="https://example.com/jobs/1",
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            raw_text="Descripcion suficiente de vacante.",
            source_label="Headhunter Ana",
        )
        self.assertFalse(created_again)
        self.assertEqual(first["opportunity_id"], second["opportunity_id"])
        self.assertEqual(second["source_label"], "Headhunter Ana")


if __name__ == "__main__":
    unittest.main()
