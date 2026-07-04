"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import pytest

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


def make_action(**overrides) -> AgentAction:
    """Build a valid AgentAction with optional field overrides."""
    defaults = {
        "action_id": "ACT-TEST",
        "customer_type": CustomerType.REGULAR,
        "department": Department.SUPPORT,
        "action_type": ActionType.REFUND_CUSTOMER,
        "amount": 50.0,
        "confidence": 0.95,
        "contains_sensitive_data": False,
        "identity_verified": True,
        "requested_by_role": RequestedByRole.AGENT,
        "expected_decision": GovernanceDecisionType.ALLOWED,
        "expected_risk_level": RiskLevel.LOW,
        "expected_approval_level": ApprovalLevel.NONE,
    }
    defaults.update(overrides)
    return AgentAction(**defaults)


@pytest.fixture
def sample_action() -> AgentAction:
    """Return a baseline valid agent action."""
    return make_action()
