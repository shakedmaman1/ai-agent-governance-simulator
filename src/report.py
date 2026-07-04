"""CSV and Markdown reporting for governance audit data."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

import pandas as pd

from src.db import get_database_path

DEFAULT_CSV_OUTPUT = Path("outputs/governance_report.csv")
DEFAULT_MD_OUTPUT = Path("outputs/governance_summary.md")

_JOIN_QUERY = """
SELECT
    a.action_id,
    a.customer_type,
    a.department,
    a.action_type,
    a.amount,
    a.confidence AS action_confidence,
    a.contains_sensitive_data,
    a.identity_verified,
    a.requested_by_role,
    a.expected_decision,
    a.expected_risk_level,
    a.expected_approval_level,
    d.decision AS actual_decision,
    d.risk_level AS actual_risk_level,
    d.approval_level AS actual_approval_level,
    d.policy_refs_json,
    d.reason,
    d.human_review_required,
    d.confidence AS decision_confidence,
    e.passed,
    e.score,
    e.failure_reasons_json,
    e.improvement_note,
    e.requires_human_review
FROM actions a
INNER JOIN decisions d ON a.action_id = d.action_id
INNER JOIN evaluations e ON a.action_id = e.action_id
ORDER BY a.action_id
"""


def _ensure_output_dir(output_path: Path) -> None:
    """Create the parent directory for a report file if needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)


