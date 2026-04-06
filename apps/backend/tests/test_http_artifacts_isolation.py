import asyncio
import os
import unittest
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
import httpx

from app.core.security import SessionData, require_operator_session
from app.core.settings import get_settings
from app.api.routes import router as api_router
from app.services import artifact_store, conversation_store, cv_store, opportunity_store, person_store, session_store
from app.services.ai_run_store import reset_ai_runs
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


@unittest.skip("ASGI client harness hangs in this environment; covered by handler-level isolation tests.")
class HttpArtifactsIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PERSISTENCE_BACKEND"] = "memory"
        get_settings.cache_clear()
        _clear_in_memory_state()
        seed_persons()
        self.app = FastAPI()
        self.app.include_router(api_router, prefix="/api")
        self.app.dependency_overrides[require_operator_session] = lambda: SessionData(
            username="tutor",
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        get_settings.cache_clear()
        _clear_in_memory_state()

    def test_artifacts_endpoint_is_isolated_by_person_id_with_http_router(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            raw_text="FastAPI role.",
        )
        opportunity_id = created["opportunity_id"]
        artifact_store.upsert_current_artifact(
            person_id="p-001",
            opportunity_id=opportunity_id,
            artifact_type="cover_letter",
            content="Carta para p-001",
        )
        artifact_store.upsert_current_artifact(
            person_id="p-001",
            opportunity_id=opportunity_id,
            artifact_type="experience_summary",
            content="Resumen para p-001",
        )

        async def run_http_checks() -> tuple[int, dict, int, dict]:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                ok = await client.get(
                    f"/api/persons/p-001/opportunities/{opportunity_id}/artifacts",
                )
                cross = await client.get(
                    f"/api/persons/p-002/opportunities/{opportunity_id}/artifacts",
                )
                return ok.status_code, ok.json(), cross.status_code, cross.json()

        ok_status, ok_payload, cross_status, cross_payload = asyncio.run(run_http_checks())
        self.assertEqual(ok_status, 200)
        self.assertEqual(len(ok_payload["items"]), 2)
        self.assertEqual(cross_status, 404)
        self.assertEqual(cross_payload.get("detail"), "Opportunity not found")


if __name__ == "__main__":
    unittest.main()
