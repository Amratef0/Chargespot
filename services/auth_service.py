"""Login / registration (merged from the team's two versions of login_and_register.py).

From the persistent version (zip): users stored in users.json.  From the other version: validators
that return True/False (usable from Streamlit; the console version looped on input()).
Fixed: registration looped forever on bad input and could not return to the menu; duplicate e-mails
were accepted; the e-mail regex rejected a.b@x.com and x@y.co.uk; phone accepted letters; ages 56+ were
rejected; passwords were stored in PLAIN TEXT (now salted PBKDF2-SHA256; old plain-text entries are
upgraded on first load); the admin password was hard-coded in the source of one version.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path

from models.exceptions import AuthError, DuplicateIDError, EmailNotVerifiedError, TokenError, ValidationError
from models.user import user_from_dict
from services import token_service as T
from services.mailer import MailDeliveryError
from utils import validators as V

ITERATIONS = 100_000
RESEND_VERIFY_SECONDS_MIN = 1          # a verification e-mail may be re-sent once per this many minutes
RESET_MAX_PER_HOUR = 3                 # password-reset e-mails per address per hour (silently capped)

DEMO_USERS = [   # DEMO accounts only (fake people). Documented in the README.
    {"name": "ChargeSpot Admin", "email": "admin@chargespot.com", "password": "Admin1234", "role": "admin",
    "email_verified": True, "phone": "0100000001", "age": 35, "gender": "male", "governorate": "CAIRO", "national_id": "29001010100001"},
    {"name": "Omar Operator", "email": "operator@chargespot.com", "password": "Operator1234", "role": "operator",
    "email_verified": True, "phone": "0100000002", "age": 30, "gender": "male", "governorate": "CAIRO", "national_id": "29001010100002"},
    {"name": "Ahmed", "email": "ahmed@gmail.com", "password": "123456789", "role": "user", "email_verified": True, "phone": "0123456",
    "age": 19 + 0, "gender": "male", "governorate": "CAIRO", "national_id": "12345678912345",
    "driver_id": "D101", "vehicle_model": "MG ZS EV"},
]


def hash_password(password, salt=None):
    salt = salt or os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"{salt}${h}"


def verify_password(password, stored):
    try:
        salt, h = stored.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt).split("$")[1], h)


class AuthService:
    def __init__(self, path, first_new_driver_number=401, vehicle_models=(), mailer=None, tokens=None,
                sessions=None, base_url=None):
        """mailer=None -> e-mail verification is OFF (library/test use). The app always passes a mailer.
        `sessions` (LoginSessionStore) lets a password reset log the account out everywhere."""
        self.path = Path(path)
        self.vehicle_models = list(vehicle_models)
        self.first_new_driver_number = first_new_driver_number
        self.mailer = mailer
        self.tokens = tokens or (T.TokenStore(self.path.with_name("auth_tokens.json")) if mailer else None)
        self.sessions = sessions
        self.base_url = (base_url or "").rstrip("/")
        self.users = self._load()

    @property
    def verification_required(self):
        return self.mailer is not None

    def _load(self):
        try:
            users = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            users = []
        if not users:
            users = [dict(u) for u in DEMO_USERS]
        changed = False
        for u in users:
            if "password" in u:                              # upgrade plain-text passwords
                u["password_hash"] = hash_password(u.pop("password"))
                changed = True
            if u.get("role", "user") == "user" and not u.get("driver_id"):
                u["driver_id"] = self._next_driver_id(users)
                changed = True
        self.users = users
        if changed or not self.path.exists():
            self._save()
        return users

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.users, indent=4), encoding="utf-8")
        tmp.replace(self.path)

    def _next_driver_id(self, users=None):
        nums = [int(u["driver_id"][1:]) for u in (users if users is not None else self.users)
                if u.get("driver_id") and V.matches("driver", u["driver_id"])]
        return f"D{max([self.first_new_driver_number - 1] + nums) + 1}"

    def find_by_email(self, email):
        e = email.strip().lower()
        return next((u for u in self.users if u["email"].lower() == e), None)

    def get_user(self, email):
        """The User object for an e-mail (used to restore a login session), or None."""
        u = self.find_by_email(email or "")
        return user_from_dict(u) if u else None

    def register(self, name, email, phone, age, gender, governorate, national_id, password, confirm_password,
                vehicle_model=None):
        """Validate everything, report ALL problems at once, then store the new driver."""
        errors = []
        if not V.is_name(name): errors.append("Name must contain 3 to 100 characters.")
        if not V.is_email(email): errors.append("Please enter a valid e-mail address.")
        if not V.is_phone(phone): errors.append("Phone must contain 7 to 15 digits (an optional leading + is allowed).")
        if not V.is_age(age): errors.append(f"Age must be a whole number between {V.AGE_MIN} and {V.AGE_MAX}.")
        if not V.is_gender(gender): errors.append("Gender must be male or female.")
        if not str(governorate).strip(): errors.append("Governorate cannot be empty.")
        if not V.is_national_id(national_id): errors.append("National ID must contain exactly 14 digits.")
        if not V.is_password(password): errors.append("Password must be 8 to 100 characters.")
        elif password != confirm_password: errors.append("Passwords do not match.")
        if self.vehicle_models and vehicle_model not in self.vehicle_models:
            errors.append("Please choose your vehicle model.")
        if errors:
            raise ValidationError(" ".join(errors))
        if self.find_by_email(email) is not None:
            raise DuplicateIDError("This e-mail is already registered.")
        if any(u.get("national_id") == national_id.strip() for u in self.users):
            raise DuplicateIDError("This national ID is already registered.")
        user = {"name": name.strip(), "email": email.strip().lower(), "phone": phone.strip(), "age": int(age),
                "gender": gender.strip().lower(), "governorate": governorate.strip().upper(),
                "national_id": national_id.strip(), "role": "user", "driver_id": self._next_driver_id(),
                "vehicle_model": vehicle_model, "password_hash": hash_password(password),
                "email_verified": not self.verification_required}
        self.users.append(user)
        self._save()
        obj = user_from_dict(user)
        obj.verification_sent = self._send_verification(user["email"], user["name"]) if self.verification_required else None
        return obj

    def login(self, email, password):
        u = self.find_by_email(email or "")
        if u is None or not verify_password(password or "", u.get("password_hash", "")):
            raise AuthError("Incorrect e-mail or password.")           # same message for both cases on purpose
        if not u.get("email_verified", True):                       # older accounts have no flag = already trusted
            raise EmailNotVerifiedError("Please verify your e-mail address first. Check your inbox for the link "
                                        "or code, or ask for a new one.")
        return user_from_dict(u)

    # ------------------------------------------------------------------ e-mail verification
    def _mail(self, to, subject, lines):
        self.mailer.send(to, subject, "\n".join(lines) + "\n\n- ChargeSpot (university project, simulated data)")

    def _send_verification(self, email, name=""):
        """Returns True if the e-mail was handed to the mail server."""
        token = self.tokens.issue(T.VERIFY_EMAIL, email)
        lines = [f"Hi {name or 'there'},", "", "Confirm your e-mail address to activate your ChargeSpot account."]
        if self.base_url:
            lines += ["", f"Open this link: {self.base_url}/?verify={token}"]
        lines += ["", f"Or paste this code in the 'Verify e-mail' tab: {token}", "",
                "It works once and expires in 24 hours. If you did not sign up, ignore this message."]
        try:
            self._mail(email, "Verify your ChargeSpot e-mail", lines)
            return True
        except MailDeliveryError:
            return False

    def verify_email(self, token):
        email = self.tokens.consume(T.VERIFY_EMAIL, token) if self.tokens else None
        u = self.find_by_email(email) if email else None
        if u is None:
            raise TokenError("This verification link or code is invalid, expired or already used.")
        u["email_verified"] = True
        self._save()
        return user_from_dict(u)

    def resend_verification(self, email):
        """Always looks successful from outside (no way to learn which e-mails are registered)."""
        u = self.find_by_email(email or "")
        if (self.verification_required and u and not u.get("email_verified", True)
                and self.tokens.issued_recently(T.VERIFY_EMAIL, u["email"], RESEND_VERIFY_SECONDS_MIN) == 0):
            self._send_verification(u["email"], u["name"])

    # ------------------------------------------------------------------ forgot / reset password
    def request_password_reset(self, email):
        """Always looks successful from outside. Sends a 30-minute single-use token if the account exists."""
        u = self.find_by_email(email or "")
        if not (self.verification_required and u):
            return
        if self.tokens.issued_recently(T.RESET_PASSWORD, u["email"], 60) >= RESET_MAX_PER_HOUR:
            return
        token = self.tokens.issue(T.RESET_PASSWORD, u["email"])
        lines = [f"Hi {u['name']},", "", "Someone asked to reset the password of your ChargeSpot account."]
        if self.base_url:
            lines += ["", f"Open this link: {self.base_url}/?reset={token}"]
        lines += ["", f"Or paste this code in the 'Forgot password' tab: {token}", "",
                "It works once and expires in 30 minutes. If this was not you, ignore this message: "
                "your password has not changed."]
        try:
            self._mail(u["email"], "Reset your ChargeSpot password", lines)
        except MailDeliveryError:
            pass                                      # reporting this would reveal that the account exists

    def reset_password(self, token, new_password, confirm_password):
        if not V.is_password(new_password):                      # check BEFORE burning the token (typo-safe)
            raise ValidationError("Password must be 8 to 100 characters.")
        if new_password != confirm_password:
            raise ValidationError("Passwords do not match.")
        email = self.tokens.consume(T.RESET_PASSWORD, token) if self.tokens else None
        u = self.find_by_email(email) if email else None
        if u is None:
            raise TokenError("This reset link or code is invalid, expired or already used.")
        u["password_hash"] = hash_password(new_password)
        u["email_verified"] = True                    # receiving the token proves control of the mailbox
        self._save()
        if self.sessions:
            self.sessions.revoke_all(u["email"])      # whoever had the old password is logged out
        return user_from_dict(u)
