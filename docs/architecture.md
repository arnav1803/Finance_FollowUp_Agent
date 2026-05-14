# Architecture Documentation

## Agent Architecture Diagram

```mermaid
flowchart TD
    subgraph Input["📥 Data Input Layer"]
        A["CSV / Excel File<br>(invoices.csv)"]
        B["Streamlit Upload<br>(app.py)"]
    end

    subgraph Ingestion["🔍 Ingestion & Validation"]
        C["pandas DataFrame"]
        D["Pydantic InvoiceRecord<br>Schema Validation"]
        E["Input Sanitisation<br>(utils.sanitize_input)"]
    end

    subgraph Agent["🤖 Agent Core (Plan-and-Execute)"]
        F{"Stage Router<br>determine_stage()"}
        G["Stage 0: Not Overdue<br>→ SKIP"]
        H["Stage 1-4: Generate Email<br>→ LLM Chain"]
        I["Stage 5: 30+ Days<br>→ ESCALATION FLAG"]
    end

    subgraph LLM["🧠 LLM Generation"]
        J["System Prompt<br>(tone + guardrails)"]
        K["ChatOpenAI (GPT-4o)<br>with_structured_output"]
        L["EmailDraft<br>(Pydantic Schema)"]
    end

    subgraph Delivery["📤 Delivery Layer"]
        M["EmailSender"]
        N["Dry-Run Mode<br>(default — log only)"]
        O["SMTP Mode<br>(smtplib)"]
    end

    subgraph Logging["📋 Audit & Logging"]
        P["SQLite AuditDB<br>(logs/audit.db)"]
        Q["JSON Export<br>(logs/audit_log.json)"]
    end

    subgraph UI["📊 Dashboard"]
        R["Streamlit App<br>4 tabs: Queue, Run,<br>Audit, Email Preview"]
    end

    A --> C
    B --> C
    C --> D
    D --> E
    E --> F
    F -->|"days ≤ 0"| G
    F -->|"1-30 days"| H
    F -->|"30+ days"| I
    H --> J
    J --> K
    K --> L
    L --> M
    M -->|"SEND_MODE=dry_run"| N
    M -->|"SEND_MODE=smtp"| O
    G --> P
    N --> P
    O --> P
    I --> P
    P --> Q
    P --> R
```

## Component Responsibilities

| Component | File | Responsibility |
|-----------|------|---------------|
| **Schema** | `src/schema.py` | Pydantic models for `InvoiceRecord` and `EmailDraft` |
| **Agent** | `src/agent.py` | Stage determination + LLM email generation |
| **Utils** | `src/utils.py` | Input sanitisation, PII masking, formatters |
| **Database** | `src/database.py` | SQLite audit trail CRUD |
| **Email Sender** | `src/email_sender.py` | SMTP/dry-run email delivery |
| **Main** | `src/main.py` | CLI pipeline orchestrator |
| **Scheduler** | `src/scheduler.py` | APScheduler cron integration |
| **Dashboard** | `app.py` | Streamlit UI |

## Design Philosophy

**Plan-and-Execute over ReAct**: The email generation workflow is deterministic and linear. Using a ReAct agent loop would introduce unnecessary hallucination risk for client-facing communications. Instead, we use a static plan-and-execute pattern where the stage router deterministically selects the action, and the LLM is only called for the creative task of drafting the email within strict guardrails.