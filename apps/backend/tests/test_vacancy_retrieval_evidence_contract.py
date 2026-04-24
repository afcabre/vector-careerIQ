import unittest

from app.services.vacancy_retrieval_evidence_contract import (
    CONTRACT_VERSION_VACANCY_RETRIEVAL_EVIDENCE,
    empty_vacancy_retrieval_evidence_contract,
    is_vacancy_retrieval_evidence_contract,
    normalize_vacancy_retrieval_evidence_contract,
)


class VacancyRetrievalEvidenceContractTests(unittest.TestCase):
    def test_empty_contract_uses_expected_defaults(self) -> None:
        contract = empty_vacancy_retrieval_evidence_contract()
        self.assertEqual(contract["contract_version"], CONTRACT_VERSION_VACANCY_RETRIEVAL_EVIDENCE)
        self.assertEqual(contract["vacancy_id"], "")
        self.assertEqual(contract["evidence"]["responsibilities"], [])
        self.assertEqual(contract["evidence"]["work_conditions"]["salary"], [])

    def test_normalize_contract_preserves_matches(self) -> None:
        normalized = normalize_vacancy_retrieval_evidence_contract(
            {
                "vacancy_id": "o-1",
                "generated_at": "2026-04-24T12:00:00Z",
                "evidence": {
                    "responsibilities": [
                        {
                            "item_id": "resp_1",
                            "item_index": 0,
                            "group_code": "resp",
                            "raw_text": "Liderar roadmap",
                            "matches": [
                                {
                                    "query_index": 0,
                                    "query_text": "liderazgo de producto",
                                    "score": 0.81,
                                    "snippet": "Lidere roadmap trimestral",
                                    "source_ref": "cv-1",
                                }
                            ],
                        }
                    ]
                },
            }
        )
        self.assertEqual(normalized["vacancy_id"], "o-1")
        self.assertEqual(normalized["evidence"]["responsibilities"][0]["matches"][0]["score"], 0.81)
        self.assertEqual(normalized["evidence"]["responsibilities"][0]["matches"][0]["source_ref"], "cv-1")

    def test_contract_validator_checks_version(self) -> None:
        self.assertTrue(
            is_vacancy_retrieval_evidence_contract(
                {"contract_version": CONTRACT_VERSION_VACANCY_RETRIEVAL_EVIDENCE}
            )
        )
        self.assertFalse(is_vacancy_retrieval_evidence_contract({"contract_version": "legacy"}))
        self.assertFalse(is_vacancy_retrieval_evidence_contract({}))


if __name__ == "__main__":
    unittest.main()
