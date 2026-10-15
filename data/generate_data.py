"""Seeded synthetic dataset generator for ChargeSpot (Member 4).

All data is SIMULATED. Run from the project root:

    python -m data.generate_data                # regenerate everything
    python -m data.generate_data --seed 7 --days 90

It writes (into data/):
    stations.csv, chargers.csv, vehicles.csv, drivers.csv,
    bookings.csv          (clean)
    sessions.csv          (one row per completed booking)
    bookings_messy.csv    (sample of bookings with deliberate defects)
    messy_defects_manifest.json  (how many defects of each kind were injected)
    charger_health.csv    (simulated daily sensor/fault readings per charger)
    charger_health_truth.csv  (which chargers were simulated as degrading - evaluation only)

Realism built in (so the analytics have real patterns to find):
    * two weekday demand peaks (morning ~8-9h, evening ~18-19h)
    * Friday/Saturday weekend: flatter midday + evening shape, ~20% more demand
    * some stations are far more popular than others
    * slow growth in demand over time
    * a booking can be shifted (<=30 min), queued, cancelled or a no-show
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from core.schema import (BOOKING_COLS, CHARGER_COLS, DATETIME_FORMAT,
                         DRIVER_COLS, SESSION_COLS, STATION_COLS,
                         VEHICLE_COLS, WEEKEND_DAYS)

DATA_DIR = Path(__file__).resolve().parent

# How popular each station is (relative demand). Station 1 has only 2 chargers -> low weight.
POPULARITY = {1: 0.5, 2: 1.0, 3: 0.9, 4: 0.7, 5: 1.5, 6: 0.6, 7: 0.5, 8: 0.5,
              9: 1.6, 10: 1.2, 11: 1.0, 12: 1.3, 13: 1.5, 14: 1.0, 15: 0.8, 16: 1.1}

VEHICLES = [
    # model, battery kWh, km per kWh (assumed), connector
    ("MG ZS EV", 51.0, 5.5, "CCS2"),
    ("Hyundai Kona Electric", 64.0, 6.2, "CCS2"),
    ("BYD Atto 3", 60.0, 5.8, "CCS2"),
    ("Tesla Model 3", 60.0, 7.0, "CCS2"),
    ("Kia Niro EV", 64.8, 6.3, "CCS2"),
    ("BMW i3", 42.0, 6.8, "CCS2"),
    ("Nissan Leaf", 40.0, 6.0, "CHAdeMO"),
    ("Renault Zoe", 52.0, 6.5, "Type 2"),
    ("Renault Twingo EV", 22.0, 6.8, "Type 2"),
]
VEHICLE_WEIGHTS = [0.17, 0.14, 0.15, 0.10, 0.08, 0.06, 0.12, 0.10, 0.08]

FIRST = ["Sara", "Omar", "Mona", "Ahmed", "Nour", "Youssef", "Hana", "Karim",
         "Laila", "Tarek", "Dina", "Mostafa", "Salma", "Hassan", "Mariam",
         "Ali", "Farah", "Khaled", "Rana", "Ziad"]
LAST = ["Hassan", "Ibrahim", "Mahmoud", "Salem", "Adel", "Fathy", "Nabil",
        "Samir", "Gamal", "Mansour", "Fouad", "Zaki"]

DURATIONS_DC = [30, 45, 60]
DURATIONS_AC = [60, 90, 120, 180]


# ---------------------------------------------------------------- builders (from the team's catalog)
def load_catalog(path=None):
    """The team's stations.json (16 stations with chargers) as a list of dicts."""
    return json.loads(Path(path or DATA_DIR / "stations.json").read_text(encoding="utf-8"))


def build_stations(catalog) -> pd.DataFrame:
    rows = [(str(s["station_id"]), s["name"], s["governorate"], s.get("area", s["governorate"]), s["address"],
             s.get("lat"), s.get("lon"), s.get("open_hour", 0), s.get("close_hour", 24),
             s.get("price_per_kwh", 6.0)) for s in catalog]
    return pd.DataFrame(rows, columns=STATION_COLS)


def build_chargers(catalog) -> pd.DataFrame:
    rows = [(c["charger_id"], str(s["station_id"]), c["type"], c["connector_type"], c["charger_power_kw"],
             c["charger_status"]) for s in catalog for c in s["chargers"]]
    return pd.DataFrame(rows, columns=CHARGER_COLS)


