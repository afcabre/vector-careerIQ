import json
import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException

import app.api.prompt_admin as prompt_admin_api
import app.services.opportunity_ai_service as opportunity_ai_service
import app.services.search_service as search_service
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import artifact_store, conversation_store, cv_store, opportunity_store, person_store, session_store
from app.services.ai_run_store import reset_ai_runs
from app.services.person_store import get_person, seed_persons
from app.services.prompt_config_store import (
    FLOW_SEARCH_CULTURE_TAVILY,
    FLOW_SEARCH_JOBS_TAVILY,
    reset_prompt_configs,
    update_prompt_config,
)


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    artifact_store._artifacts.clear()  # type: ignore[attr-defined]
    session_store._sessions.clear()  # type: ignore[attr-defined]
    conversation_store._conversations.clear()  # type: ignore[attr-defined]
    cv_store._cvs.clear()  # type: ignore[attr-defined]
    reset_prompt_configs()
    reset_ai_runs()


class _DummyUrlopenResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_DummyUrlopenResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class PromptConfigAdminTests(unittest.TestCase):
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

    def test_list_prompt_configs_returns_default_flows(self) -> None:
        response = prompt_admin_api.list_configs(_=self.session)
        keys = {item.flow_key for item in response.items}
        self.assertIn(FLOW_SEARCH_JOBS_TAVILY, keys)
        self.assertIn(FLOW_SEARCH_CULTURE_TAVILY, keys)

    def test_patch_prompt_config_requires_payload_fields(self) -> None:
        with self.assertRaises(HTTPException) as empty_patch:
            prompt_admin_api.patch_config(
                flow_key=FLOW_SEARCH_JOBS_TAVILY,
                payload=prompt_admin_api.UpdatePromptConfigRequest(),
                session=self.session,
            )
        self.assertEqual(empty_patch.exception.status_code, 422)

    def test_patch_prompt_config_validates_required_placeholder(self) -> None:
        with self.assertRaises(HTTPException) as invalid_template:
            prompt_admin_api.patch_config(
                flow_key=FLOW_SEARCH_JOBS_TAVILY,
                payload=prompt_admin_api.UpdatePromptConfigRequest(
                    template_text="Busqueda de vacantes solo en portales confiables"
                ),
                session=self.session,
            )
        self.assertEqual(invalid_template.exception.status_code, 422)
        self.assertIn("{query}", str(invalid_template.exception.detail))

    def test_search_uses_custom_jobs_prompt_config(self) -> None:
        person = get_person("p-001")
        assert person is not None
        settings = get_settings()
        settings.tavily_api_key = "test-key"
        settings.rapidapi_key = ""
        settings.rapidapi_adzuna_host = ""

        updated = update_prompt_config(
            flow_key=FLOW_SEARCH_JOBS_TAVILY,
            updated_by="tutor",
            template_text="Consulta enfocada: {query} fuentes: {target_sources}",
            target_sources=["site:linkedin.com/jobs", "site:greenhouse.io"],
            is_active=True,
        )
        self.assertIn("{query}", updated["template_text"])

        captured_query: dict[str, str] = {}

        def _capture_request(request, timeout: int = 20):  # noqa: ARG001
            payload = json.loads(request.data.decode("utf-8"))
            captured_query["value"] = str(payload.get("query", ""))
            return {"results": []}

        with patch.object(search_service, "_request_json", side_effect=_capture_request):
            with patch.object(search_service, "_remotive_search", return_value=[]):
                payload = search_service.search_opportunities(
                    person=person,
                    query="python backend",
                    max_results=6,
                    settings=settings,
                )

        self.assertTrue(payload["items"])  # fallback result path
        query_used = captured_query.get("value", "")
        self.assertIn("python backend", query_used)
        self.assertIn("site:linkedin.com/jobs", query_used)
        self.assertIn("site:greenhouse.io", query_used)

    def test_culture_signals_use_custom_culture_prompt_config(self) -> None:
        person = get_person("p-001")
        assert person is not None
        settings = get_settings()
        settings.tavily_api_key = "test-key"

        opportunity = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Product Designer",
            company="Acme",
            location="Remote",
            raw_text="Role focused on product discovery and UX.",
        )

        update_prompt_config(
            flow_key=FLOW_SEARCH_CULTURE_TAVILY,
            updated_by="tutor",
            template_text="Cultura de {company} para {roles} usando {target_sources}",
            target_sources=["site:glassdoor.com", "site:linkedin.com/company"],
            is_active=True,
        )

        captured_query: dict[str, str] = {}

        def _fake_urlopen(request, timeout: int = 20):  # noqa: ARG001
            payload = json.loads(request.data.decode("utf-8"))
            captured_query["value"] = str(payload.get("query", ""))
            return _DummyUrlopenResponse({"results": []})

        with patch.object(opportunity_ai_service, "urlopen", side_effect=_fake_urlopen):
            signals, warnings = opportunity_ai_service._tavily_culture_signals(  # type: ignore[attr-defined]
                person=person,
                opportunity=opportunity,
                settings=settings,
            )

        self.assertEqual(signals, [])
        self.assertTrue(any("Sin evidencia cultural externa suficiente" in warning for warning in warnings))
        query_used = captured_query.get("value", "")
        self.assertIn("Acme", query_used)
        self.assertIn("site:glassdoor.com", query_used)
        self.assertIn("site:linkedin.com/company", query_used)


if __name__ == "__main__":
    unittest.main()
