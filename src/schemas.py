"""Pydantic validation models for AI agent governance actions and decisions."""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

VALID_POLICY_REFS: frozenset[str] = frozenset(f"POL-{i:03d}" for i in range(1, 13))


class CustomerType(str, Enum):
    """Customer segment for policy and risk evaluation."""

    REGULAR = "regular"
    VIP = "vip"
    BUSINESS = "business"


class Department(str, Enum):
    """Organizational department requesting the agent action."""

    SUPPORT = "support"
    BILLING = "billing"
    TECHNICAL = "technical"
    RETENTION = "retention"
    COMPLIANCE = "compliance"


class ActionType(str, Enum):
    """Type of action proposed by an AI agent."""

    REFUND_CUSTOMER = "refund_customer"
    RESET_PASSWORD = "reset_password"
    CANCEL_SUBSCRIPTION = "cancel_subscription"
    EXPORT_CUSTOMER_DATA = "export_customer_data"
    CHANGE_BILLING_EMAIL = "change_billing_email"
    ESCALATE_TICKET = "escalate_ticket"
    UPDATE_CUSTOMER_PLAN = "update_customer_plan"
    SEND_RETENTION_OFFER = "send_retention_offer"
    CLOSE_SUPPORT_TICKET = "close_support_ticket"
    ACCESS_SENSITIVE_RECORD = "access_sensitive_record"


class RequestedByRole(str, Enum):
    """Role of the person or system requesting the action."""

    AGENT = "agent"
    TEAM_LEAD = "team_lead"
    MANAGER = "manager"
    ADMIN = "admin"
    COMPLIANCE = "compliance"


class GovernanceDecisionType(str, Enum):
    """Final governance outcome for a proposed action."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REQUIRES_APPROVAL = "requires_approval"


class RiskLevel(str, Enum):
    """Assessed risk level for a proposed or evaluated action."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class ApprovalLevel(str, Enum):
    """Human approval tier required before execution."""

    NONE = "none"
    TEAM_LEAD = "team_lead"
    MANAGER = "manager"
    COMPLIANCE = "compliance"


class AgentAction(BaseModel):
    """A proposed AI agent action loaded from synthetic evaluation data."""

    action_id: str
    customer_type: CustomerType
    department: Department
    action_type: ActionType
    amount: float
    confidence: float
    contains_sensitive_data: bool
    identity_verified: bool
    requested_by_role: RequestedByRole
    expected_decision: GovernanceDecisionType
    expected_risk_level: RiskLevel
    expected_approval_level: ApprovalLevel

    @field_validator("action_id", mode="before")
    @classmethod
    def strip_and_require_action_id(cls, value: object) -> str:
        """Strip whitespace and reject empty action identifiers."""
        if not isinstance(value, str):
            raise ValueError("action_id must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("action_id cannot be empty")
        return stripped

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float) -> float:
        """Ensure monetary amounts are non-negative."""
        if value < 0:
            raise ValueError("amount must be greater than or equal to 0")
        return value

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        """Ensure confidence is a probability between 0 and 1."""
        if not 0 <= value <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return value


class GovernanceDecision(BaseModel):
    """Governance outcome produced after policy and risk evaluation."""

    action_id: str
    decision: GovernanceDecisionType
    risk_level: RiskLevel
    approval_level: ApprovalLevel
    policy_refs: list[str]
    reason: str
    human_review_required: bool
    confidence: float

    @field_validator("action_id", mode="before")
    @classmethod
    def strip_and_require_action_id(cls, value: object) -> str:
        """Strip whitespace and reject empty action identifiers."""
        if not isinstance(value, str):
            raise ValueError("action_id must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("action_id cannot be empty")
        return stripped

    @field_validator("reason", mode="before")
    @classmethod
    def strip_and_require_reason(cls, value: object) -> str:
        """Strip whitespace and reject empty decision reasons."""
        if not isinstance(value, str):
            raise ValueError("reason must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason cannot be empty")
        return stripped

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        """Ensure confidence is a probability between 0 and 1."""
        if not 0 <= value <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return value

    @field_validator("policy_refs")
    @classmethod
    def validate_policy_refs(cls, value: list[str]) -> list[str]:
        """Ensure at least one valid POL-001 through POL-012 reference is present."""
        if not value:
            raise ValueError("policy_refs must contain at least one policy")
        invalid = [ref for ref in value if ref not in VALID_POLICY_REFS]
        if invalid:
            raise ValueError(
                f"invalid policy references: {invalid}. "
                f"Each ref must be one of {sorted(VALID_POLICY_REFS)}"
            )
        return value

    @model_validator(mode="after")
    def validate_decision_approval_consistency(self) -> Self:
        """Align approval level with the governance decision type."""
        if self.decision == GovernanceDecisionType.ALLOWED:
            if self.approval_level != ApprovalLevel.NONE:
                raise ValueError(
                    "allowed decisions must have approval_level 'none'"
                )
        elif self.decision == GovernanceDecisionType.REQUIRES_APPROVAL:
            if self.approval_level == ApprovalLevel.NONE:
                raise ValueError(
                    "requires_approval decisions must specify a non-none approval_level"
                )
        elif self.decision == GovernanceDecisionType.BLOCKED:
            if self.approval_level not in {ApprovalLevel.NONE, ApprovalLevel.COMPLIANCE}:
                raise ValueError(
                    "blocked decisions may only use approval_level 'none' or 'compliance'"
                )
        return self


class GovernanceEvaluationResult(BaseModel):
    """Result of comparing an actual governance decision against expected outcomes."""

    action_id: str
    passed: bool
    score: int = Field(ge=0, le=100)
    failure_reasons: list[str]
    improvement_note: str
    requires_human_review: bool

    @field_validator("action_id", mode="before")
    @classmethod
    def strip_and_require_action_id(cls, value: object) -> str:
        """Strip whitespace and reject empty action identifiers."""
        if not isinstance(value, str):
            raise ValueError("action_id must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("action_id cannot be empty")
        return stripped

    @field_validator("improvement_note", mode="before")
    @classmethod
    def strip_and_require_improvement_note(cls, value: object) -> str:
        """Strip whitespace and reject empty improvement notes."""
        if not isinstance(value, str):
            raise ValueError("improvement_note must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("improvement_note cannot be empty")
        return stripped

    @model_validator(mode="after")
    def validate_failure_reasons_when_not_passed(self) -> Self:
        """Require at least one failure reason when evaluation did not pass."""
        if not self.passed and not self.failure_reasons:
            raise ValueError(
                "failure_reasons must contain at least one item when passed is false"
            )
        return self
