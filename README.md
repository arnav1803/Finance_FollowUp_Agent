# 💼 Finance Credit Follow-Up Email Agent

> **AI Enablement Internship — Task 2**  
> Automated follow-up email generation for overdue invoices with tone escalation, audit logging, and a Streamlit dashboard.

---

## 📖 Overview

This AI agent prototype supports Finance teams by **automatically generating follow-up emails** for pending credit/invoice payments. The agent varies the **tone and urgency** of each follow-up based on the number of days overdue — starting warm & friendly and escalating progressively to stern & urgent. After 30+ days, the record is **flagged for legal/finance manual review** instead of sending more emails.

### Key Features
- 🎯 **Tone Escalation Engine** — 4-stage escalation matrix (Warm → Polite → Formal → Stern) + auto-escalation flag
- 🤖 **LLM Email Generation** — GPT-4o generates personalised, professional emails via structured output
- 🔒 **Input Sanitisation** — Defence-in-depth against prompt injection attacks
- ✉️ **SMTP / Dry-Run** — Real SMTP sending or safe dry-run logging mode
- 🗄️ **SQLite Audit Trail** — Every action logged with timestamp, tone, and send status
- 📊 **Streamlit Dashboard** — Visual interface for queue management, execution, and email preview
- ⏰ **Scheduling** — Optional APScheduler cron for daily automated runs

---

## 🏗️ Architecture

```
[CSV/Excel Data] → [Pandas Ingestion] → [Pydantic Validation] → [Input Sanitisation]
                                                                        ↓
                                                               [Stage Router]
                                                          ↙       ↓         ↘
                                                    [SKIP]  [LLM Gen]  [ESCALATE]
                                                              ↓
                                                    [EmailSender (SMTP/Dry-Run)]
                                                              ↓
                                                    [SQLite + JSON Audit Log]
                                                              ↓
                                                    [Streamlit Dashboard]
```

> See [docs/architecture.md](docs/architecture.md) for the full Mermaid diagram.

### Agent Architecture: Plan-and-Execute

We use a **Plan-and-Execute** router model rather than a dynamic ReAct loop. The email workflow is deterministic and linear — the stage router selects the action, and the LLM is only invoked for the creative task of drafting the email within strict guardrails. This design choice **minimises hallucination risk** on client-facing communications.

---

## 1. Technical Stack & Decision Log

### LLM Chosen

| Property | Value |
|----------|-------|
| **Model** | `llama-3.3-70b-versatile` |
| **Provider** | Groq |
| **Temperature** | 0.2 |

**Justification:** Groq provides ultra-fast inference (~10x faster than OpenAI) at zero cost for development. The Llama 3.3 70B model supports structured output via tool-calling, enabling reliable `with_structured_output()` mapping to our Pydantic `EmailDraft` schema. Its strong instruction-following capabilities produce consistent, professional email content with accurate tone alignment. The low temperature (0.2) ensures deterministic, professional output.

### Agent Framework

| Property | Value |
|----------|-------|
| **Framework** | LangChain v0.2.x+ |
| **Architecture** | Plan-and-Execute Router |

**Justification:** LangChain provides mature, well-documented structured output support. The plan-and-execute pattern (deterministic router → LLM chain) avoids the unpredictability of ReAct loops, which is critical for client-facing email generation.

### Prompt Design

See [docs/prompt_iterations.md](docs/prompt_iterations.md) for the full prompt evolution log.

Key design decisions:
- **Three-version iteration**: Basic → Structured → Production-grade with security guardrails
- **Parameterised tone injection**: Tone and message strategy are injected as variables, not hardcoded
- **Two-layer defence**: Input sanitisation (pre-prompt) + prompt-level guardrails (in-prompt)
- **Structured output enforcement**: Pydantic `EmailDraft` schema acts as a validation layer

---

## 2. Security Risk Mitigation

> ⚠️ **This section is mandatory and will be assessed.**

| Risk | Description | Mitigation Strategy |
|------|-------------|-------------------|
| **Prompt Injection** | Malicious input manipulating agent behaviour | `utils.sanitize_input()` strips control chars, detects 15+ injection patterns, truncates to 300 chars. Prompt-level guardrails explicitly instruct LLM to reject injection attempts. LangChain structured output forces schema compliance |
| **Data Privacy / PII** | Invoice/email data contains personal info | `mask_email()` masks email addresses in audit logs. No raw PII sent to cloud LLM beyond what's needed for email rendering. Local processing preferred |
| **API Key Exposure** | LLM/email API keys leaked in code | `python-dotenv` for env management. `.env` in `.gitignore`. `.env.example` provided with placeholder values only. Never hardcoded |
| **Hallucination Risk** | LLM generating false amounts or wrong content | Pydantic `EmailDraft` via `with_structured_output()` enforces rigid structure. All numeric data (amount, dates, days overdue) injected from source data — never LLM-generated |
| **Email Spoofing** | Emails appearing from wrong sender | Default mode is `dry_run` (no network calls). SMTP mode requires explicit opt-in. Verified sender identity in template. SPF/DKIM/DMARC recommended for production |
| **Unauthorised Access** | Anyone triggering the agent | Streamlit app runs locally by default. No exposed API endpoints. CLI requires local access |

