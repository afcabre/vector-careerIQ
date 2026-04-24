import unittest
from unittest.mock import patch

from app.services.prompt_config_store import (
    FLOW_TASK_VACANCY_BLOCKS_EXTRACT,
    FLOW_TASK_VACANCY_DIMENSIONS_EXTRACT,
)
from app.services.vacancy_dimensions_contract import CONTRACT_VERSION_VACANCY_DIMENSIONS
from app.services.vacancy_dimensions_service import (
    VacancyDimensionsExtractionError,
    extract_vacancy_dimensions,
)


def _opportunity() -> dict[str, str]:
    return {
        "opportunity_id": "o-step3-001",
        "person_id": "p-001",
        "title": "Senior Product Manager",
        "company": "Acme",
        "location": "Bogota",
        "source_url": "https://example.com/jobs/pm-1",
    }


def _vacancy_blocks() -> dict[str, object]:
    return {
        "contract_version": "vacancy_blocks.v1",
        "vacancy_id": "o-step3-001",
        "generated_at": "2026-04-21T19:00:00Z",
        "vacancy_blocks": {
            "work_conditions": ["Hibrido en Bogota", "Salario COP 12M a 18M"],
            "responsibilities": ["Liderar roadmap del producto"],
            "required_requirements": ["5 anos de experiencia en producto"],
            "desirable_requirements": ["MBA"],
            "benefits": ["Seguro medico"],
            "unclassified": [],
        },
        "warnings": [],
        "coverage_notes": [],
    }


