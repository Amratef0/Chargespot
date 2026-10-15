"""Sending e-mail. Three interchangeable senders with the same `send(to, subject, body)` method:

* SMTPMailer    real e-mail (Gmail / any SMTP server) - configured with environment variables
* FileMailer    DEVELOPMENT: writes each message to data/outbox/ instead of sending it
* MemoryMailer  tests: keeps messages in a list

Environment variables for real e-mail:
  CHARGESPOT_SMTP_HOST   CHARGESPOT_SMTP_PORT (587 = STARTTLS, 465 = SSL)   CHARGESPOT_SMTP_USER
  CHARGESPOT_SMTP_PASSWORD (for Gmail: an "app password")   CHARGESPOT_MAIL_FROM
"""
from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from models.exceptions import ChargeSpotError


class MailDeliveryError(ChargeSpotError):
    """The mail server refused or could not be reached."""


@dataclass
class Mail:
    to: str
    subject: str
    body: str


class MemoryMailer:
    def __init__(self):
        self.sent: list[Mail] = []

    def send(self, to, subject, body):
        self.sent.append(Mail(to, subject, body))


class FileMailer:
    """Development mailbox: nothing leaves the machine."""
    def __init__(self, folder):
        self.folder = Path(folder)

    def send(self, to, subject, body):
        self.folder.mkdir(parents=True, exist_ok=True)
        name = f"{datetime.now():%Y%m%d-%H%M%S-%f}-{''.join(c for c in to if c.isalnum())[:30]}.txt"
        (self.folder / name).write_text(f"To: {to}\nSubject: {subject}\n\n{body}\n", encoding="utf-8")

    def latest(self, n=5):
        files = sorted(self.folder.glob("*.txt"))[-n:] if self.folder.exists() else []
        return [f.read_text(encoding="utf-8") for f in reversed(files)]


class SMTPMailer:
    def __init__(self, host, port, user, password, sender):
        self.host, self.port, self.user, self.password, self.sender = host, int(port), user, password, sender

    def send(self, to, subject, body):
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.sender, to, subject
        msg.set_content(body)
        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=15) as s:
                    self._login_and_send(s, msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=15) as s:
                    s.starttls()
                    self._login_and_send(s, msg)
        except (smtplib.SMTPException, OSError) as e:
            raise MailDeliveryError(f"Could not send e-mail: {e.__class__.__name__}") from e

    def _login_and_send(self, s, msg):
        if self.user:
            s.login(self.user, self.password)
        s.send_message(msg)


def build_mailer(data_dir):
    """SMTP when CHARGESPOT_SMTP_HOST is set, otherwise the development FileMailer (data/outbox)."""
    host = os.environ.get("CHARGESPOT_SMTP_HOST")
    if host:
        user = os.environ.get("CHARGESPOT_SMTP_USER", "")
        return SMTPMailer(host, os.environ.get("CHARGESPOT_SMTP_PORT", "587"), user,
                          os.environ.get("CHARGESPOT_SMTP_PASSWORD", ""),
                          os.environ.get("CHARGESPOT_MAIL_FROM") or user or "no-reply@chargespot.local")
    return FileMailer(Path(data_dir) / "outbox")
