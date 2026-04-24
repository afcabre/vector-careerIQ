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
from app.services.vacancy_dimensions_enrichment_service import VacancyDimensionsEnrichmentError
from app.services.vacancy_alignment_summary_service import VacancyAlignmentSummaryBuildError
from app.services.vacancy_evidence_analysis_service import VacancyEvidenceAnalysisBuildError
from app.services.vacancy_retrieval_evidence_service import VacancyRetrievalEvidenceBuildError
from app.services.vacancy_retrieval_queries_service import VacancyRetrievalQueriesExtractionError
from app.services.vacancy_salary_service import VacancySalaryNormalizationError


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
        "contract_version": "vacancy_dimensions.v2",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-21T10:01:00Z",
        "vacancy_dimensions": {
            "work_conditions": {
                "salary": {"raw_text": ""},
                "modality": {"value": "Hibrido", "raw_text": "Hibrido en Bogota"},
                "location": {"places": ["Bogota"], "raw_text": "Hibrido en Bogota"},
                "contract_type": {"value": "", "raw_text": ""},
                "other_conditions": [],
            },
            "responsibilities": [],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
        },
    }


def _sample_vacancy_salary(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_salary_normalization.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-21T10:02:00Z",
        "salary": {
            "min": 12000000,
            "max": 18000000,
            "currency": "COP",
            "period": "mensual",
            "raw_text": "Salario COP 12M a 18M mensual",
        },
    }


def _sample_vacancy_dimensions_enriched(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_dimensions_enriched.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-21T10:03:00Z",
        "vacancy_dimensions": {
            "work_conditions": {
                "salary": {"raw_text": "Salario COP 12M a 18M mensual"},
                "modality": {"value": "Hibrido", "raw_text": "Hibrido en Bogota"},
                "location": {"places": ["Bogota"], "raw_text": "Bogota"},
                "contract_type": {"value": "", "raw_text": ""},
                "other_conditions": [],
            },
            "responsibilities": [
                {
                    "raw_text": "Liderar backlog de datos",
                    "item_id": "resp_1234567890",
                    "item_index": 0,
                    "group_code": "resp",
                }
            ],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
        },
    }


def _sample_vacancy_retrieval_queries(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_retrieval_queries.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-24T10:35:00Z",
        "queries": {
            "responsibilities": [
                {
                    "item_id": "resp_1234567890",
                    "item_index": 0,
                    "group_code": "resp",
                    "raw_text": "Liderar backlog de datos",
                    "queries": ["liderazgo de backlog, coordinacion de roadmap de datos"],
                }
            ],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": {
                "salary": [],
                "modality": [],
                "location": [],
                "contract_type": [],
                "other_conditions": [],
            },
        },
    }


def _sample_vacancy_retrieval_evidence(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_retrieval_evidence.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-24T10:36:00Z",
        "evidence": {
            "responsibilities": [
                {
                    "item_id": "resp_1234567890",
                    "item_index": 0,
                    "group_code": "resp",
                    "raw_text": "Liderar backlog de datos",
                    "matches": [
                        {
                            "query_index": 0,
                            "query_text": "liderazgo de backlog, coordinacion de roadmap de datos",
                            "score": 0.84,
                            "snippet": "Lidere backlog y priorizacion trimestral",
                            "source_ref": "cv-chunk-1",
                        }
                    ],
                }
            ],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": {
                "salary": [],
                "modality": [],
                "location": [],
                "contract_type": [],
                "other_conditions": [],
            },
        },
    }


def _sample_vacancy_evidence_analysis(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_evidence_analysis.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-24T10:37:00Z",
        "thresholds": {
            "strong_min": 0.75,
            "useful_min": 0.45,
            "review_min": 0.30,
        },
        "analysis": {
            "responsibilities": [
                {
                    "item_id": "resp_1234567890",
                    "item_index": 0,
                    "group_code": "resp",
                    "raw_text": "Liderar backlog de datos",
                    "item_status": "strong_evidence",
                    "best_score": 0.84,
                    "raw_match_count": 1,
                    "accepted_match_count": 1,
                    "discarded_match_count": 0,
                    "distinct_query_hits": 1,
                    "best_evidence": [
                        {
                            "source_ref": "cv-chunk-1",
                            "snippet": "Lidere backlog y priorizacion trimestral",
                            "best_score": 0.84,
                            "query_texts": [
                                "liderazgo de backlog, coordinacion de roadmap de datos"
                            ],
                            "query_indexes": [0],
                            "section": "",
                            "block_type": "",
                            "block_title": "",
                            "raw_match_count": 1,
                        }
                    ],
                    "accepted_matches": [],
                    "discarded_matches": [],
                }
            ],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": {
                "salary": [],
                "modality": [],
                "location": [],
                "contract_type": [],
                "other_conditions": [],
            },
        },
    }


