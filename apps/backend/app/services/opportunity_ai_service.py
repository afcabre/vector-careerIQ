from typing import TypedDict

from app.core.settings import Settings
from app.services.llm_service import FALLBACK_MESSAGE, complete_prompt
from app.services.opportunity_store import OpportunityRecord
from app.services.person_store import PersonRecord


class AnalyzeResult(TypedDict):
    analysis_text: str


class PreparationResult(TypedDict):
    guidance_text: str
    cover_letter: str
    experience_summary: str


def _person_context(person: PersonRecord) -> str:
    return (
        f"Persona consultada: {person['full_name']}\n"
        f"Ubicacion: {person['location']}\n"
        f"Roles objetivo: {', '.join(person['target_roles'])}\n"
        f"Skills: {', '.join(person['skills'])}\n"
        f"Experiencia aproximada: {person['years_experience']} anos"
    )


def _opportunity_context(opportunity: OpportunityRecord) -> str:
    return (
        f"Vacante: {opportunity['title']}\n"
        f"Empresa: {opportunity['company']}\n"
        f"Ubicacion: {opportunity['location']}\n"
        f"URL: {opportunity['source_url']}\n"
        f"Descripcion: {opportunity['snapshot_raw_text']}"
    )


def analyze_opportunity(
    person: PersonRecord,
    opportunity: OpportunityRecord,
    settings: Settings,
) -> AnalyzeResult:
    system_prompt = (
        "Eres un asistente de empleabilidad. Entrega analisis cualitativo y accionable."
    )
    user_prompt = (
        "Analiza ajuste perfil-vacante y fit cultural.\n"
        "Formato:\n"
        "1) Ajuste general\n"
        "2) Fortalezas\n"
        "3) Brechas\n"
        "4) Senales culturales\n"
        "5) Recomendacion accionable\n\n"
        f"{_person_context(person)}\n\n{_opportunity_context(opportunity)}"
    )
    response = complete_prompt(system_prompt, user_prompt, settings, temperature=0.2)
    if response == FALLBACK_MESSAGE:
        response = (
            "No fue posible ejecutar analisis con LLM. "
            "Como fallback, revisa manualmente ajuste entre roles objetivo, "
            "skills y requisitos de la vacante antes de priorizar."
        )
    return {"analysis_text": response}


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
