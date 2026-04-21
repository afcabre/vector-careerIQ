from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.core.settings import get_settings
from app.services.opportunity_store import list_opportunities
from app.services.person_store import get_person, list_persons, seed_persons
from app.services.vacancy_v2_consistency_gate import (
    build_vacancy_v2_consistency_report,
    evaluate_vacancy_v2_consistency_report,
)


def _build_person_result(
    person_id: str,
    *,
    sample_limit: int,
    min_salary_transfer_rate: float,
    max_salary_signal_in_step2_benefits_rate: float,
    min_salary_transfer_eligible: int,
) -> dict[str, Any]:
    person = get_person(person_id) or {}
    opportunities = list_opportunities(person_id)
    report = build_vacancy_v2_consistency_report(
        opportunities,
        issue_sample_limit=sample_limit,
    )
    evaluation = evaluate_vacancy_v2_consistency_report(
        report,
        min_salary_transfer_rate=min_salary_transfer_rate,
        max_salary_signal_in_step2_benefits_rate=max_salary_signal_in_step2_benefits_rate,
        min_salary_transfer_eligible=min_salary_transfer_eligible,
    )
    return {
        "person_id": person_id,
        "full_name": str(person.get("full_name", "")),
        **report,
        "gate_passed": evaluation["gate_passed"],
        "failed_checks": evaluation["failed_checks"],
        "thresholds": evaluation["thresholds"],
    }


def _resolve_person_ids(person_id: str | None, all_persons: bool) -> list[str]:
    if person_id:
        return [person_id]
    if not all_persons:
        raise ValueError("Use --person-id or --all-persons.")
    return [str(item.get("person_id", "")).strip() for item in list_persons() if str(item.get("person_id", "")).strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run vacancy v2 consistency gate and print JSON report.",
    )
    parser.add_argument("--person-id", default="", help="Specific person_id to evaluate.")
    parser.add_argument(
        "--all-persons",
        action="store_true",
        help="Evaluate all persons available in current persistence backend.",
    )
    parser.add_argument("--sample-limit", type=int, default=20, help="Issue sample limit (default: 20).")
    parser.add_argument(
        "--min-salary-transfer-rate",
        type=float,
        default=0.8,
        help="Gate threshold for salary transfer rate (default: 0.8).",
    )
    parser.add_argument(
        "--max-salary-signal-in-step2-benefits-rate",
        type=float,
        default=0.05,
        help="Gate threshold for salary signal in step2 benefits rate (default: 0.05).",
    )
    parser.add_argument(
        "--min-salary-transfer-eligible",
        type=int,
        default=1,
        help="Minimum eligible opportunities to evaluate transfer rate (default: 1).",
    )
    parser.add_argument(
        "--fail-on-gate",
        action="store_true",
        help="Return exit code 1 if any selected person fails the gate.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if settings.persistence_backend.lower() == "memory":
        seed_persons()

    try:
        person_ids = _resolve_person_ids(args.person_id.strip() or None, args.all_persons)
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    results = [
        _build_person_result(
            person_id,
            sample_limit=args.sample_limit,
            min_salary_transfer_rate=args.min_salary_transfer_rate,
            max_salary_signal_in_step2_benefits_rate=args.max_salary_signal_in_step2_benefits_rate,
            min_salary_transfer_eligible=args.min_salary_transfer_eligible,
        )
        for person_id in person_ids
    ]

    payload: dict[str, Any] = {
        "persistence_backend": settings.persistence_backend,
        "selected_persons": len(person_ids),
        "results": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.fail_on_gate and any(not item["gate_passed"] for item in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
