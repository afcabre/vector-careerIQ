import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import app.api.opportunities as opportunities_api
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import artifact_store, conversation_store, cv_store, opportunity_store, person_store, session_store
from app.services.person_store import seed_persons


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    artifact_store._artifacts.clear()  # type: ignore[attr-defined]
    session_store._sessions.clear()  # type: ignore[attr-defined]
    conversation_store._conversations.clear()  # type: ignore[attr-defined]
    cv_store._cvs.clear()  # type: ignore[attr-defined]


class PrepareArtifactsIntegrationTests(unittest.TestCase):
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

    def test_prepare_replaces_current_artifacts_per_type(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            raw_text="FastAPI and SQL role.",
        )
        opportunity_id = created["opportunity_id"]
        moved = opportunity_store.update_opportunity("p-001", opportunity_id, "analyzed", None)
        assert moved is not None
        moved = opportunity_store.update_opportunity("p-001", opportunity_id, "prioritized", None)
        assert moved is not None

        first_payload = {
            "guidance_text": "Guia inicial",
            "cover_letter": "Carta inicial",
            "experience_summary": "Resumen inicial",
            "semantic_evidence": {
                "source": "fallback_preview",
                "query": "query 1",
                "top_k": 24,
                "snippets": [],
            },
        }
        second_payload = {
            "guidance_text": "Guia final",
            "cover_letter": "Carta final",
            "experience_summary": "Resumen final",
            "semantic_evidence": {
                "source": "semantic_retrieval",
                "query": "query 2",
                "top_k": 24,
                "snippets": ["snippet 1"],
            },
        }

        with patch.object(
            opportunities_api,
            "prepare_application_materials",
            side_effect=[first_payload, second_payload],
        ):
            first = opportunities_api.prepare(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )
            second = opportunities_api.prepare(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(first.opportunity.status, "application_prepared")
        self.assertEqual(second.opportunity.status, "application_prepared")
        self.assertEqual(second.guidance_text, "Guia final")

        current_items = artifact_store.list_current_artifacts("p-001", opportunity_id)
        self.assertEqual(len(current_items), 2)
        current_by_type = {item["artifact_type"]: item for item in current_items}
        self.assertEqual(current_by_type["cover_letter"]["content"], "Carta final")
        self.assertEqual(
            current_by_type["experience_summary"]["content"],
            "Resumen final",
        )

        all_items = [
            item
            for item in artifact_store._artifacts.values()  # type: ignore[attr-defined]
            if item["person_id"] == "p-001" and item["opportunity_id"] == opportunity_id
        ]
        self.assertEqual(len(all_items), 4)
        self.assertEqual(sum(1 for item in all_items if item["is_current"]), 2)
        self.assertEqual(sum(1 for item in all_items if not item["is_current"]), 2)

        listed = opportunities_api.list_artifacts(
            person_id="p-001",
            opportunity_id=opportunity_id,
            _=self.session,
        )
        self.assertEqual(len(listed.items), 2)
        listed_types = sorted(item.artifact_type for item in listed.items)
        self.assertEqual(listed_types, ["cover_letter", "experience_summary"])


if __name__ == "__main__":
    unittest.main()
