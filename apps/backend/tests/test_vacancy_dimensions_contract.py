import unittest

from app.services.vacancy_dimensions_contract import (
    CONTRACT_VERSION_VACANCY_DIMENSIONS,
    build_item_fingerprint_id,
    empty_salary_normalization,
    empty_vacancy_dimensions_contract,
    enrich_vacancy_dimensions_items,
    is_vacancy_dimensions_contract,
    normalize_item_fingerprint_text,
    normalize_salary_normalization,
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
        self.assertEqual(dimensions["required_criteria"], [])
        self.assertEqual(dimensions["desirable_criteria"], [])
        self.assertEqual(dimensions["benefits"], [])
        self.assertEqual(dimensions["about_the_company"], [])
        self.assertEqual(dimensions["work_conditions"]["salary"]["raw_text"], "")
        self.assertEqual(dimensions["work_conditions"]["location"]["places"], [])
        self.assertEqual(dimensions["work_conditions"]["other_conditions"], [])

    def test_normalize_contract_applies_v2_shape_and_keeps_legacy_alias_compatibility(self) -> None:
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
                        "modality": {
                            "type": " Hibrido ",
                            "text": " Hibrido en Bogota ",
                        },
                        "location": {
                            "places": [" Bogota ", "Bogota"],
                            "text": " Bogota ",
                        },
                        "contract_type": {
                            "type": " Indefinido ",
                            "text": " Contrato indefinido ",
                        },
                        "schedule": {
                            "text": " Horario de oficina ",
                        },
                        "travel": {
                            "text": " Viajes ocasionales ",
                        },
                    },
                    "responsibilities": [
                        {
                            "task": " Liderar la operacion comercial ",
                            "raw_text": " Liderar la operacion comercial ",
                        },
                        {
                            "task": "Liderar la operacion comercial",
                            "raw_text": "Liderar la operacion comercial",
                        },
                    ],
                    "required_competencies": [
                        {
                            "requirement": "Experiencia en retail",
                            "raw_text": " Experiencia en sector retail ",
                        }
                    ],
                    "benefits": [
                        {
                            "benefit": "Seguro de salud",
                            "raw_text": " Seguro de salud prepagado ",
                        }
                    ],
                    "about_the_company": [
                        {"raw_text": " Empresa lider en retail regional "}
                    ],
                },
            }
        )

        self.assertEqual(normalized["vacancy_id"], "VAC-900")
        self.assertEqual(normalized["generated_at"], "2026-04-21T16:05:00Z")

        work_conditions = normalized["vacancy_dimensions"]["work_conditions"]
        self.assertEqual(work_conditions["salary"]["raw_text"], "Salario entre 12 y 18 millones")
        self.assertEqual(work_conditions["modality"]["value"], "Hibrido")
        self.assertEqual(work_conditions["location"]["places"], ["Bogota"])
        self.assertEqual(work_conditions["contract_type"]["value"], "Indefinido")
        self.assertEqual(
            work_conditions["other_conditions"],
            [{"raw_text": "Horario de oficina"}, {"raw_text": "Viajes ocasionales"}],
        )

        responsibilities = normalized["vacancy_dimensions"]["responsibilities"]
        self.assertEqual(responsibilities, [{"raw_text": "Liderar la operacion comercial"}])

        required = normalized["vacancy_dimensions"]["required_criteria"]
        self.assertEqual(required, [{"raw_text": "Experiencia en sector retail"}])

        benefits = normalized["vacancy_dimensions"]["benefits"]
        self.assertEqual(benefits, [{"raw_text": "Seguro de salud prepagado"}])

        about = normalized["vacancy_dimensions"]["about_the_company"]
        self.assertEqual(about, [{"raw_text": "Empresa lider en retail regional"}])

    def test_salary_normalization_preserves_structured_fields_for_s3_1(self) -> None:
        self.assertEqual(
            empty_salary_normalization(),
            {
                "min": None,
                "max": None,
                "currency": "",
                "period": "",
                "raw_text": "",
            },
        )

        normalized = normalize_salary_normalization(
            {
                "min": "12000000",
                "max": 18000000,
                "currency": " COP ",
                "period": " mensual ",
                "text": " Salario entre 12 y 18 millones ",
            }
        )

        self.assertEqual(normalized["min"], 12000000)
        self.assertEqual(normalized["max"], 18000000)
        self.assertEqual(normalized["currency"], "COP")
        self.assertEqual(normalized["period"], "mensual")
        self.assertEqual(normalized["raw_text"], "Salario entre 12 y 18 millones")

    def test_enrich_items_assigns_group_code_item_index_and_stable_item_id(self) -> None:
        contract = normalize_vacancy_dimensions_contract(
            {
                "vacancy_id": "VAC-100",
                "generated_at": "2026-04-23T10:31:05Z",
                "vacancy_dimensions": {
                    "work_conditions": {
                        "other_conditions": [
                            {"raw_text": "Disponibilidad para viajar"},
                            {"raw_text": "Disponibilidad para viajar"},
                        ]
                    },
                    "responsibilities": [
                        {"raw_text": "Liderar equipo de desarrollo"},
                    ],
                    "required_criteria": [
                        {"raw_text": "Experiencia con Python"},
                    ],
                    "benefits": [
                        {"raw_text": "Seguro de salud"},
                    ],
                    "about_the_company": [
                        {"raw_text": "Empresa lider en fintech"},
                    ],
                },
            }
        )

        enriched = enrich_vacancy_dimensions_items(contract)
        responsibilities = enriched["vacancy_dimensions"]["responsibilities"]
        required = enriched["vacancy_dimensions"]["required_criteria"]
        other_conditions = enriched["vacancy_dimensions"]["work_conditions"]["other_conditions"]

        self.assertEqual(responsibilities[0]["group_code"], "resp")
        self.assertEqual(responsibilities[0]["item_index"], 0)
        self.assertEqual(required[0]["group_code"], "req")
        self.assertEqual(other_conditions[0]["group_code"], "cond")
        self.assertEqual(len(other_conditions), 1)
        self.assertEqual(
            responsibilities[0]["item_id"],
            build_item_fingerprint_id("VAC-100", "resp", "Liderar equipo de desarrollo"),
        )

    def test_fingerprint_normalization_and_builder_are_stable(self) -> None:
        self.assertEqual(
            normalize_item_fingerprint_text("  Experiencia\n con\tPython  "),
            "experiencia con python",
        )
        self.assertEqual(
            build_item_fingerprint_id("VAC-1", "req", "Experiencia con Python"),
            build_item_fingerprint_id("VAC-1", "req", "  experiencia   con python "),
        )

    def test_is_contract_detects_version(self) -> None:
        self.assertTrue(
            is_vacancy_dimensions_contract({"contract_version": CONTRACT_VERSION_VACANCY_DIMENSIONS})
        )
        self.assertFalse(is_vacancy_dimensions_contract({"contract_version": "legacy"}))
        self.assertFalse(is_vacancy_dimensions_contract({}))


if __name__ == "__main__":
    unittest.main()
