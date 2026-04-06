from datetime import UTC, datetime
import json
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.settings import Settings
from app.services.llm_service import FALLBACK_MESSAGE, complete_prompt
from app.services.opportunity_store import OpportunityRecord
from app.services.person_store import PersonRecord


class CulturalSignal(TypedDict):
    source_provider: str
    source_url: str
    title: str
    snippet: str
    captured_at: str


class AnalyzeResult(TypedDict):
    analysis_text: str
    cultural_confidence: str
    cultural_warnings: list[str]
    cultural_signals: list[CulturalSignal]


class PreparationResult(TypedDict):
    guidance_text: str
    cover_letter: str
    experience_summary: str


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _short_text(raw: str, max_chars: int = 420) -> str:
    text = (raw or "").strip()
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}..."


def _company_name(opportunity: OpportunityRecord) -> str:
    company = opportunity["company"].strip()
    if company:
        return company
    source_url = opportunity["source_url"].strip()
    host = urlparse(source_url).netloc.replace("www.", "")
    if not host:
        return "empresa objetivo"
    return host.split(".")[0].replace("-", " ").title()


def _person_context(person: PersonRecord) -> str:
    preferences = person.get("culture_preferences", [])
    if isinstance(preferences, list):
        culture_preferences = ", ".join([str(item) for item in preferences if str(item).strip()])
    else:
        culture_preferences = str(preferences or "").strip()
    if not culture_preferences:
        culture_preferences = "no declaradas en perfil V1"

    return (
        f"Persona consultada: {person['full_name']}\n"
        f"Ubicacion: {person['location']}\n"
        f"Roles objetivo: {', '.join(person['target_roles'])}\n"
        f"Skills: {', '.join(person['skills'])}\n"
        f"Experiencia aproximada: {person['years_experience']} anos\n"
        f"Preferencias culturales declaradas: {culture_preferences}"
    )


def _opportunity_context(opportunity: OpportunityRecord) -> str:
    return (
        f"Vacante: {opportunity['title']}\n"
        f"Empresa: {opportunity['company']}\n"
        f"Ubicacion: {opportunity['location']}\n"
        f"URL: {opportunity['source_url']}\n"
        f"Descripcion: {opportunity['snapshot_raw_text']}"
    )


