import unittest

from app.services.vacancy_dimensions_enrichment_service import (
    VacancyDimensionsEnrichmentError,
    enrich_vacancy_dimensions_artifact,
)


def _opportunity() -> dict[str, str]:
    return {
        "opportunity_id": "o-enrich-001",
        "person_id": "p-001",
        "title": "Senior Product Manager",
        "company": "Acme",
        "location": "Bogota",
        "source_url": "https://example.com/jobs/pm-1",
    }


def _vacancy_dimensions() -> dict[str, object]:
    return {
        "contract_version": "vacancy_dimensions.v2",
        "vacancy_id": "o-enrich-001",
        "generated_at": "2026-04-23T10:31:05Z",
        "vacancy_dimensions": {
            "work_conditions": {
                "salary": {"raw_text": "Salario COP 12M a 18M mensual"},
                "modality": {"value": "Hibrido", "raw_text": "Hibrido en Bogota"},
                "location": {"places": ["Bogota"], "raw_text": "Bogota"},
                "contract_type": {"value": "Indefinido", "raw_text": "Contrato indefinido"},
                "other_conditions": [{"raw_text": "Disponibilidad para viajar"}],
            },
            "responsibilities": [{"raw_text": "Liderar roadmap"}],
            "required_criteria": [{"raw_text": "5 anos de experiencia en producto"}],
            "desirable_criteria": [],
            "benefits": [{"raw_text": "Seguro medico"}],
            "about_the_company": [{"raw_text": "Empresa lider en tecnologia B2B"}],
        },
    }


class VacancyDimensionsEnrichmentServiceTests(unittest.TestCase):
    def test_enrich_success_returns_enriched_contract(self) -> None:
        contract = enrich_vacancy_dimensions_artifact(_opportunity(), _vacancy_dimensions())

        self.assertEqual(contract["contract_version"], "vacancy_dimensions_enriched.v1")
        self.assertEqual(contract["vacancy_id"], "o-enrich-001")
        self.assertTrue(contract["generated_at"])
        responsibility = contract["vacancy_dimensions"]["responsibilities"][0]
        self.assertEqual(responsibility["group_code"], "resp")
        self.assertEqual(responsibility["item_index"], 0)
        self.assertTrue(responsibility["item_id"].startswith("resp_"))

    def test_enrich_requires_valid_dimensions_artifact(self) -> None:
        with self.assertRaises(VacancyDimensionsEnrichmentError):
            enrich_vacancy_dimensions_artifact(_opportunity(), {})

    def test_enrich_fails_when_no_atomic_items_exist(self) -> None:
        empty_dimensions = {
            "contract_version": "vacancy_dimensions.v2",
            "vacancy_id": "o-enrich-001",
            "generated_at": "2026-04-23T10:31:05Z",
            "vacancy_dimensions": {
                "work_conditions": {
                    "salary": {"raw_text": ""},
                    "modality": {"value": "", "raw_text": ""},
                    "location": {"places": [], "raw_text": ""},
                    "contract_type": {"value": "", "raw_text": ""},
                    "other_conditions": [],
                },
                "responsibilities": [],
                "required_criteria": [],
                "desirable_criteria": [],
                "benefits": [],
                "about_the_company": [],
            },
        }
        with self.assertRaises(VacancyDimensionsEnrichmentError):
            enrich_vacancy_dimensions_artifact(_opportunity(), empty_dimensions)


if __name__ == "__main__":
    unittest.main()
