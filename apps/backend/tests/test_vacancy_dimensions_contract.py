import unittest

from app.services.vacancy_dimensions_contract import (
    CONTRACT_VERSION_VACANCY_DIMENSIONS,
    empty_vacancy_dimensions_contract,
    is_vacancy_dimensions_contract,
    normalize_vacancy_dimensions_contract,
)


class VacancyDimensionsContractTests(unittest.TestCase):
    def test_empty_contract_uses_stable_defaults(self) -> None:
        contract = empty_vacancy_dimensions_contract()

        self.assertEqual(contract["contract_version"], CONTRACT_VERSION_VACANCY_DIMENSIONS)
        self.assertEqual(contract["vacancy_id"], "")
        self.assertEqual(contract["generated_at"], "")
        dimensions = contract["vacancy_dimensions"]
        self.assertEqual(dimensions["responsibilities"], [])
        self.assertEqual(dimensions["required_competencies"], [])
        self.assertEqual(dimensions["desirable_competencies"], [])
        self.assertEqual(dimensions["benefits"], [])
        self.assertEqual(dimensions["work_conditions"]["salary"]["min"], None)
        self.assertEqual(dimensions["work_conditions"]["salary"]["currency"], "")
        self.assertEqual(dimensions["work_conditions"]["travel"]["required"], None)
        self.assertEqual(dimensions["work_conditions"]["location"]["places"], [])

    def test_normalize_contract_applies_defaults_and_deduplicates_atomic_items(self) -> None:
        normalized = normalize_vacancy_dimensions_contract(
            {
                "vacancy_id": " VAC-900 ",
                "generated_at": " 2026-04-21T16:05:00Z ",
                "vacancy_dimensions": {
                    "work_conditions": {
                        "salary": {
                            "min": "12000000",
                            "max": 18000000,
                            "currency": " COP ",
                            "period": " mensual ",
                            "text": " Salario entre 12 y 18 millones ",
                        },
                        "travel": {
                            "required": "yes",
                            "frequency": "30%",
                            "scope": "Colombia",
                            "text": "Disponibilidad para viajar",
                        },
                    },
                    "responsibilities": [
                        {
                            "task": " Liderar la operacion comercial ",
                            "category": "leadership",
                            "semantic_queries": [" liderar operacion comercial "],
                            "raw_text": "Liderar la operacion comercial",
                        },
                        {
                            "task": "Liderar la operacion comercial",
                            "category": "leadership",
                            "semantic_queries": ["liderar operacion comercial"],
                            "raw_text": "Liderar la operacion comercial",
                        },
                    ],
                    "required_competencies": [
                        {
                            "id": "REQ-77",
                            "requirement": "Experiencia en retail",
                            "category": "",
                            "semantic_queries": ["retail", "retail"],
                            "raw_text": "Experiencia en sector retail",
                        }
                    ],
                    "benefits": [
                        {
                            "benefit": "Seguro de salud",
                            "category": "health",
                            "semantic_queries": [],
                            "raw_text": "Seguro de salud prepagado",
                        }
                    ],
                },
            }
        )

        self.assertEqual(normalized["vacancy_id"], "VAC-900")
        self.assertEqual(normalized["generated_at"], "2026-04-21T16:05:00Z")

        work_conditions = normalized["vacancy_dimensions"]["work_conditions"]
        self.assertEqual(work_conditions["salary"]["min"], 12000000)
        self.assertEqual(work_conditions["salary"]["max"], 18000000)
        self.assertEqual(work_conditions["salary"]["currency"], "COP")
        self.assertEqual(work_conditions["travel"]["required"], True)
        self.assertEqual(work_conditions["contract_type"]["type"], "")

        responsibilities = normalized["vacancy_dimensions"]["responsibilities"]
        self.assertEqual(len(responsibilities), 1)
        self.assertEqual(responsibilities[0]["id"], "RES-01")
        self.assertEqual(responsibilities[0]["task"], "Liderar la operacion comercial")

        required = normalized["vacancy_dimensions"]["required_competencies"]
        self.assertEqual(required[0]["id"], "REQ-77")
        self.assertEqual(required[0]["semantic_queries"], ["retail"])

        benefits = normalized["vacancy_dimensions"]["benefits"]
        self.assertEqual(benefits[0]["benefit"], "Seguro de salud")
        self.assertEqual(benefits[0]["category"], "health")

    def test_is_contract_detects_version(self) -> None:
        self.assertTrue(
            is_vacancy_dimensions_contract({"contract_version": CONTRACT_VERSION_VACANCY_DIMENSIONS})
        )
        self.assertFalse(is_vacancy_dimensions_contract({"contract_version": "legacy"}))
        self.assertFalse(is_vacancy_dimensions_contract({}))


if __name__ == "__main__":
    unittest.main()
