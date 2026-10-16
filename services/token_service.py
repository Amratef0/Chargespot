"""One-time e-mail tokens: "verify_email" (sign-up) and "reset_password" (forgot password).

Only the SHA-256 hash of a token is stored, so a leaked data file does not leak usable links. A token works once,
expires, and issuing a new one for the same purpose + e-mail invalidates the older one.
`issued_recently` lets the caller rate-limit e-mails (no mail-bombing a stranger).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from utils.storage import read_json, write_json_atomic

FMT = "%Y-%m-%dT%H:%M:%S"
VERIFY_EMAIL = "verify_email"
RESET_PASSWORD = "reset_password"
TTL_MINUTES = {VERIFY_EMAIL: 24 * 60, RESET_PASSWORD: 30}
KEEP_HISTORY = timedelta(hours=24)       # used/expired records are kept this long, only for rate limiting


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class TokenStore:
    def __init__(self, path, now_fn=datetime.now):
        self.path = Path(path)
        self.now = now_fn
        self.records: list[dict] = read_json(self.path, [])

    def issue(self, purpose: str, email: str) -> str:
        email = email.strip().lower()
        now = self.now()
        for r in self.records:                                   # a new token replaces the old unused one
            if r["purpose"] == purpose and r["email"] == email:
                r["used"] = True
        token = secrets.token_urlsafe(32)
        self.records.append({"hash": _h(token), "purpose": purpose, "email": email, "used": False,
                            "created": now.strftime(FMT),
                            "expires": (now + timedelta(minutes=TTL_MINUTES[purpose])).strftime(FMT)})
        self._prune()
        self._save()
        return token

    def consume(self, purpose: str, token) -> str | None:
        """Return the e-mail the token was issued for and burn it; None if unknown, used or expired."""
        if not token or not isinstance(token, str):
            return None
        h, now = _h(token.strip()), self.now()
        for r in self.records:
            if r["hash"] == h and r["purpose"] == purpose:
                if r["used"] or now > datetime.strptime(r["expires"], FMT):
                    return None
                r["used"] = True
                self._save()
                return r["email"]
        return None

    def issued_recently(self, purpose: str, email: str, within_minutes: int) -> int:
        email, since = email.strip().lower(), self.now() - timedelta(minutes=within_minutes)
        return sum(1 for r in self.records if r["purpose"] == purpose and r["email"] == email
                and datetime.strptime(r["created"], FMT) >= since)

    def _prune(self):
        cutoff = self.now() - KEEP_HISTORY
        self.records = [r for r in self.records if datetime.strptime(r["created"], FMT) >= cutoff]

    def _save(self):
        write_json_atomic(self.path, self.records)
