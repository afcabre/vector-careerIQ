from datetime import UTC, datetime
from threading import Lock
from typing import Any, TypedDict

from app.core.settings import get_settings
from app.services.firestore_client import get_firestore_client


FLOW_SEARCH_JOBS_TAVILY = "search_jobs_tavily"
FLOW_SEARCH_CULTURE_TAVILY = "search_culture_tavily"


class PromptConfigRecord(TypedDict):
    config_id: str
    scope: str
    flow_key: str
    template_text: str
    target_sources: list[str]
    is_active: bool
    updated_by: str
    created_at: str
    updated_at: str


class _SafeDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""


_store_lock = Lock()
_prompt_configs: dict[str, PromptConfigRecord] = {}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _is_firestore_backend() -> bool:
    settings = get_settings()
    return settings.persistence_backend.lower() == "firestore"


def _compact_whitespace(text: str) -> str:
    return " ".join(text.split())


def _sanitize_sources(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        cleaned = _compact_whitespace(str(item).strip())
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def _required_placeholders(flow_key: str) -> set[str]:
    if flow_key == FLOW_SEARCH_JOBS_TAVILY:
        return {"query"}
    if flow_key == FLOW_SEARCH_CULTURE_TAVILY:
        return {"company"}
    return set()


def _default_configs() -> dict[str, PromptConfigRecord]:
    now = _now_iso()
    defaults: list[PromptConfigRecord] = [
        {
            "config_id": f"pc-{FLOW_SEARCH_JOBS_TAVILY}",
            "scope": "global",
            "flow_key": FLOW_SEARCH_JOBS_TAVILY,
            "template_text": (
                "Busca vacantes reales para {query}. "
                "Prioriza roles objetivo: {target_roles}. "
                "Skills clave: {skills}. "
                "Ubicacion objetivo: {person_location}. "
                "Enfoca fuentes de contratacion en: {target_sources}."
            ),
            "target_sources": [
                "site:linkedin.com/jobs",
                "site:greenhouse.io",
                "site:lever.co",
                "site:jobs.ashbyhq.com",
                "site:workdayjobs.com",
                "\"careers\"",
                "\"jobs\"",
                "\"trabaja con nosotros\"",
                "\"empleo\"",
                "\"vacantes\"",
            ],
            "is_active": True,
            "updated_by": "system",
            "created_at": now,
            "updated_at": now,
        },
        {
            "config_id": f"pc-{FLOW_SEARCH_CULTURE_TAVILY}",
            "scope": "global",
            "flow_key": FLOW_SEARCH_CULTURE_TAVILY,
            "template_text": (
                "Investiga cultura organizacional y condiciones de trabajo de {company} "
                "para roles {roles}. "
                "Prioriza fuentes oficiales de contratacion y empleo: {target_sources}."
            ),
            "target_sources": [
                "site:linkedin.com/company",
                "site:glassdoor.com",
                "site:comparably.com",
                "site:indeed.com/cmp",
                "site:greenhouse.io",
                "site:lever.co",
                "\"careers\"",
                "\"people\"",
                "\"culture\"",
                "\"employee experience\"",
            ],
            "is_active": True,
            "updated_by": "system",
            "created_at": now,
            "updated_at": now,
        },
    ]
    return {item["flow_key"]: item for item in defaults}


def _normalize_firestore_record(flow_key: str, payload: dict[str, Any] | None) -> PromptConfigRecord:
    defaults = _default_configs()
    base = defaults.get(flow_key)
    if not base:
        raise KeyError(flow_key)

    source = payload or {}
    target_sources = _sanitize_sources(source.get("target_sources", base["target_sources"]))
    if not target_sources:
        target_sources = base["target_sources"]

    return PromptConfigRecord(
        config_id=str(source.get("config_id", base["config_id"])),
        scope="global",
        flow_key=flow_key,
        template_text=str(source.get("template_text", base["template_text"])).strip()
        or base["template_text"],
        target_sources=target_sources,
        is_active=bool(source.get("is_active", base["is_active"])),
        updated_by=str(source.get("updated_by", base["updated_by"])).strip() or "system",
        created_at=str(source.get("created_at", base["created_at"])).strip() or base["created_at"],
        updated_at=str(source.get("updated_at", base["updated_at"])).strip() or base["updated_at"],
    )


def _validate_update(
    flow_key: str,
    template_text: str | None,
    target_sources: list[str] | None,
) -> tuple[str | None, list[str] | None]:
    defaults = _default_configs()
    if flow_key not in defaults:
        raise KeyError(flow_key)

    cleaned_template: str | None = None
    if template_text is not None:
        cleaned_template = template_text.strip()
        if not cleaned_template:
            raise ValueError("template_text cannot be empty")
        required = _required_placeholders(flow_key)
        for placeholder in required:
            token = "{" + placeholder + "}"
            if token not in cleaned_template:
                raise ValueError(f"template_text must include {token}")

    cleaned_sources: list[str] | None = None
    if target_sources is not None:
        cleaned_sources = _sanitize_sources(target_sources)
        if not cleaned_sources:
            raise ValueError("target_sources cannot be empty")

    return cleaned_template, cleaned_sources


def reset_prompt_configs() -> None:
    with _store_lock:
        _prompt_configs.clear()


def seed_prompt_configs() -> None:
    settings = get_settings()
    if not settings.firestore_seed_on_startup:
        return
    if not _is_firestore_backend():
        return

    client = get_firestore_client(settings)
    defaults = _default_configs()
    for flow_key, record in defaults.items():
        doc_ref = client.collection("prompt_configs").document(flow_key)
        if doc_ref.get().exists:
            continue
        doc_ref.set(record)


def list_prompt_configs() -> list[PromptConfigRecord]:
    defaults = _default_configs()

    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        items: dict[str, PromptConfigRecord] = {key: value.copy() for key, value in defaults.items()}
        for doc in client.collection("prompt_configs").stream():
            flow_key = doc.id
            if flow_key not in defaults:
                continue
            items[flow_key] = _normalize_firestore_record(flow_key, doc.to_dict())
        return [items[key] for key in sorted(items)]

    with _store_lock:
        items: dict[str, PromptConfigRecord] = {key: value.copy() for key, value in defaults.items()}
        for flow_key, value in _prompt_configs.items():
            if flow_key not in defaults:
                continue
            items[flow_key] = value.copy()
    return [items[key] for key in sorted(items)]


def get_prompt_config(flow_key: str) -> PromptConfigRecord:
    defaults = _default_configs()
    if flow_key not in defaults:
        raise KeyError(flow_key)

    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        snapshot = client.collection("prompt_configs").document(flow_key).get()
        if not snapshot.exists:
            return defaults[flow_key].copy()
        return _normalize_firestore_record(flow_key, snapshot.to_dict())

    with _store_lock:
        current = _prompt_configs.get(flow_key)
        if current:
            return current.copy()
    return defaults[flow_key].copy()


def update_prompt_config(
    flow_key: str,
    updated_by: str,
    template_text: str | None = None,
    target_sources: list[str] | None = None,
    is_active: bool | None = None,
) -> PromptConfigRecord:
    cleaned_template, cleaned_sources = _validate_update(
        flow_key=flow_key,
        template_text=template_text,
        target_sources=target_sources,
    )
    current = get_prompt_config(flow_key)
    now = _now_iso()

    if cleaned_template is not None:
        current["template_text"] = cleaned_template
    if cleaned_sources is not None:
        current["target_sources"] = cleaned_sources
    if is_active is not None:
        current["is_active"] = bool(is_active)

    current["updated_by"] = updated_by.strip() or "tutor"
    current["updated_at"] = now

    if _is_firestore_backend():
        settings = get_settings()
        client = get_firestore_client(settings)
        client.collection("prompt_configs").document(flow_key).set(current)
        return current

    with _store_lock:
        _prompt_configs[flow_key] = current
    return current


def build_prompt_query(flow_key: str, context: dict[str, str], fallback: str) -> str:
    fallback_clean = _compact_whitespace(fallback.strip())
    if not fallback_clean:
        return fallback_clean

    try:
        config = get_prompt_config(flow_key)
    except KeyError:
        return fallback_clean

    if not config["is_active"]:
        return fallback_clean

    template = config["template_text"].strip()
    if not template:
        return fallback_clean

    render_context = _SafeDict(
        {
            **{key: _compact_whitespace(str(value).strip()) for key, value in context.items()},
            "target_sources": " ".join(config["target_sources"]),
        }
    )
    rendered = _compact_whitespace(template.format_map(render_context))
    return rendered or fallback_clean
