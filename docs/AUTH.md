# Authentication and authorization

## Who may do what (one source of truth)
* `models/user.py` - `permissions()` of `Driver`, `StationOperator`, `Admin` is the ONLY definition of what a role can do.
* `services/authz.py` - `PAGE_ACCESS` (which permission opens which page) and `authorize(user, *permissions)`.
* The sidebar (`app.py`) and every page (`core.state.require_page`) read `PAGE_ACCESS`; there is no second list of roles.
* **The application layer enforces it too.** Every state-changing method of `ChargeSpotApp` takes the acting `user` and
  calls `authorize` first (start/complete session, no-show, charger status, add/remove charger, add/edit/remove station,
  undo, reload, booking, waiting list, other drivers' data). Failures raise `PermissionDeniedError`.
* Rule for new code: pages call `app.<method>(user, ...)`, never `app.stations.<mutator>` directly
  (`tests/test_authorization.py` fails the build if a page does).

| Permission | Driver | Operator | Admin |
|---|:-:|:-:|:-:|
| book, cancel_own, view_own, battery, recommend | yes | | recommend only |
| view_stations | yes | yes | yes |
| update_charger_status, manage_sessions, manage_waiting, view_all_bookings | | yes | yes |
| manage_stations, undo, analytics, cancel_any, view_any_driver | | | yes |

## Login sessions (survive a refresh)
`LoginSessionStore` (`data/auth_sessions.json`) keeps SHA-256 hashes of random tokens. The browser holds the token in
the `cs_session` cookie (`core/browser_session.py`). `core.state.authenticate()` validates it on every run, so logout,
expiry (idle 2 h, absolute 12 h; constants in `login_session_service.py`) and password reset take effect at once.
Cookie limits: set by JavaScript, so not HttpOnly; SameSite=Lax, Secure on https.

## E-mail verification and forgot password
* Sign-up creates the account unverified and e-mails a single-use token (24 h). Login is refused until verified, but only
  after the password was right (a wrong password never reveals "unverified").
* Forgot password e-mails a single-use token (30 min, max 3 per hour per address). The answer on screen is always the same,
  whether or not the address exists. A reset logs the account out everywhere.
* Tokens (`data/auth_tokens.json`) are stored hashed. Links look like `<CHARGESPOT_BASE_URL>/?verify=TOKEN` and
  `/?reset=TOKEN`; the code can also be pasted into the "Verify e-mail" / "Forgot password" tabs.
* Existing accounts (demo, legacy) count as verified.

## Configuration (environment variables)
| Variable | Meaning |
|---|---|
| `CHARGESPOT_SMTP_HOST`, `_PORT` (587 STARTTLS / 465 SSL), `_USER`, `_PASSWORD` | real e-mail (Gmail: use an app password) |
| `CHARGESPOT_MAIL_FROM` | sender address (default: the SMTP user) |
| `CHARGESPOT_BASE_URL` | public URL of the app, used to build the links in e-mails (e.g. `https://chargespot.example`) |
| `CHARGESPOT_DEV_MAILBOX=1` | with NO SMTP configured: show the e-mails on the login screen (demo / defense only!) |
Without SMTP, e-mails are written to `data/outbox/` and nobody receives them.

## Known limits / next steps
* PBKDF2 uses 100 000 iterations and the hash format does not store the count; raising it needs a versioned format.
* No lockout / rate limit on the login form itself yet.
* Demo credentials are shown on the login screen: remove that expander before any public deployment.
* One server process shares the stores (same limit as the rest of the app).
