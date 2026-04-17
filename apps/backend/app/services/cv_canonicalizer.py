from __future__ import annotations

import re
from typing import TypedDict


DEFAULT_SECTION = "general"

SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "profile_summary": (
        "summary",
        "professional summary",
        "perfil",
        "perfil profesional",
        "resumen",
        "resumen profesional",
        "about",
        "profile",
    ),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "experiencia",
        "experiencia profesional",
        "trayectoria",
        "employment",
    ),
    "education": (
        "education",
        "educacion",
        "formacion",
        "formacion academica",
        "academic background",
    ),
    "skills": (
        "skills",
        "habilidades",
        "competencies",
        "competencias",
        "tools",
        "herramientas",
        "technologies",
        "tecnologias",
        "tech stack",
    ),
    "languages": (
        "languages",
        "idiomas",
        "language",
    ),
    "certifications": (
        "certifications",
        "certification",
        "certificados",
        "certificaciones",
        "licenses",
        "licencias",
    ),
}


class CanonicalBlock(TypedDict):
    title: str
    content: str
    dates: str


class CanonicalLabelBlock(TypedDict):
    label: str
    content: str


class CanonicalCV(TypedDict):
    profile_summary: str
    experience_blocks: list[CanonicalBlock]
    education_blocks: list[CanonicalBlock]
    skills_block: str
    language_blocks: list[CanonicalLabelBlock]
    certification_blocks: list[CanonicalLabelBlock]
    unknown_blocks: list[CanonicalLabelBlock]


def _empty_canonical_cv() -> CanonicalCV:
    return CanonicalCV(
        profile_summary="",
        experience_blocks=[],
        education_blocks=[],
        skills_block="",
        language_blocks=[],
        certification_blocks=[],
        unknown_blocks=[],
    )


def _normalize_heading(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    return normalized.strip(" :.-")


def _resolve_section_type(heading: str) -> str:
    normalized = _normalize_heading(heading)
    for section_type, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return section_type
        if any(alias in normalized for alias in aliases):
            return section_type
    return DEFAULT_SECTION


def _split_markdown_sections(markdown_text: str) -> list[tuple[str, str]]:
    text = markdown_text.strip()
    if not text:
        return []
    sections: list[tuple[str, str]] = []
    current_title = DEFAULT_SECTION
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            if current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+)$", line)
        if match:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_title, body))
            current_title = match.group(1).strip() or DEFAULT_SECTION
            current_lines = []
            continue
        current_lines.append(line)

    body = "\n".join(current_lines).strip()
    if body:
        sections.append((current_title, body))
    return sections


def _fallback_sections_from_text(raw_text: str) -> list[tuple[str, str]]:
    text = raw_text.strip()
    if not text:
        return []
    return [(DEFAULT_SECTION, text)]


def _extract_dates(text: str) -> str:
    matches = re.findall(
        r"\b(?:19|20)\d{2}\b(?:\s*[-/–]\s*(?:present|actualidad|current|(?:19|20)\d{2}))?",
        text,
        flags=re.IGNORECASE,
    )
    return " | ".join(matches[:2])


def _clean_item_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    cleaned: list[str] = []
    for line in lines:
        if not line:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        cleaned.append(re.sub(r"^[-*•]\s+", "", line).strip())
    return "\n".join(cleaned).strip()


def _split_blocks(body: str) -> list[str]:
    cleaned = body.strip()
    if not cleaned:
        return []
    parts = [part.strip() for part in re.split(r"\n\s*\n+", cleaned) if part.strip()]
    if len(parts) >= 2:
        return parts

    blocks: list[str] = []
    current: list[str] = []
    lines = [line.rstrip() for line in cleaned.splitlines() if line.strip()]
    for line in lines:
        looks_like_new_item = bool(
            re.search(r"\b(?:19|20)\d{2}\b", line)
            or re.match(r"^[-*•]\s+", line)
        )
        if current and looks_like_new_item:
            blocks.append("\n".join(current).strip())
            current = [line]
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [block for block in blocks if block]


def _to_title(block: str) -> str:
    first_line = block.splitlines()[0].strip()
    return re.sub(r"^[-*•]\s+", "", first_line).strip()[:160]


def _to_canonical_blocks(body: str) -> list[CanonicalBlock]:
    blocks: list[CanonicalBlock] = []
    for item in _split_blocks(body):
        cleaned = _clean_item_text(item)
        if not cleaned:
            continue
        blocks.append(
            CanonicalBlock(
                title=_to_title(cleaned),
                content=cleaned,
                dates=_extract_dates(cleaned),
            )
        )
    return blocks


def _to_label_blocks(body: str) -> list[CanonicalLabelBlock]:
    blocks: list[CanonicalLabelBlock] = []
    for item in _split_blocks(body):
        cleaned = _clean_item_text(item)
        if not cleaned:
            continue
        blocks.append(
            CanonicalLabelBlock(
                label=_to_title(cleaned),
                content=cleaned,
            )
        )
    return blocks


def canonicalize_cv(
    *,
    raw_text: str,
    structured_markdown: str,
) -> CanonicalCV:
    canonical = _empty_canonical_cv()
    sections = _split_markdown_sections(structured_markdown)
    if not sections:
        sections = _fallback_sections_from_text(raw_text)

    for heading, body in sections:
        section_type = _resolve_section_type(heading)
        cleaned_body = body.strip()
        if not cleaned_body:
            continue

        if section_type == "profile_summary":
            if canonical["profile_summary"]:
                canonical["profile_summary"] = (
                    f"{canonical['profile_summary']}\n\n{_clean_item_text(cleaned_body)}".strip()
                )
            else:
                canonical["profile_summary"] = _clean_item_text(cleaned_body)
            continue

        if section_type == "experience":
            canonical["experience_blocks"].extend(_to_canonical_blocks(cleaned_body))
            continue

        if section_type == "education":
            canonical["education_blocks"].extend(_to_canonical_blocks(cleaned_body))
            continue

        if section_type == "skills":
            skills_text = _clean_item_text(cleaned_body)
            canonical["skills_block"] = (
                f"{canonical['skills_block']}\n{skills_text}".strip()
                if canonical["skills_block"]
                else skills_text
            )
            continue

        if section_type == "languages":
            canonical["language_blocks"].extend(_to_label_blocks(cleaned_body))
            continue

        if section_type == "certifications":
            canonical["certification_blocks"].extend(_to_label_blocks(cleaned_body))
            continue

        canonical["unknown_blocks"].append(
            CanonicalLabelBlock(
                label=_normalize_heading(heading) or DEFAULT_SECTION,
                content=_clean_item_text(cleaned_body),
            )
        )

    if not canonical["profile_summary"]:
        if sections and _resolve_section_type(sections[0][0]) == DEFAULT_SECTION:
            first_body = _clean_item_text(sections[0][1])
            canonical["profile_summary"] = first_body[:1200].strip()
            if canonical["unknown_blocks"]:
                first_unknown = canonical["unknown_blocks"][0]
                if first_unknown["content"] == _clean_item_text(sections[0][1]):
                    canonical["unknown_blocks"] = canonical["unknown_blocks"][1:]

    return canonical
