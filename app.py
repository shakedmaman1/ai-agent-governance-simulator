"""Streamlit dashboard for the AI Agent Governance & Approval Simulator."""

from __future__ import annotations

import io
import json
import traceback
import uuid
from contextlib import redirect_stdout
from pathlib import Path

import pandas as pd
import streamlit as st

from src.db import get_database_path, save_full_run
from src.evaluator import evaluate_agent_action, evaluate_governance_decision
from src.main import run_workflow
from src.report import (
    DEFAULT_CSV_OUTPUT,
    DEFAULT_MD_OUTPUT,
    generate_reports,
    load_governance_data,
)
from src.schemas import (
    ActionType,
    AgentAction,
    ApprovalLevel,
    CustomerType,
    Department,
    GovernanceDecision,
    GovernanceDecisionType,
    RequestedByRole,
    RiskLevel,
)

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "actions.csv"

TABLE_COLUMNS = [
    "action_id",
    "customer_type",
    "department",
    "action_type",
    "amount",
    "expected_decision",
    "actual_decision",
    "expected_risk_level",
    "actual_risk_level",
    "expected_approval_level",
    "actual_approval_level",
    "passed",
    "score",
    "human_review_required",
    "policy_refs_json",
    "reason",
    "failure_reasons_json",
    "improvement_note",
]

CONSOLE_DEFAULTS: dict[str, object] = {
    "customer_type": CustomerType.REGULAR.value,
    "department": Department.SUPPORT.value,
    "action_type": ActionType.REFUND_CUSTOMER.value,
    "amount": 50.0,
    "confidence": 0.92,
    "contains_sensitive_data": False,
    "identity_verified": True,
    "requested_by_role": RequestedByRole.AGENT.value,
    "agent_request": "Customer requests a standard refund for a billing issue.",
}

CONSOLE_PRESETS: dict[str, dict[str, object]] = {
    "refund_750": {
        "label": "Refund $750 for verified VIP customer",
        "agent_request": (
            "VIP customer requests a $750 refund for a duplicate billing charge. "
            "Identity verified."
        ),
        "values": {
            "customer_type": CustomerType.VIP.value,
            "department": Department.BILLING.value,
            "action_type": ActionType.REFUND_CUSTOMER.value,
            "amount": 750.0,
            "confidence": 0.88,
            "contains_sensitive_data": False,
            "identity_verified": True,
            "requested_by_role": RequestedByRole.AGENT.value,
        },
    },
    "export_data": {
        "label": "Export customer data",
        "agent_request": (
            "Compliance team requests a full export of customer account data "
            "for an internal audit."
        ),
        "values": {
            "customer_type": CustomerType.REGULAR.value,
            "department": Department.COMPLIANCE.value,
            "action_type": ActionType.EXPORT_CUSTOMER_DATA.value,
            "amount": 0.0,
            "confidence": 0.94,
            "contains_sensitive_data": True,
            "identity_verified": True,
            "requested_by_role": RequestedByRole.ADMIN.value,
        },
    },
    "reset_no_identity": {
        "label": "Password reset without identity verification",
        "agent_request": (
            "Support agent proposes resetting a password before identity "
            "verification is complete."
        ),
        "values": {
            "customer_type": CustomerType.REGULAR.value,
            "department": Department.SUPPORT.value,
            "action_type": ActionType.RESET_PASSWORD.value,
            "amount": 0.0,
            "confidence": 0.90,
            "contains_sensitive_data": False,
            "identity_verified": False,
            "requested_by_role": RequestedByRole.AGENT.value,
        },
    },
}

POLICY_SUMMARIES: dict[str, str] = {
    "POL-001": "Refunds above $500 require manager approval before execution.",
    "POL-002": "Refunds above $2,000 require compliance approval.",
    "POL-003": "Exporting customer data always requires compliance approval.",
    "POL-004": "Account access actions require verified customer identity.",
    "POL-005": "Password reset is blocked when identity is not verified.",
    "POL-006": "VIP subscription cancellation requires manager approval.",
    "POL-007": "Retention offers above $300 require manager approval.",
    "POL-008": "Sensitive record access requires admin or compliance approval.",
    "POL-009": "Low-confidence actions require human review.",
    "POL-010": "Agents cannot change billing email without identity verification.",
    "POL-011": "Critical-risk actions cannot be auto-approved.",
    "POL-012": "Ticket escalation with sensitive data requires approval.",
}


