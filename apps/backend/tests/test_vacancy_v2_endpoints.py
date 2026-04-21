import asyncio
import json
import os
import unittest
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

from fastapi import HTTPException

import app.api.opportunities as opportunities_api
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import artifact_store, conversation_store, cv_store, opportunity_store, person_store, session_store
from app.services.ai_run_store import reset_ai_runs
from app.services.person_store import seed_persons
from app.services.request_trace_store import reset_request_traces
from app.services.vacancy_blocks_service import VacancyBlocksExtractionError
from app.services.vacancy_dimensions_service import VacancyDimensionsExtractionError


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    artifact_store._artifacts.clear()  # type: ignore[attr-defined]
    session_store._sessions.clear()  # type: ignore[attr-defined]
    conversation_store._conversations.clear()  # type: ignore[attr-defined]
    cv_store._cvs.clear()  # type: ignore[attr-defined]
    reset_ai_runs()
    reset_request_traces()


def _sample_vacancy_blocks(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_blocks.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-21T10:00:00Z",
        "vacancy_blocks": {
            "work_conditions": ["Hibrido en Bogota"],
            "responsibilities": ["Liderar backlog de datos"],
            "required_requirements": [],
            "desirable_requirements": [],
            "benefits": [],
            "unclassified": [],
        },
        "warnings": [],
        "coverage_notes": [],
    }


def _sample_vacancy_dimensions(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_dimensions.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-21T10:01:00Z",
        "vacancy_dimensions": {
            "work_conditions": {
                "salary": {},
                "modality": {"value": "Hibrido", "raw_text": "Hibrido en Bogota"},
                "location": {"value": "Bogota", "raw_text": "Hibrido en Bogota"},
                "contract_type": {},
                "schedule": {},
                "availability": {},
                "travel": {},
                "legal_requirements": {},
                "relocation": {},
                "mobility_requirements": {},
            },
            "responsibilities": [],
            "required_competencies": [],
            "desirable_competencies": [],
            "benefits": [],
        },
    }


async def _collect_sse_text(streaming_response: Any) -> str:
    chunks: list[str] = []
    async for chunk in streaming_response.body_iterator:
        if isinstance(chunk, bytes):
            chunks.append(chunk.decode("utf-8"))
        else:
            chunks.append(str(chunk))
    return "".join(chunks)


