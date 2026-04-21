import unittest
from unittest.mock import patch

from app.services.prompt_config_store import (
    FLOW_TASK_VACANCY_BLOCKS_EXTRACT,
    FLOW_TASK_VACANCY_PROFILE_EXTRACT,
)
from app.services.vacancy_blocks_contract import CONTRACT_VERSION_VACANCY_BLOCKS
from app.services.vacancy_blocks_service import VacancyBlocksExtractionError, extract_vacancy_blocks


def _opportunity(
    *,
    raw_text: str,
    opportunity_id: str = "o-test-001",
    person_id: str = "p-001",
) -> dict[str, str]:
    return {
        "opportunity_id": opportunity_id,
        "person_id": person_id,
        "title": "Senior Data Analyst",
        "company": "Acme",
        "location": "Bogota",
        "source_url": "https://example.com/jobs/1",
        "snapshot_raw_text": raw_text,
    }


class VacancyBlocksServiceTests(unittest.TestCase):
    def test_extract_success_returns_normalized_vacancy_blocks_contract(self) -> None:
        opportunity = _opportunity(raw_text="Texto de vacante para clasificar")
        response_payload = (
            "{"
            "\"vacancy_blocks\":{"
            "\"work_conditions\":[\" Hibrido en Bogota \"],"
            "\"responsibilities\":[\" Liderar backlog de datos \"],"
            "\"required_requirements\":[\"SQL avanzado\"],"
            "\"desirable_requirements\":[\"Ingles B2\"],"
            "\"benefits\":[\"Seguro medico\"],"
            "\"unclassified\":[\"Texto ambiguo\"]"
            "},"
            "\"warnings\":[\" Fragmento ambiguo \"],"
            "\"coverage_notes\":[\" sin salario explicito \"]"
            "}"
        )

        with patch(
            "app.services.vacancy_blocks_service.complete_prompt",
            return_value=response_payload,
        ):
            contract = extract_vacancy_blocks(opportunity, settings=object())  # type: ignore[arg-type]

        self.assertEqual(contract["contract_version"], CONTRACT_VERSION_VACANCY_BLOCKS)
        self.assertEqual(contract["vacancy_id"], "o-test-001")
        self.assertTrue(contract["generated_at"])
        self.assertEqual(contract["vacancy_blocks"]["work_conditions"], ["Hibrido en Bogota"])
        self.assertEqual(contract["vacancy_blocks"]["responsibilities"], ["Liderar backlog de datos"])
        self.assertEqual(contract["warnings"], ["Fragmento ambiguo"])
        self.assertEqual(contract["coverage_notes"], ["sin salario explicito"])

    def test_extract_missing_raw_text_raises_controlled_error(self) -> None:
        opportunity = _opportunity(raw_text="")

        with patch("app.services.vacancy_blocks_service.complete_prompt") as llm_mock:
            with self.assertRaises(VacancyBlocksExtractionError):
                extract_vacancy_blocks(opportunity, settings=object())  # type: ignore[arg-type]

        llm_mock.assert_not_called()

    def test_extract_normalizes_fixed_keys_and_ignores_unknown_output_keys(self) -> None:
        opportunity = _opportunity(raw_text="Vacante con requisitos")
        response_payload = (
            "{"
            "\"work_conditions\":[\" Hibrido \", \"hibrido\"],"
            "\"responsibilities\":[\"Liderar equipo\"],"
            "\"required_requirements\":[\"Python\"],"
            "\"desirable_requirements\":[],"
            "\"benefits\":[\"Bono anual\"],"
            "\"unclassified\":[\"Texto suelto\"],"
            "\"invented_root_key\":[\"Debe ignorarse\"],"
            "\"warnings\":[\" nota \", \"nota\"],"
            "\"coverage_notes\":[\" cobertura \"]"
            "}"
        )

        with patch(
            "app.services.vacancy_blocks_service.complete_prompt",
            return_value=response_payload,
        ):
            contract = extract_vacancy_blocks(opportunity, settings=object())  # type: ignore[arg-type]

        payload = contract["vacancy_blocks"]
        self.assertEqual(set(payload.keys()), {
            "work_conditions",
            "responsibilities",
            "required_requirements",
            "desirable_requirements",
            "benefits",
            "unclassified",
        })
        self.assertEqual(payload["work_conditions"], ["Hibrido"])
        self.assertEqual(contract["warnings"], ["nota"])
        self.assertEqual(contract["coverage_notes"], ["cobertura"])
        self.assertNotIn("invented_root_key", contract)

    def test_extract_uses_dedicated_step2_prompt_flow_not_legacy_extract_flow(self) -> None:
        opportunity = _opportunity(raw_text="Texto de vacante")
        minimal_response = (
            "{\"vacancy_blocks\":{\"work_conditions\":[],\"responsibilities\":[],"
            "\"required_requirements\":[],\"desirable_requirements\":[],"
            "\"benefits\":[],\"unclassified\":[\"Texto de vacante\"]},"
            "\"warnings\":[],\"coverage_notes\":[]}"
        )

        with patch(
            "app.services.vacancy_blocks_service.build_prompt_text",
            return_value="prompt listo",
        ) as prompt_builder_mock:
            with patch(
                "app.services.vacancy_blocks_service.complete_prompt",
                return_value=minimal_response,
            ) as complete_prompt_mock:
                extract_vacancy_blocks(opportunity, settings=object())  # type: ignore[arg-type]

        self.assertEqual(
            prompt_builder_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_BLOCKS_EXTRACT,
        )
        self.assertNotEqual(
            prompt_builder_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_PROFILE_EXTRACT,
        )
        self.assertEqual(
            complete_prompt_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_BLOCKS_EXTRACT,
        )
        self.assertNotEqual(
            complete_prompt_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_PROFILE_EXTRACT,
        )

    def test_extract_invalid_json_raises_controlled_error(self) -> None:
        opportunity = _opportunity(raw_text="Texto de vacante")
        with patch(
            "app.services.vacancy_blocks_service.complete_prompt",
            return_value="not-json",
        ):
            with self.assertRaises(VacancyBlocksExtractionError):
                extract_vacancy_blocks(opportunity, settings=object())  # type: ignore[arg-type]

    def test_extract_uses_runtime_temperature_from_internal_vacancy_v2_schema(self) -> None:
        opportunity = _opportunity(raw_text="Texto de vacante")
        response_payload = (
            "{\"vacancy_blocks\":{\"work_conditions\":[\"Hibrido\"],\"responsibilities\":[],"
            "\"required_requirements\":[],\"desirable_requirements\":[],\"benefits\":[],\"unclassified\":[]},"
            "\"warnings\":[],\"coverage_notes\":[]}"
        )

        with patch(
            "app.services.vacancy_blocks_service.get_vacancy_v2_runtime_config",
            return_value={"step2": {"llm_temperature": 0.33}, "step3": {"llm_temperature": 0.1}},
        ):
            with patch(
                "app.services.vacancy_blocks_service.complete_prompt",
                return_value=response_payload,
            ) as complete_prompt_mock:
                extract_vacancy_blocks(opportunity, settings=object())  # type: ignore[arg-type]

        self.assertEqual(complete_prompt_mock.call_args.kwargs["temperature"], 0.33)


if __name__ == "__main__":
    unittest.main()
