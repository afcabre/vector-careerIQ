import unittest

from app.services.vacancy_alignment_summary_contract import (
    CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY,
    normalize_vacancy_alignment_summary_contract,
)


class VacancyAlignmentSummaryContractTests(unittest.TestCase):
    def test_normalize_contract_preserves_summary_shape(self) -> None:
        normalized = normalize_vacancy_alignment_summary_contract(
            {
                "contract_version": CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY,
                "vacancy_id": "o-1",
                "generated_at": "2026-04-24T18:00:00Z",
                "source_artifact_version": "vacancy_evidence_analysis.v1",
                "thresholds": {
                    "strong_min": 0.75,
                    "useful_min": 0.45,
                    "review_min": 0.30,
                },
                "summary": {
                    "overall": {
                        "total_items": 3,
                        "strong_evidence_count": 1,
                        "useful_evidence_count": 1,
                        "review_count": 0,
                        "no_evidence_count": 1,
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
                            "total_items": 1,
                            "strong_evidence_count": 0,
                            "useful_evidence_count": 1,
                            "review_count": 0,
                            "no_evidence_count": 0,
                        },
                        "desirable_criteria": {
                            "total_items": 1,
                            "strong_evidence_count": 0,
                            "useful_evidence_count": 0,
                            "review_count": 0,
                            "no_evidence_count": 1,
                        },
                    },
                    "strengths": [
                        {
                            "group": "responsibilities",
                            "item_id": "resp_1",
                            "item_index": 0,
                            "raw_text": "Liderar backlog",
                            "item_status": "strong_evidence",
                            "best_score": 0.84,
                        }
                    ],
                    "gaps": [],
                    "review_items": [],
                },
            }
        )
        self.assertEqual(
            normalized["contract_version"],
            CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY,
        )
        self.assertEqual(normalized["summary"]["overall"]["total_items"], 3)
        self.assertEqual(normalized["summary"]["strengths"][0]["group"], "responsibilities")


if __name__ == "__main__":
    unittest.main()
