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


class AIRuntimeConfigRecord(TypedDict):
    config_key: str
    top_k_semantic_analysis: int
    top_k_semantic_interview: int
    interview_research_mode: str
    interview_research_max_steps: int
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
        interview_research_mode=DEFAULT_INTERVIEW_RESEARCH_MODE,
        interview_research_max_steps=DEFAULT_INTERVIEW_RESEARCH_MAX_STEPS,
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


def _normalize_firestore_record(payload: dict[str, Any] | None) -> AIRuntimeConfigRecord:
    base = _default_config()
    source = payload or {}
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
        interview_research_mode=normalized_mode,
        interview_research_max_steps=max_steps,
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


def update_ai_runtime_config(
    *,
    top_k_semantic_analysis: int | None = None,
    top_k_semantic_interview: int | None = None,
    interview_research_mode: str | None = None,
    interview_research_max_steps: int | None = None,
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
    if interview_research_mode is not None:
        current["interview_research_mode"] = _validate_interview_mode(
            interview_research_mode
        )
    if interview_research_max_steps is not None:
        current["interview_research_max_steps"] = _validate_interview_max_steps(
            interview_research_max_steps
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
