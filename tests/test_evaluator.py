"""Tests for the governance policy engine and evaluation scoring."""

from src.evaluator import (
    evaluate_agent_action,
    evaluate_governance_decision,
    evaluate_many,
)
from src.schemas import (
    ActionType,
    ApprovalLevel,
    CustomerType,
    Department,
    GovernanceDecisionType,
    RequestedByRole,
    RiskLevel,
)
from tests.conftest import make_action


def test_refund_over_500_requires_manager_approval():
    action = make_action(
        action_id="ACT-002",
        amount=750.0,
        confidence=0.88,
        expected_decision=GovernanceDecisionType.REQUIRES_APPROVAL,
        expected_risk_level=RiskLevel.HIGH,
        expected_approval_level=ApprovalLevel.MANAGER,
    )
    decision = evaluate_agent_action(action)

    assert decision.decision == GovernanceDecisionType.REQUIRES_APPROVAL
    assert decision.approval_level == ApprovalLevel.MANAGER
    assert "POL-001" in decision.policy_refs


def test_refund_over_2000_requires_compliance_approval():
    action = make_action(
        action_id="ACT-003",
        amount=2500.0,
        confidence=0.82,
        requested_by_role=RequestedByRole.MANAGER,
        expected_decision=GovernanceDecisionType.REQUIRES_APPROVAL,
        expected_risk_level=RiskLevel.CRITICAL,
        expected_approval_level=ApprovalLevel.COMPLIANCE,
    )
    decision = evaluate_agent_action(action)

    assert decision.decision == GovernanceDecisionType.REQUIRES_APPROVAL
    assert decision.approval_level == ApprovalLevel.COMPLIANCE
    assert "POL-002" in decision.policy_refs


def test_refund_without_identity_verification_is_blocked():
    action = make_action(
        action_id="ACT-040",
        amount=150.0,
        identity_verified=False,
        expected_decision=GovernanceDecisionType.BLOCKED,
        expected_risk_level=RiskLevel.HIGH,
        expected_approval_level=ApprovalLevel.NONE,
    )
    decision = evaluate_agent_action(action)

    assert decision.decision == GovernanceDecisionType.BLOCKED
    assert "POL-004" in decision.policy_refs


def test_password_reset_without_identity_verification_is_blocked():
    action = make_action(
        action_id="ACT-006",
        action_type=ActionType.RESET_PASSWORD,
        amount=0.0,
        identity_verified=False,
        expected_decision=GovernanceDecisionType.BLOCKED,
        expected_risk_level=RiskLevel.HIGH,
        expected_approval_level=ApprovalLevel.NONE,
    )
    decision = evaluate_agent_action(action)

    assert decision.decision == GovernanceDecisionType.BLOCKED
    assert "POL-005" in decision.policy_refs


def test_export_customer_data_requires_compliance_approval():
    action = make_action(
        action_id="ACT-013",
        department=Department.COMPLIANCE,
        action_type=ActionType.EXPORT_CUSTOMER_DATA,
        amount=0.0,
        contains_sensitive_data=True,
        requested_by_role=RequestedByRole.ADMIN,
        expected_decision=GovernanceDecisionType.REQUIRES_APPROVAL,
        expected_risk_level=RiskLevel.CRITICAL,
        expected_approval_level=ApprovalLevel.COMPLIANCE,
    )
    decision = evaluate_agent_action(action)

    assert decision.decision == GovernanceDecisionType.REQUIRES_APPROVAL
    assert decision.approval_level == ApprovalLevel.COMPLIANCE
    assert "POL-003" in decision.policy_refs
    assert decision.human_review_required is True


def test_vip_cancel_subscription_requires_manager_approval():
    action = make_action(
        action_id="ACT-010",
        customer_type=CustomerType.VIP,
        action_type=ActionType.CANCEL_SUBSCRIPTION,
        amount=0.0,
        expected_decision=GovernanceDecisionType.REQUIRES_APPROVAL,
        expected_risk_level=RiskLevel.HIGH,
        expected_approval_level=ApprovalLevel.MANAGER,
    )
    decision = evaluate_agent_action(action)

    assert decision.decision == GovernanceDecisionType.REQUIRES_APPROVAL
    assert decision.approval_level == ApprovalLevel.MANAGER
    assert "POL-006" in decision.policy_refs


