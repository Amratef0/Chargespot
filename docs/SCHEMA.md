# Data schema (the team's own formats)
Code: `core/schema.py` and `utils/validators.py`. **Timestamps:** `YYYY-MM-DD HH:MM` · **Weekend:** Fri/Sat ·
**Duration:** 15-240 min in steps of 15 · **All stations open 24 h.**

| ID | Format | Example |
|---|---|---|
| Station | number | `9` |
| Charger | `AC-` or `DC-` + 3 digits | `AC-101`, `DC-201` |
| Booking / Session | number (increasing) | `1042` |
| Driver | `D` + digits | `D101` |

Allowed values: booking status `Confirmed, Completed, Cancelled, No-Show` (a waiting request lives in `waiting.csv`
until it is promoted) · connector `Type 2` (AC) / `CCS2`, `CHAdeMO` (DC) · charger status `Available, Occupied, Maintenance`
· session status `Planned, Active, Completed` · roles `user` (Driver), `operator`, `admin`.

| File | Content |
|---|---|
| `stations.json` | the team's catalog: station + `chargers[]` (live: changed by the app) |
| `distances.json` | driver area → station address → km (Member 2's matrix) |
| `users.json` | accounts (git-ignored; created on first run; passwords hashed) |
| `bookings.csv` | booking_id, driver_id, station_id, charger_id, connector, created_at, start_time, end_time, duration_min, status, queued, wait_min |
| `sessions.csv` | session_id, booking_id, driver_id, station_id, charger_id, planned_start, actual_start, actual_end, duration_min, delay_min, energy_kwh, cost_egp |
| `waiting.csv` | request_id, driver_id, station_id, connector, start_time, duration_min, created_at (git-ignored) |
| `drivers.csv`, `vehicles.csv` | simulated history drivers; vehicle model, battery kWh, km/kWh (assumed), connector |
| `charger_health.csv` | simulated daily readings for the maintenance model |
| `bookings_messy.csv` + manifest | cleaning exercise with 11 injected defect types |

`bookings.csv` / `sessions.csv` hold 120 days of **simulated history** and every booking made in the app.
Rules: `end_time = start_time + duration_min` · planned time is in bookings, actual time in sessions ·
a booking never leaves a charger without a free slot: `A.start < B.end and B.start < A.end` is forbidden on one charger.
