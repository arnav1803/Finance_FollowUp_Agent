"""
Utility functions for input sanitisation and helper operations.
Provides defense-in-depth against prompt injection and malformed data.
"""

import re
from datetime import datetime


# ── Prompt Injection Defence ──────────────────────────────────────────
# Patterns commonly used in prompt injection attacks
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above",
    r"disregard\s+(all\s+)?previous",
    r"system:\s*",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<SYS>>",
    r"<</SYS>>",
    r"you\s+are\s+now",
    r"act\s+as\s+if",
    r"pretend\s+(you\s+are|to\s+be)",
    r"new\s+instructions",
    r"override\s+(previous|all)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def sanitize_input(text: str, max_length: int = 300, field_name: str = "field") -> str:
    """
    Sanitises a text input field for safe injection into LLM prompts.

    Steps:
        1. Strip leading/trailing whitespace.
        2. Remove control characters (except common whitespace).
        3. Truncate to *max_length*.
        4. Replace prompt-injection patterns with ``[REDACTED]``.

    Returns the sanitised string — never raises, always returns usable text.
    """
    if not isinstance(text, str):
        text = str(text)

    text = text.strip()

    # Remove control characters (keep newlines, carriage returns, tabs)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Truncate
    if len(text) > max_length:
        text = text[:max_length]

    # Replace injection patterns with a safe placeholder
    for pattern in COMPILED_PATTERNS:
        text = re.sub(pattern, "[REDACTED]", text)

    return text


def sanitize_invoice_fields(record_dict: dict) -> dict:
    """Sanitises all string fields in an invoice record dictionary."""
    sanitised = {}
    for key, value in record_dict.items():
        if isinstance(value, str):
            sanitised[key] = sanitize_input(value, max_length=300, field_name=key)
        else:
            sanitised[key] = value
    return sanitised


# ── PII Masking ───────────────────────────────────────────────────────

def mask_email(email: str) -> str:
    """
    Masks an email address for audit logging to protect PII.

    Example: ``rajesh@example.com`` → ``r***h@example.com``
    """
    if not email or "@" not in email:
        return "***@***.***"

    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]

    return f"{masked_local}@{domain}"


# ── Formatters ────────────────────────────────────────────────────────

def calculate_days_overdue(due_date_str: str) -> int:
    """
    Calculates the number of days an invoice is overdue from today.
    Returns a negative number if the invoice is not yet due.
    """
    try:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        return (today - due_date).days
    except (ValueError, TypeError):
        return 0


def format_currency(amount: float, currency_symbol: str = "₹") -> str:
    """Formats a numeric amount as a currency string with commas."""
    return f"{currency_symbol}{amount:,.2f}"