import unittest

from app.services.vacancy_evidence_analysis_contract import (
    CONTRACT_VERSION_VACANCY_EVIDENCE_ANALYSIS,
    ITEM_STATUS_USEFUL_EVIDENCE,
    normalize_vacancy_evidence_analysis_contract,
)


class VacancyEvidenceAnalysisContractTests(unittest.TestCase):
    def test_normalize_contract_preserves_analysis_shape(self) -> None:
        normalized = normalize_vacancy_evidence_analysis_contract(
            {
                "contract_version": CONTRACT_VERSION_VACANCY_EVIDENCE_ANALYSIS,
                "vacancy_id": "o-1",
                "generated_at": "2026-04-24T12:00:00Z",
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
                            "item_status": ITEM_STATUS_USEFUL_EVIDENCE,
                            "best_score": 0.62,
                            "raw_match_count": 2,
                            "accepted_match_count": 1,
                            "discarded_match_count": 1,
                            "distinct_query_hits": 2,
                            "best_evidence": [
                                {
                                    "source_ref": "cv-chunk-1",
                                    "snippet": "Lidere backlog trimestral",
                                    "best_score": 0.62,
                                    "query_texts": ["liderazgo de backlog"],
                                    "query_indexes": [0],
                                    "section": "experience",
                                    "block_type": "bullet",
                                    "block_title": "Product",
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
                    "work_conditions": [],
                },
            }
        )
        self.assertEqual(normalized["contract_version"], CONTRACT_VERSION_VACANCY_EVIDENCE_ANALYSIS)
        item = normalized["analysis"]["responsibilities"][0]
        self.assertEqual(item["item_status"], ITEM_STATUS_USEFUL_EVIDENCE)
        self.assertEqual(item["best_evidence"][0]["source_ref"], "cv-chunk-1")


if __name__ == "__main__":
    unittest.main()
