"""Governance policy engine for evaluating proposed AI agent actions."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.schemas import (
    ActionType,
    AgentAction,
    ApprovalLevel,
    CustomerType,
    GovernanceDecision,
    GovernanceDecisionType,
    GovernanceEvaluationResult,
    RequestedByRole,
    RiskLevel,
)

LOW_CONFIDENCE_THRESHOLD = 0.7

RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}

APPROVAL_ORDER: dict[ApprovalLevel, int] = {
    ApprovalLevel.NONE: 0,
    ApprovalLevel.TEAM_LEAD: 1,
    ApprovalLevel.MANAGER: 2,
    ApprovalLevel.COMPLIANCE: 3,
}

DECISION_ORDER: dict[GovernanceDecisionType, int] = {
    GovernanceDecisionType.ALLOWED: 0,
    GovernanceDecisionType.REQUIRES_APPROVAL: 1,
    GovernanceDecisionType.BLOCKED: 2,
}

DEFAULT_POLICY_BY_ACTION: dict[ActionType, str] = {
    ActionType.REFUND_CUSTOMER: "POL-001",
    ActionType.RESET_PASSWORD: "POL-004",
    ActionType.CANCEL_SUBSCRIPTION: "POL-006",
    ActionType.EXPORT_CUSTOMER_DATA: "POL-003",
    ActionType.CHANGE_BILLING_EMAIL: "POL-010",
    ActionType.ESCALATE_TICKET: "POL-012",
    ActionType.UPDATE_CUSTOMER_PLAN: "POL-009",
    ActionType.SEND_RETENTION_OFFER: "POL-007",
    ActionType.CLOSE_SUPPORT_TICKET: "POL-009",
    ActionType.ACCESS_SENSITIVE_RECORD: "POL-008",
}


@dataclass
class _EvaluationState:
    """Mutable accumulator for policy evaluation outcomes."""

    decision: GovernanceDecisionType = GovernanceDecisionType.ALLOWED
    risk_level: RiskLevel = RiskLevel.LOW
    approval_level: ApprovalLevel = ApprovalLevel.NONE
    policy_refs: set[str] = field(default_factory=set)
    reasons: list[str] = field(default_factory=list)
    human_review_required: bool = False


def _max_risk(current: RiskLevel, candidate: RiskLevel) -> RiskLevel:
    """Return the higher of two risk levels."""
    return current if RISK_ORDER[current] >= RISK_ORDER[candidate] else candidate


def _max_approval(current: ApprovalLevel, candidate: ApprovalLevel) -> ApprovalLevel:
    """Return the stronger of two approval levels."""
    return (
        current if APPROVAL_ORDER[current] >= APPROVAL_ORDER[candidate] else candidate
    )


def _max_decision(
    current: GovernanceDecisionType, candidate: GovernanceDecisionType
) -> GovernanceDecisionType:
    """Return the stricter governance decision."""
    return (
        current
        if DECISION_ORDER[current] >= DECISION_ORDER[candidate]
        else candidate
    )


def _is_vague_reason(reason: str) -> bool:
    """Return True when a governance reason lacks actionable detail."""
    normalized = reason.strip().lower()
    if len(normalized) < 25:
        return True
    generic_only = {"blocked", "allowed", "requires approval", "denied", "approved"}
    return normalized in generic_only


def _build_improvement_note(failure_reasons: list[str]) -> str:
    """Map failure codes to a concise improvement recommendation."""
    if not failure_reasons:
        return "Governance decision matches expected outcome."

    notes = {
        "wrong_decision": "Refine decision rules for this action type.",
        "wrong_risk_level": "Improve risk scoring thresholds and sensitive-action handling.",
        "wrong_approval_level": "Clarify approval-level mapping for policy outcomes.",
        "missing_policy_refs": "Attach policy references for auditability.",
        "vague_reason": "Return a clearer governance reason.",
        "missing_human_review": "Flag blocked and approval-required actions for human review.",
    }
    unique_notes = [notes[code] for code in failure_reasons if code in notes]
    return " ".join(dict.fromkeys(unique_notes))


def _apply_outcome(
    state: _EvaluationState,
    *,
    decision: GovernanceDecisionType | None = None,
    risk_level: RiskLevel | None = None,
    approval_level: ApprovalLevel | None = None,
    policy_ref: str | None = None,
    reason: str | None = None,
    human_review: bool = False,
) -> None:
    """Merge a policy outcome into the current evaluation state."""
    if decision is not None:
        state.decision = _max_decision(state.decision, decision)
    if risk_level is not None:
        state.risk_level = _max_risk(state.risk_level, risk_level)
    if approval_level is not None:
        state.approval_level = _max_approval(state.approval_level, approval_level)
    if policy_ref is not None:
        state.policy_refs.add(policy_ref)
    if reason:
        state.reasons.append(reason)
    if human_review:
        state.human_review_required = True


def _normalize_blocked_approval(state: _EvaluationState) -> None:
    """Ensure blocked decisions only use none or compliance approval levels."""
    if state.decision != GovernanceDecisionType.BLOCKED:
        return
    if state.approval_level not in {ApprovalLevel.NONE, ApprovalLevel.COMPLIANCE}:
        state.approval_level = ApprovalLevel.NONE


def _normalize_allowed_approval(state: _EvaluationState) -> None:
    """Ensure allowed decisions do not retain a pending approval level."""
    if state.decision == GovernanceDecisionType.ALLOWED:
        state.approval_level = ApprovalLevel.NONE


def _evaluate_refund(action: AgentAction, state: _EvaluationState) -> None:
    """Apply refund-specific governance policies."""
    if not action.identity_verified:
        _apply_outcome(
            state,
            decision=GovernanceDecisionType.BLOCKED,
            risk_level=RiskLevel.HIGH,
            policy_ref="POL-004",
            reason="Refund blocked because customer identity is not verified (POL-004).",
        )
        return

    if action.amount > 2000:
        _apply_outcome(
            state,
            decision=GovernanceDecisionType.REQUIRES_APPROVAL,
            risk_level=RiskLevel.CRITICAL,
            approval_level=ApprovalLevel.COMPLIANCE,
            policy_ref="POL-002",
            reason=(
                f"Refund of ${action.amount:,.2f} exceeds $2,000 and requires "
                "compliance approval (POL-002)."
            ),
            human_review=True,
        )
        return

    if action.amount > 500:
        _apply_outcome(
            state,
            decision=GovernanceDecisionType.REQUIRES_APPROVAL,
            risk_level=RiskLevel.HIGH,
            approval_level=ApprovalLevel.MANAGER,
            policy_ref="POL-001",
            reason=(
                f"Refund of ${action.amount:,.2f} exceeds $500 and requires "
                "manager approval (POL-001)."
            ),
            human_review=True,
        )
        return

    refund_risk = RiskLevel.LOW if action.amount <= 100 else RiskLevel.MEDIUM
    _apply_outcome(
        state,
        decision=GovernanceDecisionType.ALLOWED,
        risk_level=refund_risk,
        reason=(
            f"Refund of ${action.amount:,.2f} is within auto-approval limits."
        ),
    )


def _evaluate_reset_password(action: AgentAction, state: _EvaluationState) -> None:
    """Apply password reset governance policies."""
    if not action.identity_verified:
        risk = RiskLevel.HIGH
        if action.confidence < LOW_CONFIDENCE_THRESHOLD:
            risk = RiskLevel.CRITICAL
        _apply_outcome(
            state,
            decision=GovernanceDecisionType.BLOCKED,
            risk_level=risk,
            policy_ref="POL-005",
            reason=(
                "Password reset blocked because customer identity is not verified "
                "(POL-005)."
            ),
            human_review=True,
        )
        return

    _apply_outcome(
        state,
        decision=GovernanceDecisionType.ALLOWED,
        risk_level=RiskLevel.MEDIUM,
        policy_ref="POL-004",
        reason="Password reset allowed after identity verification (POL-004).",
    )


def _evaluate_cancel_subscription(action: AgentAction, state: _EvaluationState) -> None:
    """Apply subscription cancellation governance policies."""
    if action.customer_type == CustomerType.VIP:
        _apply_outcome(
            state,
            decision=GovernanceDecisionType.REQUIRES_APPROVAL,
            risk_level=RiskLevel.HIGH,
            approval_level=ApprovalLevel.MANAGER,
            policy_ref="POL-006",
            reason="VIP subscription cancellation requires manager approval (POL-006).",
            human_review=True,
        )
        return

    _apply_outcome(
        state,
        decision=GovernanceDecisionType.ALLOWED,
        risk_level=RiskLevel.MEDIUM,
        reason="Standard subscription cancellation is within operational limits.",
    )


def _evaluate_export_customer_data(action: AgentAction, state: _EvaluationState) -> None:
    """Apply customer data export governance policies."""
    _apply_outcome(
        state,
        decision=GovernanceDecisionType.REQUIRES_APPROVAL,
        risk_level=RiskLevel.CRITICAL,
        approval_level=ApprovalLevel.COMPLIANCE,
        policy_ref="POL-003",
        reason="Customer data export requires compliance approval (POL-003).",
        human_review=True,
    )


def _evaluate_change_billing_email(action: AgentAction, state: _EvaluationState) -> None:
    """Apply billing email change governance policies."""
    if not action.identity_verified:
        _apply_outcome(
            state,
            decision=GovernanceDecisionType.BLOCKED,
            risk_level=RiskLevel.HIGH,
            policy_ref="POL-010",
            reason=(
                "Billing email change blocked because identity is not verified "
                "for an agent-initiated request (POL-010)."
            ),
            human_review=True,
        )
        return

    _apply_outcome(
        state,
        decision=GovernanceDecisionType.REQUIRES_APPROVAL,
        risk_level=RiskLevel.MEDIUM,
        approval_level=ApprovalLevel.TEAM_LEAD,
        policy_ref="POL-010",
        reason=(
            "Billing email change requires team lead approval after identity "
            "verification (POL-010)."
        ),
        human_review=True,
    )


def _evaluate_escalate_ticket(action: AgentAction, state: _EvaluationState) -> None:
    """Apply support ticket escalation governance policies."""
    if action.contains_sensitive_data:
        _apply_outcome(
            state,
            decision=GovernanceDecisionType.REQUIRES_APPROVAL,
            risk_level=RiskLevel.HIGH,
            approval_level=ApprovalLevel.MANAGER,
            policy_ref="POL-012",
            reason=(
                "Ticket escalation with sensitive data requires manager approval "
                "(POL-012)."
            ),
            human_review=True,
        )
        return

    _apply_outcome(
        state,
        decision=GovernanceDecisionType.ALLOWED,
        risk_level=RiskLevel.LOW,
        policy_ref="POL-012",
        reason="Ticket escalation allowed when no sensitive data is involved (POL-012).",
    )


def _evaluate_update_customer_plan(action: AgentAction, state: _EvaluationState) -> None:
    """Apply customer plan update governance policies."""
    if action.customer_type in {CustomerType.VIP, CustomerType.BUSINESS}:
        _apply_outcome(
            state,
            decision=GovernanceDecisionType.REQUIRES_APPROVAL,
            risk_level=RiskLevel.MEDIUM,
            approval_level=ApprovalLevel.TEAM_LEAD,
            reason=(
                f"{action.customer_type.value.title()} plan updates require team lead "
                "approval."
            ),
            human_review=True,
        )
        return

    _apply_outcome(
        state,
        decision=GovernanceDecisionType.ALLOWED,
        risk_level=RiskLevel.LOW,
        reason="Regular customer plan update is within auto-approval limits.",
    )


def _evaluate_send_retention_offer(action: AgentAction, state: _EvaluationState) -> None:
    """Apply retention offer governance policies."""
    if action.amount > 300:
        _apply_outcome(
            state,
            decision=GovernanceDecisionType.REQUIRES_APPROVAL,
            risk_level=RiskLevel.HIGH,
            approval_level=ApprovalLevel.MANAGER,
            policy_ref="POL-007",
            reason=(
                f"Retention offer of ${action.amount:,.2f} exceeds $300 and requires "
                "manager approval (POL-007)."
            ),
            human_review=True,
        )
        return

    _apply_outcome(
        state,
        decision=GovernanceDecisionType.ALLOWED,
        risk_level=RiskLevel.MEDIUM,
        reason=(
            f"Retention offer of ${action.amount:,.2f} is within auto-approval limits."
        ),
    )


def _evaluate_close_support_ticket(action: AgentAction, state: _EvaluationState) -> None:
    """Apply support ticket closure governance policies."""
    if action.confidence < LOW_CONFIDENCE_THRESHOLD:
        _apply_outcome(
            state,
            decision=GovernanceDecisionType.REQUIRES_APPROVAL,
            risk_level=RiskLevel.MEDIUM,
            approval_level=ApprovalLevel.TEAM_LEAD,
            policy_ref="POL-009",
            reason=(
                f"Ticket closure confidence {action.confidence:.2f} is below "
                f"{LOW_CONFIDENCE_THRESHOLD:.1f} and requires human review (POL-009)."
            ),
            human_review=True,
        )
        return

    _apply_outcome(
        state,
        decision=GovernanceDecisionType.ALLOWED,
        risk_level=RiskLevel.LOW,
        reason="Support ticket closure meets confidence threshold for auto-approval.",
    )


def _evaluate_access_sensitive_record(action: AgentAction, state: _EvaluationState) -> None:
    """Apply sensitive record access governance policies."""
    if action.requested_by_role == RequestedByRole.ADMIN:
        _apply_outcome(
            state,
            decision=GovernanceDecisionType.REQUIRES_APPROVAL,
            risk_level=RiskLevel.HIGH,
            approval_level=ApprovalLevel.COMPLIANCE,
            policy_ref="POL-008",
            reason=(
                "Sensitive record access by admin still requires compliance approval "
                "(POL-008)."
            ),
            human_review=True,
        )
        return

    _apply_outcome(
        state,
        decision=GovernanceDecisionType.BLOCKED,
        risk_level=RiskLevel.CRITICAL,
        approval_level=ApprovalLevel.COMPLIANCE,
        policy_ref="POL-008",
        reason=(
            "Sensitive record access blocked for non-admin roles and requires "
            "compliance review (POL-008)."
        ),
        human_review=True,
    )


def _apply_action_rules(action: AgentAction, state: _EvaluationState) -> None:
    """Dispatch action-specific policy evaluation."""
    handlers = {
        ActionType.REFUND_CUSTOMER: _evaluate_refund,
        ActionType.RESET_PASSWORD: _evaluate_reset_password,
        ActionType.CANCEL_SUBSCRIPTION: _evaluate_cancel_subscription,
        ActionType.EXPORT_CUSTOMER_DATA: _evaluate_export_customer_data,
        ActionType.CHANGE_BILLING_EMAIL: _evaluate_change_billing_email,
        ActionType.ESCALATE_TICKET: _evaluate_escalate_ticket,
        ActionType.UPDATE_CUSTOMER_PLAN: _evaluate_update_customer_plan,
        ActionType.SEND_RETENTION_OFFER: _evaluate_send_retention_offer,
        ActionType.CLOSE_SUPPORT_TICKET: _evaluate_close_support_ticket,
        ActionType.ACCESS_SENSITIVE_RECORD: _evaluate_access_sensitive_record,
    }
    handler = handlers[action.action_type]
    handler(action, state)


def _apply_low_confidence_overlay(action: AgentAction, state: _EvaluationState) -> None:
    """Apply POL-009 low-confidence human review requirements."""
    if action.confidence >= LOW_CONFIDENCE_THRESHOLD:
        return

    _apply_outcome(
        state,
        policy_ref="POL-009",
        reason=(
            f"Action confidence {action.confidence:.2f} is below "
            f"{LOW_CONFIDENCE_THRESHOLD:.1f} and requires human review (POL-009)."
        ),
        human_review=True,
    )
    state.risk_level = _max_risk(state.risk_level, RiskLevel.MEDIUM)

    if state.decision == GovernanceDecisionType.ALLOWED:
        _apply_outcome(
            state,
            decision=GovernanceDecisionType.REQUIRES_APPROVAL,
            approval_level=ApprovalLevel.TEAM_LEAD,
            reason="Low-confidence allowed action downgraded to team lead approval.",
            human_review=True,
        )


def _apply_critical_risk_overlay(action: AgentAction, state: _EvaluationState) -> None:
    """Apply POL-011 critical-risk auto-approval prohibition."""
    if state.risk_level != RiskLevel.CRITICAL:
        return

    _apply_outcome(
        state,
        policy_ref="POL-011",
        reason="Critical risk actions cannot be auto-approved (POL-011).",
        human_review=True,
    )

    if state.decision != GovernanceDecisionType.ALLOWED:
        return

    required_approval = ApprovalLevel.MANAGER
    if action.action_type in {
        ActionType.EXPORT_CUSTOMER_DATA,
        ActionType.ACCESS_SENSITIVE_RECORD,
    } or action.contains_sensitive_data:
        required_approval = ApprovalLevel.COMPLIANCE

    _apply_outcome(
        state,
        decision=GovernanceDecisionType.REQUIRES_APPROVAL,
        approval_level=required_approval,
        reason="Critical risk level requires elevated human approval.",
        human_review=True,
    )


def _ensure_policy_reference(action: AgentAction, state: _EvaluationState) -> None:
    """Attach a baseline policy reference when no policy was recorded."""
    if state.policy_refs:
        return
    default_policy = DEFAULT_POLICY_BY_ACTION[action.action_type]
    state.policy_refs.add(default_policy)
    state.reasons.append(
        f"Action evaluated under baseline policy {default_policy} with no escalation."
    )


def _build_reason(state: _EvaluationState) -> str:
    """Combine collected reason fragments into one audit-friendly string."""
    if not state.reasons:
        return "Governance evaluation completed with default allow decision."
    return " ".join(state.reasons)


def evaluate_agent_action(action: AgentAction) -> GovernanceDecision:
    """Evaluate a proposed agent action against enterprise governance policies."""
    state = _EvaluationState()

    _apply_action_rules(action, state)
    _apply_low_confidence_overlay(action, state)
    _apply_critical_risk_overlay(action, state)
    _ensure_policy_reference(action, state)

    _normalize_blocked_approval(state)
    _normalize_allowed_approval(state)

    if (
        state.decision in {
            GovernanceDecisionType.BLOCKED,
            GovernanceDecisionType.REQUIRES_APPROVAL,
        }
        and not state.human_review_required
    ):
        state.human_review_required = True

    return GovernanceDecision(
        action_id=action.action_id,
        decision=state.decision,
        risk_level=state.risk_level,
        approval_level=state.approval_level,
        policy_refs=sorted(state.policy_refs),
        reason=_build_reason(state),
        human_review_required=state.human_review_required,
        confidence=action.confidence,
    )


def evaluate_governance_decision(
    action: AgentAction,
    decision: GovernanceDecision,
) -> GovernanceEvaluationResult:
    """Compare an actual governance decision against expected synthetic outcomes."""
    score = 100
    failure_reasons: list[str] = []

    if decision.decision != action.expected_decision:
        score -= 30
        failure_reasons.append("wrong_decision")

    if decision.risk_level != action.expected_risk_level:
        score -= 25
        failure_reasons.append("wrong_risk_level")

    if decision.approval_level != action.expected_approval_level:
        score -= 20
        failure_reasons.append("wrong_approval_level")

    if not decision.policy_refs:
        score -= 10
        failure_reasons.append("missing_policy_refs")

    if _is_vague_reason(decision.reason):
        score -= 10
        failure_reasons.append("vague_reason")

    if (
        decision.decision in {
            GovernanceDecisionType.BLOCKED,
            GovernanceDecisionType.REQUIRES_APPROVAL,
        }
        and not decision.human_review_required
    ):
        score -= 5
        failure_reasons.append("missing_human_review")

    score = max(score, 0)
    matches_expected = (
        decision.decision == action.expected_decision
        and decision.risk_level == action.expected_risk_level
        and decision.approval_level == action.expected_approval_level
    )
    passed = score >= 80 and matches_expected

    return GovernanceEvaluationResult(
        action_id=action.action_id,
        passed=passed,
        score=score,
        failure_reasons=failure_reasons,
        improvement_note=_build_improvement_note(failure_reasons),
        requires_human_review=decision.human_review_required,
    )


def evaluate_many(
    actions: list[AgentAction],
) -> list[tuple[AgentAction, GovernanceDecision, GovernanceEvaluationResult]]:
    """Evaluate a batch of agent actions and compare each result to expectations."""
    results: list[tuple[AgentAction, GovernanceDecision, GovernanceEvaluationResult]] = []
    for action in actions:
        decision = evaluate_agent_action(action)
        evaluation = evaluate_governance_decision(action, decision)
        results.append((action, decision, evaluation))
    return results
