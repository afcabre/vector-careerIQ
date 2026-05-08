import unittest
from unittest.mock import patch

from app.services.prompt_config_store import FLOW_TASK_VACANCY_EVIDENCE_ADJUDICATION
from app.services.vacancy_dimensions_enriched_contract import (
    normalize_vacancy_dimensions_enriched_contract,
)
from app.services.vacancy_evidence_adjudication_contract import (
    CONTRACT_VERSION_VACANCY_EVIDENCE_ADJUDICATION,
)
from app.services.vacancy_evidence_adjudication_service import (
    VacancyEvidenceAdjudicationBuildError,
    build_vacancy_evidence_adjudication,
)


def _person() -> dict[str, object]:
    return {
        "person_id": "p-001",
        "full_name": "Maria Gomez",
        "target_roles": ["Director TI"],
        "location": "Bogota",
        "years_experience": 20,
        "skills": ["Transformacion digital", "Arquitectura", "Power Platform"],
        "salary_expectation_min": 18000000,
        "salary_expectation_max": 25000000,
        "salary_currency": "COP",
        "salary_period": "monthly",
        "culture_preferences": ["claridad", "impacto"],
        "cultural_fit_preferences": {},
        "culture_preferences_notes": "Valora autonomia y foco en resultados.",
    }


def _opportunity() -> dict[str, object]:
    return {
        "opportunity_id": "o-001",
        "person_id": "p-001",
        "title": "Lider Estrategico en Transformacion Digital",
        "company": "Acme",
        "location": "Bogota",
        "source_url": "https://example.com/jobs/1",
        "snapshot_raw_text": "Vacante de liderazgo, transformacion digital y eficiencia operativa.",
        "vacancy_dimensions_artifact": {
            "contract_version": "vacancy_dimensions.v2",
            "vacancy_id": "o-001",
        },
        "vacancy_salary_artifact": {
            "contract_version": "vacancy_salary_normalization.v1",
            "vacancy_id": "o-001",
        },
    }


def _dimensions_enriched() -> dict[str, object]:
    return {
        "contract_version": "vacancy_dimensions_enriched.v1",
        "vacancy_id": "o-001",
        "generated_at": "2026-05-08T10:00:00Z",
        "vacancy_dimensions": {
            "work_conditions": [],
            "responsibilities": [
                {
                    "raw_text": "Liderar area de servicios digitales",
                    "item_id": "resp_1",
                    "item_index": 0,
                    "group_code": "resp",
                }
            ],
            "required_criteria": [
                {
                    "raw_text": "Minimo 5 anos de experiencia profesional",
                    "item_id": "req_1",
                    "item_index": 1,
                    "group_code": "req",
                }
            ],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
        },
    }


def _normalized_dimension_items() -> dict[str, dict[str, object]]:
    normalized = normalize_vacancy_dimensions_enriched_contract(_dimensions_enriched())
    return {
        "responsibility": normalized["vacancy_dimensions"]["responsibilities"][0],
        "required": normalized["vacancy_dimensions"]["required_criteria"][0],
    }


