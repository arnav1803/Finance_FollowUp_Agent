"""
Email sending layer with dry-run (default) and SMTP modes.

Dry-run mode logs the email to console/audit without any network calls.
SMTP mode sends via smtplib when explicitly enabled via SEND_MODE=smtp.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader, TemplateNotFound


class EmailSender:
    """
    Handles email rendering and sending/mock-sending.

    Modes:
        - ``dry_run`` (default): No network calls, just logs.
        - ``smtp``: Sends via SMTP using creds from environment.
    """

    def __init__(self):
        self.mode = os.getenv("SEND_MODE", "dry_run")

        # SMTP configuration (only used when mode == "smtp")
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.sender_email = os.getenv("SENDER_EMAIL", "noreply@example.com")

        # Jinja2 template engine
        try:
            self.env = Environment(loader=FileSystemLoader("templates"))
        except Exception:
            self.env = None

    def render_html(self, subject: str, body: str, **kwargs) -> str:
        """Render the email body into an HTML template."""
        if self.env is None:
            return f"<html><body><h2>{subject}</h2><p>{body}</p></body></html>"

        try:
            template = self.env.get_template("email.html")
            return template.render(subject=subject, body=body, **kwargs)
        except TemplateNotFound:
            # Fallback if template file doesn't exist
            return f"<html><body><h2>{subject}</h2><pre>{body}</pre></body></html>"

    def send(self, recipient_email: str, subject: str, body: str) -> dict:
        """
        Send (or mock-send) an email.

        Args:
            recipient_email: Recipient's email address.
            subject: Email subject line.
            body: Plain-text email body.

        Returns:
            Dict with status, method, and message.
        """
        html_content = self.render_html(subject, body)

        if self.mode == "dry_run":
            return {
                "status": "success",
                "method": "dry_run",
                "message": f"[DRY RUN] Email to {recipient_email} logged (not sent).",
            }

        elif self.mode == "smtp":
            return self._send_smtp(recipient_email, subject, body, html_content)

        return {
            "status": "error",
            "method": self.mode,
            "message": f"Unknown send mode: {self.mode}",
        }

    def _send_smtp(self, recipient: str, subject: str, body: str, html: str) -> dict:
        """Sends an email via SMTP. Requires SMTP env vars to be configured."""
        if not self.smtp_user or not self.smtp_password:
            return {
                "status": "error",
                "method": "smtp",
                "message": "SMTP credentials not configured in .env",
            }

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.sender_email
            msg["To"] = recipient
            msg["Subject"] = subject

            # Attach both plain text and HTML versions
            msg.attach(MIMEText(body, "plain"))
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.sender_email, recipient, msg.as_string())

            return {
                "status": "success",
                "method": "smtp",
                "message": f"Email sent to {recipient} via SMTP.",
            }

        except Exception as e:
            return {
                "status": "error",
                "method": "smtp",
                "message": f"SMTP send failed: {str(e)}",
            }