def test_retention_offer_over_300_requires_manager_approval():
    action = make_action(
        action_id="ACT-027",
        action_type=ActionType.SEND_RETENTION_OFFER,
        amount=450.0,
        expected_decision=GovernanceDecisionType.REQUIRES_APPROVAL,
        expected_risk_level=RiskLevel.HIGH,
        expected_approval_level=ApprovalLevel.MANAGER,
    )
    decision = evaluate_agent_action(action)

    assert decision.decision == GovernanceDecisionType.REQUIRES_APPROVAL
    assert decision.approval_level == ApprovalLevel.MANAGER
    assert "POL-007" in decision.policy_refs


def test_access_sensitive_record_by_non_admin_is_blocked():
    action = make_action(
        action_id="ACT-033",
        action_type=ActionType.ACCESS_SENSITIVE_RECORD,
        amount=0.0,
        contains_sensitive_data=True,
        requested_by_role=RequestedByRole.AGENT,
        expected_decision=GovernanceDecisionType.REQUIRES_APPROVAL,
        expected_risk_level=RiskLevel.CRITICAL,
        expected_approval_level=ApprovalLevel.COMPLIANCE,
    )
    decision = evaluate_agent_action(action)

    assert decision.decision == GovernanceDecisionType.BLOCKED
    assert decision.risk_level == RiskLevel.CRITICAL
    assert "POL-008" in decision.policy_refs


def test_access_sensitive_record_by_admin_requires_compliance_approval():
    action = make_action(
        action_id="ACT-034",
        action_type=ActionType.ACCESS_SENSITIVE_RECORD,
        amount=0.0,
        contains_sensitive_data=True,
        requested_by_role=RequestedByRole.ADMIN,
        expected_decision=GovernanceDecisionType.ALLOWED,
        expected_risk_level=RiskLevel.HIGH,
        expected_approval_level=ApprovalLevel.NONE,
    )
    decision = evaluate_agent_action(action)

    assert decision.decision == GovernanceDecisionType.REQUIRES_APPROVAL
    assert decision.approval_level == ApprovalLevel.COMPLIANCE
    assert "POL-008" in decision.policy_refs


def test_low_confidence_adds_pol_009_and_human_review():
    action = make_action(
        action_id="ACT-004",
        amount=200.0,
        confidence=0.65,
        expected_decision=GovernanceDecisionType.REQUIRES_APPROVAL,
        expected_risk_level=RiskLevel.MEDIUM,
        expected_approval_level=ApprovalLevel.TEAM_LEAD,
    )
    decision = evaluate_agent_action(action)

    assert "POL-009" in decision.policy_refs
    assert decision.human_review_required is True
    assert decision.decision == GovernanceDecisionType.REQUIRES_APPROVAL


def test_evaluate_governance_decision_passes_for_matching_expected_values():
    action = make_action(
        action_id="ACT-002",
        amount=750.0,
        confidence=0.88,
        expected_decision=GovernanceDecisionType.REQUIRES_APPROVAL,
        expected_risk_level=RiskLevel.HIGH,
        expected_approval_level=ApprovalLevel.MANAGER,
    )
    decision = evaluate_agent_action(action)
    result = evaluate_governance_decision(action, decision)

    assert result.passed is True
    assert result.score == 100
    assert result.failure_reasons == []


def test_evaluate_governance_decision_returns_failure_reasons_for_mismatch():
    action = make_action(
        action_id="ACT-002",
        amount=750.0,
        confidence=0.88,
        expected_decision=GovernanceDecisionType.ALLOWED,
        expected_risk_level=RiskLevel.LOW,
        expected_approval_level=ApprovalLevel.NONE,
    )
    decision = evaluate_agent_action(action)
    result = evaluate_governance_decision(action, decision)

    assert result.passed is False
    assert "wrong_decision" in result.failure_reasons
    assert "wrong_risk_level" in result.failure_reasons
    assert "wrong_approval_level" in result.failure_reasons


def test_evaluate_many_returns_one_tuple_per_action():
    actions = [
        make_action(action_id="ACT-001", amount=50.0),
        make_action(
            action_id="ACT-006",
            action_type=ActionType.RESET_PASSWORD,
            amount=0.0,
            identity_verified=False,
            expected_decision=GovernanceDecisionType.BLOCKED,
            expected_risk_level=RiskLevel.HIGH,
            expected_approval_level=ApprovalLevel.NONE,
        ),
    ]
    results = evaluate_many(actions)

    assert len(results) == 2
    assert results[0][0].action_id == "ACT-001"
    assert results[1][0].action_id == "ACT-006"
    assert results[0][1].action_id == "ACT-001"
    assert results[0][2].action_id == "ACT-001"
