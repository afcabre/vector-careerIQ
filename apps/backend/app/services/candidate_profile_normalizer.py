from __future__ import annotations

from typing import Any, TypedDict

from app.services.person_store import PersonRecord


class SalaryExpectation(TypedDict):
    min: int | None
    max: int | None
    currency: str
    period: str


class CandidatePreference(TypedDict):
    field_id: str
    enabled: bool
    selected_values: list[str]
    criticality: str


class CandidateProfileNormalized(TypedDict):
    identity: dict[str, str]
    target_profile: dict[str, Any]
    salary_expectation: SalaryExpectation
    cultural_preferences: list[CandidatePreference]
    legacy_preferences: list[str]
    culture_notes: str


def _clean_text(value: Any, *, upper: bool = False) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    compact = " ".join(text.split())
    return compact.upper() if upper else compact


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        cleaned = _clean_text(item)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def normalize_candidate_profile(person: PersonRecord) -> CandidateProfileNormalized:
    cultural_preferences: list[CandidatePreference] = []
    raw_cultural_fit = person.get("cultural_fit_preferences", {})
    if isinstance(raw_cultural_fit, dict):
        for field_id, raw in raw_cultural_fit.items():
            if not isinstance(raw, dict):
                continue
            selected_raw = raw.get("selected_values", [])
            selected_values = (
                _dedupe([str(item) for item in selected_raw])
                if isinstance(selected_raw, list)
                else []
            )
            cultural_preferences.append(
                CandidatePreference(
                    field_id=str(field_id).strip(),
                    enabled=bool(raw.get("enabled", False)),
                    selected_values=selected_values,
                    criticality=_clean_text(raw.get("criticality")) or "normal",
                )
            )

    return CandidateProfileNormalized(
        identity={
            "person_id": _clean_text(person.get("person_id")),
            "full_name": _clean_text(person.get("full_name")),
            "location": _clean_text(person.get("location")),
        },
        target_profile={
            "target_roles": _dedupe([str(item) for item in person.get("target_roles", [])]),
            "years_experience": int(person.get("years_experience", 0) or 0),
            "skills": _dedupe([str(item) for item in person.get("skills", [])]),
        },
        salary_expectation=SalaryExpectation(
            min=person.get("salary_expectation_min"),
            max=person.get("salary_expectation_max"),
            currency=_clean_text(person.get("salary_currency"), upper=True),
            period=_clean_text(person.get("salary_period")),
        ),
        cultural_preferences=cultural_preferences,
        legacy_preferences=_dedupe([str(item) for item in person.get("culture_preferences", [])]),
        culture_notes=_clean_text(person.get("culture_preferences_notes")),
    )


def candidate_profile_context(normalized: CandidateProfileNormalized) -> str:
    identity = normalized.get("identity", {})
    target_profile = normalized.get("target_profile", {})
    salary = normalized.get("salary_expectation", {})
    cultural_preferences = normalized.get("cultural_preferences", [])
    legacy_preferences = normalized.get("legacy_preferences", [])
    culture_notes = str(normalized.get("culture_notes", "")).strip()

    lines = [
        "Perfil normalizado del candidato:",
        f"- Nombre: {identity.get('full_name', '')}",
        f"- Ubicacion: {identity.get('location', '')}",
        "- Roles objetivo: " + ", ".join(target_profile.get("target_roles", []) or []),
        f"- Años de experiencia: {target_profile.get('years_experience', 0)}",
        "- Skills base: " + ", ".join(target_profile.get("skills", []) or []),
    ]

    salary_min = salary.get("min")
    salary_max = salary.get("max")
    if salary_min is not None or salary_max is not None:
        lines.append(
            "- Expectativa salarial: "
            + f"{salary_min if salary_min is not None else '?'}-"
            + f"{salary_max if salary_max is not None else '?'} "
            + f"{salary.get('currency', '')} ({salary.get('period', '')})"
        )

    enabled_preferences = [item for item in cultural_preferences if item.get("enabled")]
    if enabled_preferences:
        lines.append("- Preferencias culturales estructuradas:")
        for item in enabled_preferences:
            selected = ", ".join(item.get("selected_values", []))
            lines.append(
                f"  - {item.get('field_id')}: {selected} "
                f"[{item.get('criticality', 'normal')}]"
            )
    if legacy_preferences:
        lines.append("- Preferencias libres historicas: " + ", ".join(legacy_preferences))
    if culture_notes:
        lines.append(f"- Notas de preferencias: {culture_notes}")
    return "\n".join(lines)