def _evidence_analysis() -> dict[str, object]:
    normalized_items = _normalized_dimension_items()
    responsibility = normalized_items["responsibility"]
    required = normalized_items["required"]
    return {
        "contract_version": "vacancy_evidence_analysis.v1",
        "vacancy_id": "o-001",
        "generated_at": "2026-05-08T10:01:00Z",
        "thresholds": {
            "strong_min": 0.75,
            "useful_min": 0.45,
            "review_min": 0.30,
        },
        "analysis": {
            "responsibilities": [
                {
                    "item_id": responsibility["item_id"],
                    "item_index": responsibility["item_index"],
                    "group_code": responsibility["group_code"],
                    "raw_text": "Liderar area de servicios digitales",
                    "item_status": "useful_evidence",
                    "best_score": 0.56,
                    "raw_match_count": 1,
                    "accepted_match_count": 1,
                    "discarded_match_count": 0,
                    "distinct_query_hits": 1,
                    "best_evidence": [
                        {
                            "source_ref": "cv:chunk:2",
                            "snippet": "Lidere equipos de servicios tecnologicos y transformacion.",
                            "best_score": 0.56,
                            "query_texts": ["liderazgo de servicios tecnologicos"],
                            "query_indexes": [0],
                            "section": "experience",
                            "block_type": "experience",
                            "block_title": "Experiencia",
                            "raw_match_count": 1,
                        }
                    ],
                    "accepted_matches": [],
                    "discarded_matches": [],
                }
            ],
            "required_criteria": [
                {
                    "item_id": required["item_id"],
                    "item_index": required["item_index"],
                    "group_code": required["group_code"],
                    "raw_text": "Minimo 5 anos de experiencia profesional",
                    "item_status": "strong_evidence",
                    "best_score": 0.92,
                    "raw_match_count": 1,
                    "accepted_match_count": 1,
                    "discarded_match_count": 0,
                    "distinct_query_hits": 1,
                    "best_evidence": [
                        {
                            "source_ref": "cv:chunk:1",
                            "snippet": "Profesional con 20 anos de experiencia.",
                            "best_score": 0.92,
                            "query_texts": ["anos de experiencia profesional"],
                            "query_indexes": [0],
                            "section": "profile_summary",
                            "block_type": "profile",
                            "block_title": "Perfil",
                            "raw_match_count": 1,
                        }
                    ],
                    "accepted_matches": [],
                    "discarded_matches": [],
                }
            ],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": [],
        },
    }


