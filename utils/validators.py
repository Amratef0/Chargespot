"""Input validation with regular expressions (PDF: regex for IDs, time format, e-mail, phone).

`is_*` functions return True/False. `require_*` raise ValidationError with a friendly message.
"""
import re
from datetime import datetime

from models.exceptions import ValidationError

PATTERNS = {
    "station": re.compile(r"^\d{1,4}$"),                  # 12
    "charger": re.compile(r"^(AC|DC)-\d{3}$"),            # AC-101, DC-201
    "booking": re.compile(r"^\d{1,9}$"),                  # 1042
    "session": re.compile(r"^\d{1,9}$"),
    "driver": re.compile(r"^D\d{3,6}$"),                  # D101
    "time": re.compile(r"^([01]\d|2[0-3]):[0-5]\d$"),     # 08:30 (24 h)
    "date": re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"),
    "email": re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)*\.[A-Za-z]{2,}$"),
    "phone": re.compile(r"^\+?\d{7,15}$"),
    "national_id": re.compile(r"^\d{14}$"),
}
AGE_MIN, AGE_MAX = 18, 100          # driving age; change here if the team decides differently
GENDERS = ("male", "female")


def matches(kind: str, value) -> bool:
    return isinstance(value, str) and PATTERNS[kind].fullmatch(value.strip()) is not None


def is_id(kind: str, value) -> bool:
    return matches(kind, value if isinstance(value, str) else str(value))


def require_id(kind: str, value) -> str:
    v = str(value).strip()
    if not matches(kind, v):
        examples = {"station": "12", "charger": "AC-101 or DC-201", "booking": "1042", "session": "17",
                    "driver": "D101"}
        raise ValidationError(f"Invalid {kind} ID '{v}'. Example: {examples.get(kind, '?')}.")
    return v


def is_name(v) -> bool: return isinstance(v, str) and 3 <= len(v.strip()) <= 100
def is_email(v) -> bool: return matches("email", v.strip().lower() if isinstance(v, str) else v) and len(v.strip()) <= 100
def is_phone(v) -> bool: return matches("phone", v)
def is_national_id(v) -> bool: return matches("national_id", v)
def is_gender(v) -> bool: return isinstance(v, str) and v.strip().lower() in GENDERS


def is_age(v) -> bool:
    try:
        return AGE_MIN <= int(str(v).strip()) <= AGE_MAX and str(v).strip().isdigit()
    except ValueError:
        return False


def is_password(password: str, confirm: str | None = None) -> bool:
    ok = isinstance(password, str) and 8 <= len(password) <= 100
    return ok and (confirm is None or password == confirm)


def require_time(v: str) -> str:
    if not matches("time", v):
        raise ValidationError(f"Invalid time '{v}'. Use 24-hour HH:MM, e.g. 08:30.")
    return v.strip()


def require_date(v: str) -> str:
    if not matches("date", v):
        raise ValidationError(f"Invalid date '{v}'. Use YYYY-MM-DD.")
    try:
        datetime.strptime(v.strip(), "%Y-%m-%d")
    except ValueError:
        raise ValidationError(f"'{v}' is not a real calendar date.")
    return v.strip()