def _parse_sse_events(raw: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_name = ""
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if not event_name:
            continue
        payload = json.loads("\n".join(data_lines)) if data_lines else {}
        events.append((event_name, payload))
    return events


class VacancyV2EndpointsTests(unittest.TestCase):
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

    def test_recompute_vacancy_blocks_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Engineer",
            company="Acme",
            location="Remote",
            raw_text="Vacante con requerimientos de datos.",
        )
        opportunity_id = created["opportunity_id"]
        blocks = _sample_vacancy_blocks(opportunity_id)

        with patch.object(opportunities_api, "extract_vacancy_blocks", return_value=blocks):
            response = opportunities_api.recompute_vacancy_blocks(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.vacancy_blocks_status, "draft")
        self.assertEqual(response.vacancy_blocks_artifact["contract_version"], "vacancy_blocks.v1")
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_blocks_status"], "draft")

    def test_recompute_vacancy_blocks_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Engineer",
            company="Acme",
            location="Remote",
            raw_text="Vacante con requerimientos de datos.",
        )
        opportunity_id = created["opportunity_id"]

        with patch.object(
            opportunities_api,
            "extract_vacancy_blocks",
            side_effect=VacancyBlocksExtractionError("Step 2 invalid payload"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_blocks(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 2 invalid payload", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_blocks_status"], "error")

    def test_update_rejects_invalid_vacancy_v2_status_values(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Engineer",
            company="Acme",
            location="Remote",
            raw_text="Vacante con requerimientos de datos.",
        )
        opportunity_id = created["opportunity_id"]

        with self.assertRaises(HTTPException) as invalid_blocks_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_blocks_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_blocks_status.exception.status_code, 422)
        self.assertEqual(invalid_blocks_status.exception.detail, "Invalid vacancy_blocks_status")

        with self.assertRaises(HTTPException) as invalid_dimensions_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_dimensions_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_dimensions_status.exception.status_code, 422)
        self.assertEqual(invalid_dimensions_status.exception.detail, "Invalid vacancy_dimensions_status")

    def test_recompute_vacancy_dimensions_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con condiciones y responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        blocks = _sample_vacancy_blocks(opportunity_id)
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_blocks_artifact=blocks,
            vacancy_blocks_status="approved",
        )
        assert updated is not None
        dimensions = _sample_vacancy_dimensions(opportunity_id)

        with patch.object(opportunities_api, "extract_vacancy_dimensions", return_value=dimensions):
            response = opportunities_api.recompute_vacancy_dimensions(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.vacancy_dimensions_status, "draft")
        self.assertEqual(response.vacancy_dimensions_artifact["contract_version"], "vacancy_dimensions.v1")
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_status"], "draft")

    def test_recompute_vacancy_dimensions_uses_persisted_vacancy_blocks_input(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con condiciones y responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        blocks = _sample_vacancy_blocks(opportunity_id)
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_blocks_artifact=blocks,
            vacancy_blocks_status="approved",
        )
        assert updated is not None
        dimensions = _sample_vacancy_dimensions(opportunity_id)

        with patch.object(
            opportunities_api,
            "extract_vacancy_dimensions",
            return_value=dimensions,
        ) as extract_mock:
            opportunities_api.recompute_vacancy_dimensions(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        kwargs = extract_mock.call_args.kwargs
        self.assertEqual(kwargs["vacancy_blocks_artifact"]["contract_version"], "vacancy_blocks.v1")
        self.assertEqual(kwargs["vacancy_blocks_artifact"]["vacancy_id"], opportunity_id)

    def test_recompute_vacancy_dimensions_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con condiciones y responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]

        with patch.object(
            opportunities_api,
            "extract_vacancy_dimensions",
            side_effect=VacancyDimensionsExtractionError("Step 3 requires valid Step 2"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_dimensions(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 3 requires valid Step 2", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_status"], "error")

    def test_recompute_vacancy_v2_preserves_legacy_vacancy_profile(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con condiciones y responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        legacy_profile = {"must_have": ["Python", "FastAPI"], "nice_to_have": ["AWS"]}
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_profile=legacy_profile,
            vacancy_profile_status="approved",
        )
        assert updated is not None

        blocks = _sample_vacancy_blocks(opportunity_id)
        dimensions = _sample_vacancy_dimensions(opportunity_id)
        with patch.object(opportunities_api, "extract_vacancy_blocks", return_value=blocks):
            opportunities_api.recompute_vacancy_blocks(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )
        with patch.object(opportunities_api, "extract_vacancy_dimensions", return_value=dimensions):
            opportunities_api.recompute_vacancy_dimensions(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_profile"], legacy_profile)
        self.assertEqual(stored["vacancy_profile_status"], "approved")

    def test_vacancy_blocks_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con plataformas y datos.",
        )
        opportunity_id = created["opportunity_id"]
        blocks = _sample_vacancy_blocks(opportunity_id)

        with patch.object(opportunities_api, "extract_vacancy_blocks", return_value=blocks):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_blocks_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_blocks_recompute_started", stages)
        self.assertIn("vacancy_blocks_extracting", stages)
        self.assertIn("vacancy_blocks_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(complete_payload["opportunity"]["vacancy_blocks_status"], "draft")

    def test_vacancy_blocks_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con plataformas y datos.",
        )
        opportunity_id = created["opportunity_id"]

        with patch.object(
            opportunities_api,
            "extract_vacancy_blocks",
            side_effect=VacancyBlocksExtractionError("Step 2 blocked by invalid source"),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_blocks_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn("Step 2 blocked by invalid source", str(error_payload.get("detail", "")))

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_blocks_status"], "error")

    def test_vacancy_dimensions_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con plataformas y datos.",
        )
        opportunity_id = created["opportunity_id"]
        blocks = _sample_vacancy_blocks(opportunity_id)
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_blocks_artifact=blocks,
            vacancy_blocks_status="approved",
        )
        assert updated is not None
        dimensions = _sample_vacancy_dimensions(opportunity_id)

        with patch.object(opportunities_api, "extract_vacancy_dimensions", return_value=dimensions):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_dimensions_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_dimensions_recompute_started", stages)
        self.assertIn("vacancy_dimensions_extracting", stages)
        self.assertIn("vacancy_dimensions_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(complete_payload["opportunity"]["vacancy_dimensions_status"], "draft")

    def test_vacancy_dimensions_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con plataformas y datos.",
        )
        opportunity_id = created["opportunity_id"]

        with patch.object(
            opportunities_api,
            "extract_vacancy_dimensions",
            side_effect=VacancyDimensionsExtractionError("Step 3 blocked by invalid Step 2"),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_dimensions_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn("Step 3 blocked by invalid Step 2", str(error_payload.get("detail", "")))

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_status"], "error")


if __name__ == "__main__":
    unittest.main()
