from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from utils.storage import read_json, write_json_atomic

IDLE_MINUTES = 120          # no activity for this long -> logged out
MAX_HOURS = 12              # logged out after this long no matter what
TOUCH_EVERY_SECONDS = 60    # sliding refresh is written to disk at most this often
FMT = "%Y-%m-%dT%H:%M:%S"


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LoginSessionStore:
    def __init__(self, path, now_fn=datetime.now, idle_minutes=IDLE_MINUTES, max_hours=MAX_HOURS):
        self.path = Path(path)
        self.now = now_fn
        self.idle = timedelta(minutes=idle_minutes)
        self.max_age = timedelta(hours=max_hours)
        self.records: dict[str, dict] = read_json(self.path, {})
        if self._purge():
            self._save()

    @property
    def max_age_seconds(self) -> int:
        return int(self.max_age.total_seconds())

    def create(self, email: str) -> str:
        token = secrets.token_urlsafe(32)
        now = self.now()
        self.records[_h(token)] = {"email": email.strip().lower(), "created": now.strftime(FMT), "last_seen": now.strftime(FMT)}
        self._purge()
        self._save()
        return token

    def validate(self, token) -> str | None:
        """Return the session's e-mail if the token is valid (and slide the idle clock), else None."""
        if not token or not isinstance(token, str):
            return None
        key = _h(token)
        rec = self.records.get(key)
        if rec is None:
            return None
        now = self.now()
        created, last = datetime.strptime(rec["created"], FMT), datetime.strptime(rec["last_seen"], FMT)
        if now - created > self.max_age or now - last > self.idle:
            self.records.pop(key, None)
            self._save()
            return None
        if (now - last).total_seconds() >= TOUCH_EVERY_SECONDS:
            rec["last_seen"] = now.strftime(FMT)
            self._save()
        return rec["email"]

    def revoke(self, token) -> None:
        if token and self.records.pop(_h(token), None) is not None:
            self._save()

    def revoke_all(self, email: str) -> int:
        e = email.strip().lower()
        gone = [k for k, r in self.records.items() if r["email"] == e]
        for k in gone:
            del self.records[k]
        if gone:
            self._save()
        return len(gone)

    def _purge(self) -> bool:
        now, dead = self.now(), []
        for k, r in self.records.items():
            if now - datetime.strptime(r["created"], FMT) > self.max_age or now - datetime.strptime(r["last_seen"], FMT) > self.idle:
                dead.append(k)
        for k in dead:
            del self.records[k]
        return bool(dead)

    def _save(self):
        write_json_atomic(self.path, self.records)
