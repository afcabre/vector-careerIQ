import unittest
from unittest.mock import patch

from app.services.prompt_config_store import FLOW_TASK_VACANCY_RETRIEVAL_QUERIES_EXTRACT
from app.services.vacancy_retrieval_queries_contract import CONTRACT_VERSION_VACANCY_RETRIEVAL_QUERIES
from app.services.vacancy_retrieval_queries_service import (
    VacancyRetrievalQueriesExtractionError,
    extract_vacancy_retrieval_queries,
)


def _opportunity() -> dict[str, str]:
    return {
        "opportunity_id": "o-q-001",
        "person_id": "p-001",
        "title": "Senior Product Manager",
        "company": "Acme",
        "location": "Bogota",
        "source_url": "https://example.com/jobs/pm-1",
    }


def _vacancy_dimensions_enriched() -> dict[str, object]:
    return {
        "contract_version": "vacancy_dimensions_enriched.v1",
        "vacancy_id": "o-q-001",
        "generated_at": "2026-04-24T10:31:05Z",
        "vacancy_dimensions": {
            "work_conditions": [
                {
                    "raw_text": "Disponibilidad para viajar",
                    "item_id": "cond_123",
                    "item_index": 0,
                    "group_code": "cond",
                }
            ],
            "responsibilities": [
                {
                    "raw_text": "Liderar roadmap",
                    "item_id": "resp_123",
                    "item_index": 0,
                    "group_code": "resp",
                }
            ],
            "required_criteria": [
                {
                    "raw_text": "5 anos de experiencia en producto",
                    "item_id": "req_123",
                    "item_index": 0,
                    "group_code": "req",
                }
            ],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
        },
    }


def _vacancy_salary() -> dict[str, object]:
    return {
        "contract_version": "vacancy_salary_normalization.v1",
        "vacancy_id": "o-q-001",
        "generated_at": "2026-04-24T10:33:00Z",
        "salary": {
            "min": 12000000,
            "max": 18000000,
            "currency": "COP",
            "period": "mensual",
            "raw_text": "Salario COP 12M a 18M mensual",
        },
    }


class VacancyRetrievalQueriesServiceTests(unittest.TestCase):
    def test_extract_success_returns_normalized_queries_contract(self) -> None:
        llm_response = (
            "{"
            "\"queries\":{"
            "\"responsibilities\":[{\"item_id\":\"resp_123\",\"item_index\":0,\"group_code\":\"resp\",\"raw_text\":\"Liderar roadmap\",\"queries\":[\"liderazgo de producto, gestion de roadmap, direccion de backlog\"]}],"
            "\"required_criteria\":[{\"item_id\":\"req_123\",\"item_index\":0,\"group_code\":\"req\",\"raw_text\":\"5 anos de experiencia en producto\",\"queries\":[\"experiencia gestionando producto digital, product management senior\"]}],"
            "\"desirable_criteria\":[],"
            "\"benefits\":[{\"item_id\":\"ben_123\",\"item_index\":0,\"group_code\":\"ben\",\"raw_text\":\"Seguro medico\",\"queries\":[\"seguro medico beneficios laborales\"]}],"
            "\"about_the_company\":[{\"item_id\":\"comp_123\",\"item_index\":0,\"group_code\":\"comp\",\"raw_text\":\"Empresa B2B\",\"queries\":[\"empresa b2b tecnologia\"]}],"
            "\"work_conditions\":[{\"item_id\":\"cond_123\",\"item_index\":0,\"group_code\":\"cond\",\"raw_text\":\"Disponibilidad para viajar\",\"queries\":[\"disponibilidad para viajar experiencia profesional\"]}]"
            "}"
            "}"
        )

        with patch(
            "app.services.vacancy_retrieval_queries_service.complete_prompt",
            return_value=llm_response,
        ):
            contract = extract_vacancy_retrieval_queries(
                _opportunity(),
                _vacancy_dimensions_enriched(),
                _vacancy_salary(),
                settings=object(),
            )

        self.assertEqual(contract["contract_version"], CONTRACT_VERSION_VACANCY_RETRIEVAL_QUERIES)
        self.assertEqual(contract["vacancy_id"], "o-q-001")
        self.assertTrue(contract["generated_at"])
        self.assertEqual(contract["queries"]["responsibilities"][0]["group_code"], "resp")
        self.assertEqual(contract["queries"]["required_criteria"][0]["group_code"], "req")
        self.assertEqual(contract["queries"]["benefits"], [])
        self.assertEqual(contract["queries"]["about_the_company"], [])
        self.assertEqual(contract["queries"]["work_conditions"], [])

    def test_extract_requires_valid_enriched_artifact(self) -> None:
        with self.assertRaises(VacancyRetrievalQueriesExtractionError):
            extract_vacancy_retrieval_queries(_opportunity(), {}, _vacancy_salary(), settings=object())

    def test_extract_uses_dedicated_prompt_flow(self) -> None:
        llm_response = (
            "{"
            "\"queries\":{"
            "\"responsibilities\":[{\"item_id\":\"resp_123\",\"item_index\":0,\"group_code\":\"resp\",\"raw_text\":\"Liderar roadmap\",\"queries\":[\"liderazgo de producto\"]}],"
            "\"required_criteria\":[],"
            "\"desirable_criteria\":[],"
            "\"benefits\":[],"
            "\"about_the_company\":[],"
            "\"work_conditions\":[]"
            "}"
            "}"
        )

        with patch(
            "app.services.vacancy_retrieval_queries_service.build_prompt_text",
            return_value="prompt listo",
        ) as prompt_builder_mock:
            with patch(
                "app.services.vacancy_retrieval_queries_service.get_ai_runtime_config",
                return_value={"vacancy_retrieval_queries_per_item": 3},
            ):
                with patch(
                    "app.services.vacancy_retrieval_queries_service.complete_prompt",
                    return_value=llm_response,
                ) as complete_prompt_mock:
                    extract_vacancy_retrieval_queries(
                        _opportunity(),
                        _vacancy_dimensions_enriched(),
                        _vacancy_salary(),
                        settings=object(),
                    )

        self.assertEqual(
            prompt_builder_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_RETRIEVAL_QUERIES_EXTRACT,
        )
        self.assertEqual(
            prompt_builder_mock.call_args.kwargs["context"]["retrieval_queries_per_item"],
            "3",
        )
        self.assertEqual(
            complete_prompt_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_RETRIEVAL_QUERIES_EXTRACT,
        )
        fallback_prompt = str(prompt_builder_mock.call_args.kwargs.get("fallback", ""))
        self.assertIn("responsibilities, required_criteria, and desirable_criteria", fallback_prompt)
        self.assertIn("benefits, about_the_company, and work_conditions", fallback_prompt)
        self.assertIn("observable evidence", fallback_prompt)
        self.assertIn("budget ownership", fallback_prompt)
        self.assertIn("Do not phrase the queries as questions", fallback_prompt)
        self.assertIn("write the probes in Spanish", fallback_prompt)
        self.assertIn("Do not switch to English unnecessarily", fallback_prompt)

    def test_extract_invalid_json_raises_controlled_error(self) -> None:
        with patch(
            "app.services.vacancy_retrieval_queries_service.complete_prompt",
            return_value="not-json",
        ):
            with self.assertRaises(VacancyRetrievalQueriesExtractionError):
                extract_vacancy_retrieval_queries(
                    _opportunity(),
                    _vacancy_dimensions_enriched(),
                    _vacancy_salary(),
                    settings=object(),
                )


if __name__ == "__main__":
    unittest.main()