def _resolve_path(path: Path) -> Path:
    """Return an absolute path rooted in the project directory."""
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


@st.cache_data(show_spinner=False)
def _load_data(db_path: str) -> pd.DataFrame:
    """Load governance audit data from SQLite."""
    return load_governance_data(db_path)


def _clear_data_cache() -> None:
    """Invalidate cached governance data after a new workflow run."""
    _load_data.clear()


def _run_governance_workflow(
    reset_db: bool,
    limit: int | None,
    show_failures: bool,
) -> dict[str, object] | None:
    """Execute the governance workflow and capture CLI output."""
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            stats = run_workflow(
                input_path=str(DEFAULT_INPUT),
                limit=limit,
                show_failures=show_failures,
                reset_db=reset_db,
            )
        st.session_state["workflow_log"] = buffer.getvalue()
        return stats
    except Exception as exc:
        st.session_state["workflow_log"] = buffer.getvalue()
        st.session_state["workflow_error"] = str(exc)
        st.session_state["workflow_traceback"] = traceback.format_exc()
        return None


def _distribution_chart(dataframe: pd.DataFrame, column: str, title: str) -> None:
    """Render a bar chart for a categorical governance column."""
    if column not in dataframe.columns or dataframe.empty:
        st.info(f"No data available for {title.lower()}.")
        return

    counts = dataframe[column].value_counts().sort_index()
    chart_df = counts.rename("count").reset_index()
    chart_df.columns = [column, "count"]
    st.subheader(title)
    st.bar_chart(chart_df, x=column, y="count")


