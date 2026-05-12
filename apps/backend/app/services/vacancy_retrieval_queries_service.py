from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from difflib import SequenceMatcher
import json
import re
from typing import Any

from app.services.llm_service import FALLBACK_MESSAGE, complete_prompt
from app.services.ai_runtime_config_store import get_ai_runtime_config
from app.services.person_store import get_person
from app.services.prompt_config_store import (
    FLOW_TASK_VACANCY_RETRIEVAL_QUERIES_EXTRACT,
    build_prompt_text,
)
from app.services.vacancy_dimensions_enriched_contract import (
    is_vacancy_dimensions_enriched_contract,
    normalize_vacancy_dimensions_enriched_contract,
)
from app.services.vacancy_retrieval_queries_contract import (
    VacancyRetrievalQueriesContract,
    normalize_vacancy_retrieval_queries_contract,
)
from app.services.vacancy_salary_contract import (
    is_vacancy_salary_normalization_contract,
    normalize_vacancy_salary_normalization_contract,
)
from app.services.vacancy_v2_runtime_config import get_vacancy_v2_runtime_config


class VacancyRetrievalQueriesExtractionError(RuntimeError):
    pass


RETRIEVAL_ENABLED_GROUPS = (
    "responsibilities",
    "required_criteria",
    "desirable_criteria",
)

RETRIEVAL_DISABLED_GROUPS = (
    "benefits",
    "about_the_company",
    "work_conditions",
)

MAX_RETRIEVAL_PROBE_CHARS = 120
MAX_RETRIEVAL_QUERY_ATTEMPTS = 3
NEAR_DUPLICATE_SIMILARITY_THRESHOLD = 0.9
NEAR_DUPLICATE_JACCARD_THRESHOLD = 0.8
MIN_CRITERION_ANCHOR_SIMILARITY = 0.24
TEXT_SPLIT_PATTERN = re.compile(r"[^0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
SPANISH_HINTS = {
    "analisis",
    "años",
    "anos",
    "area",
    "arquitectura",
    "calidad",
    "candidato",
    "cargo",
    "cliente",
    "con",
    "conocimiento",
    "criterio",
    "datos",
    "de",
    "del",
    "desarrollo",
    "direccion",
    "diseno",
    "diseño",
    "en",
    "empresa",
    "equipo",
    "experiencia",
    "gestion",
    "gestión",
    "habilidades",
    "idioma",
    "liderazgo",
    "negocio",
    "para",
    "producto",
    "proyecto",
    "responsabilidades",
    "rol",
    "tecnologia",
    "tecnologías",
    "tecnologia",
    "trabajo",
    "trayectoria",
    "vacante",
    "años",
    "viajar",
    "y",
}
ENGLISH_HINTS = {
    "and",
    "architecture",
    "budget",
    "business",
    "candidate",
    "company",
    "data",
    "delivery",
    "design",
    "development",
    "engineer",
    "engineering",
    "experience",
    "for",
    "how",
    "leadership",
    "management",
    "manager",
    "product",
    "project",
    "responsibilities",
    "roadmap",
    "role",
    "stakeholder",
    "team",
    "the",
    "what",
    "with",
    "years",
    "your",
}
STOPWORD_TOKENS = {
    "a",
    "al",
    "an",
    "and",
    "con",
    "de",
    "del",
    "el",
    "en",
    "for",
    "la",
    "los",
    "of",
    "para",
    "por",
    "the",
    "un",
    "una",
    "with",
    "y",
}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _extract_json_object(raw_text: str) -> dict[str, object] | None:
    text = raw_text.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _contract_candidate_from_llm(parsed: dict[str, object]) -> dict[str, object]:
    if "queries" in parsed:
        return parsed
    return {"queries": parsed}


def _has_any_queries(contract: VacancyRetrievalQueriesContract) -> bool:
    payload = contract["queries"]
    return any(bool(payload[group]) for group in RETRIEVAL_ENABLED_GROUPS)


def _clear_disabled_retrieval_groups(contract: VacancyRetrievalQueriesContract) -> None:
    for group in RETRIEVAL_DISABLED_GROUPS:
        contract["queries"][group] = []


def _normalize_probe_text(value: str) -> str:
    return " ".join(TEXT_SPLIT_PATTERN.sub(" ", str(value or "").strip().casefold()).split())


def _tokenize_probe_text(value: str) -> list[str]:
    normalized = _normalize_probe_text(value)
    if not normalized:
        return []
    return [token for token in normalized.split() if token]


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in _tokenize_probe_text(value)
        if len(token) >= 2 and token not in STOPWORD_TOKENS
    }


