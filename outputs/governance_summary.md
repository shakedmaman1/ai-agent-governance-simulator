# AI Agent Governance Summary Report

## Overview

- **Total actions:** 40
- **Pass rate:** 67.5%
- **Average score:** 86.9
- **Decision accuracy:** 82.5%
- **Risk-level accuracy:** 82.5%
- **Approval-level accuracy:** 82.5%
- **Human review rate:** 70.0%

## Decision Distribution

- **Allowed:** 12
- **Requires approval:** 21
- **Blocked:** 7

## Most Common Failure Reasons

- `wrong_risk_level`: 7
- `wrong_decision`: 7
- `wrong_approval_level`: 7

## Top Policy References Used

- `POL-009`: 13
- `POL-011`: 8
- `POL-001`: 4
- `POL-010`: 4
- `POL-012`: 4
- `POL-007`: 4
- `POL-008`: 4
- `POL-004`: 3
- `POL-006`: 3
- `POL-003`: 3

## Failed Action Examples

- **ACT-005** (reset_password): score=75, expected=allowed, actual=allowed, failures=wrong_risk_level
- **ACT-007** (reset_password): score=75, expected=allowed, actual=allowed, failures=wrong_risk_level
- **ACT-009** (cancel_subscription): score=75, expected=allowed, actual=allowed, failures=wrong_risk_level
- **ACT-016** (change_billing_email): score=25, expected=allowed, actual=requires_approval, failures=wrong_decision, wrong_risk_level, wrong_approval_level
- **ACT-018** (change_billing_email): score=50, expected=allowed, actual=requires_approval, failures=wrong_decision, wrong_approval_level

## Recommendations

- Review decision rules for action types with frequent decision mismatches.
- Tune risk scoring thresholds, especially for sensitive and financial actions.
- Clarify approval-level mapping so policy outcomes route to the correct approver.
- Decision accuracy is below target; prioritize policy engine test coverage.
- Risk-level accuracy is below target; validate VIP, refund, and sensitive-data rules.
- Approval-level accuracy is below target; reconcile manager vs compliance thresholds.
- Human review rate is high; consider refining auto-approval criteria for low-risk actions.
