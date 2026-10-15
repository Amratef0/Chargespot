# Audit of the team's delivered code (before integration)

**What was audited:** `ChargeSpot-main.zip` (19 files) + three loose files (`main.py`, `station.py`,
`login_and_register.py`). **How:** every finding below was *run*, not only read (scripts in the
audit session; each one is also now a regression test, shown in the last column).

**The loose files differ from the zip** (e.g. loose `main.py` = 250 lines of Member 2's console menus, zip `main.py` =
25-line login stub; loose `station.py` = the old 7-argument Station, zip `station.py` = Member 1's new Station).
Assumption taken: the zip is the repository; the loose files are Member 2's older/parallel version. Both
were kept in `legacy/` and **both were merged** (Member 2's user flow and fields, Member 1's model and JSON).

## Critical (the project could not run, or a graded requirement was missing)

| # | Owner | Finding | Evidence (run on the delivered code) | Fixed by | Regression test |
|---|---|---|---|---|---|
| 1 | M1 / M2 / M3 | 3 modules do not import | `station_data`: `TypeError: Station.__init__() takes 5 positional arguments but 8 were given`; `session_service`: `No module named 'algorithms'`; `battery_service`: `No module named 'models'` | package layout `models/ algorithms/ services/ utils/` (the layout the plan itself suggests) | every test imports them |
| 2 | M1 vs M2 | Two incompatible `Station` classes (4 args + chargers vs 7 args + area/location/slots) | the two files cannot both be imported | one `Station` (M1's model + M2's `area`, price, hours) | `test_station_validation`, catalog tests |
| 3 | M2 | **Overlap rule wrong**: `is_overlap` only returned True for identical start AND end | `10:00-11:00` vs `10:30-11:30` → `False`; `10:00-12:00` vs `10:30-11:00` → `False` | `intervals_overlap` = `A.start < B.end and B.start < A.end` (the plan's rule) | `test_overlap_rule_from_the_project_plan`, `test_partial_overlap_is_detected` |
| 4 | M1 | **Hash table lost data**: no collision handling (second key overwrote the first), `get` returned `0` for a missing key, used Python's per-run randomised `hash()`, and **nothing used it** | `HashTable(1)`: put BK1, put BK2 → `get('BK1')` returned BK2's value; `grep` found no importer | rebuilt: chaining, own hash function, resize, stats; used as the ID registry of stations, chargers and bookings | `test_hash_table_keeps_both_values_on_collision` + 6 more |
| 5 | M2 | **No binary search anywhere** (required; plan assigns it to Member 2) | `grep -i binary` → nothing | `algorithms/searching.py`; used on every booking to check overlaps and in the ID-lookup experiment | `test_binary_*`, `test_overlap_check_uses_binary_search...` |
| 6 | all | Not Streamlit: both versions are console programs (`input()`/`print()`); the brief forbids a console-only submission | `main.py` | full Streamlit app (9 pages, login, roles) | `tests/test_app_smoke.py`, `test_app_flows.py` |
| 7 | M2 | Bookings were per **station**, had **no date**, no connector check, no duration | station with 5 chargers: 2nd driver at the same hour went to the waiting list; a 10:00 booking blocked 10:00 on **every day** | per charger + date + duration + connector + opening hours + past-time checks | `test_two_chargers_at_the_same_time...`, `test_back_to_back_is_allowed_and_other_days_are_independent`, `test_booking_validation` |
| 8 | M2 / M3 | Bookings, waiting list and sessions lived only in RAM (plan: "CSV persists after restart") | no file written | atomic CSV save after every change | `test_booking_is_saved_and_survives_a_restart`, `test_full_session_lifecycle` |
| 9 | M2 | Driver IDs were handed out in login order from a dict in RAM, so the same person could get a different ID after a restart | `driver_ids` dict in `main.py` | `driver_id` stored in `users.json` | `test_driver_ids_are_unique_and_persisted` |

## Important

| # | Owner | Finding | Evidence | Fixed by |
|---|---|---|---|---|
| 10 | login | `register_user()` loops forever on bad input: it prints "Returning to Home page" but never returns | 40 prompts then killed | form with all errors shown at once (`test_register_collects_all_errors...`) |
| 11 | login | e-mail regex rejects `a.b@gmail.com`, `x@mail.co.uk`; phone accepted letters (`abcd`); ages above 55 rejected; duplicate e-mail accepted (zip version) | run | `utils/validators.py` + tests |
| 12 | login | Passwords stored in **plain text** in `users.json` together with a national ID, and the admin password hard-coded in source (checklist: "no private data") | `users.json` | salted PBKDF2-SHA256; plain-text entries upgraded automatically; `users.json` is git-ignored |
| 13 | M1 | `Station.load_from_json` used the current folder → crash when the app is started from another folder | run from `/tmp` → `FileNotFoundError` | configurable path (`test_json_persistence_and_independent_of_current_folder`) |
| 14 | M1 | Rule "cannot delete a charger with active bookings" not implemented (only `Occupied` checked); undo covered only charger removal; no add/edit/remove **station** | removed `AC-101` while booked | `StationService` rules + undo for every admin action (`test_undo_stack_covers_every_admin_action`) |
| 15 | M2 | Waiting-list promotion only matched a cancelled booking with the *same* start and end; the "queue" was a plain list; queue positions not shown (plan requires them) | code | FIFO `Queue`, positions, promotion of any freed slot |
| 16 | M2 | `available_slots` list duplicated the booking state (two sources of truth) | code | removed; availability is computed from bookings (2-D grid) |
| 17 | M1 / M2 | `print()` inside model/service methods: a Streamlit page cannot show it | code | methods raise `ChargeSpotError` subclasses |
| 18 | M1 / M2 | Station catalog split between `stations.json` (1 station, with chargers) and `station_data.py` (15 stations, no chargers); a station name had a trailing space | run | `data/build_catalog.py` merges them: 16 stations, 56 chargers |
| 19 | M1 | After loading JSON the chargers are plain dicts, so AC/DC polymorphism is lost | code | `charger_from_dict` factory used by the UI |
| 20 | M2 | `time_to_minutes`, `get_areas`, `find_best_station` defined without `self`/`@staticmethod` (work only when called on the class) | code | `@staticmethod` |

## Bugs found by the tests in the integrator's OWN code (listed for honesty)
* An operator (no `driver_id`) could cancel any driver's booking because `owner=None` meant "no check" (`test_only_the_owner_or_admin_can_cancel`).
* Confirmation messages vanished because the page called `st.rerun()` right after showing them (`test_driver_cancels_through_the_page`) → flash messages.
* Recommendation scoring with min-max scaling ranked a 9 km station above a 2.7 km one (fixed earlier; absolute scales).

## What was already good
* **Member 3's code** is the cleanest of the delivery: strict validation, an explicit state machine (Planned → Active → Completed), Merge Sort with a comparison counter, battery maths that matches a hand calculation (`test_battery_estimates_hand_calculation`). Only the import paths needed the folder layout; an injectable clock was added.
* Member 1's `Charger / ACCharger / DCCharger` hierarchy, the Stack, the station search/filter ideas.
* Member 2's user flow (area → time → station options → book / waiting list / cancel / admin views) and the "nearest available station" greedy idea.
