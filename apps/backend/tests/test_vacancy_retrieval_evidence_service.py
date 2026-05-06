import unittest
from unittest.mock import patch

from app.core.settings import Settings
from app.services.vacancy_retrieval_evidence_contract import CONTRACT_VERSION_VACANCY_RETRIEVAL_EVIDENCE
from app.services.vacancy_retrieval_evidence_service import (
    VacancyRetrievalEvidenceBuildError,
    build_vacancy_retrieval_evidence,
)


def _opportunity() -> dict[str, str]:
    return {
        "opportunity_id": "o-e-001",
        "person_id": "p-001",
        "title": "Senior Product Manager",
        "company": "Acme",
        "location": "Bogota",
        "source_url": "https://example.com/jobs/pm-1",
    }


def _vacancy_retrieval_queries() -> dict[str, object]:
    return {
        "contract_version": "vacancy_retrieval_queries.v1",
        "vacancy_id": "o-e-001",
        "generated_at": "2026-04-24T10:35:00Z",
        "queries": {
            "responsibilities": [
                {
                    "item_id": "resp_123",
                    "item_index": 0,
                    "group_code": "resp",
                    "raw_text": "Liderar roadmap",
                    "queries": ["liderazgo de producto", "gestion de roadmap"],
                }
            ],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": [],
        },
    }


class VacancyRetrievalEvidenceServiceTests(unittest.TestCase):
    def test_build_success_returns_normalized_evidence_contract(self) -> None:
        active_cv = {"cv_id": "cv-123", "vector_index_status": "indexed"}
        runtime_config = {
            "top_k_semantic_per_criterion": 4,
            "retrieval_evidence_persistence_mode": "minimal",
        }
        query_matches = [
            {
                "text": "Lidere roadmap trimestral de producto",
                "score": 0.86,
                "chunk_id": "cv-chunk-1",
                "section": "experience",
                "block_type": "bullet",
                "block_title": "Product Management",
            }
        ]

        with patch(
            "app.services.vacancy_retrieval_evidence_service.get_active_cv",
            return_value=active_cv,
        ), patch(
            "app.services.vacancy_retrieval_evidence_service.get_ai_runtime_config",
            return_value=runtime_config,
        ), patch(
            "app.services.vacancy_retrieval_evidence_service.query_cv_matches",
            return_value=query_matches,
        ) as query_mock:
            contract = build_vacancy_retrieval_evidence(
                opportunity=_opportunity(),
                vacancy_retrieval_queries_artifact=_vacancy_retrieval_queries(),
                settings=Settings(),
            )

        self.assertEqual(contract["contract_version"], CONTRACT_VERSION_VACANCY_RETRIEVAL_EVIDENCE)
        self.assertEqual(contract["vacancy_id"], "o-e-001")
        self.assertEqual(len(contract["evidence"]["responsibilities"][0]["matches"]), 2)
        self.assertEqual(contract["evidence"]["responsibilities"][0]["matches"][0]["source_ref"], "cv-chunk-1")
        self.assertEqual(query_mock.call_args.kwargs["top_k"], 4)

    def test_build_requires_valid_queries_artifact(self) -> None:
        with self.assertRaises(VacancyRetrievalEvidenceBuildError):
            build_vacancy_retrieval_evidence(
                opportunity=_opportunity(),
                vacancy_retrieval_queries_artifact={},
                settings=Settings(),
            )

    def test_build_requires_indexed_active_cv(self) -> None:
        with patch(
            "app.services.vacancy_retrieval_evidence_service.get_active_cv",
            return_value={"cv_id": "cv-123", "vector_index_status": "pending"},
        ):
            with self.assertRaises(VacancyRetrievalEvidenceBuildError):
                build_vacancy_retrieval_evidence(
                    opportunity=_opportunity(),
                    vacancy_retrieval_queries_artifact=_vacancy_retrieval_queries(),
                    settings=Settings(),
                )


if __name__ == "__main__":
    unittest.main()
