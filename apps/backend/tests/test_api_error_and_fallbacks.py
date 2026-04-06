import asyncio
import os
import unittest
from datetime import UTC, datetime, timedelta
from urllib.error import URLError
from unittest.mock import patch

from fastapi import HTTPException

import app.api.opportunities as opportunities_api
import app.services.opportunity_ai_service as opportunity_ai_service
import app.services.search_service as search_service
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import artifact_store, conversation_store, cv_store, opportunity_store, person_store, session_store
from app.services.person_store import get_person, seed_persons


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    artifact_store._artifacts.clear()  # type: ignore[attr-defined]
    session_store._sessions.clear()  # type: ignore[attr-defined]
    conversation_store._conversations.clear()  # type: ignore[attr-defined]
    cv_store._cvs.clear()  # type: ignore[attr-defined]


class ApiContractsAndIsolationTests(unittest.TestCase):
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

    def test_update_opportunity_rejects_invalid_status_with_422(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            raw_text="FastAPI role.",
        )
        with self.assertRaises(HTTPException) as invalid_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=created["opportunity_id"],
                payload=opportunities_api.UpdateOpportunityRequest(status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_status.exception.status_code, 422)

    def test_update_opportunity_rejects_invalid_transition_with_409(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Analyst",
            company="DataCo",
            location="Hybrid",
            raw_text="SQL role.",
        )
        with self.assertRaises(HTTPException) as invalid_transition:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=created["opportunity_id"],
                payload=opportunities_api.UpdateOpportunityRequest(status="applied"),
                _=self.session,
            )
        self.assertEqual(invalid_transition.exception.status_code, 409)

    def test_artifacts_are_isolated_by_person_id(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="ML Engineer",
            company="AI Corp",
            location="Remote",
            raw_text="Python and ML role.",
        )
        opportunity_id = created["opportunity_id"]
        moved = opportunity_store.update_opportunity("p-001", opportunity_id, "analyzed", None)
        assert moved is not None
        moved = opportunity_store.update_opportunity("p-001", opportunity_id, "prioritized", None)
        assert moved is not None

        with patch.object(
            opportunities_api,
            "prepare_application_materials",
            return_value={
                "guidance_text": "Guia",
                "cover_letter": "Carta",
                "experience_summary": "Resumen",
                "semantic_evidence": {
                    "source": "fallback_preview",
                    "query": "query",
                    "top_k": 24,
                    "snippets": [],
                },
            },
        ):
            opportunities_api.prepare(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        with self.assertRaises(HTTPException) as cross_artifacts:
            opportunities_api.list_artifacts(
                person_id="p-002",
                opportunity_id=opportunity_id,
                _=self.session,
            )
        self.assertEqual(cross_artifacts.exception.status_code, 404)

    def test_stream_endpoints_reject_cross_person_access(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="DevOps Engineer",
            company="Cloud Co",
            location="Remote",
            raw_text="Kubernetes role.",
        )
        opportunity_id = created["opportunity_id"]

        with self.assertRaises(HTTPException) as cross_analyze:
            asyncio.run(
                opportunities_api.analyze_stream(
                    person_id="p-002",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
        self.assertEqual(cross_analyze.exception.status_code, 404)

        with self.assertRaises(HTTPException) as cross_prepare:
            asyncio.run(
                opportunities_api.prepare_stream(
                    person_id="p-002",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
        self.assertEqual(cross_prepare.exception.status_code, 404)

    def test_analyze_and_prepare_reject_missing_opportunity(self) -> None:
        missing_opportunity_id = "o-missing"

        with self.assertRaises(HTTPException) as missing_analyze:
            opportunities_api.analyze(
                person_id="p-001",
                opportunity_id=missing_opportunity_id,
                _=self.session,
                settings=get_settings(),
            )
        self.assertEqual(missing_analyze.exception.status_code, 404)
        self.assertEqual(missing_analyze.exception.detail, "Opportunity not found")

        with self.assertRaises(HTTPException) as missing_prepare:
            opportunities_api.prepare(
                person_id="p-001",
                opportunity_id=missing_opportunity_id,
                _=self.session,
                settings=get_settings(),
            )
        self.assertEqual(missing_prepare.exception.status_code, 404)
        self.assertEqual(missing_prepare.exception.detail, "Opportunity not found")

    def test_stream_endpoints_reject_missing_opportunity(self) -> None:
        missing_opportunity_id = "o-missing"

        with self.assertRaises(HTTPException) as missing_analyze_stream:
            asyncio.run(
                opportunities_api.analyze_stream(
                    person_id="p-001",
                    opportunity_id=missing_opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
        self.assertEqual(missing_analyze_stream.exception.status_code, 404)
        self.assertEqual(missing_analyze_stream.exception.detail, "Opportunity not found")

        with self.assertRaises(HTTPException) as missing_prepare_stream:
            asyncio.run(
                opportunities_api.prepare_stream(
                    person_id="p-001",
                    opportunity_id=missing_opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
        self.assertEqual(missing_prepare_stream.exception.status_code, 404)
        self.assertEqual(missing_prepare_stream.exception.detail, "Opportunity not found")


class FallbackBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PERSISTENCE_BACKEND"] = "memory"
        get_settings.cache_clear()
        _clear_in_memory_state()
        seed_persons()

    def tearDown(self) -> None:
        get_settings.cache_clear()
        _clear_in_memory_state()

    def test_search_falls_back_when_all_providers_fail(self) -> None:
        person = get_person("p-001")
        assert person is not None
        settings = get_settings()
        settings.rapidapi_key = "test-key"
        settings.rapidapi_adzuna_host = "test-host"
        settings.tavily_api_key = "test-key"

        with patch.object(search_service, "_adzuna_search_via_rapidapi", side_effect=URLError("x")):
            with patch.object(search_service, "_remotive_search", side_effect=URLError("x")):
                with patch.object(search_service, "_tavily_search", side_effect=URLError("x")):
                    payload = search_service.search_opportunities(
                        person=person,
                        query="python",
                        max_results=6,
                        settings=settings,
                    )

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["source_provider"], "fallback")
        self.assertTrue(
            any("All providers returned empty or failed" in warning for warning in payload["warnings"])
        )

    def test_llm_fallbacks_are_applied_in_analyze_and_prepare(self) -> None:
        person = get_person("p-001")
        assert person is not None
        opportunity = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            raw_text="FastAPI role.",
        )
        settings = get_settings()

        evidence = {
            "source": "fallback_preview",
            "query": "query",
            "top_k": 24,
            "snippets": [],
        }

        with patch.object(opportunity_ai_service, "_tavily_culture_signals", return_value=([], [])):
            with patch.object(opportunity_ai_service, "_build_semantic_evidence", return_value=evidence):
                with patch.object(
                    opportunity_ai_service,
                    "complete_prompt",
                    return_value=opportunity_ai_service.FALLBACK_MESSAGE,
                ):
                    analyzed = opportunity_ai_service.analyze_opportunity(
                        person=person,
                        opportunity=opportunity,
                        settings=settings,
                    )
                with patch.object(
                    opportunity_ai_service,
                    "complete_prompt",
                    side_effect=[
                        opportunity_ai_service.FALLBACK_MESSAGE,
                        opportunity_ai_service.FALLBACK_MESSAGE,
                        opportunity_ai_service.FALLBACK_MESSAGE,
                    ],
                ):
                    prepared = opportunity_ai_service.prepare_application_materials(
                        person=person,
                        opportunity=opportunity,
                        settings=settings,
                    )

        self.assertIn("No fue posible ejecutar analisis con LLM", analyzed["analysis_text"])
        self.assertIn("Fallback:", prepared["guidance_text"])
        self.assertIn("Fallback carta", prepared["cover_letter"])
        self.assertIn("Fallback resumen", prepared["experience_summary"])


if __name__ == "__main__":
    unittest.main()
