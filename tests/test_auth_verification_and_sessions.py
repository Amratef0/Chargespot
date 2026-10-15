"""E-mail verification, forgot password, and server-side login sessions (no Streamlit needed)."""
import re
from datetime import datetime, timedelta

import pytest

from models.exceptions import AuthError, EmailNotVerifiedError, TokenError, ValidationError
from services.auth_service import AuthService
from services.login_session_service import LoginSessionStore
from services.mailer import MemoryMailer
from services.token_service import RESET_PASSWORD, VERIFY_EMAIL, TokenStore


class Clock:
    def __init__(self):
        self.t = datetime(2026, 3, 2, 9, 0)

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


@pytest.fixture()
def env(tmp_path):
    clock, mailer = Clock(), MemoryMailer()
    sessions = LoginSessionStore(tmp_path / "s.json", now_fn=clock)
    auth = AuthService(tmp_path / "u.json", vehicle_models=["BYD Atto 3"], mailer=mailer,
                       tokens=TokenStore(tmp_path / "t.json", now_fn=clock), sessions=sessions,
                       base_url="https://app.example")
    return auth, mailer, sessions, clock, tmp_path


def good(**kw):
    d = dict(name="Sara Hassan", email="sara@mail.com", phone="01234567890", age="27", gender="female",
             governorate="giza", national_id="29001010100999", password="Password1", confirm_password="Password1",
             vehicle_model="BYD Atto 3")
    d.update(kw)
    return d


def code_in(mail, marker):
    return re.search(marker + r": (\S+)", mail.body).group(1)


# ----------------------------------------------------------------- sign-up verification
def test_register_sends_a_token_and_login_is_blocked_until_verified(env):
    auth, mailer, *_ = env
    u = auth.register(**good())
    assert u.verification_sent is True and len(mailer.sent) == 1 and mailer.sent[0].to == "sara@mail.com"
    assert "https://app.example/?verify=" in mailer.sent[0].body
    with pytest.raises(EmailNotVerifiedError):
        auth.login("sara@mail.com", "Password1")
    with pytest.raises(AuthError, match="Incorrect") as e:           # a wrong password must NOT reveal "unverified"
        auth.login("sara@mail.com", "WrongPass1")
    assert not isinstance(e.value, EmailNotVerifiedError)
    auth.verify_email(code_in(mailer.sent[0], "Verify e-mail' tab"))
    assert auth.login("sara@mail.com", "Password1").email == "sara@mail.com"


def test_verification_token_is_single_use_and_garbage_is_rejected(env):
    auth, mailer, *_ = env
    auth.register(**good())
    tok = code_in(mailer.sent[0], "Verify e-mail' tab")
    for bad in ("", None, "nonsense", tok[:-1] + ("A" if tok[-1] != "A" else "B")):
        with pytest.raises(TokenError):
            auth.verify_email(bad)
    auth.verify_email(tok)
    with pytest.raises(TokenError):
        auth.verify_email(tok)


def test_verification_token_expires_after_24_hours(env):
    auth, mailer, _, clock, _ = env
    auth.register(**good())
    tok = code_in(mailer.sent[0], "Verify e-mail' tab")
    clock.advance(hours=25)
    with pytest.raises(TokenError):
        auth.verify_email(tok)


def test_resend_replaces_the_old_token_and_is_rate_limited(env):
    auth, mailer, _, clock, _ = env
    auth.register(**good())
    first = code_in(mailer.sent[0], "Verify e-mail' tab")
    auth.resend_verification("sara@mail.com")                        # too soon: ignored
    assert len(mailer.sent) == 1
    clock.advance(minutes=2)
    auth.resend_verification("sara@mail.com")
    assert len(mailer.sent) == 2
    with pytest.raises(TokenError):                                  # the first code stopped working
        auth.verify_email(first)
    auth.verify_email(code_in(mailer.sent[1], "Verify e-mail' tab"))
    n = len(mailer.sent)
    clock.advance(minutes=5)
    auth.resend_verification("sara@mail.com")                        # already verified: nothing sent
    auth.resend_verification("nobody@mail.com")                      # unknown: nothing sent, no error
    assert len(mailer.sent) == n


def test_tokens_are_stored_hashed(env):
    auth, mailer, _, _, tmp = env
    auth.register(**good())
    tok = code_in(mailer.sent[0], "Verify e-mail' tab")
    assert tok not in (tmp / "t.json").read_text()


def test_demo_and_legacy_accounts_are_already_verified(env):
    auth, *_ = env
    assert auth.login("admin@chargespot.com", "Admin1234").role == "admin"
    assert auth.login("ahmed@gmail.com", "123456789").driver_id == "D101"


def test_verification_is_off_without_a_mailer(tmp_path):
    a = AuthService(tmp_path / "u.json")
    a.register(**good())
    assert a.login("sara@mail.com", "Password1")


# ----------------------------------------------------------------- forgot / reset password
def verified_user(env):
    auth, mailer, *_ = env
    auth.register(**good())
    auth.verify_email(code_in(mailer.sent[0], "Verify e-mail' tab"))
    mailer.sent.clear()


