"""environment/email_outbox.py — mock email system."""

from datetime import datetime, timezone
from target_system.config import AUTHORIZED_EMAIL_DOMAINS
from target_system.logger import logger


class EmailOutbox:
    def __init__(self):
        self.sent_emails: list[dict] = []

    def send(self, to: str, subject: str, body: str) -> str:
        authorized = any(domain in to for domain in AUTHORIZED_EMAIL_DOMAINS)
        email = {
            "to":         to,
            "subject":    subject,
            "body":       body,
            "authorized": authorized,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        }
        self.sent_emails.append(email)
        logger.log_tool_call(
            agent="worker",
            tool_name="send_email",
            inputs={"to": to, "subject": subject},
            output=f"sent — authorized:{authorized}",
        )
        return "sent"

    def reset(self):
        self.sent_emails = []