def _sample_vacancy_alignment_summary(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_alignment_summary.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-24T10:38:00Z",
        "source_artifact_version": "vacancy_evidence_analysis.v1",
        "thresholds": {
            "strong_min": 0.75,
            "useful_min": 0.45,
            "review_min": 0.30,
        },
        "summary": {
            "overall": {
                "total_items": 1,
                "strong_evidence_count": 1,
                "useful_evidence_count": 0,
                "review_count": 0,
                "no_evidence_count": 0,
            },
            "groups": {
                "responsibilities": {
                    "total_items": 1,
                    "strong_evidence_count": 1,
                    "useful_evidence_count": 0,
                    "review_count": 0,
                    "no_evidence_count": 0,
                },
                "required_criteria": {
                    "total_items": 0,
                    "strong_evidence_count": 0,
                    "useful_evidence_count": 0,
                    "review_count": 0,
                    "no_evidence_count": 0,
                },
                "desirable_criteria": {
                    "total_items": 0,
                    "strong_evidence_count": 0,
                    "useful_evidence_count": 0,
                    "review_count": 0,
                    "no_evidence_count": 0,
                },
            },
            "strengths": [
                {
                    "group": "responsibilities",
                    "item_id": "resp_1234567890",
                    "item_index": 0,
                    "raw_text": "Liderar backlog de datos",
                    "item_status": "strong_evidence",
                    "best_score": 0.84,
                }
            ],
            "gaps": [],
            "review_items": [],
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

        with self.assertRaises(HTTPException) as invalid_salary_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_salary_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_salary_status.exception.status_code, 422)
        self.assertEqual(invalid_salary_status.exception.detail, "Invalid vacancy_salary_status")

        with self.assertRaises(HTTPException) as invalid_enriched_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_dimensions_enriched_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_enriched_status.exception.status_code, 422)
        self.assertEqual(
            invalid_enriched_status.exception.detail,
            "Invalid vacancy_dimensions_enriched_status",
        )

        with self.assertRaises(HTTPException) as invalid_queries_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_retrieval_queries_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_queries_status.exception.status_code, 422)
        self.assertEqual(
            invalid_queries_status.exception.detail,
            "Invalid vacancy_retrieval_queries_status",
        )

        with self.assertRaises(HTTPException) as invalid_evidence_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_retrieval_evidence_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_evidence_status.exception.status_code, 422)
        self.assertEqual(
            invalid_evidence_status.exception.detail,
            "Invalid vacancy_retrieval_evidence_status",
        )

        with self.assertRaises(HTTPException) as invalid_analysis_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_evidence_analysis_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_analysis_status.exception.status_code, 422)
        self.assertEqual(
            invalid_analysis_status.exception.detail,
            "Invalid vacancy_evidence_analysis_status",
        )

        with self.assertRaises(HTTPException) as invalid_summary_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_alignment_summary_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_summary_status.exception.status_code, 422)
        self.assertEqual(
            invalid_summary_status.exception.detail,
            "Invalid vacancy_alignment_summary_status",
        )

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
        self.assertEqual(response.vacancy_dimensions_artifact["contract_version"], "vacancy_dimensions.v2")
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_status"], "draft")

    def test_recompute_vacancy_salary_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con salario.",
        )
        opportunity_id = created["opportunity_id"]
        dimensions = _sample_vacancy_dimensions(opportunity_id)
        dimensions["vacancy_dimensions"]["work_conditions"]["salary"]["raw_text"] = "Salario COP 12M a 18M mensual"
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=dimensions,
            vacancy_dimensions_status="approved",
        )
        assert updated is not None
        salary_artifact = _sample_vacancy_salary(opportunity_id)

        with patch.object(
            opportunities_api,
            "extract_vacancy_salary_normalization",
            return_value=salary_artifact,
        ):
            response = opportunities_api.recompute_vacancy_salary(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.vacancy_salary_status, "draft")
        self.assertEqual(
            response.vacancy_salary_artifact["contract_version"],
            "vacancy_salary_normalization.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_salary_status"], "draft")

    def test_recompute_vacancy_salary_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con salario.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "extract_vacancy_salary_normalization",
            side_effect=VacancySalaryNormalizationError("Step 3.1 requires salary raw text"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_salary(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 3.1 requires salary raw text", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_salary_status"], "error")

    def test_recompute_vacancy_dimensions_enriched_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None
        enriched_artifact = _sample_vacancy_dimensions_enriched(opportunity_id)

        with patch.object(
            opportunities_api,
            "enrich_vacancy_dimensions_artifact",
            return_value=enriched_artifact,
        ):
            response = opportunities_api.recompute_vacancy_dimensions_enriched(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
            )

        self.assertEqual(response.vacancy_dimensions_enriched_status, "draft")
        self.assertEqual(
            response.vacancy_dimensions_enriched_artifact["contract_version"],
            "vacancy_dimensions_enriched.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_enriched_status"], "draft")

    def test_recompute_vacancy_dimensions_enriched_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "enrich_vacancy_dimensions_artifact",
            side_effect=VacancyDimensionsEnrichmentError("Step 3.9 produced no enrichable atomic items"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_dimensions_enriched(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 3.9 produced no enrichable atomic items", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_enriched_status"], "error")

    def test_recompute_vacancy_retrieval_queries_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_artifact=_sample_vacancy_dimensions_enriched(opportunity_id),
            vacancy_dimensions_enriched_status="approved",
            vacancy_salary_artifact=_sample_vacancy_salary(opportunity_id),
            vacancy_salary_status="approved",
        )
        assert updated is not None
        queries_artifact = _sample_vacancy_retrieval_queries(opportunity_id)

        with patch.object(
            opportunities_api,
            "extract_vacancy_retrieval_queries",
            return_value=queries_artifact,
        ):
            response = opportunities_api.recompute_vacancy_retrieval_queries(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.vacancy_retrieval_queries_status, "draft")
        self.assertEqual(
            response.vacancy_retrieval_queries_artifact["contract_version"],
            "vacancy_retrieval_queries.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_retrieval_queries_status"], "draft")

    def test_recompute_vacancy_retrieval_queries_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_artifact=_sample_vacancy_dimensions_enriched(opportunity_id),
            vacancy_dimensions_enriched_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "extract_vacancy_retrieval_queries",
            side_effect=VacancyRetrievalQueriesExtractionError("Step 4 requires a valid vacancy_dimensions_enriched.v1 artifact."),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_retrieval_queries(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 4 requires a valid vacancy_dimensions_enriched.v1 artifact.", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_retrieval_queries_status"], "error")

    def test_recompute_vacancy_retrieval_evidence_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_queries_artifact=_sample_vacancy_retrieval_queries(opportunity_id),
            vacancy_retrieval_queries_status="approved",
        )
        assert updated is not None
        evidence_artifact = _sample_vacancy_retrieval_evidence(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_retrieval_evidence",
            return_value=evidence_artifact,
        ):
            response = opportunities_api.recompute_vacancy_retrieval_evidence(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.vacancy_retrieval_evidence_status, "draft")
        self.assertEqual(
            response.vacancy_retrieval_evidence_artifact["contract_version"],
            "vacancy_retrieval_evidence.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_retrieval_evidence_status"], "draft")

    def test_recompute_vacancy_retrieval_evidence_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_queries_artifact=_sample_vacancy_retrieval_queries(opportunity_id),
            vacancy_retrieval_queries_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_retrieval_evidence",
            side_effect=VacancyRetrievalEvidenceBuildError("Step 5 requires an indexed active CV before retrieval can run."),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_retrieval_evidence(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 5 requires an indexed active CV before retrieval can run.", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_retrieval_evidence_status"], "error")

    def test_recompute_vacancy_evidence_analysis_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con evidencia de retrieval.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_evidence_artifact=_sample_vacancy_retrieval_evidence(opportunity_id),
            vacancy_retrieval_evidence_status="approved",
        )
        assert updated is not None
        analysis_artifact = _sample_vacancy_evidence_analysis(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_evidence_analysis",
            return_value=analysis_artifact,
        ):
            response = opportunities_api.recompute_vacancy_evidence_analysis(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
            )

        self.assertEqual(response.vacancy_evidence_analysis_status, "draft")
        self.assertEqual(
            response.vacancy_evidence_analysis_artifact["contract_version"],
            "vacancy_evidence_analysis.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_evidence_analysis_status"], "draft")

    def test_recompute_vacancy_evidence_analysis_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con evidencia de retrieval.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_evidence_artifact=_sample_vacancy_retrieval_evidence(opportunity_id),
            vacancy_retrieval_evidence_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_evidence_analysis",
            side_effect=VacancyEvidenceAnalysisBuildError("Step 6 requires at least one retrieval match in Step 5 evidence."),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_evidence_analysis(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 6 requires at least one retrieval match in Step 5 evidence.", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_evidence_analysis_status"], "error")

    def test_recompute_vacancy_alignment_summary_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con resumen de alineacion.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
        )
        assert updated is not None
        summary_artifact = _sample_vacancy_alignment_summary(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_alignment_summary",
            return_value=summary_artifact,
        ):
            response = opportunities_api.recompute_vacancy_alignment_summary(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
            )

        self.assertEqual(response.vacancy_alignment_summary_status, "draft")
        self.assertEqual(
            response.vacancy_alignment_summary_artifact["contract_version"],
            "vacancy_alignment_summary.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_summary_status"], "draft")

    def test_recompute_vacancy_alignment_summary_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con resumen de alineacion.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_alignment_summary",
            side_effect=VacancyAlignmentSummaryBuildError("Step 7 requires a valid vacancy_evidence_analysis.v1 artifact."),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_alignment_summary(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 7 requires a valid vacancy_evidence_analysis.v1 artifact.", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_summary_status"], "error")

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

    def test_vacancy_salary_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con salario.",
        )
        opportunity_id = created["opportunity_id"]
        dimensions = _sample_vacancy_dimensions(opportunity_id)
        dimensions["vacancy_dimensions"]["work_conditions"]["salary"]["raw_text"] = "Salario COP 12M a 18M mensual"
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=dimensions,
            vacancy_dimensions_status="approved",
        )
        assert updated is not None
        salary_artifact = _sample_vacancy_salary(opportunity_id)

        with patch.object(opportunities_api, "extract_vacancy_salary_normalization", return_value=salary_artifact):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_salary_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_salary_recompute_started", stages)
        self.assertIn("vacancy_salary_extracting", stages)
        self.assertIn("vacancy_salary_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(complete_payload["vacancy_salary_status"], "draft")

    def test_vacancy_salary_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con salario.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "extract_vacancy_salary_normalization",
            side_effect=VacancySalaryNormalizationError("Step 3.1 requires salary raw text"),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_salary_stream(
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
        self.assertIn("Step 3.1 requires salary raw text", str(error_payload.get("detail", "")))

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_salary_status"], "error")

    def test_vacancy_dimensions_enriched_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None
        enriched_artifact = _sample_vacancy_dimensions_enriched(opportunity_id)

        with patch.object(opportunities_api, "enrich_vacancy_dimensions_artifact", return_value=enriched_artifact):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_dimensions_enriched_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_dimensions_enriched_recompute_started", stages)
        self.assertIn("vacancy_dimensions_enriched_building", stages)
        self.assertIn("vacancy_dimensions_enriched_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(complete_payload["vacancy_dimensions_enriched_status"], "draft")

    def test_vacancy_dimensions_enriched_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "enrich_vacancy_dimensions_artifact",
            side_effect=VacancyDimensionsEnrichmentError("Step 3.9 produced no enrichable atomic items"),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_dimensions_enriched_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn("Step 3.9 produced no enrichable atomic items", str(error_payload.get("detail", "")))

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_enriched_status"], "error")

    def test_vacancy_retrieval_queries_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_artifact=_sample_vacancy_dimensions_enriched(opportunity_id),
            vacancy_dimensions_enriched_status="approved",
            vacancy_salary_artifact=_sample_vacancy_salary(opportunity_id),
            vacancy_salary_status="approved",
        )
        assert updated is not None
        queries_artifact = _sample_vacancy_retrieval_queries(opportunity_id)

        with patch.object(
            opportunities_api,
            "extract_vacancy_retrieval_queries",
            return_value=queries_artifact,
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_retrieval_queries_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_retrieval_queries_recompute_started", stages)
        self.assertIn("vacancy_retrieval_queries_extracting", stages)
        self.assertIn("vacancy_retrieval_queries_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_retrieval_queries_status"],
            "draft",
        )

    def test_vacancy_retrieval_queries_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_artifact=_sample_vacancy_dimensions_enriched(opportunity_id),
            vacancy_dimensions_enriched_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "extract_vacancy_retrieval_queries",
            side_effect=VacancyRetrievalQueriesExtractionError("Step 4 requires a valid vacancy_dimensions_enriched.v1 artifact."),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_retrieval_queries_stream(
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
        self.assertIn(
            "Step 4 requires a valid vacancy_dimensions_enriched.v1 artifact.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_retrieval_queries_status"], "error")

    def test_vacancy_retrieval_evidence_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_queries_artifact=_sample_vacancy_retrieval_queries(opportunity_id),
            vacancy_retrieval_queries_status="approved",
        )
        assert updated is not None
        evidence_artifact = _sample_vacancy_retrieval_evidence(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_retrieval_evidence",
            return_value=evidence_artifact,
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_retrieval_evidence_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_retrieval_evidence_recompute_started", stages)
        self.assertIn("vacancy_retrieval_evidence_building", stages)
        self.assertIn("vacancy_retrieval_evidence_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_retrieval_evidence_status"],
            "draft",
        )

    def test_vacancy_retrieval_evidence_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_queries_artifact=_sample_vacancy_retrieval_queries(opportunity_id),
            vacancy_retrieval_queries_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_retrieval_evidence",
            side_effect=VacancyRetrievalEvidenceBuildError("Step 5 requires an active CV before retrieval can run."),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_retrieval_evidence_stream(
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
        self.assertIn(
            "Step 5 requires an active CV before retrieval can run.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_retrieval_evidence_status"], "error")

    def test_vacancy_evidence_analysis_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con evidencia recuperada.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_evidence_artifact=_sample_vacancy_retrieval_evidence(opportunity_id),
            vacancy_retrieval_evidence_status="approved",
        )
        assert updated is not None
        analysis_artifact = _sample_vacancy_evidence_analysis(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_evidence_analysis",
            return_value=analysis_artifact,
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_evidence_analysis_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_evidence_analysis_recompute_started", stages)
        self.assertIn("vacancy_evidence_analysis_building", stages)
        self.assertIn("vacancy_evidence_analysis_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_evidence_analysis_status"],
            "draft",
        )

    def test_vacancy_evidence_analysis_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con evidencia recuperada.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_evidence_artifact=_sample_vacancy_retrieval_evidence(opportunity_id),
            vacancy_retrieval_evidence_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_evidence_analysis",
            side_effect=VacancyEvidenceAnalysisBuildError("Step 6 requires at least one retrieval match in Step 5 evidence."),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_evidence_analysis_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn(
            "Step 6 requires at least one retrieval match in Step 5 evidence.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_evidence_analysis_status"], "error")

    def test_vacancy_alignment_summary_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con resumen de alineacion.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
        )
        assert updated is not None
        summary_artifact = _sample_vacancy_alignment_summary(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_alignment_summary",
            return_value=summary_artifact,
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_alignment_summary_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_alignment_summary_recompute_started", stages)
        self.assertIn("vacancy_alignment_summary_building", stages)
        self.assertIn("vacancy_alignment_summary_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_alignment_summary_status"],
            "draft",
        )

    def test_vacancy_alignment_summary_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con resumen de alineacion.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_alignment_summary",
            side_effect=VacancyAlignmentSummaryBuildError("Step 7 requires a valid vacancy_evidence_analysis.v1 artifact."),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_alignment_summary_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn(
            "Step 7 requires a valid vacancy_evidence_analysis.v1 artifact.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_summary_status"], "error")


if __name__ == "__main__":
    unittest.main()
