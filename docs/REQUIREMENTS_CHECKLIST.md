# Requirements checklist: SIC 8 brief + ChargeSpot plan  →  where it is  →  proof

✅ done and tested · ⚠️ needs an action from the team · everything else is covered by a test (`python -m pytest`, 278 tests).

## Brief - Layer 1: core system
| Requirement | Where | Proof |
|---|---|---|
| ✅ Inputs/outputs, conditions, loops, reusable functions | whole project | - |
| ✅ Clear validation messages, no crash on normal invalid use | `utils/validators.py`, `models/exceptions.py`, `core/ui.py::run_action` | `test_booking_validation`, `test_register_collects_all_errors...`, UI tests with bad input |
| ✅ Lists, tuples, dicts, sets, nested structures | busy intervals = tuples in dict-of-lists; sets for filters; nested station → chargers | `BookingService._busy` |
| ✅ 2-D structure where meaningful | charger × hour availability grid | `test_has_active_bookings_and_grid_and_sorting` |
| ✅ Clear record schema | `docs/SCHEMA.md`, `core/schema.py` | `test_frames_are_clean...` |
| ✅ Classes for main entities | `Station, Charger, Booking, ChargingSession, User` + services | - |
| ✅ Inheritance / polymorphism | `Charger → ACCharger/DCCharger`; `User → Driver/StationOperator/Admin` (`permissions()`) | `test_charger_validation_and_polymorphism`, `test_roles_and_permissions_are_polymorphic` |
| ✅ Exceptions | 11 custom exceptions incl. `SchedulingConflictError` | many |
| ✅ Regex (IDs, e-mail, phone, time, date) | `utils/validators.py::PATTERNS` | `test_time_helpers_and_regex_validation`, e-mail tests |
| ✅ Modules / file organisation | `models/ algorithms/ services/ utils/ core/ analytics/ ai/ pages/` | - |

## Brief - Layer 2: algorithms engine
| Requirement | Where | Proof |
|---|---|---|
| ✅ Stack (history/undo) | `algorithms/stack.py`, undo of every admin action | `test_undo_stack_covers_every_admin_action` |
| ✅ Queue (waiting list) | `algorithms/queue.py`, `services/waiting_service.py` | `test_queue_*`, `test_promotion_is_fifo...` |
| ✅ Sequential search (unordered data) | `Station.sequential_search_by_name`, `searching.sequential_search` | `test_sequential_search_on_unsorted_data` |
| ✅ Binary search only on correctly sorted data | `searching.binary_search` raises `UnsortedDataError`; overlap check on sorted busy lists | `test_binary_search_refuses_unsorted_data`, `test_overlap_check_uses_binary_search...` |
| ✅ Custom hash table | `algorithms/hash_table.py` (chaining); ID registries | `test_hash_table_*` |
| ✅ Manual sorting, incl. Merge Sort | `algorithms/sorting.py`; used for session history, booking lists, scheduler order | `test_merge_sort_*` |
| ✅ **No built-in sort in the required parts** | `grep "sorted(\|.sort(" services models algorithms utils core` → 0 data sorts. Built-in `sorted`/`sort_values` appear only in analytics, UI drop-downs and `scheduling_optimizer` (its `sort_fn` defaults to `sorted`, replaceable by `merge_sort`) | grep |
| ✅ Track comparisons / recursive calls / swaps | `merge_sort`, `merge_sort_with_stats`, `bubble_sort_comparisons`, `search_comparisons` | Algorithm Lab page |
| ✅ A problem-solving method with justification + alternatives | **Greedy** (`greedy_scheduler.py`); exact backtracking and local search as alternatives (`scheduling_optimizer.py`); counter-example where greedy loses | `test_counter_example_fcfs_is_not_optimal`, `docs/ALGORITHMS.md` |
| ⚠️ Each member explains their algorithms **in their own words** | draft in `docs/ALGORITHMS.md` | the defense |

