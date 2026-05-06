import unittest
from unittest.mock import patch

from app.services.vacancy_evidence_analysis_contract import ITEM_STATUS_USEFUL_EVIDENCE
from app.services.vacancy_evidence_analysis_service import (
    VacancyEvidenceAnalysisBuildError,
    build_vacancy_evidence_analysis,
)


def _opportunity() -> dict[str, str]:
    return {
        "opportunity_id": "o-a-001",
        "person_id": "p-001",
        "title": "Senior Product Manager",
        "company": "Acme",
        "location": "Bogota",
    }


def _vacancy_retrieval_evidence() -> dict[str, object]:
    return {
        "contract_version": "vacancy_retrieval_evidence.v1",
        "vacancy_id": "o-a-001",
        "generated_at": "2026-04-24T10:36:00Z",
        "evidence": {
            "responsibilities": [
                {
                    "item_id": "resp_123",
                    "item_index": 0,
                    "group_code": "resp",
                    "raw_text": "Liderar backlog",
                    "matches": [
                        {
                            "query_index": 0,
                            "query_text": "liderazgo de backlog",
                            "score": 0.62,
                            "snippet": "Lidere backlog trimestral",
                            "source_ref": "cv-chunk-1",
                            "section": "experience",
                            "block_type": "bullet",
                            "block_title": "Product",
                        },
                        {
                            "query_index": 1,
                            "query_text": "gestion de roadmap",
                            "score": 0.58,
                            "snippet": "Lidere backlog trimestral",
                            "source_ref": "cv-chunk-1",
                            "section": "experience",
                            "block_type": "bullet",
                            "block_title": "Product",
                        },
                        {
                            "query_index": 1,
                            "query_text": "gestion de roadmap",
                            "score": 0.22,
                            "snippet": "Participe en reuniones tecnicas",
                            "source_ref": "cv-chunk-9",
                            "section": "experience",
                            "block_type": "bullet",
                            "block_title": "Product",
                        },
                    ],
                }
            ],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": [],
        },
    }


class VacancyEvidenceAnalysisServiceTests(unittest.TestCase):
    def test_build_success_consolidates_and_classifies_matches(self) -> None:
        with patch(
            "app.services.vacancy_evidence_analysis_service.get_ai_runtime_config",
            return_value={
                "vacancy_retrieval_score_strong_min": 0.75,
                "vacancy_retrieval_score_useful_min": 0.45,
                "vacancy_retrieval_score_review_min": 0.30,
            },
        ):
            contract = build_vacancy_evidence_analysis(
                opportunity=_opportunity(),
                vacancy_retrieval_evidence_artifact=_vacancy_retrieval_evidence(),
            )

        item = contract["analysis"]["responsibilities"][0]
        self.assertEqual(item["item_status"], ITEM_STATUS_USEFUL_EVIDENCE)
        self.assertEqual(item["best_score"], 0.62)
        self.assertEqual(item["accepted_match_count"], 1)
        self.assertEqual(item["discarded_match_count"], 1)
        self.assertEqual(item["distinct_query_hits"], 2)
        self.assertEqual(item["best_evidence"][0]["raw_match_count"], 2)
        self.assertEqual(len(item["best_evidence"][0]["query_texts"]), 2)
        self.assertEqual(
            item["discarded_matches"][0]["discard_reason"],
            "score_below_review_threshold",
        )

    def test_build_requires_valid_evidence_artifact(self) -> None:
        with self.assertRaises(VacancyEvidenceAnalysisBuildError):
            build_vacancy_evidence_analysis(
                opportunity=_opportunity(),
                vacancy_retrieval_evidence_artifact={},
            )

    def test_build_requires_at_least_one_match(self) -> None:
        artifact = _vacancy_retrieval_evidence()
        artifact["evidence"]["responsibilities"][0]["matches"] = []
        with self.assertRaises(VacancyEvidenceAnalysisBuildError):
            build_vacancy_evidence_analysis(
                opportunity=_opportunity(),
                vacancy_retrieval_evidence_artifact=artifact,
            )


if __name__ == "__main__":
    unittest.main()
