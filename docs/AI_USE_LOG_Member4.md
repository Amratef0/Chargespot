# AI-use log — Member 4

**Tool:** Claude (Anthropic) · **Used for:** generating the first version of all Member 4 modules, tests and docs.

> ⚠️ Fill the two right-hand columns YOURSELF before submitting. The brief requires you to explain what was
> generated, what you edited and what you validated manually. Do not submit this table with the
> "TODO" cells unchanged, and do not claim a validation you did not do.

| # | File / feature | AI-generated | What I edited / changed myself | Validated manually (how) |
|---|---|---|---|---|
| 1 | `core/schema.py`, `utils/validators.py` | formats and regex | TODO | TODO |
| 2 | `data/generate_data.py`, `data/build_catalog.py` | seeded generator on the team catalog; chargers/prices/coordinates for stations 2-16 | TODO | TODO e.g. opened the CSVs, checked peaks |
| 3 | `analytics/cleaning.py`, `metrics.py`, `insights.py`, `charts.py` | cleaning pipeline, metrics, insights, charts | TODO | TODO e.g. recomputed utilization in Excel |
| 4 | `ai/forecast.py`, `analytics_assistant.py`, `recommendation.py`, `predictive_maintenance.py`, `llm_wording.py`, `analytics/scheduling_optimizer.py` | all | TODO | TODO e.g. traced the 270 vs 90 minute counter-example |
| 5 | `algorithms/hash_table.py`, `queue.py`, `searching.py`, `interval_utils.py`, `greedy_scheduler.py` | rebuilt/new during integration (owners: M1, M2) | TODO (owners) | TODO (owners: trace each on paper) |
| 6 | `services/booking_service.py`, `waiting_service.py`, `scheduler.py`, `station_service.py`, `auth_service.py` | redesign/extension during integration | TODO (owners) | TODO (owners) |
| 7 | `core/app_context.py`, `core/state.py`, `app.py`, `pages/*` | integration + UI | TODO | TODO |
| 8 | `docs/*` (audit, changes, checklist, algorithms) | drafts | TODO (rewrite your algorithm parts in your own words) | TODO |
| 9 | `tests/*` | 278 tests | TODO | Re-run `python -m pytest` on your own machine |

## What was verified automatically (not a substitute for understanding)
* `python -m pytest` — unit tests + Streamlit page smoke tests.
* The app boots with `streamlit run app.py`.
* The cleaning report equals the known injected defects exactly.

## Honest notes
* **LLM wording:** the failure paths are tested (including a real HTTPS call that was rejected with 401 for an
  invalid key). The SUCCESS path with a real key and the real model was NOT tested by the AI. Test it yourself
  before showing it, or leave the checkbox off in the demo.
* **Maintenance model:** the medium-risk threshold (20) was chosen from a threshold sweep over simulated fleets
  (seeds 1-30 for tuning, 31-60 as hold-out gave identical numbers). The data is generated to match the model's
  assumptions, so the perfect scores on the project dataset do not prove real-world accuracy.
* **Scheduling optimizer:** offline analysis (assumes all requests known in advance); gains are an upper bound.
* **Recommendation:** an early version used min-max scaling and ranked a 9 km station above a 2.7 km one because a
  186 km outlier distorted the scale; it was changed to absolute scales and covered by a test.
* The forecast model barely beats a historical-average baseline (≈2–3 % lower MAE) because the data is synthetic
  and mostly random noise. This is reported as-is in the app.
* Screenshots were NOT produced by the AI; take them from your own running app.
* **Integration:** the team's three loose files differ from the zip; the zip was treated as the repository and both versions were merged (see `TEAM_AUDIT.md`). Chargers, prices and coordinates of stations 2-16 were **invented** (the team data only had chargers for station 1).
* **Never looked at on a screen:** the UI was tested with Streamlit's `AppTest` (structure and behaviour). Nobody has checked layout or colours: open every page before the demo and take your screenshots.
* **Two real bugs were found by the integrator's own tests** (operator could cancel anyone's booking; confirmation messages vanished after `st.rerun()`), both fixed and covered.

