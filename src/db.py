"""SQLite audit persistence for agent actions, decisions, and evaluations."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from src.schemas import AgentAction, GovernanceDecision, GovernanceEvaluationResult

DEFAULT_DB_FILENAME = "governance_audit.db"
DEFAULT_OUTPUT_DIR = Path("outputs")


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


def get_database_path(db_path: str | None = None) -> Path:
    """Resolve the database path and ensure the outputs directory exists."""
    if db_path is not None:
        path = Path(db_path)
    else:
        path = DEFAULT_OUTPUT_DIR / DEFAULT_DB_FILENAME

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection to the governance audit database."""
    path = get_database_path(db_path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str | None = None) -> str:
    """Create audit tables if they do not already exist."""
    path = get_database_path(db_path)

    with get_connection(str(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS actions (
                action_id TEXT PRIMARY KEY,
                customer_type TEXT NOT NULL,
                department TEXT NOT NULL,
                action_type TEXT NOT NULL,
                amount REAL NOT NULL,
                confidence REAL NOT NULL,
                contains_sensitive_data INTEGER NOT NULL,
                identity_verified INTEGER NOT NULL,
                requested_by_role TEXT NOT NULL,
                expected_decision TEXT NOT NULL,
                expected_risk_level TEXT NOT NULL,
                expected_approval_level TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS decisions (
                action_id TEXT PRIMARY KEY,
                decision TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                approval_level TEXT NOT NULL,
                policy_refs_json TEXT NOT NULL,
                reason TEXT NOT NULL,
                human_review_required INTEGER NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evaluations (
                action_id TEXT PRIMARY KEY,
                passed INTEGER NOT NULL,
                score INTEGER NOT NULL,
                failure_reasons_json TEXT NOT NULL,
                improvement_note TEXT NOT NULL,
                requires_human_review INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        connection.commit()

    return str(path)


def save_action(action: AgentAction, db_path: str | None = None) -> None:
    """Insert or replace an agent action audit record."""
    init_db(db_path)
    created_at = _utc_now_iso()

    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO actions (
                action_id,
                customer_type,
                department,
                action_type,
                amount,
                confidence,
                contains_sensitive_data,
                identity_verified,
                requested_by_role,
                expected_decision,
                expected_risk_level,
                expected_approval_level,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action.action_id,
                action.customer_type.value,
                action.department.value,
                action.action_type.value,
                action.amount,
                action.confidence,
                int(action.contains_sensitive_data),
                int(action.identity_verified),
                action.requested_by_role.value,
                action.expected_decision.value,
                action.expected_risk_level.value,
                action.expected_approval_level.value,
                created_at,
            ),
        )
        connection.commit()


def save_decision(decision: GovernanceDecision, db_path: str | None = None) -> None:
    """Insert or replace a governance decision audit record."""
    init_db(db_path)
    created_at = _utc_now_iso()

    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO decisions (
                action_id,
                decision,
                risk_level,
                approval_level,
                policy_refs_json,
                reason,
                human_review_required,
                confidence,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision.action_id,
                decision.decision.value,
                decision.risk_level.value,
                decision.approval_level.value,
                json.dumps(decision.policy_refs),
                decision.reason,
                int(decision.human_review_required),
                decision.confidence,
                created_at,
            ),
        )
        connection.commit()


def save_evaluation(
    result: GovernanceEvaluationResult, db_path: str | None = None
) -> None:
    """Insert or replace a governance evaluation audit record."""
    init_db(db_path)
    created_at = _utc_now_iso()

    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO evaluations (
                action_id,
                passed,
                score,
                failure_reasons_json,
                improvement_note,
                requires_human_review,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.action_id,
                int(result.passed),
                result.score,
                json.dumps(result.failure_reasons),
                result.improvement_note,
                int(result.requires_human_review),
                created_at,
            ),
        )
        connection.commit()


def save_full_run(
    action: AgentAction,
    decision: GovernanceDecision,
    evaluation: GovernanceEvaluationResult,
    db_path: str | None = None,
) -> None:
    """Initialize the database and persist a complete governance run."""
    init_db(db_path)
    save_action(action, db_path)
    save_decision(decision, db_path)
    save_evaluation(evaluation, db_path)
