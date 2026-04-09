import asyncio
import json
import os
import unittest
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import app.api.opportunities as opportunities_api
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import artifact_store, conversation_store, cv_store, opportunity_store, person_store, session_store
from app.services.ai_run_store import (
    ACTION_INTERVIEW_BRIEF,
    get_current_ai_run,
    reset_ai_runs,
    upsert_current_ai_run,
)
from app.services.person_store import seed_persons
from app.services.request_trace_store import reset_request_traces


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    artifact_store._artifacts.clear()  # type: ignore[attr-defined]
    session_store._sessions.clear()  # type: ignore[attr-defined]
    conversation_store._conversations.clear()  # type: ignore[attr-defined]
    cv_store._cvs.clear()  # type: ignore[attr-defined]
    reset_ai_runs()
    reset_request_traces()


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


class InterviewBriefTests(unittest.TestCase):
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

    def test_interview_brief_uses_cached_result_when_not_forced(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Product Designer",
            company="Acme",
            location="Bogota",
            raw_text="Role with product discovery and UX strategy.",
        )
        opportunity_id = created["opportunity_id"]
        upsert_current_ai_run(
            person_id="p-001",
            opportunity_id=opportunity_id,
            action_key=ACTION_INTERVIEW_BRIEF,
            result_payload={
                "analysis_text": "Brief cacheado",
                "interview_warnings": ["warning 1"],
                "interview_sources": [],
                "semantic_evidence": {
                    "source": "semantic_retrieval",
                    "query": "query",
                    "top_k": 8,
                    "snippets": ["snippet 1"],
                },
            },
        )

        response = opportunities_api.interview_brief_action(
            person_id="p-001",
            opportunity_id=opportunity_id,
            payload=opportunities_api.ActionRequest(force_recompute=False),
            _=self.session,
            settings=get_settings(),
        )
        self.assertTrue(response.served_from_cache)
        self.assertEqual(response.analysis_text, "Brief cacheado")
        self.assertEqual(response.semantic_evidence.top_k, 8)
        self.assertEqual(response.assistant_message_id, "")

    def test_interview_brief_generates_run_and_appends_chat_message(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="QA Engineer",
            company="Acme",
            location="Remote",
            raw_text="Quality automation and testing role.",
        )
        opportunity_id = created["opportunity_id"]

        with patch.object(
            opportunities_api,
            "interview_brief",
            return_value={
                "analysis_text": "Brief generado",
                "interview_warnings": ["warning 1"],
                "interview_sources": [],
                "semantic_evidence": {
                    "source": "semantic_retrieval",
                    "query": "query",
                    "top_k": 8,
                    "snippets": ["snippet 1"],
                },
            },
        ):
            response = opportunities_api.interview_brief_action(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.ActionRequest(force_recompute=True),
                _=self.session,
                settings=get_settings(),
            )

        self.assertFalse(response.served_from_cache)
        self.assertEqual(response.analysis_text, "Brief generado")
        self.assertTrue(response.assistant_message_id)

        run = get_current_ai_run("p-001", opportunity_id, ACTION_INTERVIEW_BRIEF)
        self.assertIsNotNone(run)
        if run is not None:
            self.assertEqual(run["result_payload"]["analysis_text"], "Brief generado")

        conversation = conversation_store.get_or_create_conversation("p-001")
        self.assertEqual(conversation["messages"][-1]["role"], "assistant")
        self.assertEqual(conversation["messages"][-1]["content"], "Brief generado")

    def test_interview_brief_dedups_same_last_assistant_message(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="QA Engineer",
            company="Acme",
            location="Remote",
            raw_text="Quality automation and testing role.",
        )
        opportunity_id = created["opportunity_id"]
        conversation_store.append_message("p-001", "assistant", "Brief generado")

        with patch.object(
            opportunities_api,
            "interview_brief",
            return_value={
                "analysis_text": "Brief generado",
                "interview_warnings": [],
                "interview_sources": [],
                "semantic_evidence": {
                    "source": "semantic_retrieval",
                    "query": "query",
                    "top_k": 8,
                    "snippets": ["snippet 1"],
                },
            },
        ):
            response = opportunities_api.interview_brief_action(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.ActionRequest(force_recompute=True),
                _=self.session,
                settings=get_settings(),
            )

        conversation = conversation_store.get_or_create_conversation("p-001")
        assistant_messages = [m for m in conversation["messages"] if m["role"] == "assistant"]
        self.assertEqual(len(assistant_messages), 1)
        self.assertEqual(assistant_messages[0]["content"], "Brief generado")
        self.assertEqual(response.assistant_message_id, assistant_messages[0]["message_id"])

    def test_interview_brief_stream_emits_and_persists(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Analyst",
            company="Acme",
            location="Hybrid",
            raw_text="Data analysis role.",
        )
        opportunity_id = created["opportunity_id"]
        with patch.object(
            opportunities_api,
            "stream_interview_brief_text",
            return_value=(
                {
                    "source": "semantic_retrieval",
                    "query": "query",
                    "top_k": 8,
                    "snippets": ["snippet 1"],
                },
                [],
                [],
                iter(["Brief ", "stream"]),
            ),
        ):
            response = asyncio.run(
                opportunities_api.interview_brief_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    payload=opportunities_api.ActionRequest(force_recompute=True),
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("message_start", names)
        self.assertIn("message_delta", names)
        self.assertIn("message_complete", names)

        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(complete_payload["analysis_text"], "Brief stream")
        self.assertFalse(bool(complete_payload["served_from_cache"]))

        run = get_current_ai_run("p-001", opportunity_id, ACTION_INTERVIEW_BRIEF)
        self.assertIsNotNone(run)
        if run is not None:
            self.assertEqual(run["result_payload"]["analysis_text"], "Brief stream")


if __name__ == "__main__":
    unittest.main()
