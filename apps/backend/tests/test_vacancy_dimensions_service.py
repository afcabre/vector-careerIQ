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
        "flow": {
            "flow_key": "task_vacancy_blocks_extract",
            "contract_version": "vacancy_blocks.v2",
            "prompt_version": "2026-04-21T18:00:00Z",
        },
        "vacancy_id": "o-step3-001",
        "generated_at": "2026-04-21T19:00:00Z",
        "vacancy_blocks": {
            "about_the_company": [],
            "work_conditions": ["Hibrido en Bogota", "Salario COP 12M a 18M"],
            "responsibilities": ["Liderar roadmap del producto"],
            "required_requirements": ["5 anos de experiencia en producto"],
            "desirable_requirements": ["MBA"],
            "benefits": ["Seguro medico"],
            "unclassified": [],
        },
        "warnings": ["Fragmento ambiguo en S2", "fragmento ambiguo en S2"],
        "coverage_notes": ["S2 sin detalle de horario"],
    }


class VacancyDimensionsServiceTests(unittest.TestCase):
    def test_extract_success_returns_normalized_vacancy_dimensions_contract(self) -> None:
        llm_response = (
            "{"
            "\"vacancy_dimensions\":{"
            "\"work_conditions\":["
            "{\"raw_text\":\"Rango salarial COP 12M a 18M\"},"
            "{\"raw_text\":\"Hibrido en Bogota\"},"
            "{\"raw_text\":\"Disponibilidad para viajar ocasionalmente\"}"
            "],"
            "\"responsibilities\":[{\"raw_text\":\"Liderar roadmap\"}],"
            "\"required_criteria\":[{\"raw_text\":\"5 anos de experiencia en producto\"}],"
            "\"desirable_criteria\":[{\"raw_text\":\"MBA deseable\"}],"
            "\"benefits\":[{\"raw_text\":\"Seguro medico\"}],"
            "\"about_the_company\":[{\"raw_text\":\"Empresa lider en tecnologia B2B\"}],"
            "\"unclassified\":[]"
            "},"
            "\"warnings\":[\"Fragmento ambiguo conservado en la dimension mas probable\"],"
            "\"coverage_notes\":[\"Transformacion parcial de condiciones\"]"
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
        self.assertEqual(
            payload["work_conditions"],
            [
                {"raw_text": "Rango salarial COP 12M a 18M"},
                {"raw_text": "Hibrido en Bogota"},
                {"raw_text": "Disponibilidad para viajar ocasionalmente"},
            ],
        )
        self.assertEqual(payload["responsibilities"][0]["raw_text"], "Liderar roadmap")
        self.assertEqual(payload["required_criteria"][0]["raw_text"], "5 anos de experiencia en producto")
        self.assertEqual(payload["benefits"][0]["raw_text"], "Seguro medico")
        self.assertEqual(payload["about_the_company"][0]["raw_text"], "Empresa lider en tecnologia B2B")
        self.assertEqual(payload["unclassified"], [])
        self.assertEqual(
            contract["warnings"],
            [
                "Fragmento ambiguo en S2",
                "Fragmento ambiguo conservado en la dimension mas probable",
            ],
        )
        self.assertEqual(
            contract["coverage_notes"],
            ["S2 sin detalle de horario", "Transformacion parcial de condiciones"],
        )
        self.assertNotIn("warnings", payload)
        self.assertNotIn("coverage_notes", payload)

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
            "\"work_conditions\":[],"
            "\"responsibilities\":[{\"raw_text\":\"Coordinar equipo\"}],"
            "\"required_criteria\":[],"
            "\"desirable_criteria\":[],"
            "\"benefits\":[],"
            "\"about_the_company\":[],"
            "\"unclassified\":[\"Texto no transformable\"],"
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
            "unclassified",
        })

    def test_extract_uses_dedicated_step3_prompt_flow_not_step2_flow(self) -> None:
        llm_response = (
            "{"
            "\"vacancy_dimensions\":{"
            "\"work_conditions\":[{\"raw_text\":\"COP 12M\"}],"
            "\"responsibilities\":[{\"raw_text\":\"Liderar roadmap\"}],"
            "\"required_criteria\":[],"
            "\"desirable_criteria\":[],"
            "\"benefits\":[],"
            "\"about_the_company\":[],"
            "\"unclassified\":[]"
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
        self.assertIn("Step 3.1", fallback_prompt)
        self.assertIn("about_the_company", fallback_prompt)
        self.assertIn("coverage_notes", fallback_prompt)
        self.assertIn("raw_text only", fallback_prompt)
        self.assertIn("too abstract", fallback_prompt)
        self.assertIn("minimum explicit context", fallback_prompt)
        self.assertIn("reclassify it into required_criteria or responsibilities", fallback_prompt)

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
            "\"work_conditions\":[{\"raw_text\":\"COP 12M\"}],"
            "\"responsibilities\":[{\"raw_text\":\"Liderar roadmap\"}],"
            "\"required_criteria\":[],"
            "\"desirable_criteria\":[],"
            "\"benefits\":[],"
            "\"about_the_company\":[],"
            "\"unclassified\":[]"
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

    def test_extract_reclassifies_profile_like_about_company_fragments(self) -> None:
        llm_response = (
            "{"
            "\"vacancy_dimensions\":{"
            "\"work_conditions\":[],"
            "\"responsibilities\":[],"
            "\"required_criteria\":[],"
            "\"desirable_criteria\":[],"
            "\"benefits\":[],"
            "\"about_the_company\":["
            "{\"raw_text\":\"En Asssiprex nos encontramos en la busqueda de un Gerente de Tecnologia, un perfil estrategico con la capacidad de articular tecnologia, negocio y operacion, liderando la evolucion tecnologica de la organizacion en un entorno de alta exigencia.\"},"
            "{\"raw_text\":\"Compania multinacional con presencia en 12 paises\"}"
            "],"
            "\"unclassified\":[]"
            "},"
            "\"warnings\":[],"
            "\"coverage_notes\":[]"
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

        payload = contract["vacancy_dimensions"]
        self.assertEqual(
            payload["about_the_company"],
            [{"raw_text": "Compania multinacional con presencia en 12 paises"}],
        )
        self.assertEqual(
            payload["required_criteria"],
            [
                {
                    "raw_text": "En Asssiprex nos encontramos en la busqueda de un Gerente de Tecnologia, un perfil estrategico con la capacidad de articular tecnologia, negocio y operacion, liderando la evolucion tecnologica de la organizacion en un entorno de alta exigencia."
                }
            ],
        )
        self.assertTrue(
            any(
                "reclassified one or more about_the_company fragments into required_criteria"
                in warning
                for warning in contract["warnings"]
            )
        )


if __name__ == "__main__":
    unittest.main()
