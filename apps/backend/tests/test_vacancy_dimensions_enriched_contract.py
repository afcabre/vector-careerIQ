import unittest

from app.services.vacancy_dimensions_enriched_contract import (
    CONTRACT_VERSION_VACANCY_DIMENSIONS_ENRICHED,
    empty_vacancy_dimensions_enriched_contract,
    is_vacancy_dimensions_enriched_contract,
    normalize_vacancy_dimensions_enriched_contract,
)


class VacancyDimensionsEnrichedContractTests(unittest.TestCase):
    def test_empty_contract_uses_stable_defaults(self) -> None:
        contract = empty_vacancy_dimensions_enriched_contract()

        self.assertEqual(
            contract["contract_version"],
            CONTRACT_VERSION_VACANCY_DIMENSIONS_ENRICHED,
        )
        self.assertEqual(contract["vacancy_id"], "")
        self.assertEqual(contract["generated_at"], "")
        self.assertEqual(contract["vacancy_dimensions"]["responsibilities"], [])

    def test_normalize_contract_enriches_atomic_items(self) -> None:
        normalized = normalize_vacancy_dimensions_enriched_contract(
            {
                "vacancy_id": "VAC-1",
                "generated_at": "2026-04-23T10:31:05Z",
                "vacancy_dimensions": {
                    "work_conditions": {
                        "other_conditions": [{"raw_text": "Disponibilidad para viajar"}],
                    },
                    "responsibilities": [{"raw_text": "Liderar equipo de desarrollo"}],
                    "required_criteria": [{"raw_text": "Experiencia con Python"}],
                    "benefits": [{"raw_text": "Seguro de salud"}],
                },
            }
        )

        responsibility = normalized["vacancy_dimensions"]["responsibilities"][0]
        self.assertEqual(responsibility["group_code"], "resp")
        self.assertEqual(responsibility["item_index"], 0)
        self.assertTrue(responsibility["item_id"].startswith("resp_"))

        other_condition = normalized["vacancy_dimensions"]["work_conditions"]["other_conditions"][0]
        self.assertEqual(other_condition["group_code"], "cond")
        self.assertEqual(other_condition["item_index"], 0)

    def test_is_contract_detects_version(self) -> None:
        self.assertTrue(
            is_vacancy_dimensions_enriched_contract(
                {"contract_version": CONTRACT_VERSION_VACANCY_DIMENSIONS_ENRICHED}
            )
        )
        self.assertFalse(is_vacancy_dimensions_enriched_contract({"contract_version": "legacy"}))
        self.assertFalse(is_vacancy_dimensions_enriched_contract({}))


if __name__ == "__main__":
    unittest.main()