class VacancyEvidenceAdjudicationServiceTests(unittest.TestCase):
    def test_build_success_returns_normalized_contract(self) -> None:
        normalized_items = _normalized_dimension_items()
        responsibility = normalized_items["responsibility"]
        required = normalized_items["required"]
        llm_response = (
            "{"
            "\"items\":["
            "{"
            f"\"item_id\":\"{responsibility['item_id']}\","
            f"\"item_index\":{responsibility['item_index']},"
            "\"group\":\"responsibilities\","
            "\"group_code\":\"resp\","
            "\"raw_text\":\"Liderar area de servicios digitales\","
            "\"criterion_type\":\"leadership\","
            "\"priority\":\"important\","
            "\"alignment_status\":\"partial\","
            "\"evidence_strength\":\"medium\","
            "\"proof_summary\":\"Hay evidencia de liderazgo de servicios tecnologicos, aunque no del nombre literal del area.\","
            "\"best_supporting_evidence\":[{\"source_ref\":\"cv:chunk:2\",\"block_title\":\"Experiencia\",\"section\":\"experience\",\"snippet\":\"Lidere equipos de servicios tecnologicos y transformacion.\",\"why_it_supports\":\"Prueba liderazgo transferible de servicios tecnologicos.\"}],"
            "\"weak_or_discarded_evidence\":[],"
            "\"limitations\":[\"No aparece el nombre literal area de servicios digitales.\"],"
            "\"candidate_risk\":\"medium\","
            "\"cv_improvement_opportunity\":\"Conectar mejor el liderazgo de servicios con transformacion digital.\","
            "\"confidence\":\"medium\""
            "},"
            "{"
            f"\"item_id\":\"{required['item_id']}\","
            f"\"item_index\":{required['item_index']},"
            "\"group\":\"required_criteria\","
            "\"group_code\":\"req\","
            "\"raw_text\":\"Minimo 5 anos de experiencia profesional\","
            "\"criterion_type\":\"years_experience\","
            "\"priority\":\"important\","
            "\"alignment_status\":\"direct\","
            "\"evidence_strength\":\"high\","
            "\"proof_summary\":\"El CV declara 20 anos de experiencia profesional de forma explicita.\","
            "\"best_supporting_evidence\":[{\"source_ref\":\"cv:chunk:1\",\"block_title\":\"Perfil\",\"section\":\"profile_summary\",\"snippet\":\"Profesional con 20 anos de experiencia.\",\"why_it_supports\":\"Prueba de forma directa la antiguedad profesional.\"}],"
            "\"weak_or_discarded_evidence\":[],"
            "\"limitations\":[],"
            "\"candidate_risk\":\"low\","
            "\"cv_improvement_opportunity\":\"Mantener visible la antiguedad profesional en el resumen.\","
            "\"confidence\":\"high\""
            "}"
            "],"
            "\"warnings\":[]"
            "}"
        )

        with patch(
            "app.services.vacancy_evidence_adjudication_service.complete_prompt",
            return_value=llm_response,
        ):
            contract = build_vacancy_evidence_adjudication(
                person=_person(),
                opportunity=_opportunity(),
                vacancy_dimensions_enriched_artifact=_dimensions_enriched(),
                vacancy_evidence_analysis_artifact=_evidence_analysis(),
                settings=object(),
            )

        self.assertEqual(
            contract["contract_version"],
            CONTRACT_VERSION_VACANCY_EVIDENCE_ADJUDICATION,
        )
        self.assertEqual(contract["vacancy_id"], "o-001")
        self.assertEqual(len(contract["items"]), 2)
        self.assertEqual(contract["items"][0]["item_id"], responsibility["item_id"])
        self.assertEqual(contract["items"][1]["alignment_status"], "direct")

    def test_build_requires_valid_input_artifacts(self) -> None:
        with self.assertRaises(VacancyEvidenceAdjudicationBuildError):
            build_vacancy_evidence_adjudication(
                person=_person(),
                opportunity=_opportunity(),
                vacancy_dimensions_enriched_artifact={},
                vacancy_evidence_analysis_artifact=_evidence_analysis(),
                settings=object(),
            )

        with self.assertRaises(VacancyEvidenceAdjudicationBuildError):
            build_vacancy_evidence_adjudication(
                person=_person(),
                opportunity=_opportunity(),
                vacancy_dimensions_enriched_artifact=_dimensions_enriched(),
                vacancy_evidence_analysis_artifact={},
                settings=object(),
            )

    def test_build_uses_dedicated_prompt_flow(self) -> None:
        normalized_items = _normalized_dimension_items()
        responsibility = normalized_items["responsibility"]
        required = normalized_items["required"]
        llm_response = (
            "{"
            "\"items\":["
            f"{{\"item_id\":\"{responsibility['item_id']}\",\"item_index\":{responsibility['item_index']},\"group\":\"responsibilities\",\"group_code\":\"resp\",\"raw_text\":\"Liderar area de servicios digitales\",\"criterion_type\":\"leadership\",\"priority\":\"important\",\"alignment_status\":\"partial\",\"evidence_strength\":\"medium\",\"proof_summary\":\"Resumen\",\"best_supporting_evidence\":[],\"weak_or_discarded_evidence\":[],\"limitations\":[],\"candidate_risk\":\"low\",\"cv_improvement_opportunity\":\"\",\"confidence\":\"medium\"}},"
            f"{{\"item_id\":\"{required['item_id']}\",\"item_index\":{required['item_index']},\"group\":\"required_criteria\",\"group_code\":\"req\",\"raw_text\":\"Minimo 5 anos de experiencia profesional\",\"criterion_type\":\"years_experience\",\"priority\":\"important\",\"alignment_status\":\"direct\",\"evidence_strength\":\"high\",\"proof_summary\":\"Resumen\",\"best_supporting_evidence\":[],\"weak_or_discarded_evidence\":[],\"limitations\":[],\"candidate_risk\":\"low\",\"cv_improvement_opportunity\":\"\",\"confidence\":\"high\"}}"
            "],"
            "\"warnings\":[]"
            "}"
        )
        with patch(
            "app.services.vacancy_evidence_adjudication_service.complete_prompt",
            return_value=llm_response,
        ) as mocked_complete:
            build_vacancy_evidence_adjudication(
                person=_person(),
                opportunity=_opportunity(),
                vacancy_dimensions_enriched_artifact=_dimensions_enriched(),
                vacancy_evidence_analysis_artifact=_evidence_analysis(),
                settings=object(),
            )

        self.assertEqual(
            mocked_complete.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_EVIDENCE_ADJUDICATION,
        )


if __name__ == "__main__":
    unittest.main()
