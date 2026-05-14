"""
Finance Credit Follow-Up Email Agent — Main Pipeline.

Execution flow:
  1. Ingest invoice data from CSV.
  2. For each overdue invoice, determine escalation stage.
  3. Generate personalised email via LLM (or mock if no API key).
  4. Send via SMTP or dry-run.
  5. Log every action to SQLite audit trail + JSON export.
"""

import os
import sys
import pandas as pd
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

from src.schema import InvoiceRecord
from src.agent import FinanceEmailAgent
from src.database import AuditDB
from src.email_sender import EmailSender
from src.utils import mask_email, sanitize_invoice_fields, format_currency


def has_valid_api_key() -> bool:
    """Check if a valid Groq API key is configured."""
    # Allow forcing mock mode via env var
    if os.getenv("MOCK_MODE", "").lower() == "true":
        return False
    key = os.getenv("GROQ_API_KEY", "")
    if not key or key == "your_groq_api_key_here":
        return False
    # Valid Groq keys start with gsk_
    if not key.startswith("gsk_"):
        return False
    return True


def process_invoice(agent: FinanceEmailAgent, record: InvoiceRecord, use_llm: bool) -> dict:
    """
    Process a single invoice through the agent pipeline.

    If ``use_llm`` is False, generates mock output to demonstrate the flow.
    """
    if use_llm:
        return agent.generate_email(record)

    # ── Mock mode (no API key) ────────────────────────────────────
    stage_info = agent.determine_stage(record.days_overdue, record.follow_up_count)
    stage = stage_info.get("stage", 0)

    if stage == 0:
        return {"status": "skipped", "reason": "Not overdue", "invoice_no": record.invoice_no, "stage": 0}
    elif stage == 5:
        return {"status": "escalated", "reason": stage_info.get("status", ""), "invoice_no": record.invoice_no, "stage": 5}
    else:
        # Generate realistic mock email content per stage
        tone = stage_info.get("tone", "Unknown")
        prefix = stage_info.get("subject_prefix", "Reminder")
        amount_str = format_currency(record.amount)

        mock_subjects = {
            1: f"{prefix} – Invoice #{record.invoice_no} | {amount_str} Due",
            2: f"{prefix} – Invoice #{record.invoice_no} ({record.days_overdue} Days Overdue)",
            3: f"{prefix} – Invoice #{record.invoice_no} ({record.days_overdue} Days Overdue)",
            4: f"{prefix} – Invoice #{record.invoice_no} – Immediate Action Required",
        }

        mock_bodies = {
            1: (
                f"Hi {record.client_name},\n\n"
                f"I hope you're doing well! This is a friendly reminder that Invoice #{record.invoice_no} "
                f"for {amount_str} was due on {record.due_date}. If you have already processed this, "
                f"please disregard.\n\n"
                f"Payment link: https://billing.example.com/pay/{record.invoice_no}\n\n"
                f"Thank you!\nAccounts Receivable Team"
            ),
            2: (
                f"Dear {record.client_name},\n\n"
                f"We are writing to follow up on Invoice #{record.invoice_no} for {amount_str}, "
                f"which is now {record.days_overdue} days overdue (due: {record.due_date}). "
                f"We kindly request you confirm a payment date at your earliest convenience.\n\n"
                f"Payment link: https://billing.example.com/pay/{record.invoice_no}\n\n"
                f"Best regards,\nAccounts Receivable Team"
            ),
            3: (
                f"Dear {record.client_name},\n\n"
                f"Despite our previous reminders, Invoice #{record.invoice_no} ({amount_str}) "
                f"remains unpaid as of today, now {record.days_overdue} days overdue. "
                f"We request your immediate attention. Continued non-payment may impact your credit terms.\n\n"
                f"Please respond within 48 hours.\n"
                f"Payment link: https://billing.example.com/pay/{record.invoice_no}\n\n"
                f"Regards,\nAccounts Receivable Team"
            ),
            4: (
                f"Dear {record.client_name},\n\n"
                f"This is our FINAL reminder. Invoice #{record.invoice_no} ({amount_str}) is now "
                f"{record.days_overdue} days overdue. Failure to remit payment within 24 hours "
                f"will result in escalation to our legal and recovery team.\n\n"
                f"Pay immediately: https://billing.example.com/pay/{record.invoice_no}\n\n"
                f"Accounts Receivable Team"
            ),
        }

        return {
            "status": "generated",
            "invoice_no": record.invoice_no,
            "stage": stage,
            "email": {
                "subject": mock_subjects.get(stage, f"Reminder – {record.invoice_no}"),
                "body": mock_bodies.get(stage, "Payment reminder."),
                "tone_used": tone,
            },
        }