def build_vehicles() -> pd.DataFrame:
    return pd.DataFrame(VEHICLES, columns=VEHICLE_COLS)


def build_drivers(rng: np.random.Generator, n: int, vehicles: pd.DataFrame) -> pd.DataFrame:
    idx = rng.choice(len(vehicles), size=n, p=VEHICLE_WEIGHTS)
    rows = []
    for i in range(n):
        v = vehicles.iloc[idx[i]]
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        rows.append((f"D{101 + i}", name, v["vehicle_model"], v["connector"]))
    return pd.DataFrame(rows, columns=DRIVER_COLS)


# ---------------------------------------------------------------- demand model
def _gauss(h: np.ndarray, mu: float, sd: float) -> np.ndarray:
    return np.exp(-0.5 * ((h - mu) / sd) ** 2)


def hour_weights(is_weekend: bool, open_h: int, close_h: int) -> np.ndarray:
    """Probability of a request starting in each hour (sums to 1 over open hours)."""
    h = np.arange(24, dtype=float)
    if is_weekend:
        w = 0.15 + 0.9 * _gauss(h, 12.5, 3.0) + 1.0 * _gauss(h, 19.0, 2.0)
    else:
        w = 0.15 + 1.0 * _gauss(h, 8.5, 1.3) + 1.2 * _gauss(h, 18.5, 1.8) + 0.4 * _gauss(h, 13, 2.5)
    mask = (h >= open_h) & (h < close_h)
    w = np.where(mask, w, 0.0)
    return w / w.sum()


class _Occupancy:
    """Per charger-per day list of busy (start, end) minute intervals."""

    def __init__(self):
        self._busy: dict[tuple[str, object], list[tuple[int, int]]] = {}

    def is_free(self, ch: str, day, s: int, e: int) -> bool:
        # two intervals overlap if A.start < B.end and B.start < A.end
        return all(not (s < be and bs < e) for bs, be in self._busy.get((ch, day), []))

    def add(self, ch: str, day, s: int, e: int) -> None:
        self._busy.setdefault((ch, day), []).append((s, e))