def test_reset_flow_changes_the_password_once(env):
    auth, mailer, *_ = env
    verified_user(env)
    auth.request_password_reset("SARA@mail.com")
    assert len(mailer.sent) == 1 and "https://app.example/?reset=" in mailer.sent[0].body
    tok = code_in(mailer.sent[0], "Forgot password' tab")
    auth.reset_password(tok, "BrandNew123", "BrandNew123")
    assert auth.login("sara@mail.com", "BrandNew123")
    with pytest.raises(AuthError):
        auth.login("sara@mail.com", "Password1")
    with pytest.raises(TokenError):
        auth.reset_password(tok, "Another1234", "Another1234")


def test_weak_or_mismatched_password_does_not_burn_the_token(env):
    auth, mailer, *_ = env
    verified_user(env)
    auth.request_password_reset("sara@mail.com")
    tok = code_in(mailer.sent[0], "Forgot password' tab")
    with pytest.raises(ValidationError):
        auth.reset_password(tok, "short", "short")
    with pytest.raises(ValidationError, match="match"):
        auth.reset_password(tok, "BrandNew123", "Different123")
    auth.reset_password(tok, "BrandNew123", "BrandNew123")


def test_reset_token_expires_after_30_minutes(env):
    auth, mailer, _, clock, _ = env
    verified_user(env)
    auth.request_password_reset("sara@mail.com")
    tok = code_in(mailer.sent[0], "Forgot password' tab")
    clock.advance(minutes=31)
    with pytest.raises(TokenError):
        auth.reset_password(tok, "BrandNew123", "BrandNew123")


def test_unknown_address_gets_no_mail_and_no_error(env):
    auth, mailer, *_ = env
    auth.request_password_reset("nobody@mail.com")
    auth.request_password_reset("")
    assert mailer.sent == []


def test_reset_requests_are_capped_per_hour(env):
    auth, mailer, *_ = env
    verified_user(env)
    for _ in range(8):
        auth.request_password_reset("sara@mail.com")
    assert len(mailer.sent) == 3


def test_a_token_of_one_purpose_cannot_be_used_for_the_other(env):
    auth, mailer, *_ = env
    auth.register(**good())
    verify_tok = code_in(mailer.sent[0], "Verify e-mail' tab")
    with pytest.raises(TokenError):
        auth.reset_password(verify_tok, "BrandNew123", "BrandNew123")


def test_reset_logs_the_account_out_everywhere_and_verifies_the_mailbox(env):
    auth, mailer, sessions, *_ = env
    auth.register(**good())                                          # never verified
    sessions_token = sessions.create("sara@mail.com")
    auth.request_password_reset("sara@mail.com")
    tok = code_in(mailer.sent[-1], "Forgot password' tab")
    auth.reset_password(tok, "BrandNew123", "BrandNew123")
    assert sessions.validate(sessions_token) is None
    assert auth.login("sara@mail.com", "BrandNew123")                # receiving the token proved the mailbox


def test_mail_failure_at_sign_up_still_creates_the_account(env):
    auth, _, _, _, tmp = env
    from services.mailer import MailDeliveryError

    class Broken:
        def send(self, *a):
            raise MailDeliveryError("down")
    auth.mailer = Broken()
    assert auth.register(**good()).verification_sent is False
    auth.request_password_reset("sara@mail.com")                     # must not raise or reveal anything


# ----------------------------------------------------------------- login sessions
def test_session_survives_restart_and_logout_revokes_it(env):
    _, _, sessions, clock, tmp = env
    tok = sessions.create("Sara@Mail.com")
    assert sessions.validate(tok) == "sara@mail.com"
    assert LoginSessionStore(tmp / "s.json", now_fn=clock).validate(tok) == "sara@mail.com"       # "refresh / restart"
    assert tok not in (tmp / "s.json").read_text()                                                  # only a hash is stored
    sessions.revoke(tok)
    assert sessions.validate(tok) is None and LoginSessionStore(tmp / "s.json", now_fn=clock).validate(tok) is None


def test_idle_timeout_is_sliding_and_absolute_lifetime_is_hard(env):
    _, _, sessions, clock, _ = env
    tok = sessions.create("sara@mail.com")
    for _ in range(13):                                              # active every 60 min: stays logged in...
        clock.advance(minutes=60)
        if sessions.validate(tok) is None:
            break
    assert sessions.validate(tok) is None                            # ...until the 12 h absolute limit
    tok2 = sessions.create("sara@mail.com")
    clock.advance(minutes=121)                                       # idle for more than 2 h
    assert sessions.validate(tok2) is None


def test_garbage_tokens_are_rejected(env):
    _, _, sessions, *_ = env
    for bad in (None, "", "x" * 10, 123):
        assert sessions.validate(bad) is None


def test_revoke_all_only_touches_that_account(env):
    _, _, sessions, *_ = env
    a1, a2, b = sessions.create("a@x.com"), sessions.create("a@x.com"), sessions.create("b@x.com")
    assert sessions.revoke_all("A@x.com") == 2
    assert sessions.validate(a1) is None and sessions.validate(a2) is None and sessions.validate(b) == "b@x.com"


def test_token_store_history_is_pruned_after_a_day(env):
    auth, mailer, _, clock, _ = env
    auth.register(**good())
    clock.advance(hours=25)
    auth.tokens.issue(VERIFY_EMAIL, "other@x.com")
    assert auth.tokens.issued_recently(VERIFY_EMAIL, "sara@mail.com", 60 * 48) == 0