def main(csv_path: str = "data/invoices.csv"):
    """
    Main pipeline entry point.

    Args:
        csv_path: Path to the invoice CSV file.
    """
    use_llm = has_valid_api_key()

    if not use_llm:
        print("⚠  OPENAI_API_KEY not set — running in MOCK mode.\n")
    else:
        print("✅ API key detected — running with LLM generation.\n")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Finance Email Agent pipeline.")
    print("=" * 70)

    # ── 1. Data Ingestion ─────────────────────────────────────────────
    try:
        df = pd.read_csv(csv_path)
        print(f"📄 Loaded {len(df)} invoice records from {csv_path}\n")
    except FileNotFoundError:
        print(f"❌ File not found: {csv_path}")
        return []
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return []

    # ── Initialise components ─────────────────────────────────────────
    os.makedirs("logs", exist_ok=True)
    agent = FinanceEmailAgent()
    audit_db = AuditDB()
    email_sender = EmailSender()

    audit_logs = []
    counters = {"generated": 0, "escalated": 0, "skipped": 0, "error": 0}

    # ── 2. Process each invoice ───────────────────────────────────────
    for idx, row in df.iterrows():
        # Sanitise raw input fields
        try:
            clean_row = sanitize_invoice_fields(row.to_dict())
            record = InvoiceRecord(**clean_row)
        except Exception as e:
            print(f"  ❌ Failed to parse row {idx}: {e}")
            counters["error"] += 1
            continue

        print(f"  📋 {record.invoice_no} | {record.client_name} | "
              f"{format_currency(record.amount)} | {record.days_overdue}d overdue")

        # ── Generate email / determine action ─────────────────────────
        result = process_invoice(agent, record, use_llm)
        status = result["status"]
        counters[status] = counters.get(status, 0) + 1

        # ── Build audit entry ─────────────────────────────────────────
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "invoice_no": record.invoice_no,
            "client_name": record.client_name,
            "amount": record.amount,
            "days_overdue": record.days_overdue,
            "stage": result.get("stage", 0),
            "status": status,
            "contact_email_masked": mask_email(record.contact_email),
        }

        if status == "generated":
            email_data = result["email"]
            audit_entry["tone"] = email_data.get("tone_used", "")
            audit_entry["subject"] = email_data.get("subject", "")
            audit_entry["body"] = email_data.get("body", "")

            # ── Send / Mock-Send ──────────────────────────────────────
            send_result = email_sender.send(
                recipient_email=record.contact_email,
                subject=email_data["subject"],
                body=email_data["body"],
            )
            audit_entry["send_method"] = send_result["method"]
            print(f"     → [{send_result['method'].upper()}] Stage {result['stage']} "
                  f"({email_data['tone_used']})")

        elif status == "escalated":
            audit_entry["tone"] = "Flagged"
            print(f"     → 🚨 ESCALATED — Flagged for Legal/Finance manual review")

        elif status == "skipped":
            print(f"     → ⏭️  SKIPPED — Not yet overdue")

        elif status == "error":
            audit_entry["body"] = result.get("error", "Unknown error")
            print(f"     → ❌ ERROR: {result.get('error', 'Unknown')}")

        # ── Log to SQLite + in-memory list ────────────────────────────
        audit_db.log_entry(audit_entry)
        audit_logs.append(audit_entry)

    # ── 3. Export JSON audit log ──────────────────────────────────────
    json_path = "logs/audit_log.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audit_logs, f, indent=4, ensure_ascii=False)

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"✅ Pipeline complete. Processed {len(audit_logs)} invoices.")
    print(f"   📧 Emails generated: {counters['generated']}")
    print(f"   🚨 Escalated:        {counters['escalated']}")
    print(f"   ⏭️  Skipped:          {counters['skipped']}")
    print(f"   ❌ Errors:            {counters['error']}")
    print(f"\n   📁 JSON log: {json_path}")
    print(f"   🗄️  SQLite DB: logs/audit.db")

    return audit_logs


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "data/invoices.csv"
    main(csv_file)