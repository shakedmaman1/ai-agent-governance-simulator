"""Tests for governance report generation."""

import pytest

from src.db import save_full_run
from src.evaluator import evaluate_agent_action, evaluate_governance_decision
from src.report import generate_reports, load_governance_data
from tests.conftest import make_action

EXPECTED_COLUMNS = {
    "action_id",
    "customer_type",
    "department",
    "action_type",
    "amount",
    "action_confidence",
    "contains_sensitive_data",
    "identity_verified",
    "requested_by_role",
    "expected_decision",
    "expected_risk_level",
    "expected_approval_level",
    "actual_decision",
    "actual_risk_level",
    "actual_approval_level",
    "policy_refs_json",
    "reason",
    "human_review_required",
    "decision_confidence",
    "passed",
    "score",
    "failure_reasons_json",
    "improvement_note",
    "requires_human_review",
}


def _seed_database(db_path):
    """Persist a small set of governance runs for reporting tests."""
    actions = [
        make_action(action_id="ACT-RPT-001", amount=50.0),
        make_action(
            action_id="ACT-RPT-002",
            amount=750.0,
            confidence=0.88,
            expected_decision="requires_approval",
            expected_risk_level="High",
            expected_approval_level="manager",
        ),
    ]
    for action in actions:
        decision = evaluate_agent_action(action)
        evaluation = evaluate_governance_decision(action, decision)
        save_full_run(action, decision, evaluation, db_path=str(db_path))


def test_generate_reports_creates_csv_and_markdown(tmp_path):
    db_path = tmp_path / "audit.db"
    csv_path = tmp_path / "governance_report.csv"
    md_path = tmp_path / "governance_summary.md"

    _seed_database(db_path)

    from src.report import generate_governance_report, generate_governance_summary

    generate_governance_report(db_path=str(db_path), output_path=str(csv_path))
    generate_governance_summary(db_path=str(db_path), output_path=str(md_path))

    assert csv_path.exists()
    assert md_path.exists()


def test_load_governance_data_returns_expected_columns(tmp_path):
    db_path = tmp_path / "audit.db"
    _seed_database(db_path)

    dataframe = load_governance_data(str(db_path))

    assert len(dataframe) == 2
    assert EXPECTED_COLUMNS.issubset(set(dataframe.columns))


def test_summary_contains_required_sections(tmp_path):
    db_path = tmp_path / "audit.db"
    md_path = tmp_path / "governance_summary.md"
    _seed_database(db_path)

    from src.report import generate_governance_summary

    generate_governance_summary(db_path=str(db_path), output_path=str(md_path))
    summary = md_path.read_text(encoding="utf-8")

    assert "Total actions" in summary
    assert "Pass rate" in summary
    assert "Average score" in summary
    assert "Decision Distribution" in summary
    assert "Top Policy References Used" in summary
    assert "Recommendations" in summary


def test_empty_database_raises_value_error(tmp_path):
    db_path = tmp_path / "missing.db"

    with pytest.raises(ValueError, match="No governance audit database found"):
        load_governance_data(str(db_path))


def test_generate_reports_returns_both_paths(tmp_path, monkeypatch):
    db_path = tmp_path / "audit.db"
    csv_path = tmp_path / "reports" / "governance_report.csv"
    md_path = tmp_path / "reports" / "governance_summary.md"

    _seed_database(db_path)

    monkeypatch.setattr(
        "src.report.generate_governance_report",
        lambda db_path=None, output_path="outputs/governance_report.csv": str(csv_path),
    )
    monkeypatch.setattr(
        "src.report.generate_governance_summary",
        lambda db_path=None, output_path="outputs/governance_summary.md": str(md_path),
    )

    returned_csv, returned_md = generate_reports(str(db_path))
    assert returned_csv == str(csv_path)
    assert returned_md == str(md_path)
