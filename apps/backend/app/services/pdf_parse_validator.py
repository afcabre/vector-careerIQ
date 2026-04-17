from __future__ import annotations

import re
from typing import TypedDict


PARSE_QUALITY_HIGH = "high"
PARSE_QUALITY_MEDIUM = "medium"
PARSE_QUALITY_LOW = "low"

RECOMMENDED_MODE_STRUCTURED_MARKDOWN = "structured_markdown"
RECOMMENDED_MODE_FALLBACK_PLAIN_TEXT = "fallback_plain_text"
RECOMMENDED_MODE_MANUAL_REVIEW = "manual_review"


class PdfParseValidationResult(TypedDict):
    parse_quality: str
    issues: list[str]
    recommended_mode: str


def _normalized_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _repetition_ratio(lines: list[str]) -> float:
    if not lines:
        return 0.0
    unique = {line.lower() for line in lines}
    return 1.0 - (len(unique) / len(lines))


def _short_line_ratio(lines: list[str]) -> float:
    if not lines:
        return 0.0
    short = [line for line in lines if len(line) <= 36]
    return len(short) / len(lines)


def _single_char_token_ratio(tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    short = [token for token in tokens if len(token) == 1 and token.isalpha()]
    return len(short) / len(tokens)


def validate_pdf_parse(
    *,
    raw_text: str,
    structured_markdown: str,
) -> PdfParseValidationResult:
    text = raw_text.strip()
    markdown = structured_markdown.strip()
    if not text:
        return PdfParseValidationResult(
            parse_quality=PARSE_QUALITY_LOW,
            issues=["empty_or_near_empty"],
            recommended_mode=RECOMMENDED_MODE_MANUAL_REVIEW,
        )

    lines = _normalized_lines(text)
    tokens = re.findall(r"\b[\w\+\#\-/\.]+\b", text, flags=re.UNICODE)
    alpha_chars = sum(1 for char in text if char.isalpha())
    heading_count = len(
        re.findall(r"^\s{0,3}#{1,6}\s+.+$", markdown, flags=re.MULTILINE)
    )

    issues: list[str] = []
    severe_count = 0
    words_count = len(tokens)
    line_count = max(1, len(lines))
    avg_alpha_per_line = alpha_chars / line_count
    repetition_ratio = _repetition_ratio(lines)
    short_line_ratio = _short_line_ratio(lines)
    single_char_ratio = _single_char_token_ratio(tokens)

    if words_count < 40 or alpha_chars < 240:
        issues.append("low_content_length")
        severe_count += 1

    if avg_alpha_per_line < 18:
        issues.append("low_text_density")
        severe_count += 1

    if heading_count == 0 and words_count >= 120:
        issues.append("missing_section_markers")

    if short_line_ratio >= 0.55 and line_count >= 14:
        issues.append("suspected_column_break")
        severe_count += 1

    if repetition_ratio >= 0.18 and line_count >= 10:
        issues.append("repeated_lines")

    if single_char_ratio >= 0.12 and words_count >= 60:
        issues.append("broken_tokenization")
        severe_count += 1

    if severe_count >= 2:
        return PdfParseValidationResult(
            parse_quality=PARSE_QUALITY_LOW,
            issues=issues,
            recommended_mode=RECOMMENDED_MODE_FALLBACK_PLAIN_TEXT,
        )

    if issues:
        return PdfParseValidationResult(
            parse_quality=PARSE_QUALITY_MEDIUM,
            issues=issues,
            recommended_mode=RECOMMENDED_MODE_FALLBACK_PLAIN_TEXT,
        )

    return PdfParseValidationResult(
        parse_quality=PARSE_QUALITY_HIGH,
        issues=[],
        recommended_mode=RECOMMENDED_MODE_STRUCTURED_MARKDOWN,
    )
