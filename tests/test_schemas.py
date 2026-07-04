"""Tests for Pydantic governance schemas."""

import pytest
from pydantic import ValidationError

from src.schemas import (
    AgentAction,
    ApprovalLevel,
    GovernanceDecision,
    GovernanceDecisionType,
    GovernanceEvaluationResult,
    RequestedByRole,
    RiskLevel,
)
from tests.conftest import make_action


def test_valid_agent_action_is_accepted():
    action = make_action(action_id="ACT-001")
    assert action.action_id == "ACT-001"
    assert action.confidence == 0.95


def test_confidence_above_one_is_rejected():
    with pytest.raises(ValidationError):
        make_action(confidence=1.5)


def test_negative_amount_is_rejected():
    with pytest.raises(ValidationError):
        make_action(amount=-1.0)


def test_invalid_policy_ref_is_rejected():
    with pytest.raises(ValidationError):
        GovernanceDecision(
            action_id="ACT-001",
            decision=GovernanceDecisionType.BLOCKED,
            risk_level=RiskLevel.HIGH,
            approval_level=ApprovalLevel.NONE,
            policy_refs=["POL-999"],
            reason="Invalid policy reference for testing purposes.",
            human_review_required=False,
            confidence=0.9,
        )


def test_requires_approval_with_none_approval_level_is_rejected():
    with pytest.raises(ValidationError):
        GovernanceDecision(
            action_id="ACT-001",
            decision=GovernanceDecisionType.REQUIRES_APPROVAL,
            risk_level=RiskLevel.HIGH,
            approval_level=ApprovalLevel.NONE,
            policy_refs=["POL-001"],
            reason="Requires approval but approval level is missing.",
            human_review_required=True,
            confidence=0.9,
        )


def test_allowed_with_manager_approval_level_is_rejected():
    with pytest.raises(ValidationError):
        GovernanceDecision(
            action_id="ACT-001",
            decision=GovernanceDecisionType.ALLOWED,
            risk_level=RiskLevel.LOW,
            approval_level=ApprovalLevel.MANAGER,
            policy_refs=["POL-001"],
            reason="Allowed decision cannot retain manager approval level.",
            human_review_required=False,
            confidence=0.9,
        )


def test_failed_evaluation_requires_failure_reasons():
    with pytest.raises(ValidationError):
        GovernanceEvaluationResult(
            action_id="ACT-001",
            passed=False,
            score=50,
            failure_reasons=[],
            improvement_note="Needs review.",
            requires_human_review=True,
        )


def test_requested_by_role_compliance_is_accepted():
    action = make_action(requested_by_role=RequestedByRole.COMPLIANCE)
    assert action.requested_by_role == RequestedByRole.COMPLIANCE
    assert action.requested_by_role.value == "compliance"
