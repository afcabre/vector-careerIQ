from typing import Iterator

from app.core.settings import Settings
from app.services.conversation_store import MessageRecord
from app.services.cv_store import get_active_cv
from app.services.person_store import PersonRecord

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - fallback path when package is missing.
    OpenAI = None  # type: ignore[assignment]


FALLBACK_MESSAGE = (
    "No pude consultar el proveedor LLM en este momento. El mensaje quedo "
    "registrado y puedes reintentar."
)


def _system_prompt(person: PersonRecord) -> str:
    target_roles = ", ".join(person["target_roles"]) or "sin rol objetivo definido"
    skills = ", ".join(person["skills"]) or "sin skills registradas"
    cv_context = ""
    active_cv = get_active_cv(person["person_id"])
    if active_cv:
        text = active_cv["extracted_text"].strip()
        if text:
            cv_context = text[:1200]
    return (
        "Eres un asistente de empleabilidad que responde para la persona consultada "
        "activa, nunca para el operador.\n"
        f"PERSONA: {person['full_name']}\n"
        f"UBICACION: {person['location']}\n"
        f"ROLES OBJETIVO: {target_roles}\n"
        f"SKILLS: {skills}\n"
        f"CONTEXTO_CV: {cv_context or 'sin CV activo'}\n"
        "Responde en espanol, de forma clara y accionable."
    )


def _history_messages(history: list[MessageRecord], max_items: int = 12) -> list[dict[str, str]]:
    trimmed = history[-max_items:]
    return [{"role": item["role"], "content": item["content"]} for item in trimmed]


def _build_messages(person: PersonRecord, history: list[MessageRecord]) -> list[dict[str, str]]:
    return [{"role": "system", "content": _system_prompt(person)}, *_history_messages(history)]


def _client(settings: Settings) -> OpenAI | None:
    if OpenAI is None or not settings.openai_api_key:
        return None
    try:
        return OpenAI(api_key=settings.openai_api_key)
    except Exception:
        return None


def generate_reply(
    person: PersonRecord,
    history: list[MessageRecord],
    settings: Settings,
) -> str:
    client = _client(settings)
    if client is None:
        return FALLBACK_MESSAGE

    try:
        response = client.chat.completions.create(
            model=settings.openai_chat_model,
            temperature=0.2,
            messages=_build_messages(person, history),
        )
    except Exception:
        return FALLBACK_MESSAGE

    if not response.choices:
        return FALLBACK_MESSAGE
    content = response.choices[0].message.content or ""
    content = content.strip()
    return content or FALLBACK_MESSAGE


def complete_prompt(
    system_prompt: str,
    user_prompt: str,
    settings: Settings,
    *,
    temperature: float = 0.2,
) -> str:
    client = _client(settings)
    if client is None:
        return FALLBACK_MESSAGE
    try:
        response = client.chat.completions.create(
            model=settings.openai_chat_model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception:
        return FALLBACK_MESSAGE

    if not response.choices:
        return FALLBACK_MESSAGE
    content = response.choices[0].message.content or ""
    return content.strip() or FALLBACK_MESSAGE


def stream_reply(
    person: PersonRecord,
    history: list[MessageRecord],
    settings: Settings,
) -> Iterator[str]:
    client = _client(settings)
    if client is None:
        for token in FALLBACK_MESSAGE.split(" "):
            yield f"{token} "
        return

    try:
        stream = client.chat.completions.create(
            model=settings.openai_chat_model,
            temperature=0.2,
            messages=_build_messages(person, history),
            stream=True,
        )
    except Exception:
        for token in FALLBACK_MESSAGE.split(" "):
            yield f"{token} "
        return

    emitted = False
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content or ""
        if not delta:
            continue
        emitted = True
        yield delta

    if not emitted:
        yield FALLBACK_MESSAGE