def simulate(seed: int = 42, n_days: int = 120, end_date: str = "2026-10-13",
             n_drivers: int = 300, base_requests: float = 13.0, catalog=None):
    """Simulate bookings + sessions on the team's station catalog. Returns a dict of DataFrames."""
    rng = np.random.default_rng(seed)
    catalog = catalog or load_catalog()
    stations = build_stations(catalog)
    chargers = build_chargers(catalog)
    vehicles = build_vehicles()
    drivers = build_drivers(rng, n_drivers, vehicles)
    veh_by_model = vehicles.set_index("vehicle_model")
    drv_by_id = drivers.set_index("driver_id")
    price = stations.set_index("station_id")["price_per_kwh"].to_dict()
    pop = {str(s["station_id"]): POPULARITY.get(s["station_id"], 1.0) for s in catalog}
    hours = {str(s["station_id"]): (s.get("open_hour", 0), s.get("close_hour", 24)) for s in catalog}

    usable = chargers[chargers["status"] != "Maintenance"]
    ch_by_station = {sid: g.sort_values("charger_id") for sid, g in usable.groupby("station_id")}

    occ = _Occupancy()
    end = pd.Timestamp(end_date).normalize()
    start_day = end - pd.Timedelta(days=n_days - 1)
    records = []

    for di in range(n_days):
        day = start_day + pd.Timedelta(days=di)
        weekend = day.weekday() in WEEKEND_DAYS
        growth = 1.0 + 0.003 * di                       # slow demand growth
        dow_mult = 1.2 if weekend else 1.0
        for sid in ch_by_station:
            open_h, close_h = hours[sid]
            close_min = close_h * 60
            lam_day = base_requests * pop[sid] * growth * dow_mult
            w = hour_weights(weekend, open_h, close_h)
            counts = rng.poisson(lam_day * w)
            reqs = []
            for hour in np.nonzero(counts)[0]:
                for _ in range(counts[hour]):
                    minute = int(rng.choice([0, 15, 30, 45]))
                    start = int(hour) * 60 + minute
                    drv = drivers.iloc[int(rng.integers(len(drivers)))]
                    lead = float(rng.exponential(6 * 60)) + 30   # minutes booked in advance
                    created = day + pd.Timedelta(minutes=start - lead)
                    reqs.append((created, start, drv))
            reqs.sort(key=lambda r: r[0])                # first come, first served

            for created, start, drv in reqs:
                conn = drv["connector"]
                cands = ch_by_station[sid]
                cands = cands[cands["connector"] == conn]
                if cands.empty:
                    continue                             # station cannot serve this car
                dur = int(rng.choice(DURATIONS_AC if conn == "Type 2" else DURATIONS_DC))
                cids = cands["charger_id"].tolist()

                def place(s0: int):
                    for off in (0, 15, 30):              # greedy: earliest free slot
                        s, e = s0 + off, s0 + off + dur
                        if e > close_min:
                            break
                        for c in cids:
                            if occ.is_free(c, day, s, e):
                                return c, s
                    return None

                got = place(start)
                queued, wait = 0, 0
                if got is None:                          # no slot -> waiting list
                    queued = 1
                    wait = int(rng.integers(10, 61))
                    if rng.random() < 0.6:
                        shifted = start + int(np.ceil(wait / 15) * 15)
                        got = place(shifted)
                    if got is None:
                        records.append(dict(driver_id=drv["driver_id"], station_id=sid, charger_id=np.nan,
                                            connector=conn, created_at=created, start_min=start, day=day,
                                            duration_min=dur, status="Cancelled", queued=1,
                                            wait_min=int(rng.integers(10, 46))))
                        continue
                ch, s = got
                roll = rng.random()
                if roll < 0.10:
                    status = "Cancelled"                 # cancelled booking frees the slot
                elif roll < 0.14:
                    status = "No-Show"
                    occ.add(ch, day, s, s + dur)
                else:
                    status = "Completed"
                    occ.add(ch, day, s, s + dur)
                records.append(dict(driver_id=drv["driver_id"], station_id=sid, charger_id=ch,
                                    connector=conn, created_at=created, start_min=s, day=day,
                                    duration_min=dur, status=status, queued=queued,
                                    wait_min=wait))

    df = pd.DataFrame(records)
    df["start_time"] = df["day"] + pd.to_timedelta(df["start_min"], unit="m")
    df["end_time"] = df["start_time"] + pd.to_timedelta(df["duration_min"], unit="m")
    df = df.sort_values(["created_at", "station_id"], kind="mergesort").reset_index(drop=True)
    df["booking_id"] = [str(i + 1) for i in range(len(df))]
    bookings = df[BOOKING_COLS].copy()

    # ---- sessions (actual times differ from planned times)
    ch_info = chargers.set_index("charger_id")
    srows = []
    done = bookings[bookings["status"] == "Completed"]
    for i, b in enumerate(done.itertuples(index=False), start=1):
        delay = int(min(rng.exponential(6), 40)) if rng.random() < 0.7 else int(min(rng.exponential(14), 40))
        a_start = b.start_time + pd.Timedelta(minutes=delay)
        dur = max(10, int(round(b.duration_min * rng.uniform(0.7, 1.05))))
        a_end = a_start + pd.Timedelta(minutes=dur)
        ch = ch_info.loc[b.charger_id]
        veh = veh_by_model.loc[drv_by_id.loc[b.driver_id, "vehicle_model"]]
        kw = min(ch["power_kw"], 11) if ch["charger_type"] == "AC" else ch["power_kw"] * 0.7
        energy = round(max(1.0, min(kw * 0.9 * dur / 60, 0.8 * veh["battery_kwh"])), 2)
        srows.append((str(i), b.booking_id, b.driver_id, b.station_id, b.charger_id,
                      b.start_time, a_start, a_end, dur, delay, energy,
                      round(energy * price[b.station_id], 2)))
    sessions = pd.DataFrame(srows, columns=SESSION_COLS)
    return dict(stations=stations, chargers=chargers, vehicles=vehicles,
                drivers=drivers, bookings=bookings, sessions=sessions)


# ---------------------------------------------------------------- messy file
DEFECT_KINDS = [
    "duplicate_rows", "mixed_date_formats", "missing_start_time",
    "invalid_duration", "connector_variants", "status_variants",
    "invalid_booking_id", "missing_charger_id", "end_before_start",
    "missing_wait_min", "unknown_station",
]


