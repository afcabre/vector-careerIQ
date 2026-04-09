import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException

import app.api.ai_runtime_admin as ai_runtime_admin_api
import app.services.opportunity_ai_service as opportunity_ai_service
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import opportunity_store, person_store
from app.services.ai_runtime_config_store import (
    DEFAULT_TOP_K_SEMANTIC_ANALYSIS,
    DEFAULT_TOP_K_SEMANTIC_INTERVIEW,
    DEFAULT_INTERVIEW_RESEARCH_MODE,
    DEFAULT_INTERVIEW_RESEARCH_MAX_STEPS,
    reset_ai_runtime_config,
    update_ai_runtime_config,
)
from app.services.person_store import get_person, seed_persons


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    reset_ai_runtime_config()


class AIRuntimeConfigAdminTests(unittest.TestCase):
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

    def test_get_ai_runtime_config_returns_defaults(self) -> None:
        response = ai_runtime_admin_api.get_config(_=self.session)
        self.assertEqual(response.config_key, "global")
        self.assertEqual(response.top_k_semantic_analysis, DEFAULT_TOP_K_SEMANTIC_ANALYSIS)
        self.assertEqual(response.top_k_semantic_interview, DEFAULT_TOP_K_SEMANTIC_INTERVIEW)
        self.assertEqual(response.interview_research_mode, DEFAULT_INTERVIEW_RESEARCH_MODE)
        self.assertEqual(response.interview_research_max_steps, DEFAULT_INTERVIEW_RESEARCH_MAX_STEPS)

    def test_patch_ai_runtime_config_updates_values(self) -> None:
        updated = ai_runtime_admin_api.patch_config(
            payload=ai_runtime_admin_api.UpdateAIRuntimeConfigRequest(
                top_k_semantic_analysis=15,
                top_k_semantic_interview=10,
                interview_research_mode="adaptive",
                interview_research_max_steps=6,
            ),
            session=self.session,
        )
        self.assertEqual(updated.top_k_semantic_analysis, 15)
        self.assertEqual(updated.top_k_semantic_interview, 10)
        self.assertEqual(updated.interview_research_mode, "adaptive")
        self.assertEqual(updated.interview_research_max_steps, 6)
        self.assertEqual(updated.updated_by, "tutor")

    def test_patch_ai_runtime_config_requires_payload_fields(self) -> None:
        with self.assertRaises(HTTPException) as empty_patch:
            ai_runtime_admin_api.patch_config(
                payload=ai_runtime_admin_api.UpdateAIRuntimeConfigRequest(),
                session=self.session,
            )
        self.assertEqual(empty_patch.exception.status_code, 422)

    def test_update_ai_runtime_config_rejects_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            update_ai_runtime_config(
                top_k_semantic_analysis=99,
                updated_by="tutor",
            )

    def test_analyze_bundle_uses_runtime_top_k(self) -> None:
        person = get_person("p-001")
        assert person is not None
        opportunity = opportunity_store.import_text_opportunity(
            person_id=person["person_id"],
            title="Product Designer",
            company="Acme",
            location="Remote",
            raw_text="Role focused on UX strategy and product discovery.",
        )
        settings = get_settings()
        update_ai_runtime_config(
            top_k_semantic_analysis=11,
            updated_by="tutor",
        )

        captured: dict[str, int] = {}

        def _fake_semantic_evidence(person_arg, opportunity_arg, settings_arg, top_k=24):  # noqa: ARG001
            captured["top_k"] = top_k
            return {
                "source": "semantic_retrieval",
                "query": "test query",
                "top_k": top_k,
                "snippets": ["snippet 1"],
            }

        with patch.object(
            opportunity_ai_service,
            "_build_semantic_evidence",
            side_effect=_fake_semantic_evidence,
        ):
            bundle = opportunity_ai_service.build_analyze_prompt_bundle(
                person=person,
                opportunity=opportunity,
                settings=settings,
            )

        self.assertEqual(captured.get("top_k"), 11)
        self.assertEqual(bundle["semantic_evidence"]["top_k"], 11)


if __name__ == "__main__":
    unittest.main()
