
from __future__ import annotations

import os
from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Africa/Cairo"


@lru_cache(maxsize=8)
def _zone(name: str):
    try:
        return ZoneInfo(name)
    except Exception:             # unknown name or no tz database (Windows without the `tzdata` package)
        return None


def now() -> datetime:
    zone = _zone(os.environ.get("CHARGESPOT_TIMEZONE") or DEFAULT_TIMEZONE)
    return datetime.now(zone).replace(tzinfo=None) if zone else datetime.now()


def today() -> date:
    return now().date()