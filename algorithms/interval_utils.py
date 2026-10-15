"""Time-interval helpers. The overlap rule comes straight from the project plan."""
from models.exceptions import ValidationError
from utils.validators import PATTERNS


def intervals_overlap(a_start, a_end, b_start, b_end):
    """True if the two intervals share time. Back-to-back bookings (A.end == B.start) do NOT overlap."""
    return a_start < b_end and b_start < a_end


def time_to_minutes(hhmm: str) -> int:
    if not PATTERNS["time"].fullmatch(str(hhmm).strip()):
        raise ValidationError(f"Invalid time '{hhmm}'. Use HH:MM.")
    h, m = str(hhmm).strip().split(":")
    return int(h) * 60 + int(m)


def minutes_to_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
