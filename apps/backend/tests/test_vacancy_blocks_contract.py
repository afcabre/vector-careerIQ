import unittest

from app.services.vacancy_blocks_contract import (
    CONTRACT_VERSION_VACANCY_BLOCKS,
    empty_vacancy_blocks_contract,
    is_vacancy_blocks_contract,
    normalize_vacancy_blocks_contract,
)


class VacancyBlocksContractTests(unittest.TestCase):
    def test_empty_contract_uses_stable_defaults(self) -> None:
        contract = empty_vacancy_blocks_contract()

        self.assertEqual(contract["contract_version"], CONTRACT_VERSION_VACANCY_BLOCKS)
        self.assertEqual(contract["vacancy_id"], "")
        self.assertEqual(contract["generated_at"], "")
        self.assertEqual(contract["warnings"], [])
        self.assertEqual(contract["coverage_notes"], [])
        self.assertEqual(
            contract["vacancy_blocks"],
            {
                "work_conditions": [],
                "responsibilities": [],
                "required_requirements": [],
                "desirable_requirements": [],
                "benefits": [],
                "unclassified": [],
            },
        )

    def test_normalize_contract_keeps_fixed_keys_and_deduplicates_items(self) -> None:
        normalized = normalize_vacancy_blocks_contract(
            {
                "vacancy_id": "  VAC-123  ",
                "generated_at": " 2026-04-21T16:00:00Z ",
                "vacancy_blocks": {
                    "work_conditions": [
                        " Hibrido en Bogota ",
                        "Hibrido en Bogota",
                    ],
                    "responsibilities": [
                        " Liderar el equipo comercial ",
                    ],
                    "required_requirements": [
                        "5 anos de experiencia en ventas B2B",
                    ],
                    "desirable_requirements": [
                        "MBA",
                    ],
                    "benefits": [
                        "Seguro de salud",
                    ],
                    "unclassified": [
                        "Texto ambiguo",
                    ],
                    "invented_key": [
                        "Debe ignorarse",
                    ],
                },
                "warnings": [" fragmento ambiguo ", "fragmento ambiguo"],
                "coverage_notes": [" sin salario explicito "],
            }
        )

        self.assertEqual(normalized["vacancy_id"], "VAC-123")
        self.assertEqual(normalized["generated_at"], "2026-04-21T16:00:00Z")
        self.assertEqual(normalized["vacancy_blocks"]["work_conditions"], ["Hibrido en Bogota"])
        self.assertEqual(normalized["vacancy_blocks"]["responsibilities"], ["Liderar el equipo comercial"])
        self.assertEqual(
            normalized["vacancy_blocks"]["required_requirements"],
            ["5 anos de experiencia en ventas B2B"],
        )
        self.assertEqual(normalized["warnings"], ["fragmento ambiguo"])
        self.assertEqual(normalized["coverage_notes"], ["sin salario explicito"])
        self.assertNotIn("invented_key", normalized["vacancy_blocks"])

    def test_is_contract_detects_version(self) -> None:
        self.assertTrue(is_vacancy_blocks_contract({"contract_version": CONTRACT_VERSION_VACANCY_BLOCKS}))
        self.assertFalse(is_vacancy_blocks_contract({"contract_version": "legacy"}))
        self.assertFalse(is_vacancy_blocks_contract({}))


if __name__ == "__main__":
    unittest.main()
