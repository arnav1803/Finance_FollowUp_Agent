"""
Pydantic models for structured data validation.
Enforces strict schemas for invoice records and LLM-generated email drafts.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class EmailDraft(BaseModel):
    """Schema enforced on every LLM-generated email via ``with_structured_output``."""
    subject: str = Field(description="The subject line of the email.")
    body: str = Field(description="The main body content of the email in plain text.")
    tone_used: str = Field(description="The detected and applied tone (e.g., Warm & Friendly, Polite but Firm).")


class InvoiceRecord(BaseModel):
    """Validated representation of a single invoice row from the data source."""
    invoice_no: str
    client_name: str
    amount: float
    due_date: str
    contact_email: str
    follow_up_count: int = 0
    days_overdue: int = 0

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v):
        if v < 0:
            raise ValueError("Invoice amount cannot be negative")
        return v

    @field_validator("follow_up_count")
    @classmethod
    def follow_up_non_negative(cls, v):
        if v < 0:
            raise ValueError("Follow-up count cannot be negative")
        return v