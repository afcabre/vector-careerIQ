from datetime import UTC, datetime
from threading import Lock
from typing import Any, TypedDict

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client


AI_RUNTIME_CONFIG_KEY = "global"
AI_RUNTIME_TOP_K_MIN = 4
AI_RUNTIME_TOP_K_MAX = 30
DEFAULT_TOP_K_SEMANTIC_ANALYSIS = 12
DEFAULT_TOP_K_SEMANTIC_INTERVIEW = 8
DEFAULT_TOP_K_SEMANTIC_PER_CRITERION = 6
CV_CHUNKING_STRATEGY_TOKEN_WINDOW = "token_window"
CV_CHUNKING_STRATEGY_SEMANTIC_SECTIONS = "semantic_sections"
CV_CHUNKING_STRATEGIES = {
    CV_CHUNKING_STRATEGY_TOKEN_WINDOW,
    CV_CHUNKING_STRATEGY_SEMANTIC_SECTIONS,
}
DEFAULT_CV_CHUNKING_STRATEGY = CV_CHUNKING_STRATEGY_SEMANTIC_SECTIONS
CV_MARKDOWN_EXTRACTION_MODE_HEURISTIC = "heuristic"
CV_MARKDOWN_EXTRACTION_MODE_PYMUPDF4LLM = "pymupdf4llm"
CV_MARKDOWN_EXTRACTION_MODES = {
    CV_MARKDOWN_EXTRACTION_MODE_HEURISTIC,
    CV_MARKDOWN_EXTRACTION_MODE_PYMUPDF4LLM,
}
DEFAULT_CV_MARKDOWN_EXTRACTION_MODE = CV_MARKDOWN_EXTRACTION_MODE_HEURISTIC
RETRIEVAL_EVIDENCE_PERSISTENCE_MODE_MINIMAL = "minimal"
RETRIEVAL_EVIDENCE_PERSISTENCE_MODE_FULL = "full"
RETRIEVAL_EVIDENCE_PERSISTENCE_MODES = {
    RETRIEVAL_EVIDENCE_PERSISTENCE_MODE_MINIMAL,
    RETRIEVAL_EVIDENCE_PERSISTENCE_MODE_FULL,
}
DEFAULT_RETRIEVAL_EVIDENCE_PERSISTENCE_MODE = RETRIEVAL_EVIDENCE_PERSISTENCE_MODE_MINIMAL
INTERVIEW_RESEARCH_MODE_GUIDED = "guided"
INTERVIEW_RESEARCH_MODE_ADAPTIVE = "adaptive"
INTERVIEW_RESEARCH_MODES = {
    INTERVIEW_RESEARCH_MODE_GUIDED,
    INTERVIEW_RESEARCH_MODE_ADAPTIVE,
}
INTERVIEW_RESEARCH_MAX_STEPS_MIN = 3
INTERVIEW_RESEARCH_MAX_STEPS_MAX = 8
DEFAULT_INTERVIEW_RESEARCH_MODE = INTERVIEW_RESEARCH_MODE_GUIDED
DEFAULT_INTERVIEW_RESEARCH_MAX_STEPS = 5
RETRIEVAL_QUERIES_PER_ITEM_MIN = 1
RETRIEVAL_QUERIES_PER_ITEM_MAX = 5
DEFAULT_VACANCY_RETRIEVAL_QUERIES_PER_ITEM = 4
DEFAULT_VACANCY_RETRIEVAL_SCORE_STRONG_MIN = 0.75
DEFAULT_VACANCY_RETRIEVAL_SCORE_USEFUL_MIN = 0.45
DEFAULT_VACANCY_RETRIEVAL_SCORE_REVIEW_MIN = 0.30


class AIRuntimeConfigRecord(TypedDict):
    config_key: str
    top_k_semantic_analysis: int
    top_k_semantic_interview: int
    top_k_semantic_per_criterion: int
    cv_chunking_strategy: str
    cv_markdown_extraction_mode: str
    retrieval_evidence_persistence_mode: str
    interview_research_mode: str
    interview_research_max_steps: int
    vacancy_retrieval_queries_per_item: int
    vacancy_retrieval_score_strong_min: float
    vacancy_retrieval_score_useful_min: float
    vacancy_retrieval_score_review_min: float
    trace_truncation_enabled: bool
    updated_by: str
    created_at: str
    updated_at: str


_store_lock = Lock()
_ai_runtime_config: AIRuntimeConfigRecord | None = None


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _is_firestore_backend() -> bool:
    settings = get_settings()
    return settings.persistence_backend.lower() == "firestore"