## Brief - Layer 3: data, dashboard, AI
| Requirement | Where | Proof |
|---|---|---|
| ✅ Realistic dataset | `data/generate_data.py` (seeded, on the team catalog) | `test_generator.py` |
| ✅ DataFrame ops, missing/invalid data, filter/group/aggregate | `analytics/cleaning.py`, `metrics.py` | `test_cleaning.py`, `test_metrics.py` |
| ✅ ≥ 2 insights, generated from data | `analytics/insights.py` | `test_insights_are_generated_from_data...` |
| ✅ Time-based analysis | daily/weekly trend, heatmap, forecast | - |
| ✅ Runs in Streamlit; sidebar/tabs/columns; inputs, filters, tables, metrics | `app.py`, `pages/` | `test_app_smoke.py` (41), `test_app_flows.py` (6) |
| ✅ ≥ 3 visualizations | 15+ charts in `pages/6_Analytics.py` | - |
| ✅ Session state | `core/state.py` | - |
| ⚠️ AI-use log (what was generated / edited / validated) | `docs/AI_USE_LOG_Member4.md` has the AI-generated column; **each member must fill the edited/validated columns** | - |

## ChargeSpot plan - modules
| Plan item | Where | Proof |
|---|---|---|
| ✅ Add/edit/remove stations and chargers; AC/DC; status; search/filter (city, connector, power, status); availability summary | `pages/1_Stations.py`, `StationService` | `test_add_duplicate_charger...`, `test_search_and_filters` |
| ✅ "Cannot remove a charger with active bookings"; undo last admin change | `StationService` | `test_removing_a_booked_charger...` |
| ✅ Booking validation (date, duration, hours, compatibility) | `BookingService.validate_request` | `test_booking_validation`, `test_booking_must_finish_before_closing...` |
| ✅ Overlap rule `A.start < B.end and B.start < A.end`; back-to-back allowed | `interval_utils.py` | `test_overlap_rule_from_the_project_plan` |
| ✅ Greedy: earliest compatible free slot + alternatives | `greedy_scheduler.py` | `test_greedy_*`, `test_conflict_alternatives_waiting_list_and_automatic_promotion` |
| ✅ Cancellation and status | `BookingService`, `ChargeSpotApp.cancel_booking` | `test_cancel_frees_the_slot...` |
| ✅ Waiting list: FIFO, positions, automatic promotion | `waiting_service.py` | `test_waiting_positions_fifo...` |
| ✅ Sessions: start/complete, actual timestamps, planned vs actual, simulated energy, history | `session_service.py`, `pages/4_Sessions.py` | `test_full_session_lifecycle` |
| ✅ Block invalid actions (start a cancelled booking, occupied charger) | `SessionService.start_session` | `test_cannot_start_a_cancelled_booking`, `test_session_flow_and_state_rules` |
| ✅ Driver dashboard + Battery Monitor (estimates labelled as estimates; low-battery warning) | `pages/5_Driver_Dashboard.py` | `test_battery_*`, `test_battery_monitor_validates_and_estimates` |
| ✅ Admin analytics: utilization, demand by hour/day, cancellation rate, average waiting time, station comparison | `pages/6_Analytics.py` | `test_metrics.py` |
| ✅ CSV storage that persists after a restart | `core/app_context.py` + atomic writes | `test_booking_is_saved_and_survives_a_restart` |
| ✅ Role-based pages (bonus: real login) | `app.py`, `models/user.py` | `test_permission_is_enforced_on_restricted_pages` |

## Submission package
| Item | Status |
|---|---|
| Runnable Streamlit app, organized files, setup instructions | ✅ `README.md` |
| No hard-coded final results; works with changed data | ✅ insights generated; upload any bookings CSV in Analytics |
| Dataset file + cleaning/analysis evidence | ✅ `data/*.csv`, Data-quality tab (report equals the injected defects) |
| Algorithm comparison or explanation | ✅ Algorithm Lab + `docs/ALGORITHMS.md` |
| Testing notes for edge cases | ✅ `docs/EDGE_CASE_TESTING_NOTES.md` |
| ⚠️ **Screenshots of the working app** | **not produced**: take them from your own running app (admin, driver, operator) |
| ⚠️ Visual check of the UI by a human | the automated tests check structure and behaviour, **not how it looks** |
| No sensitive keys or private data | ✅ `users.json` and `secrets.toml` are git-ignored; demo accounts are fake |

## Bonus ideas already covered
Map view (approximate positions) · AI features (forecast, assistant, recommendation, scheduling optimizer, predictive maintenance; optional LLM wording) · exportable CSV reports · login/role-based pages · extra algorithm comparison with measured evidence. **Not done:** deployment link.
