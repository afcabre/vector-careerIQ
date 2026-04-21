from __future__ import annotations

import re
from typing import Any, TypedDict

from app.services.opportunity_store import OpportunityRecord
from app.services.vacancy_blocks_contract import normalize_vacancy_blocks_contract
from app.services.vacancy_dimensions_contract import normalize_vacancy_dimensions_contract


class VacancyV2ConsistencyIssue(TypedDict):
    opportunity_id: str
    title: str
    company: str
    vacancy_blocks_status: str
    vacancy_dimensions_status: str
    issues: list[str]


class VacancyV2ConsistencyReport(TypedDict):
    total_opportunities: int
    opportunities_with_step2: int
    opportunities_with_step3: int
    salary_transfer_eligible: int
    salary_transfer_ok: int
    salary_transfer_missing: int
    salary_transfer_rate: float
    salary_signal_in_step2_benefits: int
    salary_signal_in_step2_benefits_rate: float
    issue_samples: list[VacancyV2ConsistencyIssue]


class VacancyV2ConsistencyThresholds(TypedDict):
    min_salary_transfer_rate: float
    max_salary_signal_in_step2_benefits_rate: float
    min_salary_transfer_eligible: int


class VacancyV2ConsistencyEvaluation(TypedDict):
    gate_passed: bool
    failed_checks: list[str]
    thresholds: VacancyV2ConsistencyThresholds


_SALARY_SIGNAL_PATTERN = re.compile(
    r"(?i)(salary|salario|sueldo|remuner|compens|pay|usd|cop|eur|mxn|\$\s*\d)"
)


def _has_salary_signal(text: str) -> bool:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return False
    return bool(_SALARY_SIGNAL_PATTERN.search(cleaned))


def _has_salary_data_in_step3(raw_salary: Any) -> bool:
    salary = raw_salary if isinstance(raw_salary, dict) else {}
    if salary.get("min") is not None:
        return True
    if salary.get("max") is not None:
        return True
    if str(salary.get("currency", "")).strip():
        return True
    if str(salary.get("period", "")).strip():
        return True
    return bool(str(salary.get("text", "")).strip())


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def build_vacancy_v2_consistency_report(
    opportunities: list[OpportunityRecord],
    *,
    issue_sample_limit: int = 20,
) -> VacancyV2ConsistencyReport:
    with_step2 = 0
    with_step3 = 0
    salary_transfer_eligible = 0
    salary_transfer_ok = 0
    salary_signal_in_step2_benefits = 0
    issue_samples: list[VacancyV2ConsistencyIssue] = []

    for item in opportunities:
        raw_blocks_artifact = item.get("vacancy_blocks_artifact", {})
        raw_dimensions_artifact = item.get("vacancy_dimensions_artifact", {})
        has_step2 = isinstance(raw_blocks_artifact, dict) and len(raw_blocks_artifact) > 0
        has_step3 = isinstance(raw_dimensions_artifact, dict) and len(raw_dimensions_artifact) > 0

        if has_step2:
            with_step2 += 1
        if has_step3:
            with_step3 += 1

        step2_has_salary_signal = False
        step3_has_salary_data = False
        step2_salary_in_benefits = False

        if has_step2:
            normalized_blocks = normalize_vacancy_blocks_contract(raw_blocks_artifact)
            work_conditions = normalized_blocks["vacancy_blocks"]["work_conditions"]
            benefits = normalized_blocks["vacancy_blocks"]["benefits"]
            step2_has_salary_signal = any(_has_salary_signal(value) for value in work_conditions)
            step2_salary_in_benefits = any(_has_salary_signal(value) for value in benefits)

        if has_step3:
            normalized_dimensions = normalize_vacancy_dimensions_contract(raw_dimensions_artifact)
            step3_has_salary_data = _has_salary_data_in_step3(
                normalized_dimensions["vacancy_dimensions"]["work_conditions"]["salary"]
            )

        issues: list[str] = []
        if step2_salary_in_benefits:
            salary_signal_in_step2_benefits += 1
            issues.append("salary_signal_found_in_step2_benefits")

        if step2_has_salary_signal:
            salary_transfer_eligible += 1
            if step3_has_salary_data:
                salary_transfer_ok += 1
            else:
                issues.append("salary_missing_in_step3")

        if issues and len(issue_samples) < issue_sample_limit:
            issue_samples.append(
                {
                    "opportunity_id": str(item.get("opportunity_id", "")),
                    "title": str(item.get("title", "")),
                    "company": str(item.get("company", "")),
                    "vacancy_blocks_status": str(item.get("vacancy_blocks_status", "")),
                    "vacancy_dimensions_status": str(item.get("vacancy_dimensions_status", "")),
                    "issues": issues,
                }
            )

    salary_transfer_missing = max(0, salary_transfer_eligible - salary_transfer_ok)
    return {
        "total_opportunities": len(opportunities),
        "opportunities_with_step2": with_step2,
        "opportunities_with_step3": with_step3,
        "salary_transfer_eligible": salary_transfer_eligible,
        "salary_transfer_ok": salary_transfer_ok,
        "salary_transfer_missing": salary_transfer_missing,
        "salary_transfer_rate": _ratio(salary_transfer_ok, salary_transfer_eligible),
        "salary_signal_in_step2_benefits": salary_signal_in_step2_benefits,
        "salary_signal_in_step2_benefits_rate": _ratio(
            salary_signal_in_step2_benefits,
            with_step2,
        ),
        "issue_samples": issue_samples,
    }


def evaluate_vacancy_v2_consistency_report(
    report: VacancyV2ConsistencyReport,
    *,
    min_salary_transfer_rate: float = 0.8,
    max_salary_signal_in_step2_benefits_rate: float = 0.05,
    min_salary_transfer_eligible: int = 1,
) -> VacancyV2ConsistencyEvaluation:
    failed_checks: list[str] = []

    if report["salary_transfer_eligible"] < min_salary_transfer_eligible:
        failed_checks.append("insufficient_salary_transfer_eligible")

    if (
        report["salary_transfer_eligible"] >= min_salary_transfer_eligible
        and report["salary_transfer_rate"] < min_salary_transfer_rate
    ):
        failed_checks.append("salary_transfer_rate_below_threshold")

    if (
        report["salary_signal_in_step2_benefits_rate"]
        > max_salary_signal_in_step2_benefits_rate
    ):
        failed_checks.append("salary_signal_in_step2_benefits_rate_above_threshold")

    return {
        "gate_passed": len(failed_checks) == 0,
        "failed_checks": failed_checks,
        "thresholds": {
            "min_salary_transfer_rate": min_salary_transfer_rate,
            "max_salary_signal_in_step2_benefits_rate": max_salary_signal_in_step2_benefits_rate,
            "min_salary_transfer_eligible": min_salary_transfer_eligible,
        },
    }
