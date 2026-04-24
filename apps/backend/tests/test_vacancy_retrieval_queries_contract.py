import unittest

from app.services.vacancy_retrieval_queries_contract import (
    CONTRACT_VERSION_VACANCY_RETRIEVAL_QUERIES,
    empty_vacancy_retrieval_queries_contract,
    is_vacancy_retrieval_queries_contract,
    normalize_vacancy_retrieval_queries_contract,
)


class VacancyRetrievalQueriesContractTests(unittest.TestCase):
    def test_empty_contract_uses_stable_defaults(self) -> None:
        contract = empty_vacancy_retrieval_queries_contract()

        self.assertEqual(contract["contract_version"], CONTRACT_VERSION_VACANCY_RETRIEVAL_QUERIES)
        self.assertEqual(contract["vacancy_id"], "")
        self.assertEqual(contract["generated_at"], "")
        self.assertEqual(contract["queries"]["responsibilities"], [])
        self.assertEqual(contract["queries"]["work_conditions"]["salary"], [])

    def test_normalize_contract_applies_shape_and_deduplicates_queries(self) -> None:
        normalized = normalize_vacancy_retrieval_queries_contract(
            {
                "vacancy_id": " VAC-1 ",
                "generated_at": " 2026-04-24T10:35:00Z ",
                "queries": {
                    "responsibilities": [
                        {
                            "item_id": "resp_123",
                            "item_index": 0,
                            "group_code": "resp",
                            "raw_text": " Liderar roadmap ",
                            "queries": [" liderar roadmap ", "liderar roadmap"],
                        }
                    ],
                    "required_criteria": [],
                    "desirable_criteria": [],
                    "benefits": [],
                    "about_the_company": [],
                    "work_conditions": {
                        "salary": [
                            {
                                "item_id": "salary_1",
                                "item_index": 0,
                                "group_code": "salary",
                                "raw_text": " Salario COP 12M a 18M mensual ",
                                "queries": ["salario mensual cop 12 a 18 millones"],
                            }
                        ]
                    },
                },
            }
        )

        self.assertEqual(normalized["vacancy_id"], "VAC-1")
        responsibility = normalized["queries"]["responsibilities"][0]
        self.assertEqual(responsibility["queries"], ["liderar roadmap"])
        salary = normalized["queries"]["work_conditions"]["salary"][0]
        self.assertEqual(salary["group_code"], "salary")

    def test_is_contract_detects_version(self) -> None:
        self.assertTrue(
            is_vacancy_retrieval_queries_contract(
                {"contract_version": CONTRACT_VERSION_VACANCY_RETRIEVAL_QUERIES}
            )
        )
        self.assertFalse(is_vacancy_retrieval_queries_contract({"contract_version": "legacy"}))
        self.assertFalse(is_vacancy_retrieval_queries_contract({}))


if __name__ == "__main__":
    unittest.main()
