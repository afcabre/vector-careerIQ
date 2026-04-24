import unittest

from app.services.vacancy_salary_contract import (
    CONTRACT_VERSION_VACANCY_SALARY_NORMALIZATION,
    empty_vacancy_salary_normalization_contract,
    is_vacancy_salary_normalization_contract,
    normalize_vacancy_salary_normalization_contract,
)


class VacancySalaryNormalizationContractTests(unittest.TestCase):
    def test_empty_contract_uses_stable_defaults(self) -> None:
        contract = empty_vacancy_salary_normalization_contract()

        self.assertEqual(
            contract["contract_version"],
            CONTRACT_VERSION_VACANCY_SALARY_NORMALIZATION,
        )
        self.assertEqual(contract["vacancy_id"], "")
        self.assertEqual(contract["generated_at"], "")
        self.assertEqual(
            contract["salary"],
            {
                "min": None,
                "max": None,
                "currency": "",
                "period": "",
                "raw_text": "",
            },
        )

    def test_normalize_contract_accepts_root_or_nested_salary_payload(self) -> None:
        nested = normalize_vacancy_salary_normalization_contract(
            {
                "vacancy_id": " VAC-1 ",
                "generated_at": " 2026-04-23T10:33:00Z ",
                "salary": {
                    "min": "12000000",
                    "max": 18000000,
                    "currency": " COP ",
                    "period": " mensual ",
                    "raw_text": " Salario entre 12 y 18 millones ",
                },
            }
        )
        flat = normalize_vacancy_salary_normalization_contract(
            {
                "vacancy_id": "VAC-2",
                "min": "5000",
                "max": "7000",
                "currency": "USD",
                "period": "monthly",
                "text": "USD 5k-7k monthly",
            }
        )

        self.assertEqual(nested["vacancy_id"], "VAC-1")
        self.assertEqual(nested["salary"]["currency"], "COP")
        self.assertEqual(flat["vacancy_id"], "VAC-2")
        self.assertEqual(flat["salary"]["min"], 5000)
        self.assertEqual(flat["salary"]["raw_text"], "USD 5k-7k monthly")

    def test_is_contract_detects_version(self) -> None:
        self.assertTrue(
            is_vacancy_salary_normalization_contract(
                {"contract_version": CONTRACT_VERSION_VACANCY_SALARY_NORMALIZATION}
            )
        )
        self.assertFalse(is_vacancy_salary_normalization_contract({"contract_version": "legacy"}))
        self.assertFalse(is_vacancy_salary_normalization_contract({}))


if __name__ == "__main__":
    unittest.main()
