"""CLI entry point for the AI Agent Governance Simulator."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from pydantic import ValidationError

from src.db import get_database_path, save_full_run
from src.evaluator import evaluate_agent_action, evaluate_governance_decision
from src.report import generate_reports
from src.schemas import (
    ActionType,
    AgentAction,
    ApprovalLevel,
    CustomerType,
    Department,
    GovernanceDecisionType,
    RequestedByRole,
    RiskLevel,
)

DEFAULT_INPUT = Path("data/actions.csv")


def parse_bool(value: str) -> bool:
    """Convert CSV boolean strings to Python bool values."""
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def _parse_action_row(row: dict[str, str]) -> AgentAction:
    """Convert a CSV row dictionary into a validated AgentAction."""
    return AgentAction(
        action_id=row["action_id"],
        customer_type=CustomerType(row["customer_type"]),
        department=Department(row["department"]),
        action_type=ActionType(row["action_type"]),
        amount=float(row["amount"]),
        confidence=float(row["confidence"]),
        contains_sensitive_data=parse_bool(row["contains_sensitive_data"]),
        identity_verified=parse_bool(row["identity_verified"]),
        requested_by_role=RequestedByRole(row["requested_by_role"]),
        expected_decision=GovernanceDecisionType(row["expected_decision"]),
        expected_risk_level=RiskLevel(row["expected_risk_level"]),
        expected_approval_level=ApprovalLevel(row["expected_approval_level"]),
    )


def load_actions(csv_path: str | Path) -> list[AgentAction]:
    """Load and validate agent actions from a CSV file."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    actions: list[AgentAction] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for line_number, row in enumerate(reader, start=2):
            try:
                actions.append(_parse_action_row(row))
            except (ValidationError, ValueError, KeyError) as exc:
                action_id = row.get("action_id", "unknown")
                raise ValueError(
                    f"Invalid action at CSV line {line_number} "
                    f"(action_id={action_id}): {exc}"
                ) from exc
    return actions


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    """Read raw CSV rows without validation."""
    with csv_path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def run_workflow(
    input_path: str | Path = "data/actions.csv",
    limit: int | None = None,
    show_failures: bool = False,
    reset_db: bool = False,
) -> dict[str, object]:
    """Run the full governance workflow from CSV input through reporting."""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    if reset_db:
        db_path = get_database_path()
        if db_path.exists():
            db_path.unlink()

    rows = _read_csv_rows(path)
    if limit is not None:
        rows = rows[:limit]

    stats: dict[str, object] = {
        "loaded": len(rows),
        "processed": 0,
        "errors": 0,
        "passed": 0,
        "failed": 0,
        "failure_details": [],
        "csv_path": None,
        "md_path": None,
    }

    for row in rows:
        action_id = row.get("action_id", "unknown")
        print(f"Processing {action_id}...")

        try:
            action = _parse_action_row(row)
            decision = evaluate_agent_action(action)
            evaluation = evaluate_governance_decision(action, decision)
            save_full_run(action, decision, evaluation)

            stats["processed"] = int(stats["processed"]) + 1
            if evaluation.passed:
                stats["passed"] = int(stats["passed"]) + 1
            else:
                stats["failed"] = int(stats["failed"]) + 1
                failure_details = stats["failure_details"]
                assert isinstance(failure_details, list)
                failure_details.append(
                    {
                        "action_id": action.action_id,
                        "failure_reasons": evaluation.failure_reasons,
                        "improvement_note": evaluation.improvement_note,
                    }
                )
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            stats["errors"] = int(stats["errors"]) + 1
            print(f"  Error processing {action_id}: {exc}")

    if int(stats["processed"]) > 0:
        csv_path, md_path = generate_reports()
        stats["csv_path"] = csv_path
        stats["md_path"] = md_path
    else:
        print("No actions processed; skipping report generation.")

    if show_failures:
        failure_details = stats["failure_details"]
        assert isinstance(failure_details, list)
        if failure_details:
            print("\nFailed evaluations:")
            for item in failure_details:
                reasons = ", ".join(item["failure_reasons"]) or "none"
                print(f"  - {item['action_id']}: {reasons}")
        elif int(stats["failed"]) == 0:
            print("\nNo failed evaluations.")

    return stats


def _print_summary(stats: dict[str, object]) -> None:
    """Print a terminal summary of the governance workflow run."""
    loaded = int(stats["loaded"])
    processed = int(stats["processed"])
    errors = int(stats["errors"])
    passed = int(stats["passed"])
    failed = int(stats["failed"])

    evaluated = passed + failed
    pass_rate = (passed / evaluated * 100) if evaluated else 0.0

    print("\n=== Governance Run Summary ===")
    print(f"Total actions loaded: {loaded}")
    print(f"Successfully processed: {processed}")
    print(f"Errors: {errors}")
    print(f"Passed evaluations: {passed}")
    print(f"Failed evaluations: {failed}")
    print(f"Pass rate: {pass_rate:.1f}%")

    csv_path = stats.get("csv_path")
    md_path = stats.get("md_path")
    if csv_path:
        print(f"CSV report: {csv_path}")
    if md_path:
        print(f"Markdown summary: {md_path}")


def main() -> None:
    """Parse CLI arguments and execute the governance workflow."""
    parser = argparse.ArgumentParser(
        description="Simulate enterprise AI agent governance and approval workflows."
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Path to the input actions CSV file (default: data/actions.csv)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N actions from the input file",
    )
    parser.add_argument(
        "--show-failures",
        action="store_true",
        help="Print failed action IDs and failure reasons",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Delete the existing audit database before running",
    )
    args = parser.parse_args()

    try:
        stats = run_workflow(
            input_path=args.input,
            limit=args.limit,
            show_failures=args.show_failures,
            reset_db=args.reset_db,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    _print_summary(stats)


if __name__ == "__main__":
    main()
