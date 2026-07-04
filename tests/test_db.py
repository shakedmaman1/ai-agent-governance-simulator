"""Tests for SQLite audit persistence."""

import json
import sqlite3

from src.db import init_db, save_action, save_full_run
from src.evaluator import evaluate_agent_action, evaluate_governance_decision
from tests.conftest import make_action


def test_init_db_creates_all_tables(tmp_path):
    db_path = tmp_path / "audit.db"
    init_db(str(db_path))

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert {"actions", "decisions", "evaluations"}.issubset(tables)


def test_save_full_run_inserts_one_row_per_table(tmp_path):
    db_path = tmp_path / "audit.db"
    action = make_action(action_id="ACT-DB-001")
    decision = evaluate_agent_action(action)
    evaluation = evaluate_governance_decision(action, decision)

    save_full_run(action, decision, evaluation, db_path=str(db_path))

    with sqlite3.connect(db_path) as connection:
        action_count = connection.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
        decision_count = connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        evaluation_count = connection.execute(
            "SELECT COUNT(*) FROM evaluations"
        ).fetchone()[0]

    assert action_count == 1
    assert decision_count == 1
    assert evaluation_count == 1


def test_save_action_uses_insert_or_replace(tmp_path):
    db_path = tmp_path / "audit.db"
    action = make_action(action_id="ACT-DB-002", amount=50.0)
    save_action(action, db_path=str(db_path))

    updated = make_action(action_id="ACT-DB-002", amount=125.0)
    save_action(updated, db_path=str(db_path))

    with sqlite3.connect(db_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
        amount = connection.execute(
            "SELECT amount FROM actions WHERE action_id = ?",
            ("ACT-DB-002",),
        ).fetchone()[0]

    assert count == 1
    assert amount == 125.0


def test_list_fields_are_stored_as_json_strings(tmp_path):
    db_path = tmp_path / "audit.db"
    action = make_action(
        action_id="ACT-DB-003",
        amount=750.0,
        confidence=0.88,
        expected_decision="requires_approval",
        expected_risk_level="High",
        expected_approval_level="manager",
    )
    decision = evaluate_agent_action(action)
    evaluation = evaluate_governance_decision(action, decision)

    save_full_run(action, decision, evaluation, db_path=str(db_path))

    with sqlite3.connect(db_path) as connection:
        policy_refs_json = connection.execute(
            "SELECT policy_refs_json FROM decisions WHERE action_id = ?",
            ("ACT-DB-003",),
        ).fetchone()[0]
        failure_reasons_json = connection.execute(
            "SELECT failure_reasons_json FROM evaluations WHERE action_id = ?",
            ("ACT-DB-003",),
        ).fetchone()[0]

    policy_refs = json.loads(policy_refs_json)
    failure_reasons = json.loads(failure_reasons_json)

    assert isinstance(policy_refs, list)
    assert len(policy_refs) >= 1
    assert isinstance(failure_reasons, list)


def test_booleans_are_stored_as_integers(tmp_path):
    db_path = tmp_path / "audit.db"
    action = make_action(
        action_id="ACT-DB-004",
        contains_sensitive_data=True,
        identity_verified=False,
    )
    decision = evaluate_agent_action(action)
    evaluation = evaluate_governance_decision(action, decision)

    save_full_run(action, decision, evaluation, db_path=str(db_path))

    with sqlite3.connect(db_path) as connection:
        action_row = connection.execute(
            "SELECT contains_sensitive_data, identity_verified FROM actions WHERE action_id = ?",
            ("ACT-DB-004",),
        ).fetchone()
        decision_row = connection.execute(
            "SELECT human_review_required FROM decisions WHERE action_id = ?",
            ("ACT-DB-004",),
        ).fetchone()
        evaluation_row = connection.execute(
            "SELECT passed, requires_human_review FROM evaluations WHERE action_id = ?",
            ("ACT-DB-004",),
        ).fetchone()

    assert action_row == (1, 0)
    assert decision_row[0] in (0, 1)
    assert evaluation_row[0] in (0, 1)
    assert evaluation_row[1] in (0, 1)