def _default_config() -> AIRuntimeConfigRecord:
    now = _now_iso()
    return AIRuntimeConfigRecord(
        config_key=AI_RUNTIME_CONFIG_KEY,
        top_k_semantic_analysis=DEFAULT_TOP_K_SEMANTIC_ANALYSIS,
        top_k_semantic_interview=DEFAULT_TOP_K_SEMANTIC_INTERVIEW,
        top_k_semantic_per_criterion=DEFAULT_TOP_K_SEMANTIC_PER_CRITERION,
        cv_chunking_strategy=DEFAULT_CV_CHUNKING_STRATEGY,
        cv_markdown_extraction_mode=DEFAULT_CV_MARKDOWN_EXTRACTION_MODE,
        retrieval_evidence_persistence_mode=DEFAULT_RETRIEVAL_EVIDENCE_PERSISTENCE_MODE,
        interview_research_mode=DEFAULT_INTERVIEW_RESEARCH_MODE,
        interview_research_max_steps=DEFAULT_INTERVIEW_RESEARCH_MAX_STEPS,
        vacancy_retrieval_queries_per_item=DEFAULT_VACANCY_RETRIEVAL_QUERIES_PER_ITEM,
        vacancy_retrieval_score_strong_min=DEFAULT_VACANCY_RETRIEVAL_SCORE_STRONG_MIN,
        vacancy_retrieval_score_useful_min=DEFAULT_VACANCY_RETRIEVAL_SCORE_USEFUL_MIN,
        vacancy_retrieval_score_review_min=DEFAULT_VACANCY_RETRIEVAL_SCORE_REVIEW_MIN,
        trace_truncation_enabled=True,
        updated_by="system",
        created_at=now,
        updated_at=now,
    )