class VacancyDimensionsServiceTests(unittest.TestCase):
    def test_extract_success_returns_normalized_vacancy_dimensions_contract(self) -> None:
        llm_response = (
            "{"
            "\"vacancy_dimensions\":{"
            "\"work_conditions\":{"
            "\"salary\":{\"raw_text\":\"Rango salarial COP 12M a 18M\"},"
            "\"modality\":{\"value\":\"Hibrido\",\"raw_text\":\"Hibrido en Bogota\"},"
            "\"location\":{\"places\":[\"Bogota\"],\"raw_text\":\"Bogota\"},"
            "\"contract_type\":{\"value\":\"Indefinido\",\"raw_text\":\"Contrato indefinido\"},"
            "\"other_conditions\":[{\"raw_text\":\"Disponibilidad para viajar ocasionalmente\"}]"
            "},"
            "\"responsibilities\":[{\"raw_text\":\"Liderar roadmap\"}],"
            "\"required_criteria\":[{\"raw_text\":\"5 anos de experiencia en producto\"}],"
            "\"desirable_criteria\":[{\"raw_text\":\"MBA deseable\"}],"
            "\"benefits\":[{\"raw_text\":\"Seguro medico\"}],"
            "\"about_the_company\":[{\"raw_text\":\"Empresa lider en tecnologia B2B\"}]"
            "}"
            "}"
        )

        with patch(
            "app.services.vacancy_dimensions_service.complete_prompt",
            return_value=llm_response,
        ):
            contract = extract_vacancy_dimensions(
                _opportunity(),
                _vacancy_blocks(),
                settings=object(),
            )

        self.assertEqual(contract["contract_version"], CONTRACT_VERSION_VACANCY_DIMENSIONS)
        self.assertEqual(contract["vacancy_id"], "o-step3-001")
        self.assertTrue(contract["generated_at"])
        payload = contract["vacancy_dimensions"]
        self.assertEqual(payload["work_conditions"]["salary"]["raw_text"], "Rango salarial COP 12M a 18M")
        self.assertEqual(payload["work_conditions"]["modality"]["value"], "Hibrido")
        self.assertEqual(payload["responsibilities"][0]["raw_text"], "Liderar roadmap")
        self.assertEqual(payload["required_criteria"][0]["raw_text"], "5 anos de experiencia en producto")
        self.assertEqual(payload["benefits"][0]["raw_text"], "Seguro medico")
        self.assertEqual(payload["about_the_company"][0]["raw_text"], "Empresa lider en tecnologia B2B")

    def test_extract_invalid_or_missing_step2_artifact_raises_controlled_error(self) -> None:
        with self.assertRaises(VacancyDimensionsExtractionError):
            extract_vacancy_dimensions(_opportunity(), {}, settings=object())

        with self.assertRaises(VacancyDimensionsExtractionError):
            extract_vacancy_dimensions(
                _opportunity(),
                {"contract_version": "legacy"},
                settings=object(),
            )

    def test_extract_normalizes_fixed_shape_and_ignores_unknown_root_keys(self) -> None:
        llm_response = (
            "{"
            "\"work_conditions\":{\"salary\":{\"raw_text\":\"\"}},"
            "\"responsibilities\":[{\"raw_text\":\"Coordinar equipo\"}],"
            "\"required_criteria\":[],"
            "\"desirable_criteria\":[],"
            "\"benefits\":[],"
            "\"about_the_company\":[],"
            "\"unknown_key\":{\"foo\":\"bar\"}"
            "}"
        )

        with patch(
            "app.services.vacancy_dimensions_service.complete_prompt",
            return_value=llm_response,
        ):
            contract = extract_vacancy_dimensions(
                _opportunity(),
                _vacancy_blocks(),
                settings=object(),
            )

        self.assertEqual(set(contract["vacancy_dimensions"].keys()), {
            "work_conditions",
            "responsibilities",
            "required_criteria",
            "desirable_criteria",
            "benefits",
            "about_the_company",
        })

    def test_extract_uses_dedicated_step3_prompt_flow_not_step2_flow(self) -> None:
        llm_response = (
            "{"
            "\"vacancy_dimensions\":{"
            "\"work_conditions\":{\"salary\":{\"raw_text\":\"COP 12M\"}},"
            "\"responsibilities\":[{\"raw_text\":\"Liderar roadmap\"}],"
            "\"required_criteria\":[],"
            "\"desirable_criteria\":[],"
            "\"benefits\":[],"
            "\"about_the_company\":[]"
            "}"
            "}"
        )

        with patch(
            "app.services.vacancy_dimensions_service.build_prompt_text",
            return_value="prompt listo",
        ) as prompt_builder_mock:
            with patch(
                "app.services.vacancy_dimensions_service.complete_prompt",
                return_value=llm_response,
            ) as complete_prompt_mock:
                extract_vacancy_dimensions(_opportunity(), _vacancy_blocks(), settings=object())

        self.assertEqual(
            prompt_builder_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_DIMENSIONS_EXTRACT,
        )
        self.assertNotEqual(
            prompt_builder_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_BLOCKS_EXTRACT,
        )
        self.assertEqual(
            complete_prompt_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_DIMENSIONS_EXTRACT,
        )
        self.assertNotEqual(
            complete_prompt_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_BLOCKS_EXTRACT,
        )
        fallback_prompt = str(prompt_builder_mock.call_args.kwargs.get("fallback", ""))
        self.assertIn("salary/compensation", fallback_prompt)
        self.assertIn("salary.raw_text", fallback_prompt)
        self.assertIn("about_the_company", fallback_prompt)
        self.assertIn("raw_text only", fallback_prompt)

    def test_extract_invalid_json_raises_controlled_error(self) -> None:
        with patch(
            "app.services.vacancy_dimensions_service.complete_prompt",
            return_value="not-json",
        ):
            with self.assertRaises(VacancyDimensionsExtractionError):
                extract_vacancy_dimensions(_opportunity(), _vacancy_blocks(), settings=object())

    def test_extract_uses_runtime_temperature_from_internal_vacancy_v2_schema(self) -> None:
        llm_response = (
            "{"
            "\"vacancy_dimensions\":{"
            "\"work_conditions\":{\"salary\":{\"raw_text\":\"COP 12M\"}},"
            "\"responsibilities\":[{\"raw_text\":\"Liderar roadmap\"}],"
            "\"required_criteria\":[],"
            "\"desirable_criteria\":[],"
            "\"benefits\":[],"
            "\"about_the_company\":[]"
            "}"
            "}"
        )

        with patch(
            "app.services.vacancy_dimensions_service.get_vacancy_v2_runtime_config",
            return_value={"step2": {"llm_temperature": 0.1}, "step3": {"llm_temperature": 0.44}},
        ):
            with patch(
                "app.services.vacancy_dimensions_service.complete_prompt",
                return_value=llm_response,
            ) as complete_prompt_mock:
                extract_vacancy_dimensions(_opportunity(), _vacancy_blocks(), settings=object())

        self.assertEqual(complete_prompt_mock.call_args.kwargs["temperature"], 0.44)


if __name__ == "__main__":
    unittest.main()