def _tavily_culture_signals(
    person: PersonRecord,
    opportunity: OpportunityRecord,
    settings: Settings,
    max_results: int = 4,
) -> tuple[list[CulturalSignal], list[str]]:
    warnings: list[str] = []
    if not settings.tavily_api_key:
        warnings.append("No Tavily API key: fit cultural con evidencia externa limitada")
        return [], warnings

    company = _company_name(opportunity)
    roles = ", ".join(person["target_roles"][:2]).strip()
    query = (
        f"{company} company culture values leadership work environment employee experience "
        f"{roles}"
    ).strip()

    payload = json.dumps(
        {
            "api_key": settings.tavily_api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
        }
    ).encode("utf-8")
    request = Request(
        url="https://api.tavily.com/search",
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
        body = json.loads(raw)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        warnings.append("No fue posible consultar Tavily para señales culturales")
        return [], warnings
    except Exception:
        warnings.append("Error inesperado al consultar señales culturales externas")
        return [], warnings

    signals: list[CulturalSignal] = []
    for result in body.get("results", []):
        url = str(result.get("url", "")).strip()
        title = str(result.get("title", "")).strip()
        snippet = _short_text(str(result.get("content", "")))
        if not (url or title or snippet):
            continue
        signals.append(
            {
                "source_provider": "tavily",
                "source_url": url,
                "title": title or "Fuente sin titulo",
                "snippet": snippet or "Sin snippet disponible",
                "captured_at": _now_iso(),
            }
        )

    if not signals:
        warnings.append("Sin evidencia cultural externa suficiente para la empresa objetivo")
    elif len(signals) < 2:
        warnings.append("Evidencia cultural debil: pocas fuentes externas")

    return signals, warnings


def _cultural_confidence(signals_count: int) -> str:
    if signals_count <= 0:
        return "low"
    if signals_count == 1:
        return "low"
    if signals_count <= 3:
        return "medium"
    return "medium_high"


def _cultural_evidence_context(signals: list[CulturalSignal]) -> str:
    if not signals:
        return "Sin evidencia externa disponible."
    lines: list[str] = []
    for index, signal in enumerate(signals, start=1):
        lines.append(
            f"[{index}] {signal['title']} | {signal['source_url']} | {signal['snippet']}"
        )
    return "\n".join(lines)


def analyze_opportunity(
    person: PersonRecord,
    opportunity: OpportunityRecord,
    settings: Settings,
) -> AnalyzeResult:
    signals, warnings = _tavily_culture_signals(person, opportunity, settings)
    confidence = _cultural_confidence(len(signals))
    system_prompt = (
        "Eres un asistente de empleabilidad. Entrega analisis cualitativo y accionable.\n"
        "Para fit cultural: evita conclusiones absolutas, declara vacios de evidencia "
        "y nivel de confianza."
    )
    user_prompt = (
        "Analiza ajuste perfil-vacante y fit cultural.\n"
        "Formato:\n"
        "1) Ajuste general\n"
        "2) Fortalezas\n"
        "3) Brechas\n"
        "4) Fit cultural (incluye nivel de confianza y vacios)\n"
        "5) Recomendacion accionable\n\n"
        f"{_person_context(person)}\n\n"
        f"{_opportunity_context(opportunity)}\n\n"
        "Evidencia cultural externa recopilada:\n"
        f"{_cultural_evidence_context(signals)}\n\n"
        "Si la evidencia externa es debil o contradictoria, dilo explicitamente."
    )
    response = complete_prompt(system_prompt, user_prompt, settings, temperature=0.2)
    if response == FALLBACK_MESSAGE:
        response = (
            "No fue posible ejecutar analisis con LLM. "
            "Como fallback, revisa manualmente ajuste entre roles objetivo, "
            "skills y requisitos de la vacante antes de priorizar."
        )
    return {
        "analysis_text": response,
        "cultural_confidence": confidence,
        "cultural_warnings": warnings,
        "cultural_signals": signals,
    }


def prepare_application_materials(
    person: PersonRecord,
    opportunity: OpportunityRecord,
    settings: Settings,
) -> PreparationResult:
    system_prompt = (
        "Eres un asistente de postulaciones. Escribe contenido profesional, concreto y util."
    )
    base_context = f"{_person_context(person)}\n\n{_opportunity_context(opportunity)}"

    guidance = complete_prompt(
        system_prompt,
        (
            "Genera ayuda textual breve para postular:\n"
            "- enfoque recomendado\n"
            "- puntos a destacar\n"
            "- precauciones\n\n"
            f"{base_context}"
        ),
        settings,
        temperature=0.2,
    )
    if guidance == FALLBACK_MESSAGE:
        guidance = (
            "Fallback: enfoca la postulacion en logros medibles, alinea lenguaje "
            "a la vacante y destaca skills mas cercanos al rol."
        )

    cover_letter = complete_prompt(
        system_prompt,
        (
            "Escribe una carta de presentacion breve (max 220 palabras), "
            "personalizada para la vacante.\n\n"
            f"{base_context}"
        ),
        settings,
        temperature=0.4,
    )
    if cover_letter == FALLBACK_MESSAGE:
        cover_letter = (
            "Fallback carta: presentacion breve, interes por rol, 2-3 fortalezas "
            "relevantes y cierre con disponibilidad para entrevista."
        )

    experience_summary = complete_prompt(
        system_prompt,
        (
            "Escribe un resumen adaptado de experiencia (max 180 palabras), "
            "enfocado en ajuste con la vacante.\n\n"
            f"{base_context}"
        ),
        settings,
        temperature=0.3,
    )
    if experience_summary == FALLBACK_MESSAGE:
        experience_summary = (
            "Fallback resumen: sintetiza experiencia por logros y habilidades "
            "alineadas al rol objetivo."
        )

    return {
        "guidance_text": guidance,
        "cover_letter": cover_letter,
        "experience_summary": experience_summary,
    }