---

## 3. Project Setup

### Prerequisites
- Python 3.10+
- OpenAI API key (for LLM mode; mock mode works without it)

### Installation

```bash
# Clone & navigate
git clone <repo-url>
cd Finance_FollowUp_Agent

# Virtual environment
python -m venv venv
.\venv\Scripts\activate       # Windows
# source venv/bin/activate    # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy environment template
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux

# Edit .env and add your Groq API key (get one free at https://console.groq.com)
```

### Running

```bash
# CLI Pipeline (processes all invoices)
python -m src.main

# Streamlit Dashboard
streamlit run app.py

# Run Tests
pytest tests/ -v

# Scheduler (optional — runs daily at 9 AM)
python -m src.scheduler
```

---

## 4. Tone Escalation Matrix

| Stage | Trigger | Tone | Key Message | CTA |
|-------|---------|------|-------------|-----|
| 1st Follow-Up | 1–7 days overdue | Warm & Friendly | Gentle reminder, assume oversight | Pay now link |
| 2nd Follow-Up | 8–14 days overdue | Polite but Firm | Payment still pending | Confirm payment date |
| 3rd Follow-Up | 15–21 days overdue | Formal & Serious | Escalating concern; mention impact | Respond within 48 hrs |
| 4th Follow-Up | 22–30 days overdue | Stern & Urgent | Final reminder before escalation | Pay immediately |
| Escalation | 30+ days overdue | 🚨 Flagged | Human review required | Assign to finance manager |

---

## 5. Project Structure

```
Finance_FollowUp_Agent/
├── app.py                      # Streamlit dashboard
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
├── .gitignore
├── README.md
│
├── src/
│   ├── __init__.py
│   ├── agent.py                # Core agent — stage router + LLM chain
│   ├── schema.py               # Pydantic models (EmailDraft, InvoiceRecord)
│   ├── utils.py                # Input sanitisation, PII masking, formatters
│   ├── database.py             # SQLite audit trail
│   ├── email_sender.py         # SMTP / dry-run delivery
│   ├── main.py                 # CLI pipeline entry point
│   └── scheduler.py            # APScheduler cron integration
│
├── data/
│   └── invoices.csv            # Sample invoice data (6 records)
│
├── templates/
│   └── email.html              # Jinja2 HTML email template
│
├── tests/
│   ├── test_agent.py           # Unit tests (stage, sanitisation, DB, schema)
│   └── test_pipeline.py        # Integration test (full mock pipeline)
│
├── docs/
│   ├── architecture.md         # Mermaid architecture diagram
│   └── prompt_iterations.md    # Prompt design evolution log
│
├── samples/                    # Sample output artifacts
│   └── sample_audit_log.json
│
└── logs/                       # Runtime output (.gitignored)
    ├── audit_log.json
    └── audit.db
```

---

## 6. Sample Output

See `samples/sample_audit_log.json` for a full pipeline run output, or run:

```bash
python -m src.main
```

### Example Stage 1 Email (Warm & Friendly)
```
Subject: Quick Reminder – Invoice #INV-2024-001 | ₹45,000.00 Due

Hi Rajesh Kumar,

I hope you're doing well! This is a friendly reminder that Invoice #INV-2024-001
for ₹45,000.00 was due on 2024-04-20. If you have already processed this,
please disregard.

Payment link: https://billing.example.com/pay/INV-2024-001

Thank you!
Accounts Receivable Team
```

### Example Stage 4 Email (Stern & Urgent)
```
Subject: FINAL NOTICE – Invoice #INV-2024-004 – Immediate Action Required

Dear Neha Sharma,

This is our FINAL reminder. Invoice #INV-2024-004 (₹12,500.00) is now
28 days overdue. Failure to remit payment within 24 hours will result in
escalation to our legal and recovery team.

Pay immediately: https://billing.example.com/pay/INV-2024-004

Accounts Receivable Team
```

---

*Built with ❤️ for the AI Enablement Internship*