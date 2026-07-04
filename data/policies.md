# Enterprise AI Agent Governance Policies

This document defines the business policies enforced by the AI Agent Governance & Approval Simulator.
All policies apply to proposed agent actions **before** execution.

---

## POL-001 — High-Value Refund Manager Approval

**Category:** Billing / Financial  
**Severity:** High

Refunds with an amount **greater than $500** require **manager** approval before execution.

| Condition | Threshold | Required Approval |
|-----------|-----------|-------------------|
| `action_type = refund_customer` AND `amount > 500` | $500 | manager |

---

## POL-002 — Critical Refund Compliance Approval

**Category:** Billing / Financial  
**Severity:** Critical

Refunds with an amount **greater than $2,000** require **compliance** approval before execution.
This policy takes precedence over POL-001 for amounts exceeding $2,000.

| Condition | Threshold | Required Approval |
|-----------|-----------|-------------------|
| `action_type = refund_customer` AND `amount > 2000` | $2,000 | compliance |

---

## POL-003 — Customer Data Export Compliance Gate

**Category:** Data Privacy / Compliance  
**Severity:** Critical

Exporting customer data always requires **compliance** approval, regardless of requester role.

| Condition | Required Approval |
|-----------|-------------------|
| `action_type = export_customer_data` | compliance |

---

## POL-004 — Account Access Identity Verification

**Category:** Security / Identity  
**Severity:** High

Account access actions require **identity verification** before they can proceed.
If identity is not verified, the action must be **blocked**.

| Condition | Required |
|-----------|----------|
| `action_type IN (reset_password, change_billing_email, refund_customer)` AND `identity_verified = false` | Block action |

---

## POL-005 — Password Reset Identity Block

**Category:** Security / Identity  
**Severity:** Critical

Password reset requests are **blocked** when the customer's identity has **not** been verified.

| Condition | Decision |
|-----------|----------|
| `action_type = reset_password` AND `identity_verified = false` | blocked |

---

## POL-006 — VIP Subscription Cancellation Approval

**Category:** Retention / Customer Success  
**Severity:** High

Cancelling a subscription for a **VIP** customer requires **manager** approval.

| Condition | Required Approval |
|-----------|-------------------|
| `action_type = cancel_subscription` AND `customer_type = vip` | manager |

---

## POL-007 — High-Value Retention Offer Approval

**Category:** Retention / Financial  
**Severity:** High

Retention offers with a value **greater than $300** require **manager** approval.

| Condition | Threshold | Required Approval |
|-----------|-----------|-------------------|
| `action_type = send_retention_offer` AND `amount > 300` | $300 | manager |

---

## POL-008 — Sensitive Record Access Approval

**Category:** Data Privacy / Security  
**Severity:** Critical

Accessing sensitive records requires **admin** or **compliance** approval.
Agents and team leads cannot auto-approve this action.

| Condition | Required Approval |
|-----------|-------------------|
| `action_type = access_sensitive_record` AND `requested_by_role NOT IN (admin, compliance)` | compliance |

---

## POL-009 — Low Confidence Human Review

**Category:** AI Safety / Quality  
**Severity:** Medium

Actions with a confidence score **below 0.70** require human review and cannot be auto-approved.

| Condition | Threshold | Required Approval |
|-----------|-----------|-------------------|
| `confidence < 0.70` | 0.70 | team_lead |

---

## POL-010 — Billing Email Change Identity Requirement

**Category:** Security / Billing  
**Severity:** High

Agents cannot change a customer's billing email without **identity verification**.
If an agent requests this action without verified identity, it must be **blocked**.

| Condition | Decision |
|-----------|----------|
| `action_type = change_billing_email` AND `requested_by_role = agent` AND `identity_verified = false` | blocked |

---

## POL-011 — Critical Risk Auto-Approval Prohibition

**Category:** Risk Management  
**Severity:** Critical

Actions assessed at **Critical** risk level cannot be auto-approved under any circumstances.
They must be routed for human approval at the appropriate level.

| Condition | Decision |
|-----------|----------|
| `risk_level = Critical` | requires_approval (never auto-allowed) |

---

## POL-012 — Support Ticket Escalation with Sensitive Data

**Category:** Support / Data Privacy  
**Severity:** Medium

Escalating a support ticket is generally **allowed**.
However, if the ticket **contains sensitive data**, the escalation requires **team_lead** approval.

| Condition | Decision |
|-----------|----------|
| `action_type = escalate_ticket` AND `contains_sensitive_data = false` | allowed |
| `action_type = escalate_ticket` AND `contains_sensitive_data = true` | requires_approval (team_lead) |

---

## Policy Summary Table

| Policy ID | Title | Trigger | Outcome |
|-----------|-------|---------|---------|
| POL-001 | High-Value Refund Manager Approval | refund > $500 | manager approval |
| POL-002 | Critical Refund Compliance Approval | refund > $2,000 | compliance approval |
| POL-003 | Customer Data Export Compliance Gate | export_customer_data | compliance approval |
| POL-004 | Account Access Identity Verification | account action, no identity | blocked |
| POL-005 | Password Reset Identity Block | reset_password, no identity | blocked |
| POL-006 | VIP Subscription Cancellation Approval | vip cancel | manager approval |
| POL-007 | High-Value Retention Offer Approval | retention offer > $300 | manager approval |
| POL-008 | Sensitive Record Access Approval | access_sensitive_record by non-admin | compliance approval |
| POL-009 | Low Confidence Human Review | confidence < 0.70 | team_lead approval |
| POL-010 | Billing Email Change Identity Requirement | agent + no identity | blocked |
| POL-011 | Critical Risk Auto-Approval Prohibition | risk = Critical | requires_approval |
| POL-012 | Support Ticket Escalation with Sensitive Data | escalate + sensitive | team_lead approval |
