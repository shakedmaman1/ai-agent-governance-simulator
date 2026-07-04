"""Tests for CLI workflow helpers."""

from pathlib import Path

import pytest

from src.main import load_actions, parse_bool, run_workflow
from src.schemas import AgentAction


def test_parse_bool_handles_true_variants():
    assert parse_bool("true") is True
    assert parse_bool("True") is True
    assert parse_bool("TRUE") is True
    assert parse_bool("1") is True
    assert parse_bool("yes") is True


def test_parse_bool_handles_false_variants():
    assert parse_bool("false") is False
    assert parse_bool("False") is False
    assert parse_bool("FALSE") is False
    assert parse_bool("0") is False
    assert parse_bool("no") is False


def test_parse_bool_rejects_invalid_string():
    with pytest.raises(ValueError, match="Invalid boolean value"):
        parse_bool("maybe")


def test_load_actions_loads_all_rows_from_csv():
    actions = load_actions("data/actions.csv")
    assert len(actions) == 40


def test_load_actions_returns_agent_action_objects():
    actions = load_actions("data/actions.csv")
    assert all(isinstance(action, AgentAction) for action in actions)


def test_load_actions_includes_compliance_role():
    actions = load_actions("data/actions.csv")
    compliance_actions = [
        action for action in actions if action.requested_by_role.value == "compliance"
    ]
    assert len(compliance_actions) == 2
    assert {action.action_id for action in compliance_actions} == {"ACT-014", "ACT-035"}


def test_run_workflow_with_limit_and_reset_db(tmp_path, monkeypatch):
    db_path = tmp_path / "governance_audit.db"
    csv_path = tmp_path / "governance_report.csv"
    md_path = tmp_path / "governance_summary.md"

    def patched_get_database_path(db_path=None):
        if db_path is not None:
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path / "governance_audit.db"

    monkeypatch.setattr("src.db.get_database_path", patched_get_database_path)

    def patched_generate_reports(db_path=None):
        from src.report import (
            generate_governance_report,
            generate_governance_summary,
        )

        db = str(tmp_path / "governance_audit.db")
        return (
            generate_governance_report(db_path=db, output_path=str(csv_path)),
            generate_governance_summary(db_path=db, output_path=str(md_path)),
        )

    monkeypatch.setattr("src.main.generate_reports", patched_generate_reports)

    stats = run_workflow(
        input_path="data/actions.csv",
        limit=5,
        reset_db=True,
    )

    assert stats["loaded"] == 5
    assert stats["processed"] == 5
    assert stats["errors"] == 0
    assert db_path.exists()


def test_run_workflow_summary_dict_contains_expected_metrics(tmp_path, monkeypatch):
    csv_path = tmp_path / "governance_report.csv"
    md_path = tmp_path / "governance_summary.md"

    def patched_get_database_path(db_path=None):
        if db_path is not None:
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        path = tmp_path / "governance_audit.db"
        tmp_path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr("src.db.get_database_path", patched_get_database_path)

    def patched_generate_reports(db_path=None):
        from src.report import (
            generate_governance_report,
            generate_governance_summary,
        )

        db = str(tmp_path / "governance_audit.db")
        return (
            generate_governance_report(db_path=db, output_path=str(csv_path)),
            generate_governance_summary(db_path=db, output_path=str(md_path)),
        )

    monkeypatch.setattr("src.main.generate_reports", patched_generate_reports)

    stats = run_workflow(
        input_path="data/actions.csv",
        limit=5,
        reset_db=True,
    )

    evaluated = int(stats["passed"]) + int(stats["failed"])
    pass_rate = (int(stats["passed"]) / evaluated * 100) if evaluated else 0.0

    # Map workflow stats to the expected summary semantics.
    summary = {
        "total_actions": stats["loaded"],
        "successful": stats["processed"],
        "errors": stats["errors"],
        "passed": stats["passed"],
        "failed": stats["failed"],
        "pass_rate": pass_rate,
        "csv_report": stats["csv_path"],
        "markdown_summary": stats["md_path"],
    }

    assert summary["total_actions"] == 5
    assert summary["successful"] == 5
    assert summary["errors"] == 0
    assert summary["passed"] >= 0
    assert summary["failed"] >= 0
    assert 0 <= summary["pass_rate"] <= 100
    assert Path(summary["csv_report"]).exists()
    assert Path(summary["markdown_summary"]).exists()