def make_messy(bookings: pd.DataFrame, seed: int = 42, n_rows: int = 2000,
               defect_rate: float = 0.015):
    """Take a sample of clean bookings and inject deliberate defects.

    Each defect type is applied to a DISJOINT set of rows, so the cleaning
    report can be checked against the manifest exactly.
    Returns (messy_dataframe_of_strings, manifest_dict).
    """
    rng = np.random.default_rng(seed + 1)
    sample = bookings.sample(n=min(n_rows, len(bookings)), random_state=seed).copy()
    # only rows that are valid targets for every defect (have charger, etc.)
    sample = sample[sample["status"].isin(["Completed", "No-Show"])].reset_index(drop=True)
    sample["start_time"] = sample["start_time"].dt.strftime(DATETIME_FORMAT)
    sample["end_time"] = sample["end_time"].dt.strftime(DATETIME_FORMAT)
    sample["created_at"] = sample["created_at"].dt.strftime(DATETIME_FORMAT)
    df = sample.astype(object)

    k = max(5, int(len(df) * defect_rate))
    perm = rng.permutation(len(df))
    blocks = {kind: perm[i * k:(i + 1) * k] for i, kind in enumerate(DEFECT_KINDS)}
    manifest = {kind: int(len(ix)) for kind, ix in blocks.items()}
    dup_src = blocks["duplicate_rows"]            # rows that will be copied (left untouched)

    alt_fmts = ["%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M", "%b %d %Y %H:%M"]
    for j, i in enumerate(blocks["mixed_date_formats"]):
        fmt = alt_fmts[j % len(alt_fmts)]
        for col in ("start_time", "end_time", "created_at"):
            df.at[i, col] = pd.Timestamp(df.at[i, col]).strftime(fmt)

    df.loc[blocks["missing_start_time"], "start_time"] = np.nan

    for j, i in enumerate(blocks["invalid_duration"]):
        df.at[i, "duration_min"] = [-30, 0, 999, -60][j % 4]

    conn_var = {"CCS2": [" ccs2", "CCS2 ", "Ccs2", "ccs"], "CHAdeMO": ["chademo", "CHADEMO", " CHAdeMO"],
                "Type 2": ["type2", "TYPE 2", "type 2 ", "Type-2"]}
    for j, i in enumerate(blocks["connector_variants"]):
        opts = conn_var[df.at[i, "connector"]]
        df.at[i, "connector"] = opts[j % len(opts)]

    stat_var = {"Completed": ["completed", "COMPLETED", " Completed"], "No-Show": ["no show", "NO-SHOW", "noshow"]}
    for j, i in enumerate(blocks["status_variants"]):
        opts = stat_var[df.at[i, "status"]]
        df.at[i, "status"] = opts[j % len(opts)]

    for j, i in enumerate(blocks["invalid_booking_id"]):
        df.at[i, "booking_id"] = ["BKXYZ", "12a45", "BK-77", "bk"][j % 4]

    df.loc[blocks["missing_charger_id"], "charger_id"] = np.nan

    for i in blocks["end_before_start"]:
        s = pd.Timestamp(df.at[i, "start_time"])
        df.at[i, "end_time"] = (s - pd.Timedelta(minutes=int(df.at[i, "duration_min"]))).strftime(DATETIME_FORMAT)

    df.loc[blocks["missing_wait_min"], "wait_min"] = np.nan
    df.loc[blocks["unknown_station"], "station_id"] = "999"

    dups = df.loc[dup_src].copy()
    messy = pd.concat([df, dups], ignore_index=True)
    messy = messy.sample(frac=1.0, random_state=seed).reset_index(drop=True)   # shuffle
    return messy, manifest


# ---------------------------------------------------------------- charger health
# Ground-truth behaviour classes used ONLY to evaluate the maintenance model.
HEALTH_CLASSES = ("healthy", "stable_noisy", "early_degradation", "degrading")