def _detect_text_language(value: str) -> str:
    tokens = _tokenize_probe_text(value)
    if not tokens:
        return "unknown"
    spanish_score = sum(1 for token in tokens if token in SPANISH_HINTS)
    english_score = sum(1 for token in tokens if token in ENGLISH_HINTS)
    lowered = str(value or "").casefold()
    spanish_score += sum(lowered.count(char) for char in ("á", "é", "í", "ó", "ú", "ñ"))
    if spanish_score >= max(2, english_score + 1):
        return "es"
    if english_score >= max(2, spanish_score + 1):
        return "en"
    return "unknown"


def _vacancy_context_text(
    opportunity: dict[str, Any],
    vacancy_dimensions_enriched_artifact: VacancyRetrievalQueriesContract | dict[str, Any],
) -> str:
    parts = [
        str(opportunity.get("title", "")).strip(),
        str(opportunity.get("company", "")).strip(),
        str(opportunity.get("location", "")).strip(),
        str(opportunity.get("snapshot_raw_text", "")).strip(),
    ]
    vacancy_dimensions = (
        vacancy_dimensions_enriched_artifact.get("vacancy_dimensions", {})
        if isinstance(vacancy_dimensions_enriched_artifact, dict)
        else {}
    )
    if isinstance(vacancy_dimensions, dict):
        for group in ("responsibilities", "required_criteria", "desirable_criteria"):
            group_items = vacancy_dimensions.get(group)
            if not isinstance(group_items, list):
                continue
            for item in group_items:
                if not isinstance(item, dict):
                    continue
                parts.append(str(item.get("raw_text", "")).strip())
    return " ".join(part for part in parts if part)


def _person_has_explicit_spanish_profile(person_id: str) -> bool:
    person = get_person(person_id)
    if not person:
        return False
    languages = person.get("languages", [])
    if not isinstance(languages, list):
        return False
    for item in languages:
        if not isinstance(item, dict):
            continue
        language = _normalize_probe_text(item.get("language", ""))
        if language in {"es", "espanol", "español", "castellano", "spanish"}:
            return True
    return False


def _should_enforce_spanish_probes(
    opportunity: dict[str, Any],
    vacancy_dimensions_enriched_artifact: dict[str, Any],
) -> bool:
    vacancy_language = _detect_text_language(
        _vacancy_context_text(opportunity, vacancy_dimensions_enriched_artifact)
    )
    if vacancy_language != "es":
        return False
    person_id = str(opportunity.get("person_id", "")).strip()
    if not person_id:
        return False
    return _person_has_explicit_spanish_profile(person_id)


def _is_near_duplicate_probe(candidate: str, accepted: list[str]) -> bool:
    candidate_tokens = _content_tokens(candidate)
    candidate_normalized = _normalize_probe_text(candidate)
    for existing in accepted:
        existing_tokens = _content_tokens(existing)
        union = candidate_tokens | existing_tokens
        jaccard = (len(candidate_tokens & existing_tokens) / len(union)) if union else 0.0
        similarity = SequenceMatcher(
            None,
            candidate_normalized,
            _normalize_probe_text(existing),
        ).ratio()
        if similarity >= NEAR_DUPLICATE_SIMILARITY_THRESHOLD or jaccard >= NEAR_DUPLICATE_JACCARD_THRESHOLD:
            return True
    return False


def _has_anchor_overlap(query: str, criterion_text: str) -> bool:
    query_tokens = _content_tokens(query)
    criterion_tokens = _content_tokens(criterion_text)
    if not query_tokens or not criterion_tokens:
        return False
    if query_tokens & criterion_tokens:
        return True
    return (
        SequenceMatcher(
            None,
            _normalize_probe_text(query),
            _normalize_probe_text(criterion_text),
        ).ratio()
        >= MIN_CRITERION_ANCHOR_SIMILARITY
    )


def _invalid_probe_reason(
    query: str,
    *,
    criterion_text: str,
    enforce_spanish: bool,
    accepted_queries: list[str],
) -> str | None:
    cleaned = str(query or "").strip()
    if not cleaned:
        return "empty_probe"
    if "?" in cleaned:
        return "contains_question_mark"
    if len(cleaned) > MAX_RETRIEVAL_PROBE_CHARS:
        return "too_long"
    if enforce_spanish and _detect_text_language(cleaned) == "en":
        return "wrong_language_for_spanish_case"
    if not _has_anchor_overlap(cleaned, criterion_text):
        return "near_zero_lexical_overlap"
    if _is_near_duplicate_probe(cleaned, accepted_queries):
        return "near_duplicate"
    return None


