import os
import unittest
from datetime import UTC, datetime, timedelta

import app.api.opportunities as opportunities_api
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import (
    artifact_store,
    conversation_store,
    cv_store,
    opportunity_store,
    person_store,
    session_store,
)
from app.services.ai_run_store import reset_ai_runs
from app.services.person_store import seed_persons
from app.services.request_trace_store import reset_request_traces
from app.services.vacancy_v2_consistency_gate import build_vacancy_v2_consistency_report


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    artifact_store._artifacts.clear()  # type: ignore[attr-defined]
    session_store._sessions.clear()  # type: ignore[attr-defined]
    conversation_store._conversations.clear()  # type: ignore[attr-defined]
    cv_store._cvs.clear()  # type: ignore[attr-defined]
    reset_ai_runs()
    reset_request_traces()


def _blocks_artifact(*, work_conditions: list[str], benefits: list[str]) -> dict:
    return {
        "contract_version": "vacancy_blocks.v1",
        "vacancy_id": "vacancy-1",
        "generated_at": "2026-04-21T10:00:00Z",
        "vacancy_blocks": {
            "work_conditions": work_conditions,
            "responsibilities": [],
            "required_requirements": [],
            "desirable_requirements": [],
            "benefits": benefits,
            "unclassified": [],
        },
        "warnings": [],
        "coverage_notes": [],
    }


def _dimensions_artifact(*, salary_text: str = "") -> dict:
    return {
        "contract_version": "vacancy_dimensions.v1",
        "vacancy_id": "vacancy-1",
        "generated_at": "2026-04-21T10:01:00Z",
        "vacancy_dimensions": {
            "work_conditions": {
                "salary": {
                    "min": None,
                    "max": None,
                    "currency": "",
                    "period": "",
                    "text": salary_text,
                }
            },
            "responsibilities": [],
            "required_competencies": [],
            "desirable_competencies": [],
            "benefits": [],
        },
    }


class VacancyV2ConsistencyGateTests(unittest.TestCase):
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

    def test_report_counts_salary_transfer_and_misclassification(self) -> None:
        ok = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Engineer",
            company="Acme",
            location="Bogota",
            raw_text="Texto 1",
        )
        missing = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Bogota",
            raw_text="Texto 2",
        )
        wrong_bucket = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="ML Engineer",
            company="Acme",
            location="Bogota",
            raw_text="Texto 3",
        )

        opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=ok["opportunity_id"],
            status=None,
            notes=None,
            vacancy_blocks_artifact=_blocks_artifact(
                work_conditions=["Salario: COP 20M"],
                benefits=[],
            ),
            vacancy_blocks_status="approved",
            vacancy_dimensions_artifact=_dimensions_artifact(salary_text="COP 20M"),
            vacancy_dimensions_status="approved",
        )
        opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=missing["opportunity_id"],
            status=None,
            notes=None,
            vacancy_blocks_artifact=_blocks_artifact(
                work_conditions=["Compensation up to USD 5k"],
                benefits=[],
            ),
            vacancy_blocks_status="approved",
            vacancy_dimensions_artifact=_dimensions_artifact(salary_text=""),
            vacancy_dimensions_status="draft",
        )
        opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=wrong_bucket["opportunity_id"],
            status=None,
            notes=None,
            vacancy_blocks_artifact=_blocks_artifact(
                work_conditions=[],
                benefits=["Salario emocional y bono de 2M"],
            ),
            vacancy_blocks_status="draft",
            vacancy_dimensions_artifact=_dimensions_artifact(salary_text=""),
            vacancy_dimensions_status="draft",
        )

        report = build_vacancy_v2_consistency_report(
            opportunity_store.list_opportunities("p-001"),
            issue_sample_limit=10,
        )
        self.assertEqual(report["total_opportunities"], 3)
        self.assertEqual(report["opportunities_with_step2"], 3)
        self.assertEqual(report["opportunities_with_step3"], 3)
        self.assertEqual(report["salary_transfer_eligible"], 2)
        self.assertEqual(report["salary_transfer_ok"], 1)
        self.assertEqual(report["salary_transfer_missing"], 1)
        self.assertEqual(report["salary_transfer_rate"], 0.5)
        self.assertEqual(report["salary_signal_in_step2_benefits"], 1)
        self.assertEqual(report["salary_signal_in_step2_benefits_rate"], 0.3333)
        self.assertEqual(len(report["issue_samples"]), 2)

    def test_api_endpoint_applies_sample_limit(self) -> None:
        first = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Role 1",
            company="Acme",
            location="Bogota",
            raw_text="Texto A",
        )
        second = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Role 2",
            company="Acme",
            location="Bogota",
            raw_text="Texto B",
        )

        for item in [first, second]:
            opportunity_store.update_opportunity(
                person_id="p-001",
                opportunity_id=item["opportunity_id"],
                status=None,
                notes=None,
                vacancy_blocks_artifact=_blocks_artifact(
                    work_conditions=["Salario hasta 10M"],
                    benefits=[],
                ),
                vacancy_blocks_status="approved",
                vacancy_dimensions_artifact=_dimensions_artifact(salary_text=""),
                vacancy_dimensions_status="draft",
            )

        response = opportunities_api.get_vacancy_v2_consistency_report(
            person_id="p-001",
            sample_limit=1,
            _=self.session,
        )
        self.assertEqual(response.person_id, "p-001")
        self.assertEqual(response.salary_transfer_eligible, 2)
        self.assertEqual(response.salary_transfer_missing, 2)
        self.assertEqual(len(response.issue_samples), 1)


if __name__ == "__main__":
    unittest.main()