def simulate_charger_health(chargers: pd.DataFrame, n_days: int = 120,
                            end_date: str = "2026-10-13", seed: int = 42):
    """Daily health readings per active charger (SIMULATED sensor/fault data).

    Columns: charger_id, date, power_ratio (delivered / rated power),
             error_count (faults logged that day), temp_c (daily mean).
    Classes: most chargers are healthy; a few have a chronically high but STABLE
    error rate (must not be flagged); a few slowly degrade (should be flagged).
    Uses its own random stream so bookings/sessions are unaffected.
    Returns (health_df, truth_df[charger_id, true_class, at_risk]).
    """
    rng = np.random.default_rng(seed + 2)
    active = chargers[chargers["status"] != "Maintenance"]["charger_id"].tolist()
    order = list(rng.permutation(active))
    classes = {c: "healthy" for c in active}
    for c in order[:2]:
        classes[c] = "stable_noisy"
    for c in order[2:4]:
        classes[c] = "early_degradation"
    for c in order[4:7]:
        classes[c] = "degrading"

    end = pd.Timestamp(end_date).normalize()
    dates = pd.date_range(end - pd.Timedelta(days=n_days - 1), end, freq="D")
    degr_days = 40                                   # degradation starts 40 days before the end
    rows = []
    for cid in active:
        cls = classes[cid]
        for i, d in enumerate(dates):
            ramp = max(0.0, (i - (n_days - degr_days)) / degr_days)      # 0 -> 1 over last 40 days
            ratio = rng.normal(0.97, 0.02)
            lam, temp = 0.15, rng.normal(38, 2.5)
            if cls == "stable_noisy":
                lam = 0.8
            elif cls == "early_degradation":
                ratio -= 0.08 * ramp
                lam += 0.5 * ramp
                temp += 6 * ramp
            elif cls == "degrading":
                ratio -= 0.19 * ramp
                lam += 1.85 * ramp
                temp += 18 * ramp
            rows.append((cid, d, round(float(np.clip(ratio, 0.3, 1.0)), 4),
                         int(rng.poisson(lam)), round(float(temp), 1)))
    health = pd.DataFrame(rows, columns=["charger_id", "date", "power_ratio", "error_count", "temp_c"])
    truth = pd.DataFrame({"charger_id": active, "true_class": [classes[c] for c in active]})
    truth["at_risk"] = truth["true_class"].isin(["early_degradation", "degrading"])
    return health, truth


# ---------------------------------------------------------------- orchestration
def generate_all(out_dir: Path | str = DATA_DIR, seed: int = 42, n_days: int = 120,
                 end_date: str = "2026-10-13", n_drivers: int = 300, catalog_path=None,
                 base_requests: float = 13.0) -> dict:
    """Write the simulated HISTORY (bookings, sessions, drivers, vehicles, health, messy file).
    stations.json / distances.json / users.json are the team's own files and are never overwritten."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog(catalog_path or out / "stations.json")
    d = simulate(seed=seed, n_days=n_days, end_date=end_date, n_drivers=n_drivers,
                 base_requests=base_requests, catalog=catalog)
    for name in ("vehicles", "drivers"):
        d[name].to_csv(out / f"{name}.csv", index=False)

    b = d["bookings"].copy()
    for col in ("created_at", "start_time", "end_time"):
        b[col] = b[col].dt.strftime(DATETIME_FORMAT)
    b.to_csv(out / "bookings.csv", index=False)

    s = d["sessions"].copy()
    for col in ("planned_start", "actual_start", "actual_end"):
        s[col] = s[col].dt.strftime(DATETIME_FORMAT)
    s.to_csv(out / "sessions.csv", index=False)

    health, truth = simulate_charger_health(d["chargers"], n_days, end_date, seed)
    h = health.copy()
    h["date"] = h["date"].dt.strftime("%Y-%m-%d")
    h.to_csv(out / "charger_health.csv", index=False)
    truth.to_csv(out / "charger_health_truth.csv", index=False)
    d["charger_health"] = health

    messy, manifest = make_messy(d["bookings"], seed=seed)
    messy.to_csv(out / "bookings_messy.csv", index=False)
    (out / "messy_defects_manifest.json").write_text(json.dumps(
        {"seed": seed, "rows_in_file": int(len(messy)), "injected": manifest}, indent=2))
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate the simulated ChargeSpot dataset")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--end-date", default="2026-10-13")
    ap.add_argument("--drivers", type=int, default=300)
    a = ap.parse_args()
    res = generate_all(seed=a.seed, n_days=a.days, end_date=a.end_date, n_drivers=a.drivers)
    print({k: len(v) for k, v in res.items()})