def _validate_and_clean_contract(
    contract: VacancyRetrievalQueriesContract,
    *,
    enforce_spanish: bool,
) -> tuple[VacancyRetrievalQueriesContract, dict[str, Any]]:
    cleaned = normalize_vacancy_retrieval_queries_contract(contract)
    removed_reasons: Counter[str] = Counter()
    invalid_examples: list[str] = []
    emptied_items: list[str] = []

    for group in RETRIEVAL_ENABLED_GROUPS:
        cleaned_items = []
        for item in cleaned["queries"][group]:
            accepted_queries: list[str] = []
            original_queries = list(item.get("queries", []))
            for query in original_queries:
                reason = _invalid_probe_reason(
                    query,
                    criterion_text=item.get("raw_text", ""),
                    enforce_spanish=enforce_spanish,
                    accepted_queries=accepted_queries,
                )
                if reason:
                    removed_reasons[reason] += 1
                    if len(invalid_examples) < 5:
                        invalid_examples.append(
                            f"{item.get('item_id', '') or item.get('raw_text', '')}: {reason}: {query}"
                        )
                    continue
                accepted_queries.append(str(query).strip())
            item["queries"] = accepted_queries
            if original_queries and not accepted_queries:
                emptied_items.append(item.get("item_id", "") or item.get("raw_text", ""))
            cleaned_items.append(item)
        cleaned["queries"][group] = cleaned_items

    _clear_disabled_retrieval_groups(cleaned)
    return cleaned, {
        "removed_reasons": dict(removed_reasons),
        "invalid_examples": invalid_examples,
        "emptied_items": emptied_items,
    }


def _build_validation_feedback(report: dict[str, Any]) -> str:
    reasons = report.get("removed_reasons", {})
    if not isinstance(reasons, dict) or not reasons:
        return ""
    reason_summary = ", ".join(
        f"{reason}={count}" for reason, count in sorted(reasons.items())
    )
    feedback = (
        "Validation feedback for the previous attempt: some probes were rejected. "
        f"Rejected counts: {reason_summary}. "
        "Regenerate only short, declarative retrieval probes that stay close to the criterion anchors."
    )
    examples = report.get("invalid_examples", [])
    if isinstance(examples, list) and examples:
        feedback += " Invalid examples: " + " | ".join(str(example) for example in examples[:3])
    return feedback


