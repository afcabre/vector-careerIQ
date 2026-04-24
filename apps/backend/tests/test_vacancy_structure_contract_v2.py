import unittest

from app.services.vacancy_structure_contract_v2 import (
    CONTRACT_VERSION_V2,
    empty_vacancy_structure_v2,
    is_vacancy_structure_v2,
    normalize_vacancy_structure_v2,
)


class VacancyStructureContractV2Tests(unittest.TestCase):
    def test_empty_contract_uses_stable_defaults(self) -> None:
        contract = empty_vacancy_structure_v2()

        self.assertEqual(contract["contract_version"], CONTRACT_VERSION_V2)
        self.assertEqual(contract["summary"], "")
        self.assertEqual(contract["criteria"], [])
        self.assertEqual(contract["confidence"], "low")
        self.assertEqual(contract["extraction_source"], "none")
        self.assertEqual(
            contract["role_properties"],
            {
                "organizational_level": "no_especificado",
                "company_type": "no_especificado",
                "sector": "no_especificado",
            },
        )

    def test_normalize_contract_sanitizes_and_deduplicates_criteria(self) -> None:
        normalized = normalize_vacancy_structure_v2(
            {
                "summary": "  Lidera la operacion comercial regional.  ",
                "role_properties": {
                    "organizational_level": "director",
                    "company_type": "multinational",
                    "sector": "software b2b",
                },
                "criteria": [
                    {
                        "label": "Minimo 8 anos liderando equipos comerciales",
                        "priority": "required",
                        "vacancy_dimension": "experience",
                        "category": "years_of_experience",
                        "raw_text": "Debe acreditar minimo 8 anos liderando equipos comerciales",
                        "normalized_value": {"years_min": 8},
                        "metadata": {"source_section": "requirements"},
                    },
                    {
                        "label": "Minimo 8 anos liderando equipos comerciales",
                        "priority": "required",
                        "vacancy_dimension": "experience",
                        "category": "years_of_experience",
                        "raw_text": "Debe acreditar minimo 8 anos liderando equipos comerciales",
                    },
                    {
                        "label": "",
                        "priority": "constraint",
                        "vacancy_dimension": "location",
                        "category": "geo_scope",
                        "raw_text": "Disponibilidad para viajar por Colombia y Peru",
                        "normalized_value": {"countries": ["CO", "PE"]},
                    },
                ],
                "confidence": "HIGH",
                "extraction_source": "  llm  ",
            }
        )

        self.assertEqual(normalized["summary"], "Lidera la operacion comercial regional.")
        self.assertEqual(normalized["role_properties"]["organizational_level"], "director")
        self.assertEqual(normalized["role_properties"]["company_type"], "multinational")
        self.assertEqual(normalized["role_properties"]["sector"], "software b2b")
        self.assertEqual(normalized["confidence"], "high")
        self.assertEqual(normalized["extraction_source"], "llm")
        self.assertEqual(len(normalized["criteria"]), 2)

        first = normalized["criteria"][0]
        self.assertEqual(first["criterion_id"], "criterion_1_minimo_8_anos_liderando_equipos_comerciales")
        self.assertEqual(first["priority"], "required")
        self.assertEqual(first["vacancy_dimension"], "experience")
        self.assertEqual(first["category"], "years_of_experience")
        self.assertEqual(first["normalized_value"], {"years_min": 8})
        self.assertEqual(first["metadata"], {"source_section": "requirements"})

        second = normalized["criteria"][1]
        self.assertEqual(
            second["label"],
            "Disponibilidad para viajar por Colombia y Peru",
        )
        self.assertEqual(second["priority"], "constraint")
        self.assertEqual(second["vacancy_dimension"], "location")
        self.assertEqual(second["normalized_value"], {"countries": ["CO", "PE"]})

    def test_normalize_contract_falls_back_for_unknown_values(self) -> None:
        normalized = normalize_vacancy_structure_v2(
            {
                "role_properties": {},
                "criteria": [
                    {
                        "criterion_id": "custom-1",
                        "label": "Framework principal: React",
                        "priority": "must_have",
                        "vacancy_dimension": "framework",
                        "category": "",
                        "raw_text": "",
                    }
                ],
                "confidence": "uncertain",
            }
        )

        self.assertEqual(normalized["confidence"], "medium")
        self.assertEqual(len(normalized["criteria"]), 1)
        criterion = normalized["criteria"][0]
        self.assertEqual(criterion["criterion_id"], "custom-1")
        self.assertEqual(criterion["priority"], "required")
        self.assertEqual(criterion["vacancy_dimension"], "other")
        self.assertEqual(criterion["category"], "general")

    def test_is_vacancy_structure_v2_detects_contract_version(self) -> None:
        self.assertTrue(is_vacancy_structure_v2({"contract_version": CONTRACT_VERSION_V2}))
        self.assertFalse(is_vacancy_structure_v2({"contract_version": "legacy"}))
        self.assertFalse(is_vacancy_structure_v2({}))


if __name__ == "__main__":
    unittest.main()
