# Edge-case testing notes
Run `python -m pytest -v` (278 tests, ~1 min). Every row is covered by an automated test.

| Area | Edge cases | Expected | Tests (file) |
|---|---|---|---|
| Overlap | partial, contained, identical, back-to-back, other day | conflict / conflict / conflict / **allowed** / allowed | `test_team_algorithms` (overlap), `test_team_services` (booking) |
| Booking validation | duration 20 or 255 min, start 10:07, past time, outside opening hours, charger in Maintenance, no compatible connector | clear `ValidationError`, nothing saved | `test_team_services`, `test_integration_flow` |
| Two chargers, same hour | both fit; a third driver gets alternatives | greedy answer + alternatives | `test_integration_flow` |
| Waiting list | duplicates, positions after a removal, FIFO promotion, request that still does not fit, expired request, any freed slot | as specified | `test_team_services`, `test_integration_flow` |
| Cancellation | someone else's booking, operator, twice, unknown ID, admin | refused / refused / refused / `NotFoundError` / allowed | `test_integration_flow` |
| Sessions | start a cancelled / no-show booking, occupied charger, second active session on one charger, complete before start, energy 0 / negative / text / bool | `InvalidSessionStateError` / `ValueError`, no half-created session | `test_team_services`, `test_integration_flow` |
| Battery | 0/100 limits, target ≤ current, power ≤ 0, text, bool | `InvalidBatteryValueError`; hand-checked numbers | `test_team_services` |
| Stations | duplicate charger ID, remove Occupied or booked charger, bad IDs/names, unknown ID, JSON path from another folder | friendly errors; saved and reloaded | `test_team_services` |
| Undo | every admin action, empty stack, ID re-used before undo | message / `None` / `DuplicateIDError` | `test_team_services` |
| Hash table | collisions, missing key, update, remove, resize, deterministic hash, size 0 | nothing lost; `None` for missing | `test_team_algorithms` |
| Searches | unsorted input to binary search, empty list, single item, absent target, key function, logarithmic bound | `UnsortedDataError`; `(-1, n)` | `test_team_algorithms` |
| Merge sort | equals builtin on random data, stability, empty/single, reverse, input unchanged, comparison bound | as specified | `test_team_algorithms` |
| Auth | valid e-mails (`a.b@x.com`, `.co.uk`), invalid ones, letters in phone, age 17 / 70, duplicate e-mail and national ID, wrong password vs unknown user, plain-text upgrade | all problems at once; same login error for both cases | `test_team_services` |
| Persistence | restart after booking / waiting request / session | state identical | `test_integration_flow` |
| Cleaning | 11 injected defect types; clean data; run twice; missing column; empty file; garbage text | exact detection; idempotent; `CleaningError` | `test_cleaning` |
| Metrics / insights | hand-calculated utilization (10 %), clip at 100 %, empty data, days without bookings | as specified | `test_metrics` |
| AI | forecast too short / leakage; recommendation inputs, closed or unreachable stations; optimizer validity vs exact solver; maintenance hand calculation, noisy vs degrading; LLM numbers changed, no key, HTTP errors | friendly errors; fallbacks | `test_forecast_and_assistant`, `test_recommendation`, `test_scheduling_optimizer`, `test_predictive_maintenance`, `test_llm_wording` |
| Streamlit | every page × allowed role; restricted pages; wrong password; incomplete registration; filters with no result; unsorted input in the search demo; battery target below current; driver books / cancels / waits; operator starts and completes; admin adds a charger then undoes | no exception, friendly message, data saved | `test_app_smoke`, `test_app_flows` |
