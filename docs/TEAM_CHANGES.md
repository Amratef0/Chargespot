# What changed in each member's code (and what each member must be able to explain)

Rule followed: **keep names, flows and ideas; change only what was wrong or missing.** Originals are untouched in
`legacy/team_original_zip/` and `legacy/team_original_loose/` (`users.json` was removed from the copy: it held a
plain-text password; the demo user was migrated into hashed form).

> ⚠️ The PDF says everyone may be asked in the defense to explain and modify their own code **live**. Lines marked
> **NEW (integration)** were written during integration, not by the owner. The owner must read them until they can
> trace them on paper.

## Member 1 - stations, chargers, hash table, stack, sequential search, regex
| File | Kept | Changed / added |
|---|---|---|
| `models/charger.py` | `Charger`, `ACCharger`, `DCCharger`, `get_info`, `casting_charge_to_dict` | validation (power, status, connector per type, ID format) · `charger_from_dict` factory |
| `models/station.py` | registry `all_stations`, `add_charger`, `remove_charger`, `update_charger_status`, `get_availability_summary`, `sequential_search_by_name`, `filter_by_governorate`, `filter_stations_by_connector`, `save/load_json` | raise exceptions instead of `print` · configurable JSON path · atomic save · extra fields `area`, `price_per_kwh`, `lat/lon`, opening hours (Member 2 needed them) · `status` property · filters by status and power |
| `algorithms/stack.py` | unchanged | - |
| `algorithms/hash_table.py` | method names `put/get/hash` | **NEW (integration)**: chaining, resize, own hash function, stats (the old one lost data and was unused) |
| `services/station_service.py` | `remove_charger_with_undo`, `undo_last_admin_action` | **NEW**: undo for *every* admin action, station add/edit/remove, "no removal with active bookings" rule, hash registry of stations and chargers |
| `utils/validators.py` | - | **NEW**: regex for IDs, time, date, e-mail, phone, national ID |
| `models/user.py` | - | **NEW**: `User → Driver / StationOperator / Admin` with polymorphic `permissions()` |
| `services/auth_service.py` | the registration fields and validators from both versions | **NEW**: hashed passwords, duplicate checks, all errors at once, persistent driver IDs |

## Member 2 - bookings, waiting list, queue, greedy scheduling, binary search, overlap
| File | Kept | Changed / added |
|---|---|---|
| `models/booking.py` | the 8 original fields in the same order | + `charger_id`, `connector`, `created_at`, `queued`, `wait_min`; times are full datetimes |
| `services/booking_service.py` | `check_booking_overlap`, `create_booking`, `cancel_booking`, `time_to_minutes`, `is_overlap` | **REDESIGNED**: per charger and date, correct overlap rule, validation (duration, 15-min step, hours, connector, past), binary-search overlap check on a sorted busy list, hash booking registry, `availability_grid` (2-D) |
| `services/waiting_service.py` | `WaitingQueue`, `add_to_waiting_list`, `remove_request`, `get_request`, `get_matching_requests` | now on a real FIFO `Queue`, with positions, expiry, promotion of any freed slot in FIFO order |
| `algorithms/queue.py` | - | **NEW**: `Queue` (enqueue, dequeue, peek, position, remove) |
| `algorithms/searching.py` | - | **NEW**: sequential, binary (refuses unsorted data), insertion point, trace |
| `algorithms/interval_utils.py` | - | **NEW**: the plan's overlap rule |
| `algorithms/greedy_scheduler.py` | the "nearest / earliest available" greedy idea | **NEW** charger-level version + alternatives |
| `services/scheduler.py` | `Scheduler`, `get_areas`, `get_distance`, `find_suitable_stations`, `find_best_station`, the ordering rule | availability per charger/date/duration; hand-written O(n²) swap loop replaced by the team's `merge_sort` |
| `data/distances.json` | the matrix from `station_data.py`, unchanged | moved from code to data |
| pages `2_Bookings.py`, `3_Waiting_List.py` | the console flow of the loose `main.py` | ported to Streamlit |

## Member 3 - sessions, battery, merge sort, exceptions
| File | Kept | Changed / added |
|---|---|---|
| `algorithms/sorting.py` | `merge_sort` exactly as delivered | + `merge_sort_with_stats` (recursive calls) |
| `models/charging_session.py`, `services/battery_service.py` | unchanged (line endings only) | - |
| `services/session_service.py` | everything | + optional `now` argument (simulate time in a demo) · `load_session` · `next_session_id` · "completion before start" check |
| `models/exceptions.py` | the 3 original exceptions | + `ValidationError`, `DuplicateIDError`, `NotFoundError`, `SchedulingConflictError`, `ChargerInUseError`, `InvalidStatusError`, `AuthError`, `UnsortedDataError` |
| pages `4_Sessions.py`, `5_Driver_Dashboard.py` | - | **NEW** UI |

## Glue (Member 4 / integration)
`core/app_context.py` (`ChargeSpotApp`) connects the modules: a completed session marks the booking *Completed*,
frees the charger and triggers waiting-list promotion; a cancelled booking does the same. Streamlit pages contain
no business logic. `core/state.py`: `st.cache_resource` = one shared app, `st.session_state` = who is logged in.

## Decisions the team should confirm (changeable in one place)
| Decision | Where |
|---|---|
| Adult drivers only: age 18-100 (the two versions said 13-100 and 16-55) | `utils/validators.py: AGE_MIN, AGE_MAX` |
| A connector is "compatible" when the vehicle's connector equals the charger's connector (CCS2 / CHAdeMO / Type 2) | `ChargeSpotApp.book_at_station` |
| All stations are open 24 h (their slots ran 00:00-23:00) | `stations.json: open_hour/close_hour` |
| Chargers for stations 2-16, prices and coordinates were **invented** by Member 4 (the team data had chargers only for station 1); coordinates are approximate and used only for maps | `data/build_catalog.py` |
| Station IDs stay numbers, charger IDs `AC-101` / `DC-201`, booking IDs numbers, driver IDs `D101` | `utils/validators.py`, `docs/SCHEMA.md` |