def extract_vacancy_retrieval_queries(
    opportunity: dict[str, Any],
    vacancy_dimensions_enriched_artifact: dict[str, Any],
    vacancy_salary_artifact: dict[str, Any] | None,
    settings: Any,
) -> VacancyRetrievalQueriesContract:
    if not isinstance(vacancy_dimensions_enriched_artifact, dict) or not is_vacancy_dimensions_enriched_contract(vacancy_dimensions_enriched_artifact):
        raise VacancyRetrievalQueriesExtractionError(
            "Step 4 requires a valid vacancy_dimensions_enriched.v1 artifact."
        )

    normalized_enriched = normalize_vacancy_dimensions_enriched_contract(vacancy_dimensions_enriched_artifact)
    vacancy_id = normalized_enriched["vacancy_id"] or str(opportunity.get("opportunity_id", "")).strip()
    generated_at = _now_iso()
    enriched_json = json.dumps(normalized_enriched, ensure_ascii=False)

    salary_json = "{}"
    if isinstance(vacancy_salary_artifact, dict) and is_vacancy_salary_normalization_contract(vacancy_salary_artifact):
        salary_json = json.dumps(
            normalize_vacancy_salary_normalization_contract(vacancy_salary_artifact),
            ensure_ascii=False,
        )
    ai_runtime_config = get_ai_runtime_config()
    retrieval_queries_per_item = int(ai_runtime_config["vacancy_retrieval_queries_per_item"])

    system_prompt = (
        "You are a vacancy retrieval query generator. Return valid JSON only for vacancy_retrieval_queries.v1. "
        "Do not reclassify the vacancy. Do not generate categories. Do not decide compliance. "
        "Generate search queries that help retrieve evidence from the CV for each item. "
        "Queries must be short retrieval probes, not interview questions, not role-play prompts, and not compliance judgments. "
        "Use the dominant language of the vacancy and CV pair; if both are in Spanish, generate the probes in Spanish. "
        "Do not use question marks or second-person interview wording. "
        "Do not switch to English unnecessarily; preserve acronyms, proper nouns, and technology names when needed. "
        "Queries must be probative, not just semantically similar restatements of the requirement. "
        "When the criterion is abstract, translate it into observable signals such as roles, responsibilities, metrics, business outcomes, certifications, years of experience, budget ownership, stakeholder management, governance, architecture, cost optimization, profitability, delivery control, or transformation results. "
        f"For each item that merits queries, generate exactly {retrieval_queries_per_item} distinct useful queries with diverse probative angles."
    )
    fallback_user_prompt = (
        "Generate retrieval queries and respond with valid JSON only. "
        "Root key allowed: queries. "
        "Allowed keys inside queries: responsibilities, required_criteria, desirable_criteria, benefits, about_the_company, work_conditions. "
        "work_conditions must be a flat list of query items, not an object with subcategories. "
        "Generate non-empty queries only for responsibilities, required_criteria, and desirable_criteria. "
        "Keep benefits, about_the_company, and work_conditions present but empty. "
        "Each query item must include exactly: item_id, item_index, group_code, raw_text, queries. "
        "Use the metadata already present in the input items. Do not invent new ids or group codes. "
        "Queries should be phrased to retrieve evidence from the CV, not to summarize the vacancy. "
        "Use short retrieval probes rather than long sentences. "
        "Do not phrase the queries as questions. Do not use question marks. "
        "If the vacancy and CV context are in Spanish, write the probes in Spanish. "
        "Do not switch to English unnecessarily; preserve acronyms, proper nouns, and technology names only when needed. "
        "Avoid second-person interview wording such as 'can you', 'what is your', or 'how have you'. "
        "Prioritize observable evidence patterns such as equivalent responsibilities, measurable outcomes, technologies used, certifications, years of experience, business cases, budget ownership, stakeholder coordination, time-cost-scope control, efficiency gains, profitability, governance, standards, architecture, and transformation results. "
        "When a criterion is abstract, translate it into concrete observable evidence rather than merely repeating the wording of the vacancy. "
        f"For each item that merits queries, generate exactly {retrieval_queries_per_item} distinct useful queries with diverse probative angles. "
        "If an item does not justify a useful query, leave queries empty. "
        f"Vacancy title: {opportunity.get('title', '')}. "
        f"Company: {opportunity.get('company', '')}. "
        f"Location: {opportunity.get('location', '')}. "
        f"URL: {opportunity.get('source_url', '')}. "
        f"Input vacancy_dimensions_enriched.v1: {enriched_json}. "
        f"Input vacancy_salary_normalization.v1: {salary_json}"
    )
    user_prompt = build_prompt_text(
        flow_key=FLOW_TASK_VACANCY_RETRIEVAL_QUERIES_EXTRACT,
        context={
            "opportunity_title": str(opportunity.get("title", "")).strip(),
            "opportunity_company": str(opportunity.get("company", "")).strip(),
            "opportunity_location": str(opportunity.get("location", "")).strip(),
            "opportunity_url": str(opportunity.get("source_url", "")).strip(),
            "vacancy_dimensions_enriched_json": enriched_json,
            "vacancy_salary_json": salary_json,
            "retrieval_queries_per_item": str(retrieval_queries_per_item),
        },
        fallback=fallback_user_prompt,
    )

    runtime_config = get_vacancy_v2_runtime_config(settings)
    llm_temperature = float(runtime_config["step3"]["llm_temperature"])
    enforce_spanish = _should_enforce_spanish_probes(opportunity, normalized_enriched)
    validation_feedback = ""

    for attempt in range(MAX_RETRIEVAL_QUERY_ATTEMPTS):
        effective_user_prompt = user_prompt
        if validation_feedback:
            effective_user_prompt = f"{user_prompt}\n\n{validation_feedback}"

        response_text = complete_prompt(
            system_prompt,
            effective_user_prompt,
            settings,
            temperature=llm_temperature,
            person_id=str(opportunity.get("person_id", "")).strip(),
            opportunity_id=str(opportunity.get("opportunity_id", "")).strip(),
            flow_key=FLOW_TASK_VACANCY_RETRIEVAL_QUERIES_EXTRACT,
        )
        if not response_text or response_text == FALLBACK_MESSAGE:
            raise VacancyRetrievalQueriesExtractionError(
                "Step 4 LLM response unavailable; retrieval query extraction aborted."
            )

        parsed = _extract_json_object(response_text)
        if not parsed:
            raise VacancyRetrievalQueriesExtractionError(
                "Step 4 LLM response is not valid JSON; retrieval query extraction aborted."
            )

        candidate = _contract_candidate_from_llm(parsed)
        normalized = normalize_vacancy_retrieval_queries_contract(candidate)
        normalized["vacancy_id"] = vacancy_id
        normalized["generated_at"] = generated_at
        _clear_disabled_retrieval_groups(normalized)

        cleaned, validation_report = _validate_and_clean_contract(
            normalized,
            enforce_spanish=enforce_spanish,
        )
        if _has_any_queries(cleaned) and (
            not validation_report["emptied_items"] or attempt == MAX_RETRIEVAL_QUERY_ATTEMPTS - 1
        ):
            return cleaned
        validation_feedback = _build_validation_feedback(validation_report)

    raise VacancyRetrievalQueriesExtractionError(
        "Step 4 LLM response produced empty retrieval queries; extraction aborted."
    )
