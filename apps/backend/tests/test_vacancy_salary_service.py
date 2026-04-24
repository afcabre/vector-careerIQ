import unittest
from unittest.mock import patch

from app.services.prompt_config_store import FLOW_TASK_VACANCY_SALARY_NORMALIZE
from app.services.vacancy_salary_contract import CONTRACT_VERSION_VACANCY_SALARY_NORMALIZATION
from app.services.vacancy_salary_service import (
    VacancySalaryNormalizationError,
    extract_vacancy_salary_normalization,
)


def _opportunity() -> dict[str, str]:
    return {
        "opportunity_id": "o-salary-001",
        "person_id": "p-001",
        "title": "Senior Product Manager",
        "company": "Acme",
        "location": "Bogota",
        "source_url": "https://example.com/jobs/pm-1",
    }


def _vacancy_dimensions(*, salary_raw_text: str = "Salario COP 12M a 18M mensual") -> dict[str, object]:
    return {
        "contract_version": "vacancy_dimensions.v2",
        "vacancy_id": "o-salary-001",
        "generated_at": "2026-04-23T10:31:05Z",
        "vacancy_dimensions": {
            "work_conditions": {
                "salary": {"raw_text": salary_raw_text},
                "modality": {"value": "Hibrido", "raw_text": "Hibrido en Bogota"},
                "location": {"places": ["Bogota"], "raw_text": "Bogota"},
                "contract_type": {"value": "Indefinido", "raw_text": "Contrato indefinido"},
                "other_conditions": [],
            },
            "responsibilities": [],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
        },
    }


class VacancySalaryNormalizationServiceTests(unittest.TestCase):
    def test_extract_success_returns_normalized_salary_contract(self) -> None:
        llm_response = (
            "{"
            "\"salary\":{"
            "\"min\":\"12000000\","
            "\"max\":18000000,"
            "\"currency\":\" COP \","
            "\"period\":\" mensual \","
            "\"raw_text\":\"Salario COP 12M a 18M mensual\""
            "}"
            "}"
        )

        with patch(
            "app.services.vacancy_salary_service.complete_prompt",
            return_value=llm_response,
        ):
            contract = extract_vacancy_salary_normalization(
                _opportunity(),
                _vacancy_dimensions(),
                settings=object(),
            )

        self.assertEqual(
            contract["contract_version"],
            CONTRACT_VERSION_VACANCY_SALARY_NORMALIZATION,
        )
        self.assertEqual(contract["vacancy_id"], "o-salary-001")
        self.assertTrue(contract["generated_at"])
        self.assertEqual(contract["salary"]["min"], 12000000)
        self.assertEqual(contract["salary"]["max"], 18000000)
        self.assertEqual(contract["salary"]["currency"], "COP")
        self.assertEqual(contract["salary"]["period"], "mensual")

    def test_extract_requires_valid_dimensions_artifact_and_salary_signal(self) -> None:
        with self.assertRaises(VacancySalaryNormalizationError):
            extract_vacancy_salary_normalization(_opportunity(), {}, settings=object())

        with self.assertRaises(VacancySalaryNormalizationError):
            extract_vacancy_salary_normalization(
                _opportunity(),
                _vacancy_dimensions(salary_raw_text=""),
                settings=object(),
            )

    def test_extract_preserves_input_raw_text_when_llm_omits_it(self) -> None:
        llm_response = (
            "{"
            "\"salary\":{"
            "\"min\":\"12000000\","
            "\"max\":18000000,"
            "\"currency\":\"COP\","
            "\"period\":\"mensual\","
            "\"raw_text\":\"\""
            "}"
            "}"
        )

        with patch(
            "app.services.vacancy_salary_service.complete_prompt",
            return_value=llm_response,
        ):
            contract = extract_vacancy_salary_normalization(
                _opportunity(),
                _vacancy_dimensions(salary_raw_text="Salario COP 12M a 18M mensual"),
                settings=object(),
            )

        self.assertEqual(contract["salary"]["raw_text"], "Salario COP 12M a 18M mensual")

    def test_extract_uses_dedicated_salary_prompt_flow(self) -> None:
        llm_response = (
            "{"
            "\"salary\":{"
            "\"min\":null,"
            "\"max\":null,"
            "\"currency\":\"\","
            "\"period\":\"\","
            "\"raw_text\":\"Salario COP 12M a 18M mensual\""
            "}"
            "}"
        )

        with patch(
            "app.services.vacancy_salary_service.build_prompt_text",
            return_value="prompt listo",
        ) as prompt_builder_mock:
            with patch(
                "app.services.vacancy_salary_service.complete_prompt",
                return_value=llm_response,
            ) as complete_prompt_mock:
                extract_vacancy_salary_normalization(_opportunity(), _vacancy_dimensions(), settings=object())

        self.assertEqual(
            prompt_builder_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_SALARY_NORMALIZE,
        )
        self.assertEqual(
            complete_prompt_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_SALARY_NORMALIZE,
        )
        fallback_prompt = str(prompt_builder_mock.call_args.kwargs.get("fallback", ""))
        self.assertIn("Allowed keys inside salary", fallback_prompt)
        self.assertIn("Salary raw text", fallback_prompt)

    def test_extract_invalid_json_raises_controlled_error(self) -> None:
        with patch(
            "app.services.vacancy_salary_service.complete_prompt",
            return_value="not-json",
        ):
            with self.assertRaises(VacancySalaryNormalizationError):
                extract_vacancy_salary_normalization(_opportunity(), _vacancy_dimensions(), settings=object())

    def test_extract_uses_runtime_temperature_from_internal_vacancy_v2_schema(self) -> None:
        llm_response = (
            "{"
            "\"salary\":{"
            "\"min\":null,"
            "\"max\":null,"
            "\"currency\":\"\","
            "\"period\":\"\","
            "\"raw_text\":\"Salario COP 12M a 18M mensual\""
            "}"
            "}"
        )

        with patch(
            "app.services.vacancy_salary_service.get_vacancy_v2_runtime_config",
            return_value={"step2": {"llm_temperature": 0.1}, "step3": {"llm_temperature": 0.22}},
        ):
            with patch(
                "app.services.vacancy_salary_service.complete_prompt",
                return_value=llm_response,
            ) as complete_prompt_mock:
                extract_vacancy_salary_normalization(_opportunity(), _vacancy_dimensions(), settings=object())

        self.assertEqual(complete_prompt_mock.call_args.kwargs["temperature"], 0.22)


if __name__ == "__main__":
    unittest.main()
