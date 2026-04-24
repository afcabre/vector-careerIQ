import unittest

from app.services.vacancy_alignment_summary_service import (
    VacancyAlignmentSummaryBuildError,
    build_vacancy_alignment_summary,
)


def _opportunity() -> dict[str, str]:
    return {
        "opportunity_id": "o-s-001",
        "person_id": "p-001",
        "title": "Senior Product Manager",
        "company": "Acme",
        "location": "Bogota",
    }


def _vacancy_evidence_analysis() -> dict[str, object]:
    return {
        "contract_version": "vacancy_evidence_analysis.v1",
        "vacancy_id": "o-s-001",
        "generated_at": "2026-04-24T17:00:00Z",
        "thresholds": {
            "strong_min": 0.75,
            "useful_min": 0.45,
            "review_min": 0.30,
        },
        "analysis": {
            "responsibilities": [
                {
                    "item_id": "resp_1",
                    "item_index": 0,
                    "group_code": "resp",
                    "raw_text": "Liderar backlog",
                    "item_status": "strong_evidence",
                    "best_score": 0.84,
                    "raw_match_count": 1,
                    "accepted_match_count": 1,
                    "discarded_match_count": 0,
                    "distinct_query_hits": 1,
                    "best_evidence": [],
                    "accepted_matches": [],
                    "discarded_matches": [],
                }
            ],
            "required_criteria": [
                {
                    "item_id": "req_1",
                    "item_index": 1,
                    "group_code": "req",
                    "raw_text": "Experiencia en Python",
                    "item_status": "useful_evidence",
                    "best_score": 0.51,
                    "raw_match_count": 1,
                    "accepted_match_count": 1,
                    "discarded_match_count": 0,
                    "distinct_query_hits": 1,
                    "best_evidence": [],
                    "accepted_matches": [],
                    "discarded_matches": [],
                }
            ],
            "desirable_criteria": [
                {
                    "item_id": "des_1",
                    "item_index": 2,
                    "group_code": "des",
                    "raw_text": "Conocimiento en DAX",
                    "item_status": "no_evidence",
                    "best_score": 0.0,
                    "raw_match_count": 0,
                    "accepted_match_count": 0,
                    "discarded_match_count": 0,
                    "distinct_query_hits": 0,
                    "best_evidence": [],
                    "accepted_matches": [],
                    "discarded_matches": [],
                }
            ],
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


class VacancyAlignmentSummaryServiceTests(unittest.TestCase):
    def test_build_summary_success_returns_primary_group_rollup(self) -> None:
        contract = build_vacancy_alignment_summary(
            opportunity=_opportunity(),
            vacancy_evidence_analysis_artifact=_vacancy_evidence_analysis(),
        )

        self.assertEqual(contract["summary"]["overall"]["total_items"], 3)
        self.assertEqual(contract["summary"]["overall"]["strong_evidence_count"], 1)
        self.assertEqual(contract["summary"]["overall"]["useful_evidence_count"], 1)
        self.assertEqual(contract["summary"]["overall"]["no_evidence_count"], 1)
        self.assertEqual(contract["summary"]["strengths"][0]["group"], "responsibilities")
        self.assertEqual(contract["summary"]["gaps"][0]["group"], "desirable_criteria")

    def test_build_summary_requires_valid_six_artifact(self) -> None:
        with self.assertRaises(VacancyAlignmentSummaryBuildError):
            build_vacancy_alignment_summary(
                opportunity=_opportunity(),
                vacancy_evidence_analysis_artifact={},
            )

    def test_build_summary_requires_primary_groups(self) -> None:
        artifact = _vacancy_evidence_analysis()
        artifact["analysis"]["responsibilities"] = []
        artifact["analysis"]["required_criteria"] = []
        artifact["analysis"]["desirable_criteria"] = []
        with self.assertRaises(VacancyAlignmentSummaryBuildError):
            build_vacancy_alignment_summary(
                opportunity=_opportunity(),
                vacancy_evidence_analysis_artifact=artifact,
            )


if __name__ == "__main__":
    unittest.main()
