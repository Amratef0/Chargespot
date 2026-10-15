# ChargeSpot - EV charging management (SIC 8 final project)

Streamlit app: stations and chargers, bookings with overlap prevention, a FIFO waiting list, charging sessions,
a driver dashboard with a battery monitor, and an admin analytics dashboard with several AI features.
**All data is simulated** (no real chargers or vehicles). Station coordinates are approximate.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
.\.venv\Scripts\Activate.ps1        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py                                      # first start creates the simulated history (~30 s)
python -m pytest                                          # the whole test suite, about 1 minute
```

**Demo accounts** (fake people): `admin@chargespot.com / Admin1234` · `operator@chargespot.com / Operator1234` ·
`ahmed@gmail.com / 123456789` (driver). Anyone can also register as a driver (the e-mail address must be verified before the first login; see `docs/AUTH.md`).

## Roles

| Role             | Pages                                                                                                                                              |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Driver           | Smart Recommendation · Bookings (book, alternatives, waiting list, cancel) · Waiting List · Driver Dashboard (battery monitor, history) · Stations |
| Station Operator | Stations (change charger status) · Bookings (all, availability grid) · Waiting List · Charging Sessions (start/complete)                           |
| Administrator    | everything above + add/edit/remove stations and chargers with **Undo** · Admin Analytics · Algorithm Lab                                           |

## Project structure

```
app.py                 login + role-based navigation
models/                Station, Charger (AC/DC), Booking, ChargingSession, User roles, exceptions
algorithms/            stack, queue, hash_table, sorting (merge sort), searching, interval_utils, greedy_scheduler
services/              station, booking, waiting, scheduler, session, battery, auth
utils/validators.py    regex validation
core/                  app_context (wires everything + saves CSV), state (Streamlit), schema, data_store
analytics/ ai/         Pandas cleaning/metrics/charts/insights; forecast, recommendation, optimizer, maintenance
pages/                 the Streamlit pages (no business logic in them)
data/                  stations.json, distances.json, simulated history, generator, catalog builder
tests/                 test suite          docs/   audit, changes, checklist, algorithms, schema, demo script
legacy/                the team's original files, untouched (for comparison)
```

How the pieces connect: **`core/app_context.py`** - e.g. completing a session marks the booking _Completed_, frees the
charger, and promotes waiting drivers. State: `st.cache_resource` holds one shared app (changes are saved to CSV/JSON
immediately and survive a restart); `st.session_state` holds who is logged in.

## Data structures and algorithms (all hand-written; details in `docs/ALGORITHMS.md`)

Stack (undo) · Queue (waiting list) · Hash table (ID registries) · Sequential search · Binary search (overlap checks,
ID lookup) · Merge Sort (histories) · Greedy slot assignment (+ exact/local-search alternatives for comparison).
The **Algorithm Lab** page measures them on the real data.

## Analytics and AI (admin)

Cleaning with a defect report (11 defect types injected, all detected exactly) · KPIs and generated insights · demand
heatmap/trend · station map · demand forecast vs baselines · rule-based assistant (English/Arabic) · scheduling
optimizer · predictive maintenance · smart station recommendation. Optional LLM rewording of the assistant's answers
(`ANTHROPIC_API_KEY`; off by default; any rewrite whose numbers differ is rejected).
Honest limits: the data is synthetic, so forecast/maintenance accuracy shows the method works, not real-world accuracy.

## Docs

`docs/TEAM_AUDIT.md` (what was wrong, with evidence) · `docs/TEAM_CHANGES.md` (what changed per member) ·
`docs/REQUIREMENTS_CHECKLIST.md` · `docs/ALGORITHMS.md` · `docs/SCHEMA.md` · `docs/EDGE_CASE_TESTING_NOTES.md` ·
`docs/DEMO_SCRIPT_AND_DEFENSE_QA.md` · `docs/AI_USE_LOG_Member4.md` · `docs/AUTH.md` (roles, sessions, e-mail verification, password reset, e-mail setup)

## Known limitations

- One server process shares one app object (fine for a demo, not for many simultaneous servers).
- Compatibility = same connector type; all stations open 24 h; times are naive (no time zones).
- Screenshots must be taken by the team from the running app.
