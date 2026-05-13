import os
import unittest
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

import app.api.opportunities as opportunities_api
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import opportunity_store, person_store
from app.services.alignment_runtime_telemetry_store import reset_alignment_runtime_runs
from app.services.person_store import seed_persons


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    reset_alignment_runtime_runs()


class AlignmentRuntimeTelemetryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PERSISTENCE_BACKEND"] = "memory"
        get_settings.cache_clear()
        _clear_in_memory_state()
        seed_persons()
        self.session = SessionData(
            username="tutor",
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )
        self.person_id = "p-001"
        created = opportunity_store.create_opportunity(
            person_id=self.person_id,
            source_type="manual_text",
            source_provider="manual",
            source_url="",
            source_label="",
            title="Senior Backend Engineer",
            company="Acme",
            location="Bogotá",
            snapshot_raw_text="Vacante con responsabilidades backend y python.",
            snapshot_payload={},
        )
        self.opportunity_id = created["opportunity_id"]

    def tearDown(self) -> None:
        get_settings.cache_clear()
        _clear_in_memory_state()

    def test_alignment_runtime_run_step_and_summary_persist(self) -> None:
        started = opportunities_api.start_alignment_runtime_run(
            self.person_id, self.opportunity_id, self.session
        )
        self.assertTrue(started.run_id.startswith("ar-"))

        step_response = opportunities_api.upsert_alignment_runtime_step(
            self.person_id,
            self.opportunity_id,
            started.run_id,
            opportunities_api.AlignmentRuntimeStepTelemetryRequest(
                step_key="S5",
                status="done",
                started_at="2026-05-13T00:00:00Z",
                ended_at="2026-05-13T00:00:01Z",
                duration_ms=1000,
                attempt_index=1,
                attempt_count=1,
                provider=None,
                model=None,
                input_size_hints={"criteria_count": 8},
                output_size_hints={"hits": 32},
                params_effective={"top_k_effective": 6},
            ),
            self.session,
        )
        self.assertEqual(step_response.steps[0]["step_key"], "S5")
        self.assertEqual(step_response.steps[0]["duration_ms"], 1000)

        completed = opportunities_api.finalize_alignment_runtime_run(
            self.person_id,
            self.opportunity_id,
            started.run_id,
            opportunities_api.AlignmentRuntimeRunCompleteRequest(
                status="done",
                total_duration_ms=4800,
                slowest_steps=[{"step_key": "S6.5", "duration_ms": 1700}],
                total_retries=1,
                llm_calls_count=2,
                retrieval_summary={
                    "criteria_count": 8,
                    "queries_per_item_effective": 4,
                    "top_k_effective": 6,
                    "total_hits_retrieved": 32,
                },
                warnings=[],
            ),
            self.session,
        )
        self.assertEqual(completed.status, "done")
        self.assertEqual(completed.summary["total_duration_ms"], 4800)
        self.assertEqual(completed.summary["total_retries"], 1)

        listed = opportunities_api.get_alignment_runtime_runs(
            self.person_id, self.opportunity_id, 2, self.session
        )
        self.assertEqual(len(listed.items), 1)
        self.assertEqual(listed.items[0].run_id, started.run_id)
        self.assertEqual(listed.items[0].summary["llm_calls_count"], 2)

    def test_alignment_runtime_run_list_returns_latest_previous(self) -> None:
        first = opportunities_api.start_alignment_runtime_run(
            self.person_id, self.opportunity_id, self.session
        )
        opportunities_api.finalize_alignment_runtime_run(
            self.person_id,
            self.opportunity_id,
            first.run_id,
            opportunities_api.AlignmentRuntimeRunCompleteRequest(
                status="done",
                total_duration_ms=1000,
                slowest_steps=[],
                total_retries=0,
                llm_calls_count=0,
                retrieval_summary={},
                warnings=[],
            ),
            self.session,
        )
        second = opportunities_api.start_alignment_runtime_run(
            self.person_id, self.opportunity_id, self.session
        )
        opportunities_api.finalize_alignment_runtime_run(
            self.person_id,
            self.opportunity_id,
            second.run_id,
            opportunities_api.AlignmentRuntimeRunCompleteRequest(
                status="done",
                total_duration_ms=1200,
                slowest_steps=[],
                total_retries=0,
                llm_calls_count=0,
                retrieval_summary={},
                warnings=[],
            ),
            self.session,
        )

        listed = opportunities_api.get_alignment_runtime_runs(
            self.person_id, self.opportunity_id, 2, self.session
        )
        self.assertEqual(len(listed.items), 2)
        self.assertEqual(listed.items[0].run_id, second.run_id)
        self.assertEqual(listed.items[1].run_id, first.run_id)

    def test_upsert_step_unknown_run_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as error:
            opportunities_api.upsert_alignment_runtime_step(
                self.person_id,
                self.opportunity_id,
                "ar-missing",
                opportunities_api.AlignmentRuntimeStepTelemetryRequest(
                    step_key="S5",
                    status="running",
                ),
                self.session,
            )
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
