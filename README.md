# AI Agent Governance & Approval Simulator

A small portfolio project that simulates enterprise AI agent governance—validating proposed agent actions against business policies, scoring risk, and routing decisions through human-in-the-loop approval workflows.

## Business Problem

Enterprise companies deploy AI agents to assist support, billing, retention, and operations teams. Before an agent executes an action (refunds, password resets, data exports, etc.), a governance layer must determine whether the action is safe to auto-approve, must be blocked, or requires human approval at a specific organizational level.

This simulator demonstrates how that pre-execution control plane works: policy checks, risk scoring, approval routing, and full auditability.

## Planned Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  actions.csv │────▶│  Pydantic    │────▶│  Policy     │────▶│  Risk        │
│  (input)     │     │  Validation  │     │  Engine     │     │  Scorer      │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
                                                    │                  │
                                                    ▼                  ▼
                                           ┌─────────────────────────────┐
                                           │  Decision: allowed /        │
                                           │  blocked / requires_approval│
                                           └─────────────────────────────┘
                                                    │
                    ┌───────────────────────────────┼───────────────────────┐
                    ▼                               ▼                       ▼
             ┌─────────────┐                ┌─────────────┐         ┌─────────────┐
             │ SQLite      │                │ CSV Report  │         │ Markdown    │
             │ Audit Log   │                │             │         │ Report      │
             └─────────────┘                └─────────────┘         └─────────────┘
```

**Planned modules (Phase 2+):**

| Module | Responsibility |
|--------|----------------|
| `schemas.py` | Pydantic models for actions, decisions, and audit records |
| `evaluator.py` | Policy engine, risk scoring, and approval routing |
| `db.py` | SQLite audit log with parameterized queries |
| `main.py` | CLI entry point via argparse |
| `tests/` | pytest coverage for validation, policies, and reporting |

## Planned Features

- Load proposed AI agent actions from CSV
- Validate action data with Pydantic
- Evaluate actions against documented business policies (POL-001–POL-012)
- Calculate risk level (Low / Medium / High / Critical)
- Decide: **allowed**, **blocked**, or **requires_approval**
- Determine required approval level (none / team_lead / manager / compliance)
- Persist all decisions to SQLite audit logs
- Generate CSV and Markdown summary reports
- Run end-to-end from the command line
- *(Optional, later)* Streamlit dashboard for visual review

## Tech Stack

- Python 3.11+
- Pydantic — data validation
- SQLite (`sqlite3`) — audit persistence
- pandas — reporting and CSV handling
- pytest — automated tests
- python-dotenv — environment configuration
- argparse — CLI interface

## Planned CLI Command

```bash
python -m src.main evaluate --input data/actions.csv --output outputs/
```

Additional flags (planned):

```bash
python -m src.main evaluate --input data/actions.csv --output outputs/ --verbose
python -m src.main report --db outputs/audit.db --format csv
python -m src.main report --db outputs/audit.db --format markdown
```

## Data Notice

**All data in this project is synthetic demo data.** No real customer information, credentials, or production secrets are used. Action records in `data/actions.csv` are fabricated for portfolio demonstration purposes only.

## Disclaimer

This is a **portfolio / demo project**, not production software. It is designed to demonstrate AI governance concepts—policy-based decision logic, risk scoring, human-in-the-loop approval, and auditability—in a form suitable for technical interviews and Junior AI Solutions Engineer portfolios.
