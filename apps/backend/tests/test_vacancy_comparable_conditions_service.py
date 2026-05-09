import unittest

from app.services.vacancy_comparable_conditions_service import (
    VacancyComparableConditionsBuildError,
    build_vacancy_comparable_conditions,
)


def _opportunity() -> dict[str, str]:
    return {
        "opportunity_id": "o-comp-001",
        "person_id": "p-001",
        "title": "Gerente de Tecnologia",
        "company": "Asssiprex",
        "location": "Bogota, Colombia",
        "snapshot_raw_text": (
            "Ubicacion: Bogota D.C.\n"
            "Modalidad: Hibrido 4x1\n"
            "Compensacion: $12.000.000 COP + comisiones\n"
            "Contrato: termino indefinido"
        ),
    }


def _vacancy_dimensions() -> dict[str, object]:
    return {
        "contract_version": "vacancy_dimensions.v2",
        "vacancy_id": "o-comp-001",
        "generated_at": "2026-05-09T10:00:00Z",
        "vacancy_dimensions": {
            "work_conditions": [
                {"raw_text": "Modalidad: Hibrido 4x1"},
                {"raw_text": "Ubicacion: Bogota D.C."},
                {"raw_text": "Compensacion: $12.000.000 COP + comisiones"},
                {"raw_text": "Contrato: termino indefinido"},
            ],
            "responsibilities": [],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "unclassified": [],
        },
        "warnings": [],
        "coverage_notes": [],
    }


def _vacancy_salary() -> dict[str, object]:
    return {
        "contract_version": "vacancy_salary_normalization.v1",
        "vacancy_id": "o-comp-001",
        "generated_at": "2026-05-09T10:01:00Z",
        "salary": {
            "min": 12000000,
            "max": None,
            "currency": "COP",
            "period": "monthly",
            "raw_text": "$12.000.000 COP + comisiones",
            "has_variable_component": True,
            "variable_component_type": "commission",
            "variable_component_note": "comisiones",
        },
    }


class VacancyComparableConditionsServiceTests(unittest.TestCase):
    def test_build_normalizes_location_modality_compensation_and_contract(self) -> None:
        artifact = build_vacancy_comparable_conditions(
            opportunity=_opportunity(),
            vacancy_dimensions_artifact=_vacancy_dimensions(),
            vacancy_salary_artifact=_vacancy_salary(),
        )

        self.assertEqual(
            artifact["contract_version"],
            "vacancy_comparable_conditions.v1",
        )
        self.assertEqual(artifact["vacancy_id"], "o-comp-001")
        self.assertEqual(artifact["location"]["normalized_city"], "Bogota")
        self.assertEqual(artifact["location"]["normalized_country"], "Colombia")
        self.assertEqual(artifact["modality"]["mode"], "hybrid")
        self.assertEqual(artifact["modality"]["intensity"], "4x1")
        self.assertEqual(artifact["contract_type"]["value"], "indefinite")
        self.assertEqual(artifact["compensation"]["currency"], "COP")
        self.assertEqual(artifact["compensation"]["min_amount"], 12000000)
        self.assertTrue(artifact["compensation"]["has_variable_component"])
        self.assertEqual(artifact["compensation"]["variable_component_type"], "commission")

    def test_build_uses_fallback_location_and_unknowns_when_signals_missing(self) -> None:
        opportunity = {
            **_opportunity(),
            "location": "Medellin, Colombia",
            "snapshot_raw_text": "",
        }
        vacancy_dimensions = {
            **_vacancy_dimensions(),
            "vacancy_dimensions": {
                **_vacancy_dimensions()["vacancy_dimensions"],
                "work_conditions": [],
            },
        }

        artifact = build_vacancy_comparable_conditions(
            opportunity=opportunity,
            vacancy_dimensions_artifact=vacancy_dimensions,
            vacancy_salary_artifact={},
        )

        self.assertEqual(artifact["location"]["normalized_city"], "Medellin")
        self.assertEqual(artifact["modality"]["mode"], "unknown")
        self.assertEqual(artifact["contract_type"]["value"], "unknown")
        self.assertEqual(artifact["compensation"]["confidence"], "none")

    def test_build_requires_valid_dimensions_artifact(self) -> None:
        with self.assertRaises(VacancyComparableConditionsBuildError):
            build_vacancy_comparable_conditions(
                opportunity=_opportunity(),
                vacancy_dimensions_artifact={},
                vacancy_salary_artifact={},
            )


if __name__ == "__main__":
    unittest.main()