def _coerce_top_k(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number < AI_RUNTIME_TOP_K_MIN:
        return AI_RUNTIME_TOP_K_MIN
    if number > AI_RUNTIME_TOP_K_MAX:
        return AI_RUNTIME_TOP_K_MAX
    return number


def _coerce_retrieval_queries_per_item(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number < RETRIEVAL_QUERIES_PER_ITEM_MIN:
        return RETRIEVAL_QUERIES_PER_ITEM_MIN
    if number > RETRIEVAL_QUERIES_PER_ITEM_MAX:
        return RETRIEVAL_QUERIES_PER_ITEM_MAX
    return number


def _coerce_score_threshold(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return number


def _normalize_firestore_record(payload: dict[str, Any] | None) -> AIRuntimeConfigRecord:
    base = _default_config()
    source = payload or {}
    raw_chunking_strategy = str(
        source.get("cv_chunking_strategy", base["cv_chunking_strategy"])
    ).strip().lower()
    normalized_chunking_strategy = (
        raw_chunking_strategy
        if raw_chunking_strategy in CV_CHUNKING_STRATEGIES
        else base["cv_chunking_strategy"]
    )
    raw_md_mode = str(
        source.get("cv_markdown_extraction_mode", base["cv_markdown_extraction_mode"])
    ).strip().lower()
    normalized_md_mode = (
        raw_md_mode
        if raw_md_mode in CV_MARKDOWN_EXTRACTION_MODES
        else base["cv_markdown_extraction_mode"]
    )
    raw_retrieval_persistence_mode = str(
        source.get(
            "retrieval_evidence_persistence_mode",
            base["retrieval_evidence_persistence_mode"],
        )
    ).strip().lower()
    normalized_retrieval_persistence_mode = (
        raw_retrieval_persistence_mode
        if raw_retrieval_persistence_mode in RETRIEVAL_EVIDENCE_PERSISTENCE_MODES
        else base["retrieval_evidence_persistence_mode"]
    )
    raw_mode = str(
        source.get("interview_research_mode", base["interview_research_mode"])
    ).strip().lower()
    normalized_mode = (
        raw_mode
        if raw_mode in INTERVIEW_RESEARCH_MODES
        else base["interview_research_mode"]
    )
    raw_max_steps = source.get(
        "interview_research_max_steps", base["interview_research_max_steps"]
    )
    try:
        max_steps = int(raw_max_steps)
    except (TypeError, ValueError):
        max_steps = base["interview_research_max_steps"]
    if max_steps < INTERVIEW_RESEARCH_MAX_STEPS_MIN:
        max_steps = INTERVIEW_RESEARCH_MAX_STEPS_MIN
    if max_steps > INTERVIEW_RESEARCH_MAX_STEPS_MAX:
        max_steps = INTERVIEW_RESEARCH_MAX_STEPS_MAX

    return AIRuntimeConfigRecord(
        config_key=AI_RUNTIME_CONFIG_KEY,
        top_k_semantic_analysis=_coerce_top_k(
            source.get("top_k_semantic_analysis"),
            base["top_k_semantic_analysis"],
        ),
        top_k_semantic_interview=_coerce_top_k(
            source.get("top_k_semantic_interview"),
            base["top_k_semantic_interview"],
        ),
        top_k_semantic_per_criterion=_coerce_top_k(
            source.get("top_k_semantic_per_criterion"),
            base["top_k_semantic_per_criterion"],
        ),
        cv_chunking_strategy=normalized_chunking_strategy,
        cv_markdown_extraction_mode=normalized_md_mode,
        retrieval_evidence_persistence_mode=normalized_retrieval_persistence_mode,
        interview_research_mode=normalized_mode,
        interview_research_max_steps=max_steps,
        vacancy_retrieval_queries_per_item=_coerce_retrieval_queries_per_item(
            source.get("vacancy_retrieval_queries_per_item"),
            base["vacancy_retrieval_queries_per_item"],
        ),
        vacancy_retrieval_score_strong_min=_coerce_score_threshold(
            source.get("vacancy_retrieval_score_strong_min"),
            base["vacancy_retrieval_score_strong_min"],
        ),
        vacancy_retrieval_score_useful_min=_coerce_score_threshold(
            source.get("vacancy_retrieval_score_useful_min"),
            base["vacancy_retrieval_score_useful_min"],
        ),
        vacancy_retrieval_score_review_min=_coerce_score_threshold(
            source.get("vacancy_retrieval_score_review_min"),
            base["vacancy_retrieval_score_review_min"],
        ),
        trace_truncation_enabled=bool(
            source.get("trace_truncation_enabled", base["trace_truncation_enabled"])
        ),
        updated_by=str(source.get("updated_by", base["updated_by"])).strip() or "system",
        created_at=str(source.get("created_at", base["created_at"])).strip() or base["created_at"],
        updated_at=str(source.get("updated_at", base["updated_at"])).strip() or base["updated_at"],
    )


def reset_ai_runtime_config() -> None:
    global _ai_runtime_config
    with _store_lock:
        _ai_runtime_config = None


def seed_ai_runtime_config() -> None:
    settings = get_settings()
    if not settings.firestore_seed_on_startup:
        return
    if not _is_firestore_backend():
        return

    client = get_firestore_client(settings)
    doc_ref = client.collection("ai_runtime_configs").document(AI_RUNTIME_CONFIG_KEY)
    if doc_ref.get().exists:
        return
    doc_ref.set(_default_config())


def get_ai_runtime_config() -> AIRuntimeConfigRecord:
    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        snapshot = client.collection("ai_runtime_configs").document(AI_RUNTIME_CONFIG_KEY).get()
        if not snapshot.exists:
            return _default_config()
        return _normalize_firestore_record(snapshot.to_dict())

    with _store_lock:
        if _ai_runtime_config is not None:
            return _ai_runtime_config.copy()
    return _default_config()


def _validate_top_k(value: int, field_name: str) -> int:
    number = int(value)
    if number < AI_RUNTIME_TOP_K_MIN or number > AI_RUNTIME_TOP_K_MAX:
        raise ValueError(
            f"{field_name} must be between {AI_RUNTIME_TOP_K_MIN} and {AI_RUNTIME_TOP_K_MAX}"
        )
    return number


def _validate_interview_mode(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in INTERVIEW_RESEARCH_MODES:
        allowed = ", ".join(sorted(INTERVIEW_RESEARCH_MODES))
        raise ValueError(f"interview_research_mode must be one of: {allowed}")
    return normalized


def _validate_interview_max_steps(value: int) -> int:
    number = int(value)
    if (
        number < INTERVIEW_RESEARCH_MAX_STEPS_MIN
        or number > INTERVIEW_RESEARCH_MAX_STEPS_MAX
    ):
        raise ValueError(
            "interview_research_max_steps must be between "
            f"{INTERVIEW_RESEARCH_MAX_STEPS_MIN} and {INTERVIEW_RESEARCH_MAX_STEPS_MAX}"
        )
    return number


def _validate_retrieval_queries_per_item(value: int) -> int:
    number = int(value)
    if (
        number < RETRIEVAL_QUERIES_PER_ITEM_MIN
        or number > RETRIEVAL_QUERIES_PER_ITEM_MAX
    ):
        raise ValueError(
            "vacancy_retrieval_queries_per_item must be between "
            f"{RETRIEVAL_QUERIES_PER_ITEM_MIN} and {RETRIEVAL_QUERIES_PER_ITEM_MAX}"
        )
    return number


def _validate_score_threshold(value: float, field_name: str) -> float:
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")
    return number


def _validate_cv_chunking_strategy(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in CV_CHUNKING_STRATEGIES:
        allowed = ", ".join(sorted(CV_CHUNKING_STRATEGIES))
        raise ValueError(f"cv_chunking_strategy must be one of: {allowed}")
    return normalized


def _validate_cv_markdown_extraction_mode(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in CV_MARKDOWN_EXTRACTION_MODES:
        allowed = ", ".join(sorted(CV_MARKDOWN_EXTRACTION_MODES))
        raise ValueError(f"cv_markdown_extraction_mode must be one of: {allowed}")
    return normalized


def _validate_retrieval_evidence_persistence_mode(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in RETRIEVAL_EVIDENCE_PERSISTENCE_MODES:
        allowed = ", ".join(sorted(RETRIEVAL_EVIDENCE_PERSISTENCE_MODES))
        raise ValueError(
            f"retrieval_evidence_persistence_mode must be one of: {allowed}"
        )
    return normalized


def _validate_vacancy_retrieval_score_threshold_order(
    strong_min: float,
    useful_min: float,
    review_min: float,
) -> None:
    if strong_min < useful_min:
        raise ValueError(
            "vacancy_retrieval_score_strong_min must be greater than or equal to "
            "vacancy_retrieval_score_useful_min"
        )
    if useful_min < review_min:
        raise ValueError(
            "vacancy_retrieval_score_useful_min must be greater than or equal to "
            "vacancy_retrieval_score_review_min"
        )


def update_ai_runtime_config(
    *,
    top_k_semantic_analysis: int | None = None,
    top_k_semantic_interview: int | None = None,
    top_k_semantic_per_criterion: int | None = None,
    cv_chunking_strategy: str | None = None,
    cv_markdown_extraction_mode: str | None = None,
    retrieval_evidence_persistence_mode: str | None = None,
    interview_research_mode: str | None = None,
    interview_research_max_steps: int | None = None,
    vacancy_retrieval_queries_per_item: int | None = None,
    vacancy_retrieval_score_strong_min: float | None = None,
    vacancy_retrieval_score_useful_min: float | None = None,
    vacancy_retrieval_score_review_min: float | None = None,
    trace_truncation_enabled: bool | None = None,
    updated_by: str,
) -> AIRuntimeConfigRecord:
    current = get_ai_runtime_config()

    if top_k_semantic_analysis is not None:
        current["top_k_semantic_analysis"] = _validate_top_k(
            top_k_semantic_analysis,
            "top_k_semantic_analysis",
        )
    if top_k_semantic_interview is not None:
        current["top_k_semantic_interview"] = _validate_top_k(
            top_k_semantic_interview,
            "top_k_semantic_interview",
        )
    if top_k_semantic_per_criterion is not None:
        current["top_k_semantic_per_criterion"] = _validate_top_k(
            top_k_semantic_per_criterion,
            "top_k_semantic_per_criterion",
        )
    if cv_chunking_strategy is not None:
        current["cv_chunking_strategy"] = _validate_cv_chunking_strategy(
            cv_chunking_strategy
        )
    if cv_markdown_extraction_mode is not None:
        current["cv_markdown_extraction_mode"] = _validate_cv_markdown_extraction_mode(
            cv_markdown_extraction_mode
        )
    if retrieval_evidence_persistence_mode is not None:
        current["retrieval_evidence_persistence_mode"] = (
            _validate_retrieval_evidence_persistence_mode(
                retrieval_evidence_persistence_mode
            )
        )
    if interview_research_mode is not None:
        current["interview_research_mode"] = _validate_interview_mode(
            interview_research_mode
        )
    if interview_research_max_steps is not None:
        current["interview_research_max_steps"] = _validate_interview_max_steps(
            interview_research_max_steps
        )
    if vacancy_retrieval_queries_per_item is not None:
        current["vacancy_retrieval_queries_per_item"] = _validate_retrieval_queries_per_item(
            vacancy_retrieval_queries_per_item
        )
    if vacancy_retrieval_score_strong_min is not None:
        current["vacancy_retrieval_score_strong_min"] = _validate_score_threshold(
            vacancy_retrieval_score_strong_min,
            "vacancy_retrieval_score_strong_min",
        )
    if vacancy_retrieval_score_useful_min is not None:
        current["vacancy_retrieval_score_useful_min"] = _validate_score_threshold(
            vacancy_retrieval_score_useful_min,
            "vacancy_retrieval_score_useful_min",
        )
    if vacancy_retrieval_score_review_min is not None:
        current["vacancy_retrieval_score_review_min"] = _validate_score_threshold(
            vacancy_retrieval_score_review_min,
            "vacancy_retrieval_score_review_min",
        )
    _validate_vacancy_retrieval_score_threshold_order(
        current["vacancy_retrieval_score_strong_min"],
        current["vacancy_retrieval_score_useful_min"],
        current["vacancy_retrieval_score_review_min"],
    )
    if trace_truncation_enabled is not None:
        current["trace_truncation_enabled"] = bool(trace_truncation_enabled)

    current["updated_by"] = updated_by.strip() or "tutor"
    current["updated_at"] = _now_iso()

    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        client.collection("ai_runtime_configs").document(AI_RUNTIME_CONFIG_KEY).set(current)
        return current

    global _ai_runtime_config
    with _store_lock:
        _ai_runtime_config = current
    return current
