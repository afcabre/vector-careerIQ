import asyncio
import json
import os
import unittest
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import app.api.chat as chat_api
import app.api.opportunities as opportunities_api
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import artifact_store, conversation_store, cv_store, opportunity_store, person_store, session_store
from app.services.conversation_store import get_or_create_conversation
from app.services.person_store import seed_persons


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    artifact_store._artifacts.clear()  # type: ignore[attr-defined]
    session_store._sessions.clear()  # type: ignore[attr-defined]
    conversation_store._conversations.clear()  # type: ignore[attr-defined]
    cv_store._cvs.clear()  # type: ignore[attr-defined]


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


class SseFlowsTests(unittest.TestCase):
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

    def test_chat_stream_emits_contract_and_persists_message(self) -> None:
        with patch.object(chat_api, "stream_reply", return_value=iter(["Hola ", "mundo"])):
            response = asyncio.run(
                chat_api.stream_message(
                    person_id="p-001",
                    payload=chat_api.SendMessageRequest(message="Prueba stream"),
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

        deltas = [payload["delta"] for name, payload in events if name == "message_delta"]
        self.assertEqual("".join(deltas), "Hola mundo")

        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(complete_payload["person_id"], "p-001")

        conversation = get_or_create_conversation("p-001")
        self.assertEqual(conversation["messages"][-1]["role"], "assistant")
        self.assertEqual(conversation["messages"][-1]["content"], "Hola mundo")

    def test_analyze_stream_emits_payload_and_updates_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Analyst",
            company="DataCo",
            location="Hybrid",
            raw_text="SQL role",
        )
        opportunity_id = created["opportunity_id"]
        moved = opportunity_store.update_opportunity("p-001", opportunity_id, "analyzed", None)
        assert moved is not None
        moved = opportunity_store.update_opportunity("p-001", opportunity_id, "prioritized", None)
        assert moved is not None

        bundle = {
            "system_prompt": "sys",
            "user_prompt": "usr",
            "cultural_confidence": "medium",
            "cultural_warnings": ["evidencia debil"],
            "cultural_signals": [],
            "semantic_evidence": {
                "source": "fallback_preview",
                "query": "query",
                "top_k": 24,
                "snippets": [],
            },
        }
        with patch.object(
            opportunities_api,
            "stream_analyze_text",
            return_value=(bundle, iter(["Ana", "lisis"])),
        ):
            response = asyncio.run(
                opportunities_api.analyze_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("message_start", names)
        self.assertIn("tool_status", names)
        self.assertIn("message_delta", names)
        self.assertIn("message_complete", names)

        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(complete_payload["analysis_text"], "Analisis")
        self.assertEqual(complete_payload["opportunity"]["status"], "analyzed")
        self.assertEqual(complete_payload["semantic_evidence"]["top_k"], 24)

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["status"], "analyzed")

    def test_prepare_stream_emits_channels_and_persists_artifacts(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            raw_text="FastAPI role",
        )
        opportunity_id = created["opportunity_id"]
        moved = opportunity_store.update_opportunity("p-001", opportunity_id, "analyzed", None)
        assert moved is not None
        moved = opportunity_store.update_opportunity("p-001", opportunity_id, "prioritized", None)
        assert moved is not None

        bundle = {
            "system_prompt": "sys",
            "guidance_prompt": "g",
            "cover_letter_prompt": "c",
            "experience_summary_prompt": "s",
            "semantic_evidence": {
                "source": "semantic_retrieval",
                "query": "query",
                "top_k": 24,
                "snippets": ["s1"],
            },
        }
        with patch.object(
            opportunities_api,
            "stream_prepare_sections",
            return_value=(
                bundle,
                iter(["Gu", "ia"]),
                iter(["Car", "ta"]),
                iter(["Res", "umen"]),
            ),
        ):
            response = asyncio.run(
                opportunities_api.prepare_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        delta_channels = [payload["channel"] for name, payload in events if name == "message_delta"]
        self.assertIn("guidance_text", delta_channels)
        self.assertIn("cover_letter", delta_channels)
        self.assertIn("experience_summary", delta_channels)

        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(complete_payload["guidance_text"], "Guia")
        self.assertEqual(len(complete_payload["artifacts"]), 2)
        self.assertEqual(complete_payload["opportunity"]["status"], "application_prepared")

        current_items = artifact_store.list_current_artifacts("p-001", opportunity_id)
        by_type = {item["artifact_type"]: item["content"] for item in current_items}
        self.assertEqual(by_type["cover_letter"], "Carta")
        self.assertEqual(by_type["experience_summary"], "Resumen")

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["status"], "application_prepared")


if __name__ == "__main__":
    unittest.main()