def _parse_json_list(value: object) -> list[str]:
    """Safely parse a JSON list column from SQLite."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return []


def _format_percent(value: float) -> str:
    """Format a ratio as a percentage string."""
    return f"{value * 100:.1f}%"


def _build_recommendations(
    failure_counter: Counter[str],
    decision_accuracy: float,
    risk_accuracy: float,
    approval_accuracy: float,
    human_review_rate: float,
) -> list[str]:
    """Generate actionable recommendations from report metrics."""
    recommendations = []

    if failure_counter.get("wrong_decision", 0) > 0:
        recommendations.append(
            "Review decision rules for action types with frequent decision mismatches."
        )
    if failure_counter.get("wrong_risk_level", 0) > 0:
        recommendations.append(
            "Tune risk scoring thresholds, especially for sensitive and financial actions."
        )
    if failure_counter.get("wrong_approval_level", 0) > 0:
        recommendations.append(
            "Clarify approval-level mapping so policy outcomes route to the correct approver."
        )
    if failure_counter.get("missing_policy_refs", 0) > 0:
        recommendations.append(
            "Ensure every governance outcome records the policies that influenced the decision."
        )
    if failure_counter.get("vague_reason", 0) > 0:
        recommendations.append(
            "Return more specific audit reasons that cite policy IDs and triggering conditions."
        )
    if failure_counter.get("missing_human_review", 0) > 0:
        recommendations.append(
            "Flag blocked and approval-required actions for human review consistently."
        )

    if decision_accuracy < 0.85:
        recommendations.append(
            "Decision accuracy is below target; prioritize policy engine test coverage."
        )
    if risk_accuracy < 0.85:
        recommendations.append(
            "Risk-level accuracy is below target; validate VIP, refund, and sensitive-data rules."
        )
    if approval_accuracy < 0.85:
        recommendations.append(
            "Approval-level accuracy is below target; reconcile manager vs compliance thresholds."
        )
    if human_review_rate > 0.50:
        recommendations.append(
            "Human review rate is high; consider refining auto-approval criteria for low-risk actions."
        )

    if not recommendations:
        recommendations.append(
            "Governance outcomes align well with expectations; continue monitoring policy drift."
        )

    return recommendations


def load_governance_data(db_path: str | None = None) -> pd.DataFrame:
    """Load joined governance audit data from SQLite."""
    path = get_database_path(db_path)

    if not path.exists():
        raise ValueError(
            f"No governance audit database found at {path}. Run a governance evaluation first."
        )

    with sqlite3.connect(path) as connection:
        dataframe = pd.read_sql_query(_JOIN_QUERY, connection)

    if dataframe.empty:
        raise ValueError(
            "No governance audit records found. Save actions, decisions, and evaluations first."
        )

    bool_columns = [
        "contains_sensitive_data",
        "identity_verified",
        "human_review_required",
        "passed",
        "requires_human_review",
    ]
    for column in bool_columns:
        if column in dataframe.columns:
            dataframe[column] = dataframe[column].astype(bool)

    return dataframe


def generate_governance_report(
    db_path: str | None = None,
    output_path: str = "outputs/governance_report.csv",
) -> str:
    """Generate a CSV report from joined governance audit data."""
    dataframe = load_governance_data(db_path)
    csv_path = Path(output_path)
    _ensure_output_dir(csv_path)
    dataframe.to_csv(csv_path, index=False)
    return str(csv_path)


def generate_governance_summary(
    db_path: str | None = None,
    output_path: str = "outputs/governance_summary.md",
) -> str:
    """Generate a Markdown summary report from governance audit data."""
    dataframe = load_governance_data(db_path)
    md_path = Path(output_path)
    _ensure_output_dir(md_path)

    total_actions = len(dataframe)
    pass_rate = dataframe["passed"].mean()
    average_score = dataframe["score"].mean()
    decision_accuracy = (
        dataframe["actual_decision"] == dataframe["expected_decision"]
    ).mean()
    risk_accuracy = (
        dataframe["actual_risk_level"] == dataframe["expected_risk_level"]
    ).mean()
    approval_accuracy = (
        dataframe["actual_approval_level"] == dataframe["expected_approval_level"]
    ).mean()
    human_review_rate = dataframe["human_review_required"].mean()

    decision_counts = Counter(dataframe["actual_decision"])
    blocked_count = int(decision_counts.get("blocked", 0))
    requires_approval_count = int(decision_counts.get("requires_approval", 0))
    allowed_count = int(decision_counts.get("allowed", 0))

    failure_counter: Counter[str] = Counter()
    for reasons in dataframe["failure_reasons_json"]:
        for reason in _parse_json_list(reasons):
            failure_counter[reason] += 1

    policy_counter: Counter[str] = Counter()
    for policies in dataframe["policy_refs_json"]:
        for policy_ref in _parse_json_list(policies):
            policy_counter[policy_ref] += 1

    failed_actions = dataframe[dataframe["passed"] == False].head(5)  # noqa: E712

    recommendations = _build_recommendations(
        failure_counter=failure_counter,
        decision_accuracy=decision_accuracy,
        risk_accuracy=risk_accuracy,
        approval_accuracy=approval_accuracy,
        human_review_rate=human_review_rate,
    )

    lines = [
        "# AI Agent Governance Summary Report",
        "",
        "## Overview",
        "",
        f"- **Total actions:** {total_actions}",
        f"- **Pass rate:** {_format_percent(pass_rate)}",
        f"- **Average score:** {average_score:.1f}",
        f"- **Decision accuracy:** {_format_percent(decision_accuracy)}",
        f"- **Risk-level accuracy:** {_format_percent(risk_accuracy)}",
        f"- **Approval-level accuracy:** {_format_percent(approval_accuracy)}",
        f"- **Human review rate:** {_format_percent(human_review_rate)}",
        "",
        "## Decision Distribution",
        "",
        f"- **Allowed:** {allowed_count}",
        f"- **Requires approval:** {requires_approval_count}",
        f"- **Blocked:** {blocked_count}",
        "",
        "## Most Common Failure Reasons",
        "",
    ]

    if failure_counter:
        for reason, count in failure_counter.most_common():
            lines.append(f"- `{reason}`: {count}")
    else:
        lines.append("- No failure reasons recorded.")

    lines.extend(["", "## Top Policy References Used", ""])

    if policy_counter:
        for policy_ref, count in policy_counter.most_common(10):
            lines.append(f"- `{policy_ref}`: {count}")
    else:
        lines.append("- No policy references recorded.")

    lines.extend(["", "## Failed Action Examples", ""])

    if failed_actions.empty:
        lines.append("- No failed actions in the current audit dataset.")
    else:
        for _, row in failed_actions.iterrows():
            failure_reasons = ", ".join(_parse_json_list(row["failure_reasons_json"])) or "none"
            lines.append(
                f"- **{row['action_id']}** ({row['action_type']}): "
                f"score={row['score']}, expected={row['expected_decision']}, "
                f"actual={row['actual_decision']}, failures={failure_reasons}"
            )

    lines.extend(["", "## Recommendations", ""])
    for recommendation in recommendations:
        lines.append(f"- {recommendation}")

    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return str(md_path)


def generate_reports(db_path: str | None = None) -> tuple[str, str]:
    """Generate CSV and Markdown governance reports."""
    csv_path = generate_governance_report(db_path=db_path)
    md_path = generate_governance_summary(db_path=db_path)
    return csv_path, md_path
