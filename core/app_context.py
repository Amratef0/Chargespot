"""ChargeSpotApp: ONE object that wires every team module together (Member 4 - integration).

    stations  (Member 1)  StationService   - stations, chargers, hash registry, undo Stack
    bookings  (Member 2)  BookingService   - per-charger bookings, overlap rule, binary search
    waiting   (Member 2)  WaitingQueue     - FIFO Queue + promotion
    scheduler (Member 2)  Scheduler        - nearest-available-station greedy
    sessions  (Member 3)  SessionService   - start/complete, Merge Sort history
    battery   (Member 3)  BatteryService   - range / time estimates
    auth                  AuthService      - login/register, e-mail verification, password reset
    login_sessions        LoginSessionStore- server-side login sessions (survive a page refresh)

Security boundary: every state-changing method below takes the acting `user` and calls `authorize(...)` first,
so the rules hold for ANY caller, not only for the Streamlit pages. Pages must call these methods and must not
call the mutators of `app.stations` / `app.sessions` directly (tests/test_authorization.py enforces that).

Persistence: every change is written to CSV/JSON immediately (atomic), so data survives a restart.
The Streamlit pages only call this class (they contain no business logic).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from algorithms.greedy_scheduler import pick_charger_greedy, suggest_alternatives
from core import clock
from core.data_store import DATA_DIR, atomic_write_csv, ensure_dataset
from core.schema import BOOKING_COLS, DATETIME_FORMAT, SESSION_COLS, STATION_COLS, CHARGER_COLS
from models.booking import Booking
from models.charging_session import ChargingSession
from models.exceptions import NotFoundError, ValidationError
from services.auth_service import AuthService
from services.authz import authorize
from services.login_session_service import LoginSessionStore
from services.mailer import build_mailer
from services.token_service import TokenStore
from services.battery_service import BatteryService
from services.booking_service import BookingService
from services.scheduler import Scheduler
from services.session_service import SessionService
from services.station_service import StationService
from services.waiting_service import WaitingQueue

FMT = DATETIME_FORMAT


class ChargeSpotApp:
    def __init__(self, data_dir=DATA_DIR, now_fn=clock.now, mailer=None):
        self.dir = Path(data_dir)
        self.now = now_fn
        self.mailer_override = mailer              # tests pass a MemoryMailer; the app builds one from the environment
        self._load_all()

    # ============================================================== loading
    def _load_all(self):
        ensure_dataset(self.dir)
        self.version = 0
        self._frames = (-1, None)
        self.vehicles = pd.read_csv(self.dir / "vehicles.csv")
        self.history_drivers = pd.read_csv(self.dir / "drivers.csv")
        self.bookings = BookingService()
        self.stations = StationService(self.dir / "stations.json",
                                       has_active_bookings=lambda cid: self.bookings.has_active_bookings(cid, self.now()))
        self.waiting = WaitingQueue()
        self.sessions = SessionService()
        distances = json.loads((self.dir / "distances.json").read_text(encoding="utf-8"))
        self.scheduler = Scheduler(distances)
        nums = [int(d[1:]) for d in self.history_drivers["driver_id"]]
        self.login_sessions = LoginSessionStore(self.dir / "auth_sessions.json", now_fn=self.now)
        self.mailer = self.mailer_override or build_mailer(self.dir)
        self.auth = AuthService(self.dir / "users.json", first_new_driver_number=max(nums) + 1,
                                vehicle_models=list(self.vehicles["vehicle_model"]), mailer=self.mailer,
                                tokens=TokenStore(self.dir / "auth_tokens.json", now_fn=self.now),
                                sessions=self.login_sessions, base_url=os.environ.get("CHARGESPOT_BASE_URL"))
        self._sync_user_vehicles()
        self._load_bookings()
        self._load_sessions()
        self._load_waiting()
        self.waiting.purge_expired(self.now())

    def reload(self):
        self._load_all()

    def _sync_user_vehicles(self):
        """Demo users that also exist in the simulated history must own the same car."""
        hist = self.history_drivers.set_index("driver_id")["vehicle_model"].to_dict()
        changed = False
        for u in self.auth.users:
            if u.get("driver_id") in hist and u.get("vehicle_model") != hist[u["driver_id"]]:
                u["vehicle_model"], changed = hist[u["driver_id"]], True
        if changed:
            self.auth._save()

    def _load_bookings(self):
        p = self.dir / "bookings.csv"
        if not p.exists():
            return
        raw = pd.read_csv(p, dtype=str, keep_default_na=False)
        names = {s.station_id: (s.name, s.area) for s in self.stations.stations}
        cols = {c: pd.to_datetime(raw[c], format=FMT).dt.to_pydatetime() for c in ("created_at", "start_time", "end_time")}
        for i, r in enumerate(raw.itertuples(index=False)):
            sid = int(r.station_id)
            name, area = names.get(sid, ("(removed station)", ""))
            self.bookings.load_booking(Booking(
                int(r.booking_id), r.driver_id, sid, name, area, cols["start_time"][i], cols["end_time"][i],
                r.status, r.charger_id or None, r.connector, cols["created_at"][i], int(r.queued), int(r.wait_min)))

    def _load_sessions(self):
        p = self.dir / "sessions.csv"
        if not p.exists():
            return
        raw = pd.read_csv(p, dtype=str, keep_default_na=False)
        cols = {c: pd.to_datetime(raw[c], format=FMT).dt.to_pydatetime() for c in ("planned_start", "actual_start", "actual_end")}
        for i, r in enumerate(raw.itertuples(index=False)):
            s = ChargingSession(int(r.session_id), int(r.booking_id), r.charger_id, r.driver_id,
                                cols["planned_start"][i], float(r.duration_min))
            s.start_time, s.end_time = cols["actual_start"][i], cols["actual_end"][i]
            s.duration_minutes, s.energy_delivered_kwh, s.status = float(r.duration_min), float(r.energy_kwh), "Completed"
            self.sessions.load_session(s)

    def _load_waiting(self):
        p = self.dir / "waiting.csv"
        if not p.exists():
            return
        raw = pd.read_csv(p, dtype=str, keep_default_na=False)
        for r in raw.itertuples(index=False):
            self.waiting.load_request({
                "request_id": int(r.request_id), "driver_id": r.driver_id, "station_id": int(r.station_id),
                "connector": r.connector, "start_time": datetime.strptime(r.start_time, FMT),
                "duration_min": int(r.duration_min), "created_at": datetime.strptime(r.created_at, FMT)})

    # ============================================================== saving (called after every change)
    def touch(self):
        self.version += 1

    def _save_bookings(self):
        atomic_write_csv(self.bookings_frame(), self.dir / "bookings.csv")

    def _save_sessions(self):
        atomic_write_csv(self.sessions_frame(), self.dir / "sessions.csv")

    def _save_waiting(self):
        rows = [{"request_id": r["request_id"], "driver_id": r["driver_id"], "station_id": r["station_id"],
                 "connector": r["connector"], "start_time": r["start_time"].strftime(FMT),
                 "duration_min": r["duration_min"], "created_at": r["created_at"].strftime(FMT)}
                for r in self.waiting.queue]
        cols = ["request_id", "driver_id", "station_id", "connector", "start_time", "duration_min", "created_at"]
        atomic_write_csv(pd.DataFrame(rows, columns=cols), self.dir / "waiting.csv")

    # ============================================================== booking flow (Member 2's user flow)
    def find_station_options(self, driver_area, connector, start, duration_min):
        return self.scheduler.find_suitable_stations(driver_area, self.stations.stations, connector, start,
                                                     duration_min, self.bookings)

    def book_at_station(self, user, station, connector, start, duration_min):
        """Greedy: earliest compatible free charger at the requested time. Returns a result dict."""
        self._need_driver(user)
        self.bookings.validate_request(station, self._probe_charger(station, connector), start, duration_min, self.now())
        day, s = start.strftime("%Y-%m-%d"), start.hour * 60 + start.minute
        usable, close = station.usable_chargers(connector), station.close_hour * 60
        busy_of = lambda cid: self.bookings.busy_intervals(cid, day)
        opt = pick_charger_greedy(usable, busy_of, s, duration_min, close, max_shift=0)
        if opt is None:
            return {"status": "unavailable", "alternatives": suggest_alternatives(usable, busy_of, s, duration_min, close)}
        b = self.bookings.create_booking(user.driver_id, station, station.find_charger(opt.charger_id), start,
                                         duration_min, now=self.now())
        self._save_bookings(); self.touch()
        return {"status": "confirmed", "booking": b}

    def book_alternative(self, user, station, option, day, duration_min):
        """Book a slot suggested by the greedy scheduler (option = SlotOption)."""
        self._need_driver(user)
        start = datetime.strptime(day, "%Y-%m-%d") + timedelta(minutes=option.start_min)
        b = self.bookings.create_booking(user.driver_id, station, station.find_charger(option.charger_id), start,
                                         duration_min, now=self.now())
        self._save_bookings(); self.touch()
        return b

    def join_waiting_list(self, user, station, connector, start, duration_min):
        self._need_driver(user)
        self.bookings.validate_request(station, self._probe_charger(station, connector), start, duration_min, self.now())
        req = self.waiting.add_to_waiting_list(user.driver_id, station.station_id, connector, start, duration_min, self.now())
        self._save_waiting(); self.touch()
        return req

    def cancel_booking(self, user, booking_id):
        """Cancel, free the slot, then promote waiting drivers (FIFO). Returns (booking, promoted)."""
        authorize(user)                                    # must be logged in; owner / admin rule follows
        if user.can("cancel_any"):
            owner = None                                   # administrators may cancel any booking
        elif user.driver_id:
            owner = user.driver_id                         # drivers: only their own
        else:
            raise ValidationError("Only the booking's owner or an administrator can cancel a booking.")
        b = self.bookings.cancel_booking(booking_id, owner)
        promoted = self.waiting.promote_eligible(self.stations.get_station(b.station_id), self.bookings, self.now())
        self._save_bookings(); self._save_waiting(); self.touch()
        return b, promoted

    def cancel_waiting(self, user, request_id):
        authorize(user)
        r = self.waiting.get_request(request_id)
        if r is None:
            raise NotFoundError(f"Waiting request {request_id} not found.")
        if r["driver_id"] != user.driver_id and not user.can("manage_waiting"):
            raise ValidationError("You can only cancel your own waiting requests.")
        self.waiting.remove_request(request_id)
        self._save_waiting(); self.touch()
        return r

    def _probe_charger(self, station, connector):
        usable = station.usable_chargers(connector)
        if not usable:
            raise ValidationError(f"{station.name} has no working {connector} charger.")
        return usable[0]

    @staticmethod
    def _need_driver(user):
        authorize(user, "book")
        if not user.driver_id:
            raise ValidationError("Only driver accounts can book.")

    # ============================================================== station administration (guarded)
    def update_charger_status(self, user, station, charger_id, new_status):
        authorize(user, "update_charger_status")
        self.stations.update_charger_status(station, charger_id, new_status)
        self.touch()
        return True

    def add_charger(self, user, station_id, charger_object):
        authorize(user, "manage_stations")
        res = self.stations.add_charger(station_id, charger_object)
        self.touch()
        return res

    def remove_charger(self, user, station, charger_id):
        authorize(user, "manage_stations")
        res = self.stations.remove_charger_with_undo(station, charger_id)
        self.touch()
        return res

    def add_station(self, user, *args, **kwargs):
        authorize(user, "manage_stations")
        res = self.stations.add_station(*args, **kwargs)
        self.touch()
        return res

    def edit_station(self, user, station_id, **fields):
        authorize(user, "manage_stations")
        res = self.stations.edit_station(station_id, **fields)
        self.touch()
        return res

    def remove_station(self, user, station_id):
        authorize(user, "manage_stations")
        res = self.stations.remove_station(station_id)
        self.touch()
        return res

    def undo_last_admin_action(self, user):
        authorize(user, "undo")
        msg = self.stations.undo_last_admin_action()
        self.touch()
        return msg

    def reload_from_disk(self, user):
        authorize(user, "analytics")
        self.reload()

    def resolve_driver_id(self, user, requested=None):
        """Whose driver data may `user` look at? Own data always; anybody's only with 'view_any_driver'."""
        authorize(user, "view_own", "view_any_driver")
        own = user.driver_id
        if requested is None or requested == own:
            if own is None:
                raise ValidationError("Choose a driver to look at.")
            return own
        authorize(user, "view_any_driver")
        return requested

    # ============================================================== sessions (Member 3 + glue)
    def vehicle_of_driver(self, driver_id):
        user = next((u for u in self.auth.users if u.get("driver_id") == driver_id), None)
        model = user.get("vehicle_model") if user else None
        if model is None:
            row = self.history_drivers[self.history_drivers["driver_id"] == driver_id]
            model = row["vehicle_model"].iloc[0] if len(row) else None
        v = self.vehicles[self.vehicles["vehicle_model"] == model]
        return None if v.empty else v.iloc[0].to_dict()

    def suggest_energy(self, booking, duration_min):
        """Simulated energy (kWh) for a session: charger power x efficiency x time, capped by the battery."""
        station, c = self.stations.get_charger(booking.charger_id)
        kw = min(c["charger_power_kw"], 11) if c["type"] == "AC" else c["charger_power_kw"] * 0.7
        veh = self.vehicle_of_driver(booking.driver_id)
        cap = 0.8 * veh["battery_kwh"] if veh else 60.0
        return round(max(1.0, min(kw * 0.9 * duration_min / 60, cap)), 2)

    def start_session(self, user, booking_id, now=None):
        authorize(user, "manage_sessions")
        now = now or self.now()
        b = self.bookings.get_booking(booking_id)
        station, charger = self.stations.get_charger(b.charger_id)
        sid = self.sessions.next_session_id()
        self.sessions.create_session(sid, b.booking_id, b.charger_id, b.driver_id, b.start_time, b.duration_min)
        try:
            session = self.sessions.start_session(sid, b.status, charger["charger_status"], now)
        except Exception:
            self.sessions.sessions.pop()                          # do not keep a half-created session
            raise
        self.stations.update_charger_status(station, b.charger_id, "Occupied", record=False)
        self.touch()
        return session

    def complete_session(self, user, session_id, energy_kwh=None, now=None):
        authorize(user, "manage_sessions")
        now = now or self.now()
        session = self.sessions.get_session(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id} not found.")
        b = self.bookings.get_booking(session.booking_id)
        if energy_kwh is None:
            minutes = max(1.0, (now - session.start_time).total_seconds() / 60) if session.start_time else b.duration_min
            energy_kwh = self.suggest_energy(b, minutes)
        self.sessions.complete_session(session_id, energy_kwh, now)
        self.bookings.mark_completed(b.booking_id)
        station, _ = self.stations.get_charger(b.charger_id)
        self.stations.update_charger_status(station, b.charger_id, "Available", record=False)
        promoted = self.waiting.promote_eligible(station, self.bookings, now)      # "charger freed" event
        self._save_bookings(); self._save_sessions(); self._save_waiting(); self.touch()
        return session, promoted

    def mark_no_show(self, user, booking_id):
        authorize(user, "manage_sessions")
        b = self.bookings.mark_no_show(booking_id)
        self._save_bookings(); self.touch()
        return b

    def battery_for(self, driver_id):
        v = self.vehicle_of_driver(driver_id)
        if v is None:
            raise ValidationError("No vehicle is registered for this driver.")
        return BatteryService(float(v["battery_kwh"]), float(v["km_per_kwh"]))

    # ============================================================== DataFrames for Pandas / charts
    def stations_frame(self):
        rows = [(str(s.station_id), s.name, s.governorate, s.area, s.address, s.lat, s.lon,
                 s.open_hour, s.close_hour, s.price_per_kwh) for s in self.stations.stations]
        return pd.DataFrame(rows, columns=STATION_COLS)

    def chargers_frame(self):
        rows = [(c["charger_id"], str(s.station_id), c.get("type"), c.get("connector_type"),
                 c["charger_power_kw"], c["charger_status"]) for s in self.stations.stations for c in s.chargers]
        return pd.DataFrame(rows, columns=CHARGER_COLS)

    def bookings_frame(self):
        rows = [(str(b.booking_id), b.driver_id, str(b.station_id), b.charger_id, b.connector, b.created_at,
                 b.start_time, b.end_time, b.duration_min, b.status, b.queued, b.wait_min)
                for b in self.bookings.bookings]
        df = pd.DataFrame(rows, columns=BOOKING_COLS)
        for c in ("created_at", "start_time", "end_time"):
            df[c] = pd.to_datetime(df[c])
        return df

    def sessions_frame(self):
        price = {s.station_id: s.price_per_kwh for s in self.stations.stations}
        rows = []
        for s in self.sessions.sessions:
            if s.status != "Completed":
                continue
            try:
                st, _ = self.stations.get_charger(s.charger_id)
                sid = st.station_id
            except NotFoundError:
                sid = self.bookings.get_booking(s.booking_id).station_id
            delay = max(0, int(round((s.start_time - s.planned_start).total_seconds() / 60))) if s.planned_start else 0
            rows.append((str(s.session_id), str(s.booking_id), s.user_id, str(sid), s.charger_id, s.planned_start,
                        s.start_time, s.end_time, int(round(s.duration_minutes)), delay, s.energy_delivered_kwh,
                         round(s.energy_delivered_kwh * price.get(sid, 6.0), 2)))
        df = pd.DataFrame(rows, columns=SESSION_COLS)
        for c in ("planned_start", "actual_start", "actual_end"):
            df[c] = pd.to_datetime(df[c])
        return df

    def drivers_frame(self):
        veh = self.vehicles.set_index("vehicle_model")["connector"].to_dict()
        reg = pd.DataFrame([(u["driver_id"], u["name"], u.get("vehicle_model"), veh.get(u.get("vehicle_model")))
                            for u in self.auth.users if u.get("driver_id")],
                        columns=["driver_id", "name", "vehicle_model", "connector"])
        both = pd.concat([reg, self.history_drivers], ignore_index=True)
        return both.drop_duplicates("driver_id", keep="first").reset_index(drop=True)

    def frames(self):
        """All tables as DataFrames (IDs are strings). Cached until the next change."""
        if self._frames[0] != self.version:
            health_p = self.dir / "charger_health.csv"
            health = pd.read_csv(health_p, parse_dates=["date"]) if health_p.exists() else pd.DataFrame(
                columns=["charger_id", "date", "power_ratio", "error_count", "temp_c"])
            self._frames = (self.version, {
                "stations": self.stations_frame(), "chargers": self.chargers_frame(), "vehicles": self.vehicles,
                "drivers": self.drivers_frame(), "bookings": self.bookings_frame(),
                "sessions": self.sessions_frame(), "charger_health": health})
        return self._frames[1]