def _apply_filters(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Apply sidebar filters to the governance data table."""
    filtered = dataframe.copy()

    filter_specs = [
        ("Decision", "actual_decision"),
        ("Risk level", "actual_risk_level"),
        ("Approval level", "actual_approval_level"),
        ("Action type", "action_type"),
        ("Department", "department"),
    ]

    for label, column in filter_specs:
        if column not in filtered.columns:
            continue
        options = sorted(filtered[column].dropna().unique().tolist())
        selected = st.multiselect(label, options=options, default=[], key=f"filter_{column}")
        if selected:
            filtered = filtered[filtered[column].isin(selected)]

    passed_filter = st.selectbox(
        "Evaluation result",
        options=["All", "Passed", "Failed"],
        index=0,
        key="filter_passed",
    )
    if passed_filter == "Passed":
        filtered = filtered[filtered["passed"] == True]  # noqa: E712
    elif passed_filter == "Failed":
        filtered = filtered[filtered["passed"] == False]  # noqa: E712

    return filtered


def _enum_index(options: list[str], value: str) -> int:
    """Return the selectbox index for a value, defaulting to zero."""
    try:
        return options.index(value)
    except ValueError:
        return 0


def _new_console_action_id() -> str:
    """Generate a unique action ID for console submissions."""
    return f"CONSOLE-{uuid.uuid4().hex[:8].upper()}"


def _build_console_action(form_values: dict[str, object]) -> AgentAction:
    """Build an AgentAction from console form values with demo placeholders."""
    return AgentAction(
        action_id=str(form_values["action_id"]),
        customer_type=CustomerType(str(form_values["customer_type"])),
        department=Department(str(form_values["department"])),
        action_type=ActionType(str(form_values["action_type"])),
        amount=float(form_values["amount"]),
        confidence=float(form_values["confidence"]),
        contains_sensitive_data=bool(form_values["contains_sensitive_data"]),
        identity_verified=bool(form_values["identity_verified"]),
        requested_by_role=RequestedByRole(str(form_values["requested_by_role"])),
        expected_decision=GovernanceDecisionType.ALLOWED,
        expected_risk_level=RiskLevel.LOW,
        expected_approval_level=ApprovalLevel.NONE,
    )


def _render_why_decision_panel(decision: GovernanceDecision) -> None:
    """Show a concise explanation of why the governance engine decided this way."""
    st.markdown("#### Why this decision?")
    with st.container(border=True):
        st.markdown(f"**Decision:** `{decision.decision.value}`")
        st.markdown(f"**Main reason:** {decision.reason}")
        st.markdown(
            f"**Policy refs:** {', '.join(f'`{ref}`' for ref in decision.policy_refs)}"
            if decision.policy_refs
            else "**Policy refs:** none"
        )
        st.markdown(f"**Risk level:** `{decision.risk_level.value}`")
        st.markdown(f"**Approval level:** `{decision.approval_level.value}`")
        st.markdown(
            f"**Human review required:** "
            f"{'Yes' if decision.human_review_required else 'No'}"
        )

        matched_policies = [
            f"- **{ref}** — {POLICY_SUMMARIES[ref]}"
            for ref in decision.policy_refs
            if ref in POLICY_SUMMARIES
        ]
        if matched_policies:
            st.markdown("**Policy explanations**")
            st.markdown("\n".join(matched_policies))


def _render_interview_demo_guide() -> None:
    """Show a step-by-step guide for a 60-second live interview demo."""
    with st.expander("60-second Interview Demo", expanded=False):
        st.markdown(
            """
Follow these steps in order:

1. Click **Refund $750 for verified VIP customer** to load the preset.
2. Click **Evaluate Proposed Agent Action**.
3. Scroll to **Proposed agent action (JSON)** and point out the structured agent proposal.
4. Scroll to **Governance decision (JSON)** and show the governance outcome.
5. Open **Why this decision?** and explain **POL-001**:
   refunds above $500 require **manager approval** before execution.
6. Click **Save to audit log** to persist the action, decision, and evaluation.
7. Switch to **Governance Dashboard** and show:
   - updated metrics
   - the new record in the data table
   - **Reports** (CSV download + Markdown summary preview)

**Talking point:** The agent proposed a refund, but the governance layer routed it for
human approval instead of auto-executing it.
            """
        )


def _save_console_to_audit_log(action: AgentAction, decision: GovernanceDecision) -> None:
    """Persist a console evaluation to SQLite and regenerate reports."""
    evaluation = evaluate_governance_decision(action, decision)
    save_full_run(action, decision, evaluation)
    csv_path, md_path = generate_reports()
    _clear_data_cache()
    st.session_state["console_save_message"] = (
        f"Saved **{action.action_id}** to the audit log "
        f"(action, decision, evaluation).\n\n"
        f"- Database: `{get_database_path()}`\n"
        f"- CSV report: `{csv_path}`\n"
        f"- Markdown summary: `{md_path}`"
    )


def _render_decision_banner(decision: GovernanceDecision) -> None:
    """Show a visual banner for the governance outcome."""
    label = decision.decision.value.replace("_", " ").title()
    message = decision.reason

    if decision.decision == GovernanceDecisionType.ALLOWED:
        st.success(f"**Allowed** — {message}")
    elif decision.decision == GovernanceDecisionType.REQUIRES_APPROVAL:
        st.warning(f"**Requires Approval** — {message}")
    else:
        st.error(f"**Blocked** — {message}")

    st.caption(f"Governance outcome: {label}")


def _render_console_results(action: AgentAction, decision: GovernanceDecision) -> None:
    """Render governance evaluation output for the agent console."""
    _render_decision_banner(decision)
    _render_why_decision_panel(decision)

    metric_cols = st.columns(5)
    metric_cols[0].metric("Decision", decision.decision.value)
    metric_cols[1].metric("Risk level", decision.risk_level.value)
    metric_cols[2].metric("Approval level", decision.approval_level.value)
    metric_cols[3].metric("Human review", "Yes" if decision.human_review_required else "No")
    metric_cols[4].metric("Confidence", f"{decision.confidence:.2f}")

    st.markdown("#### Simulated flow")
    st.markdown(
        "1. **User request** → 2. **AI agent action proposal** → "
        "3. **Governance engine decision** → 4. **Audit-style output**"
    )

    output_cols = st.columns(2)
    with output_cols[0]:
        st.markdown("**Proposed agent action (JSON)**")
        st.json(action.model_dump(mode="json"))
    with output_cols[1]:
        st.markdown("**Governance decision (JSON)**")
        st.json(decision.model_dump(mode="json"))


def _apply_console_preset(preset_key: str) -> None:
    """Load a preset configuration into the console form state."""
    preset = CONSOLE_PRESETS[preset_key]
    st.session_state["console_defaults"] = {
        **CONSOLE_DEFAULTS,
        **preset["values"],
        "agent_request": preset["agent_request"],
    }
    st.session_state["console_preset_key"] = preset_key
    st.session_state.pop("console_save_message", None)


def _render_agent_console() -> None:
    """Render the interactive AI Agent Console tab."""
    st.subheader("AI Agent Console")
    st.markdown(
        "This console simulates an enterprise AI agent proposing an action. Before execution, "
        "the governance layer checks policy rules, risk level, approval requirements, and "
        "human-review conditions."
    )

    _render_interview_demo_guide()

    defaults = {**CONSOLE_DEFAULTS, **st.session_state.get("console_defaults", {})}

    st.markdown("#### Quick demo presets")
    preset_cols = st.columns(3)
    for index, (preset_key, preset) in enumerate(CONSOLE_PRESETS.items()):
        if preset_cols[index].button(preset["label"], use_container_width=True):
            _apply_console_preset(preset_key)
            st.session_state.pop("console_result", None)
            st.rerun()

    with st.form("agent_console_form", clear_on_submit=False):
        st.markdown("#### Propose an agent action")
        agent_request = st.text_area(
            "Agent request (demo text only — not parsed by an LLM)",
            value=str(defaults.get("agent_request", CONSOLE_DEFAULTS["agent_request"])),
            help="Descriptive demo text showing what the user asked the agent to do.",
        )

        form_cols = st.columns(2)
        with form_cols[0]:
            customer_type = st.selectbox(
                "Customer type",
                options=[item.value for item in CustomerType],
                index=_enum_index(
                    [item.value for item in CustomerType],
                    str(defaults["customer_type"]),
                ),
            )
            department = st.selectbox(
                "Department",
                options=[item.value for item in Department],
                index=_enum_index(
                    [item.value for item in Department],
                    str(defaults["department"]),
                ),
            )
            action_type = st.selectbox(
                "Action type",
                options=[item.value for item in ActionType],
                index=_enum_index(
                    [item.value for item in ActionType],
                    str(defaults["action_type"]),
                ),
            )
            amount = st.number_input(
                "Amount (USD)",
                min_value=0.0,
                value=float(defaults["amount"]),
                step=1.0,
            )
        with form_cols[1]:
            confidence = st.slider(
                "Confidence",
                min_value=0.0,
                max_value=1.0,
                value=float(defaults["confidence"]),
                step=0.01,
            )
            contains_sensitive_data = st.checkbox(
                "Contains sensitive data",
                value=bool(defaults["contains_sensitive_data"]),
            )
            identity_verified = st.checkbox(
                "Identity verified",
                value=bool(defaults["identity_verified"]),
            )
            requested_by_role = st.selectbox(
                "Requested by role",
                options=[item.value for item in RequestedByRole],
                index=_enum_index(
                    [item.value for item in RequestedByRole],
                    str(defaults["requested_by_role"]),
                ),
            )

        evaluate_clicked = st.form_submit_button(
            "Evaluate Proposed Agent Action",
            type="primary",
            use_container_width=True,
        )

    if evaluate_clicked:
        try:
            form_values = {
                "action_id": _new_console_action_id(),
                "customer_type": customer_type,
                "department": department,
                "action_type": action_type,
                "amount": amount,
                "confidence": confidence,
                "contains_sensitive_data": contains_sensitive_data,
                "identity_verified": identity_verified,
                "requested_by_role": requested_by_role,
                "agent_request": agent_request,
            }
            action = _build_console_action(form_values)
            decision = evaluate_agent_action(action)
            st.session_state["console_result"] = {
                "action": action,
                "decision": decision,
                "agent_request": agent_request,
            }
            st.session_state.pop("console_save_message", None)
        except Exception as exc:
            st.error(f"Could not evaluate the proposed action: {exc}")
            with st.expander("Developer details"):
                st.code(traceback.format_exc())

    result = st.session_state.get("console_result")
    if result:
        st.markdown("---")
        st.markdown(f"**User request:** {result['agent_request']}")
        _render_console_results(result["action"], result["decision"])

        if st.session_state.get("console_save_message"):
            st.success(st.session_state["console_save_message"])

        if st.button(
            "Save to audit log",
            type="primary",
            use_container_width=True,
            key="save_console_audit",
        ):
            try:
                with st.spinner("Saving to SQLite and regenerating reports..."):
                    _save_console_to_audit_log(result["action"], result["decision"])
                st.rerun()
            except Exception as exc:
                st.session_state.pop("console_save_message", None)
                st.error(f"Could not save to audit log: {exc}")
                with st.expander("Developer details"):
                    st.code(traceback.format_exc())


def _render_governance_dashboard(
    db_path: Path,
    csv_path: Path,
    md_path: Path,
) -> None:
    """Render the main governance analytics dashboard tab."""
    if not db_path.exists():
        st.info(
            "No audit database found yet. Use **Run full governance workflow** in the sidebar "
            "or evaluate an action in **AI Agent Console** and save it to the audit log."
        )
        _render_demo_explanation()
        return

    try:
        dataframe = _load_data(str(db_path))
    except ValueError as exc:
        st.warning(str(exc))
        _render_demo_explanation()
        return
    except Exception as exc:
        st.error(f"Could not load governance data: {exc}")
        with st.expander("Developer details"):
            st.code(traceback.format_exc())
        return

    if "workflow_error" in st.session_state:
        st.error(st.session_state["workflow_error"])
        with st.expander("Developer details"):
            st.code(st.session_state.get("workflow_traceback", ""))

    stats = st.session_state.get("workflow_stats", {})
    total_actions = len(dataframe)
    passed_count = int(dataframe["passed"].sum())
    failed_count = int((~dataframe["passed"]).sum())
    evaluated = passed_count + failed_count
    pass_rate = (passed_count / evaluated * 100) if evaluated else 0.0
    average_score = float(dataframe["score"].mean()) if total_actions else 0.0
    human_review_rate = (
        float(dataframe["human_review_required"].mean()) * 100 if total_actions else 0.0
    )

    st.subheader("Overview")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Total actions", total_actions)
    metric_cols[1].metric(
        "Successfully processed",
        stats.get("processed", total_actions),
    )
    metric_cols[2].metric("Errors", stats.get("errors", 0))
    metric_cols[3].metric("Pass rate", f"{pass_rate:.1f}%")

    metric_cols = st.columns(4)
    metric_cols[0].metric("Passed evaluations", passed_count)
    metric_cols[1].metric("Failed evaluations", failed_count)
    metric_cols[2].metric("Average score", f"{average_score:.1f}")
    metric_cols[3].metric("Human review rate", f"{human_review_rate:.1f}%")

    chart_cols = st.columns(3)
    with chart_cols[0]:
        _distribution_chart(dataframe, "actual_decision", "Decision Distribution")
    with chart_cols[1]:
        _distribution_chart(dataframe, "actual_risk_level", "Risk-Level Distribution")
    with chart_cols[2]:
        _distribution_chart(dataframe, "actual_approval_level", "Approval-Level Distribution")

    st.subheader("Governance Data")
    st.caption("Filter the joined audit records from SQLite.")
    filtered = _apply_filters(dataframe)
    display_columns = [column for column in TABLE_COLUMNS if column in filtered.columns]
    st.dataframe(filtered[display_columns], use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(filtered)} of {len(dataframe)} records.")

    st.subheader("Failed Cases")
    failed = dataframe[dataframe["passed"] == False]  # noqa: E712
    if failed.empty:
        st.success("No failed evaluations in the current audit dataset.")
    else:
        for _, row in failed.iterrows():
            failure_reasons = row.get("failure_reasons_json", "[]")
            try:
                reasons_list = json.loads(failure_reasons)
                reasons_text = ", ".join(reasons_list) if reasons_list else "none"
            except json.JSONDecodeError:
                reasons_text = str(failure_reasons)

            st.markdown(f"**{row['action_id']}** — `{row['action_type']}`")
            st.write(f"- Failure reasons: {reasons_text}")
            st.write(f"- Improvement note: {row.get('improvement_note', '')}")
            st.write(f"- Governance reason: {row.get('reason', '')}")
            st.divider()

    st.subheader("Reports")
    report_cols = st.columns(2)

    if csv_path.exists():
        csv_bytes = csv_path.read_bytes()
        report_cols[0].download_button(
            label="Download governance_report.csv",
            data=csv_bytes,
            file_name=csv_path.name,
            mime="text/csv",
            use_container_width=True,
            key="download_csv",
        )
    else:
        report_cols[0].warning("CSV report not found. Run the workflow to generate it.")

    if md_path.exists():
        md_bytes = md_path.read_bytes()
        report_cols[1].download_button(
            label="Download governance_summary.md",
            data=md_bytes,
            file_name=md_path.name,
            mime="text/markdown",
            use_container_width=True,
            key="download_md",
        )
    else:
        report_cols[1].warning("Markdown summary not found. Run the workflow to generate it.")

    if md_path.exists():
        st.markdown("### Summary Preview")
        st.markdown(md_path.read_text(encoding="utf-8"))

    _render_demo_explanation()


def _render_demo_explanation() -> None:
    """Explain the portfolio demo for interview reviewers."""
    st.subheader("Interview Demo Explanation")
    st.markdown(
        """
This dashboard demonstrates a practical **enterprise AI governance layer** that sits
between AI agents and operational systems.

- **AI agent action control** — proposed actions are validated before execution
- **Policy-based governance** — business rules (POL-001 to POL-012) drive allow/block/approve outcomes
- **Risk scoring** — each action receives a Low / Medium / High / Critical rating
- **Human approval routing** — sensitive actions route to team lead, manager, or compliance
- **Audit logging** — actions, decisions, and evaluations persist in SQLite
- **Reporting and QA** — CSV/Markdown exports and pass/fail scoring against expected outcomes

Use the sidebar to rerun the workflow, or open **AI Agent Console** to simulate a single
agent proposal and governance decision live.
        """
    )


def main() -> None:
    """Render the Streamlit governance dashboard."""
    st.set_page_config(
        page_title="AI Agent Governance Simulator",
        page_icon="🛡️",
        layout="wide",
    )

    st.title("AI Agent Governance & Approval Simulator")
    st.caption(
        "Visual demo of policy-based AI agent control, risk scoring, approval routing, "
        "and audit reporting."
    )

    db_path = _resolve_path(get_database_path())
    csv_path = _resolve_path(DEFAULT_CSV_OUTPUT)
    md_path = _resolve_path(DEFAULT_MD_OUTPUT)

    with st.sidebar:
        st.header("Controls")
        reset_db = st.checkbox("Reset database before run", value=False)
        limit_value = st.number_input(
            "Limit actions (0 = all)",
            min_value=0,
            max_value=40,
            value=0,
            step=1,
        )
        show_failures = st.checkbox("Show failed evaluations in workflow log", value=False)

        if st.button("Run full governance workflow", type="primary", use_container_width=True):
            limit = None if limit_value == 0 else int(limit_value)
            with st.spinner("Running governance workflow..."):
                stats = _run_governance_workflow(
                    reset_db=reset_db,
                    limit=limit,
                    show_failures=show_failures,
                )
            if stats is not None:
                st.session_state["workflow_stats"] = stats
                st.session_state.pop("workflow_error", None)
                st.session_state.pop("workflow_traceback", None)
                _clear_data_cache()
                st.success("Workflow completed.")
            else:
                st.error("Workflow failed. See details in the main panel.")

        if "workflow_log" in st.session_state and st.session_state["workflow_log"]:
            with st.expander("Workflow log"):
                st.code(st.session_state["workflow_log"])

    dashboard_tab, console_tab = st.tabs(["Governance Dashboard", "AI Agent Console"])

    with dashboard_tab:
        _render_governance_dashboard(db_path, csv_path, md_path)

    with console_tab:
        _render_agent_console()


main()
