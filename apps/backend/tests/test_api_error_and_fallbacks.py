import asyncio
import os
import unittest
from datetime import UTC, datetime, timedelta
from urllib.error import URLError
from unittest.mock import patch

from fastapi import HTTPException

import app.api.opportunities as opportunities_api
import app.api.search as search_api
import app.services.opportunity_ai_service as opportunity_ai_service
import app.services.search_service as search_service
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import artifact_store, conversation_store, cv_store, opportunity_store, person_store, session_store
from app.services.ai_run_store import reset_ai_runs
from app.services.person_store import get_person, seed_persons
from app.services.prompt_config_store import reset_prompt_configs


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    artifact_store._artifacts.clear()  # type: ignore[attr-defined]
    session_store._sessions.clear()  # type: ignore[attr-defined]
    conversation_store._conversations.clear()  # type: ignore[attr-defined]
    cv_store._cvs.clear()  # type: ignore[attr-defined]
    reset_prompt_configs()
    reset_ai_runs()


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

    def test_search_api_rejects_missing_person(self) -> None:
        with self.assertRaises(HTTPException) as missing_person:
            search_api.search(
                person_id="p-unknown",
                payload=search_api.SearchRequest(query="python backend", max_results=6),
                _=self.session,
                settings=get_settings(),
            )
        self.assertEqual(missing_person.exception.status_code, 404)
        self.assertEqual(missing_person.exception.detail, "Person not found")

    def test_search_results_are_not_persisted_until_explicit_save(self) -> None:
        mocked_search_item = {
            "search_result_id": "sr-v1-001",
            "source_provider": "remotive",
            "source_url": "https://remotive.com/remote-jobs/software-dev/backend-engineer-1",
            "title": "Backend Engineer",
            "company": "RemoteCo",
            "location": "Remote",
            "snippet": "Role focused on Python and FastAPI",
            "captured_at": "2026-04-06T00:00:00+00:00",
            "normalized_payload": {"source": "search", "provider": "remotive"},
        }

        self.assertEqual(len(opportunity_store.list_opportunities("p-001")), 0)

        with patch.object(
            search_api,
            "search_opportunities",
            return_value={"items": [mocked_search_item], "warnings": []},
        ):
            response = search_api.search(
                person_id="p-001",
                payload=search_api.SearchRequest(query="python backend", max_results=6),
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(len(response.items), 1)
        self.assertEqual(response.items[0].search_result_id, mocked_search_item["search_result_id"])
        self.assertEqual(len(opportunity_store.list_opportunities("p-001")), 0)

        saved = opportunities_api.create_from_search(
            person_id="p-001",
            payload=opportunities_api.FromSearchRequest(
                source_provider=response.items[0].source_provider,
                source_url=response.items[0].source_url,
                title=response.items[0].title,
                company=response.items[0].company,
                location=response.items[0].location,
                snippet=response.items[0].snippet,
                normalized_payload=response.items[0].normalized_payload,
            ),
            _=self.session,
        )
        self.assertTrue(saved.created)
        self.assertEqual(len(opportunity_store.list_opportunities("p-001")), 1)

    def test_analyze_profile_match_uses_cached_result_when_not_forced(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            raw_text="FastAPI role.",
        )
        opportunity_id = created["opportunity_id"]
        semantic = {
            "source": "semantic_retrieval",
            "query": "q",
            "top_k": 24,
            "snippets": ["s1"],
        }
        with patch.object(
            opportunities_api,
            "analyze_profile_match",
            return_value={"analysis_text": "Analisis nuevo", "semantic_evidence": semantic},
        ) as mocked:
            first = opportunities_api.analyze_profile_match_action(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.ActionRequest(force_recompute=True),
                _=self.session,
                settings=get_settings(),
            )
            second = opportunities_api.analyze_profile_match_action(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.ActionRequest(force_recompute=False),
                _=self.session,
                settings=get_settings(),
            )

        self.assertFalse(first.served_from_cache)
        self.assertTrue(second.served_from_cache)
        self.assertEqual(first.analysis_text, second.analysis_text)
        self.assertEqual(mocked.call_count, 1)

    def test_prepare_generates_only_selected_targets(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Engineer",
            company="DataCo",
            location="Remote",
            raw_text="Python and SQL role.",
        )
        opportunity_id = created["opportunity_id"]

        payload = {
            "outputs": {"cover_letter": "Carta personalizada"},
            "semantic_evidence": {
                "source": "semantic_retrieval",
                "query": "prepare query",
                "top_k": 24,
                "snippets": ["cv snippet"],
            },
        }
        with patch.object(opportunities_api, "prepare_selected_materials", return_value=payload):
            response = opportunities_api.prepare(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.PrepareRequest(
                    targets=["cover_letter"],
                    force_recompute=True,
                ),
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.guidance_text, "")
        self.assertEqual(len(response.artifacts), 1)
        self.assertEqual(response.artifacts[0].artifact_type, "cover_letter")
        self.assertFalse(response.served_from_cache)


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

    def test_search_degrades_partially_when_adzuna_fails(self) -> None:
        person = get_person("p-001")
        assert person is not None
        settings = get_settings()
        settings.rapidapi_key = "test-key"
        settings.rapidapi_adzuna_host = "test-host"
        settings.tavily_api_key = "test-key"

        remotive_item = {
            "search_result_id": "sr-rem-1",
            "source_provider": "remotive",
            "source_url": "https://remotive.com/job/1",
            "title": "Backend Engineer",
            "company": "RemotiveCo",
            "location": "Remote",
            "snippet": "Remotive snippet",
            "captured_at": "2026-04-06T00:00:00+00:00",
            "normalized_payload": {"provider": "remotive"},
        }
        tavily_item = {
            "search_result_id": "sr-tav-1",
            "source_provider": "tavily",
            "source_url": "https://example.com/jobs/1",
            "title": "Platform Engineer",
            "company": "ExampleCo",
            "location": "",
            "snippet": "Tavily snippet",
            "captured_at": "2026-04-06T00:00:00+00:00",
            "normalized_payload": {"provider": "tavily"},
        }

        with patch.object(search_service, "_adzuna_search_via_rapidapi", side_effect=URLError("x")):
            with patch.object(search_service, "_remotive_search", return_value=[remotive_item]):
                with patch.object(search_service, "_tavily_search", return_value=[tavily_item]):
                    payload = search_service.search_opportunities(
                        person=person,
                        query="python",
                        max_results=6,
                        settings=settings,
                    )

        self.assertEqual(len(payload["items"]), 2)
        providers = {item["source_provider"] for item in payload["items"]}
        self.assertEqual(providers, {"remotive", "tavily"})
        self.assertTrue(
            any("Adzuna provider failed" in warning for warning in payload["warnings"])
        )
        self.assertFalse(
            any("All providers returned empty or failed" in warning for warning in payload["warnings"])
        )
        tavily_result = next(item for item in payload["items"] if item["source_provider"] == "tavily")
        self.assertEqual(tavily_result["location"], person["location"])

    def test_search_warns_for_missing_optional_config_but_keeps_results(self) -> None:
        person = get_person("p-001")
        assert person is not None
        settings = get_settings()
        settings.rapidapi_key = ""
        settings.rapidapi_adzuna_host = ""
        settings.tavily_api_key = ""

        remotive_item = {
            "search_result_id": "sr-rem-only",
            "source_provider": "remotive",
            "source_url": "https://remotive.com/job/99",
            "title": "Data Engineer",
            "company": "Remote Data",
            "location": "Remote",
            "snippet": "Remotive result",
            "captured_at": "2026-04-06T00:00:00+00:00",
            "normalized_payload": {"provider": "remotive"},
        }

        with patch.object(search_service, "_remotive_search", return_value=[remotive_item]):
            payload = search_service.search_opportunities(
                person=person,
                query="data engineer",
                max_results=6,
                settings=settings,
            )

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["source_provider"], "remotive")
        self.assertTrue(
            any("Adzuna via RapidAPI is not configured" in warning for warning in payload["warnings"])
        )
        self.assertTrue(any("Tavily API key is missing" in warning for warning in payload["warnings"]))
        self.assertFalse(
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
