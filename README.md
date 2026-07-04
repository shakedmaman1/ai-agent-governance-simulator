# AI Agent Governance & Approval Simulator

A small portfolio project that simulates enterprise AI agent governance - validating proposed agent actions against business policies, scoring risk, and routing decisions through human-in-the-loop approval workflows.

## Business Problem

Enterprise companies deploy AI agents to assist support, billing, retention, and operations teams. Before an agent executes an action (refunds, password resets, data exports, etc.), a governance layer must determine whether the action is safe to auto-approve, must be blocked, or requires human approval at a specific organizational level.

This simulator demonstrates how that pre-execution control plane works: policy checks, risk scoring, approval routing, and full auditability.

## Architecture

```text
actions.csv
   |
   v
Pydantic validation
   |
   v
Policy engine
   |
   v
Risk scoring
   |
   v
Approval routing
   |
   v
SQLite audit log
   |
   v
CSV / Markdown reports
   |
   v
Streamlit dashboard
```

### Implemented modules

| Module | Responsibility |
|--------|----------------|
| `schemas.py` | Pydantic models and enums for actions, decisions, and evaluation results |
| `evaluator.py` | Policy engine, risk scoring, approval routing, and evaluation scoring |
| `db.py` | SQLite audit logging with parameterized queries |
| `report.py` | CSV and Markdown report generation |
| `main.py` | CLI entry point via argparse |
| `app.py` | Streamlit dashboard and AI Agent Console |
| `tests/` | pytest coverage for schemas, policies, DB, reports, and CLI |

## Features

- Load proposed AI agent actions from CSV
- Validate action data with Pydantic
- Evaluate actions against documented business policies (POL-001 to POL-012)
- Calculate risk level (Low / Medium / High / Critical)
- Decide: **allowed**, **blocked**, or **requires_approval**
- Determine required approval level (none / team_lead / manager / compliance)
- Persist all decisions to SQLite audit logs
- Generate CSV and Markdown summary reports
- Run end-to-end from the command line
- Interactive Streamlit dashboard with AI Agent Console
- Automated test suite with pytest

## Tech Stack

- Python 3.11+
- Pydantic - data validation
- SQLite (`sqlite3`) - audit persistence
- pandas - reporting and CSV handling
- pytest - automated tests
- python-dotenv - environment configuration
- argparse - CLI interface
- Streamlit - visual dashboard

## How to Run

### Setup

```powershell
cd ai-agent-governance-simulator
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
```

### Run the full workflow

Process all 40 synthetic actions, save audit records, and generate reports:

```powershell
python -m src.main
```

### CLI options

```powershell
# Process a custom input file
python -m src.main --input data/actions.csv

# Process only the first N actions
python -m src.main --limit 5

# Print failed action IDs and failure reasons
python -m src.main --show-failures

# Delete the existing audit database before running
python -m src.main --reset-db
```

### Outputs

After a successful run, the project writes:

| Output | Description |
|--------|-------------|
| `outputs/governance_audit.db` | SQLite audit log generated locally and ignored by git |
| `outputs/governance_report.csv` | Joined governance data export |
| `outputs/governance_summary.md` | Markdown summary with metrics and recommendations |

### Run tests

```powershell
python -m pytest -q
```

### Run dashboard

```powershell
python -m streamlit run app.py
```

Alternative if `streamlit` is on your PATH:

```powershell
streamlit run app.py
```

The dashboard lets you rerun the governance workflow, explore metrics and charts, filter audit records, review failed cases, and download or preview generated reports.

Open the **AI Agent Console** tab for a live 60-second interview demo:

1. Load the **$750 VIP refund** preset
2. Evaluate the action
3. Explain **POL-001** in the **Why this decision?** panel
4. Save to the audit log
5. Switch to **Governance Dashboard** to show reports

## Data Notice

**All data in this project is synthetic demo data.** No real customer information, credentials, or production secrets are used. Action records in `data/actions.csv` are fabricated for portfolio demonstration purposes only.

## Disclaimer

This is a **portfolio / demo project**, not production software. It is designed to demonstrate AI governance concepts - policy-based decision logic, risk scoring, human-in-the-loop approval, and auditability - in a form suitable for technical interviews and Junior AI Solutions Engineer portfolios.


