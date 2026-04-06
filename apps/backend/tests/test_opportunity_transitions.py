import os
import unittest

from app.core.settings import get_settings
from app.services import opportunity_store
from app.services.request_trace_store import reset_request_traces


def _reset_state() -> None:
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    reset_request_traces()


class OpportunityTransitionsTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PERSISTENCE_BACKEND"] = "memory"
        get_settings.cache_clear()
        _reset_state()

    def tearDown(self) -> None:
        get_settings.cache_clear()
        _reset_state()

    def test_is_valid_transition_rules(self) -> None:
        self.assertTrue(opportunity_store.is_valid_transition("detected", "detected"))
        self.assertTrue(opportunity_store.is_valid_transition("detected", "analyzed"))
        self.assertTrue(opportunity_store.is_valid_transition("application_prepared", "prioritized"))
        self.assertTrue(opportunity_store.is_valid_transition("prioritized", "discarded"))
        self.assertTrue(opportunity_store.is_valid_transition("discarded", "analyzed"))

        self.assertFalse(opportunity_store.is_valid_transition("detected", "prioritized"))
        self.assertFalse(opportunity_store.is_valid_transition("applied", "not-a-status"))
        self.assertFalse(opportunity_store.is_valid_transition("unknown", "analyzed"))
        self.assertFalse(opportunity_store.is_valid_transition("discarded", "discarded_v2"))

    def test_update_opportunity_respects_transition_constraints(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            raw_text="FastAPI and SQL role.",
        )
        opportunity_id = created["opportunity_id"]

        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status="analyzed",
            notes="reviewed",
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "analyzed")
        self.assertEqual(updated["notes"], "reviewed")

        invalid = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status="applied",
            notes=None,
        )
        self.assertIsNone(invalid)
        current = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert current is not None
        self.assertEqual(current["status"], "analyzed")

        discarded = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status="discarded",
            notes=None,
        )
        self.assertIsNotNone(discarded)
        self.assertEqual(discarded["status"], "discarded")

        reopened = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status="prioritized",
            notes=None,
        )
        self.assertIsNotNone(reopened)
        self.assertEqual(reopened["status"], "prioritized")

    def test_update_opportunity_denies_cross_person_access(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Analyst",
            company="DataCo",
            location="Hybrid",
            raw_text="SQL and BI dashboards.",
        )

        denied = opportunity_store.update_opportunity(
            person_id="p-002",
            opportunity_id=created["opportunity_id"],
            status="analyzed",
            notes="should fail",
        )
        self.assertIsNone(denied)


if __name__ == "__main__":
    unittest.main()
