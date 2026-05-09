import unittest

from app.services.vacancy_comparable_conditions_contract import (
    CONTRACT_VERSION_VACANCY_COMPARABLE_CONDITIONS,
    empty_vacancy_comparable_conditions_contract,
    is_vacancy_comparable_conditions_contract,
    normalize_vacancy_comparable_conditions_contract,
)


class VacancyComparableConditionsContractTests(unittest.TestCase):
    def test_empty_contract_uses_stable_defaults(self) -> None:
        contract = empty_vacancy_comparable_conditions_contract()

        self.assertEqual(
            contract["contract_version"],
            CONTRACT_VERSION_VACANCY_COMPARABLE_CONDITIONS,
        )
        self.assertEqual(contract["vacancy_id"], "")
        self.assertEqual(contract["location"]["confidence"], "none")
        self.assertEqual(contract["modality"]["mode"], "unknown")
        self.assertEqual(contract["contract_type"]["value"], "unknown")
        self.assertFalse(contract["compensation"]["has_variable_component"])

    def test_normalize_contract_accepts_reduced_comparable_fields(self) -> None:
        normalized = normalize_vacancy_comparable_conditions_contract(
            {
                "vacancy_id": " VAC-1 ",
                "generated_at": " 2026-05-09T10:00:00Z ",
                "location": {
                    "raw": " Bogota D.C. ",
                    "normalized_city": " Bogota ",
                    "normalized_country": " Colombia ",
                    "confidence": " HIGH ",
                },
                "modality": {
                    "raw": " Hibrido 4x1 ",
                    "mode": " hybrid ",
                    "intensity": " 4x1 ",
                    "confidence": " high ",
                },
                "compensation": {
                    "raw": " $12.000.000 + comisiones ",
                    "currency": " cop ",
                    "min_amount": "12000000",
                    "period": " monthly ",
                    "has_variable_component": True,
                    "variable_component_type": " commission ",
                    "variable_component_note": " comisiones ",
                    "confidence": " medium ",
                },
                "contract_type": {
                    "raw": " indefinido ",
                    "value": " indefinite ",
                    "confidence": " high ",
                },
                "warnings": [" vacancy_location_not_normalized "],
            }
        )

        self.assertEqual(normalized["vacancy_id"], "VAC-1")
        self.assertEqual(normalized["location"]["normalized_city"], "Bogota")
        self.assertEqual(normalized["modality"]["mode"], "hybrid")
        self.assertEqual(normalized["compensation"]["currency"], "COP")
        self.assertEqual(normalized["compensation"]["min_amount"], 12000000)
        self.assertEqual(normalized["contract_type"]["value"], "indefinite")
        self.assertEqual(normalized["warnings"], ["vacancy_location_not_normalized"])

    def test_is_contract_detects_version(self) -> None:
        self.assertTrue(
            is_vacancy_comparable_conditions_contract(
                {"contract_version": CONTRACT_VERSION_VACANCY_COMPARABLE_CONDITIONS}
            )
        )
        self.assertFalse(
            is_vacancy_comparable_conditions_contract({"contract_version": "legacy"})
        )
        self.assertFalse(is_vacancy_comparable_conditions_contract({}))


if __name__ == "__main__":
    unittest.main()
