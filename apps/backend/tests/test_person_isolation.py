import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException

import app.api.opportunities as opportunities_api
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import artifact_store, conversation_store, opportunity_store, person_store, session_store
from app.services.ai_run_store import reset_ai_runs
from app.services.person_store import seed_persons


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    artifact_store._artifacts.clear()  # type: ignore[attr-defined]
    session_store._sessions.clear()  # type: ignore[attr-defined]
    conversation_store._conversations.clear()  # type: ignore[attr-defined]
    reset_ai_runs()


class PersonIsolationIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PERSISTENCE_BACKEND"] = "memory"
        get_settings.cache_clear()
        _clear_in_memory_state()
        seed_persons()
        self.session = SessionData(
            username="tutor",
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

    def tearDown(self) -> None:
        get_settings.cache_clear()
        _clear_in_memory_state()

    def test_opportunities_are_isolated_by_person_id_in_api_handlers(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            raw_text="Python backend role with FastAPI and SQL skills required.",
        )
        opportunity_id = created["opportunity_id"]

        list_p001 = opportunities_api.list_opportunities("p-001", self.session)
        self.assertTrue(any(item.opportunity_id == opportunity_id for item in list_p001.items))

        list_p002 = opportunities_api.list_opportunities("p-002", self.session)
        self.assertFalse(any(item.opportunity_id == opportunity_id for item in list_p002.items))

        with self.assertRaises(HTTPException) as cross_access:
            opportunities_api.get_opportunity("p-002", opportunity_id, self.session)
        self.assertEqual(cross_access.exception.status_code, 404)

    def test_analyze_handler_enforces_person_scope(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Analyst",
            company="DataCo",
            location="Hybrid",
            raw_text="SQL and analytics role with dashboarding responsibilities.",
        )
        opportunity_id = created["opportunity_id"]

        fake_analyze_payload = {
            "analysis_text": "Analisis de prueba",
            "cultural_confidence": "medium",
            "cultural_warnings": [],
            "cultural_signals": [],
            "semantic_evidence": {
                "source": "fallback_preview",
                "query": "test query",
                "top_k": 24,
                "snippets": [],
            },
        }

        with patch.object(
            opportunities_api,
            "analyze_opportunity",
            return_value=fake_analyze_payload,
        ):
            analyze_ok = opportunities_api.analyze(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )
            self.assertEqual(analyze_ok.opportunity.person_id, "p-001")
            self.assertEqual(analyze_ok.opportunity.status, "analyzed")

            with self.assertRaises(HTTPException) as cross_analyze:
                opportunities_api.analyze(
                    person_id="p-002",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            self.assertEqual(cross_analyze.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
