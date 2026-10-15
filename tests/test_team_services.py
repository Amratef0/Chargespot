"""Tests for the team's services after integration. Every audit finding has a regression test here."""
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from models.charger import ACCharger, DCCharger, charger_from_dict
from models.exceptions import (AuthError, ChargerInUseError, DuplicateIDError, InvalidBatteryValueError,
                               InvalidSessionStateError, InvalidStatusError, NotFoundError,
                               SchedulingConflictError, ValidationError)
from models.station import Station
from services.auth_service import AuthService, hash_password, verify_password
from services.battery_service import BatteryService
from services.booking_service import BookingService
from services.scheduler import Scheduler
from services.session_service import SessionService
from services.station_service import StationService
from services.waiting_service import WaitingQueue

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 1, 8, 0)
DAY = datetime(2026, 10, 2)


def at(h, m=0, day=DAY):
    return day.replace(hour=h, minute=m)


@pytest.fixture()
def stations(tmp_path):
    shutil.copy(ROOT / "data" / "stations.json", tmp_path / "stations.json")
    bs = BookingService()
    svc = StationService(tmp_path / "stations.json", lambda cid: bs.has_active_bookings(cid, NOW))
    return svc, bs


@pytest.fixture()
def st9(stations):
    return stations[0].get_station(9)                     # Nasr City 1: 2 CCS2, 1 CHAdeMO, 2 Type 2


def dc(st, i=0):
    return st.usable_chargers("CCS2")[i]


# =================================================================== BookingService (Member 2)
def test_partial_overlap_is_detected(st9):
    """Audit #2/#10: the old is_overlap only compared identical start AND end."""
    bs, c = BookingService(), dc(st9)
    bs.create_booking("D101", st9, c, at(10), 60, now=NOW)
    for h, m, d in [(10, 30, 60), (9, 30, 60), (10, 15, 30), (9, 0, 240)]:
        with pytest.raises(SchedulingConflictError):
            bs.create_booking("D102", st9, c, at(h, m), d, now=NOW)


def test_back_to_back_is_allowed_and_other_days_are_independent(st9):
    bs, c = BookingService(), dc(st9)
    bs.create_booking("D101", st9, c, at(10), 60, now=NOW)
    bs.create_booking("D102", st9, c, at(11), 60, now=NOW)                      # starts when the first ends
    bs.create_booking("D103", st9, c, at(10, day=DAY + timedelta(days=1)), 60, now=NOW)   # audit #13: dates


def test_two_chargers_at_the_same_time_audit_9(st9):
    """Audit #9: bookings were per STATION, so a 5-charger station took one booking per hour."""
    bs = BookingService()
    bs.create_booking("D101", st9, dc(st9, 0), at(10), 60, now=NOW)
    bs.create_booking("D102", st9, dc(st9, 1), at(10), 60, now=NOW)
    assert len(bs.bookings) == 2


@pytest.mark.parametrize("start,dur,msg", [
    (at(10), 20, "multiple of 15"), (at(10), 15 * 17, "between"), (at(10, 7), 60, "15-minute"),
    (at(7, day=NOW.replace(hour=0)), 60, "past")])
def test_booking_validation(st9, start, dur, msg):
    with pytest.raises(ValidationError, match=msg):
        BookingService().create_booking("D101", st9, dc(st9), start, dur, now=NOW)


def test_booking_must_finish_before_closing_and_not_on_broken_charger(stations):
    svc, _ = stations
    st = svc.get_station(9)
    st.close_hour = 12
    with pytest.raises(ValidationError, match="open"):
        BookingService().create_booking("D101", st, dc(st), at(11, 30), 60, now=NOW)
    st.close_hour = 24
    broken = dict(dc(st), charger_status="Maintenance")
    with pytest.raises(ValidationError, match="maintenance"):
        BookingService().create_booking("D101", st, broken, at(10), 60, now=NOW)


def test_cancel_frees_the_slot_and_ownership_is_checked(st9):
    bs, c = BookingService(), dc(st9)
    b = bs.create_booking("D101", st9, c, at(10), 60, now=NOW)
    with pytest.raises(ValidationError, match="own"):
        bs.cancel_booking(b.booking_id, "D999")
    bs.cancel_booking(b.booking_id, "D101")
    assert b.status == "Cancelled" and not bs.check_booking_overlap(c["charger_id"], at(10), at(11))
    with pytest.raises(ValidationError, match="Confirmed"):
        bs.cancel_booking(b.booking_id)
    bs.create_booking("D102", st9, c, at(10), 60, now=NOW)            # slot is bookable again


def test_unknown_booking_and_status_helpers(st9):
    bs = BookingService()
    with pytest.raises(NotFoundError):
        bs.get_booking(999)
    with pytest.raises(NotFoundError):
        bs.get_booking("abc")
    b = bs.create_booking("D101", st9, dc(st9), at(10), 60, now=NOW)
    assert bs.mark_no_show(b.booking_id).status == "No-Show"
    assert bs.check_booking_overlap(b.charger_id, at(10), at(11))        # a no-show still blocks the slot
    with pytest.raises(ValidationError):
        bs.mark_completed(b.booking_id)


def test_overlap_check_uses_binary_search_on_sorted_busy_list(st9):
    bs, c = BookingService(), dc(st9)
    for h in (14, 8, 11, 20, 5):                                          # inserted out of order
        bs.create_booking("D101", st9, c, at(h), 60, now=NOW)
    busy = bs.busy_intervals(c["charger_id"], "2026-10-02")
    assert [s for s, _, _ in busy] == sorted(s for s, _, _ in busy)       # invariant binary search relies on
    before = bs.search_comparisons
    bs.check_booking_overlap(c["charger_id"], at(16), at(17))
    assert 0 < bs.search_comparisons - before <= 4


def test_has_active_bookings_and_grid_and_sorting(st9):
    bs, c = BookingService(), dc(st9)
    bs.create_booking("D101", st9, c, at(10), 60, now=NOW)
    assert bs.has_active_bookings(c["charger_id"], NOW) and not bs.has_active_bookings(c["charger_id"], at(12))
    grid = bs.availability_grid(st9, "2026-10-02")
    assert len(grid) == len(st9.chargers) and all(len(r) == 24 for r in grid)
    row = [r for r, ch in zip(grid, st9.chargers) if ch["charger_id"] == c["charger_id"]][0]
    assert row[10] == "Booked" and row[9] == "Free" and row[11] == "Free"
    ordered, comps = bs.sorted_by_start(reverse=True)
    assert ordered[0].booking_id == 1 and comps == 0


# =================================================================== WaitingQueue (Member 2)
def test_waiting_positions_fifo_and_duplicates():
    wq = WaitingQueue()
    r1 = wq.add_to_waiting_list("D101", 9, "CCS2", at(10), 60, NOW)
    r2 = wq.add_to_waiting_list("D102", 9, "CCS2", at(10), 60, NOW)
    assert (r1["position"], r2["position"]) == (1, 2) and wq.position(r2["request_id"]) == 2
    with pytest.raises(ValidationError, match="already waiting"):
        wq.add_to_waiting_list("D101", 9, "CCS2", at(10), 60, NOW)
    wq.remove_request(r1["request_id"])
    assert wq.position(r2["request_id"]) == 1
    with pytest.raises(NotFoundError):
        wq.position(r1["request_id"])
    assert wq.requests_for_driver("D102")[0][0] == 1


def test_promotion_is_fifo_and_skips_requests_that_still_do_not_fit(st9):
    bs, wq, c = BookingService(), WaitingQueue(), dc(st9)
    wq_ids = [wq.add_to_waiting_list(d, 9, "CCS2", at(10), 60, NOW) for d in ("D101", "D102", "D103")]
    for ch in st9.usable_chargers("CCS2"):                                # fill both CCS2 chargers at 10:00
        bs.create_booking("X", st9, ch, at(10), 60, now=NOW)
    assert wq.promote_eligible(st9, bs, NOW) == []                        # nothing free yet
    b = bs.bookings[0]
    bs.cancel_booking(b.booking_id)
    promoted = wq.promote_eligible(st9, bs, NOW)
    assert [r["driver_id"] for r, _ in promoted] == ["D101"]              # first in line gets it
    assert promoted[0][1].queued == 1 and [r["driver_id"] for r in wq.queue] == ["D102", "D103"]


def test_promotion_handles_any_freed_slot_not_only_identical_times(st9):
    """Audit #14: the old code only matched a cancelled booking with the same start AND end."""
    bs, wq = BookingService(), WaitingQueue()
    big = bs.create_booking("X", st9, dc(st9, 0), at(10), 120, now=NOW)
    bs.create_booking("X", st9, dc(st9, 1), at(10), 120, now=NOW)
    wq.add_to_waiting_list("D101", 9, "CCS2", at(10, 30), 45, NOW)         # different start and length
    bs.cancel_booking(big.booking_id)
    assert len(wq.promote_eligible(st9, bs, NOW)) == 1


def test_waiting_matching_and_expiry():
    wq = WaitingQueue()
    wq.add_to_waiting_list("D101", 9, "CCS2", at(10), 60, NOW)
    wq.add_to_waiting_list("D102", 9, "CCS2", at(12), 60, NOW)
    assert [r["driver_id"] for r in wq.get_matching_requests(9, at(10, 30), at(11, 30))] == ["D101"]
    assert [r["driver_id"] for r in wq.purge_expired(at(11))] == ["D101"] and len(wq.queue) == 1


# =================================================================== Scheduler (Member 2)
def test_scheduler_orders_available_first_then_nearest(stations):
    svc, bs = stations
    sch = Scheduler(json.loads((ROOT / "data" / "distances.json").read_text()))
    opts = sch.find_suitable_stations("Nasr City", svc.stations, "CCS2", at(10), 60, bs)
    assert {o["station"].governorate for o in opts} == {"Cairo"}           # cross-city: no route data -> skipped
    d = [o["distance"] for o in opts]
    assert d == sorted(d) and Scheduler.find_best_station(opts) is opts[0]
    for ch in opts[0]["station"].usable_chargers("CCS2"):                  # block the nearest station
        bs.create_booking("X", opts[0]["station"], ch, at(10), 60, now=NOW)
    opts2 = sch.find_suitable_stations("Nasr City", svc.stations, "CCS2", at(10), 60, bs)
    blocked = [o for o in opts2 if o["station"] is opts[0]["station"]][0]
    assert not blocked["is_available"] and blocked["alternatives"] and opts2[-1] is blocked
    assert Scheduler.find_best_station(opts2)["station"] is not opts[0]["station"]


def test_scheduler_static_helpers_and_no_option(stations):
    svc, bs = stations
    assert "Smouha" in Scheduler.get_areas(svc.stations) and Scheduler({}).get_distance("x", "y") is None
    assert Scheduler.find_best_station([]) is None


# =================================================================== Stations (Member 1)
def test_charger_validation_and_polymorphism():
    with pytest.raises(ValidationError, match="Invalid charger ID"):
        ACCharger("X-1", 22)
    with pytest.raises(ValidationError, match="power"):
        DCCharger("DC-300", -5)
    with pytest.raises(ValidationError, match="cannot use connector"):
        ACCharger("AC-300", 22, "CCS2")
    with pytest.raises(InvalidStatusError):
        ACCharger("AC-300", 22, "Type 2", "Broken")
    with pytest.raises(ValidationError, match="start with"):
        DCCharger("AC-300", 50)
    a, d = charger_from_dict(ACCharger("AC-300", 22).casting_charge_to_dict()), charger_from_dict(DCCharger("DC-300", 50).casting_charge_to_dict())
    assert type(a).__name__ == "ACCharger" and type(d).__name__ == "DCCharger" and "[DCCharger]" in d.get_info()


def test_station_validation():
    with pytest.raises(ValidationError):
        Station("abc", "Name here", "Cairo", "Addr")
    with pytest.raises(ValidationError):
        Station(1, "ab", "Cairo", "Addr")
    with pytest.raises(ValidationError):
        Station(1, "Good name", "", "Addr")


def test_add_duplicate_charger_and_remove_rules(stations):
    svc, bs = stations
    st = svc.get_station(2)
    with pytest.raises(DuplicateIDError):
        svc.add_charger(2, ACCharger("AC-102", 22))                        # exists in the network already
    c = st.usable_chargers("CCS2")[0]
    st.update_charger_status(c["charger_id"], "Occupied")
    with pytest.raises(ChargerInUseError, match="Occupied"):
        svc.remove_charger_with_undo(st, c["charger_id"])
    st.update_charger_status(c["charger_id"], "Available")
    bs.create_booking("D101", st, c, at(10), 60, now=NOW)
    with pytest.raises(ChargerInUseError, match="active bookings"):        # audit #15
        svc.remove_charger_with_undo(st, c["charger_id"])
    with pytest.raises(NotFoundError):
        svc.remove_charger_with_undo(st, "AC-999")
    with pytest.raises(InvalidStatusError):
        st.update_charger_status(c["charger_id"], "Broken")


def test_undo_stack_covers_every_admin_action(stations):
    svc, _ = stations
    st = svc.get_station(2)
    n0, c0 = len(svc.stations), len(st.chargers)
    svc.add_charger(2, ACCharger("AC-150", 22))
    svc.update_charger_status(st, "AC-150", "Maintenance")
    svc.remove_charger_with_undo(st, "AC-150")
    svc.edit_station(2, price_per_kwh=9.0)
    svc.add_station(77, "Test station", "Cairo", "Somewhere")
    svc.remove_station(77)
    assert len(svc.admin_stack.stack) == 6
    assert "restored" in svc.undo_last_admin_action() and len(svc.stations) == n0 + 1
    assert "removed again" in svc.undo_last_admin_action() and len(svc.stations) == n0
    assert "edit" in svc.undo_last_admin_action() and st.price_per_kwh != 9.0
    assert "restored" in svc.undo_last_admin_action() and st.find_charger("AC-150")["charger_status"] == "Maintenance"
    assert "back to Available" in svc.undo_last_admin_action()
    assert "removed from" in svc.undo_last_admin_action() and len(st.chargers) == c0
    assert svc.undo_last_admin_action() is None                            # nothing left, no crash


def test_station_removal_blocked_when_a_charger_is_booked(stations):
    svc, bs = stations
    st = svc.get_station(2)
    bs.create_booking("D101", st, st.usable_chargers()[0], at(10), 60, now=NOW)
    with pytest.raises(ChargerInUseError):
        svc.remove_station(2)


def test_registry_lookup_and_rebuild_after_changes(stations):
    svc, _ = stations
    s, c = svc.get_charger("DC-201")
    assert s.station_id == 1 and svc.get_station("9").name.endswith("Nasr City 1")
    for bad in ("zz", 999):
        with pytest.raises(NotFoundError):
            svc.get_station(bad)
    with pytest.raises(NotFoundError):
        svc.get_charger("AC-999")
    svc.add_charger(2, ACCharger("AC-160", 11))
    assert svc.get_charger("AC-160")[0].station_id == 2


def test_json_persistence_and_independent_of_current_folder(stations, tmp_path, monkeypatch):
    """Audit #14: load_from_json used the current folder, so it crashed when started elsewhere."""
    svc, _ = stations
    svc.add_charger(2, ACCharger("AC-170", 11))
    monkeypatch.chdir(tmp_path.parent)                                      # somewhere else
    svc2 = StationService(tmp_path / "stations.json")
    assert svc2.get_charger("AC-170")[0].station_id == 2


def test_search_and_filters(stations):
    svc, _ = stations
    assert [s.name for s in svc.search("nasr")] == ["ChargeSpot Nasr City 1", "ChargeSpot Nasr City 2"]
    assert all(s.governorate == "Alexandria" for s in svc.search(governorate="alexandria"))
    assert svc.search(connector="CHAdeMO") and svc.search(min_kw=150) and svc.search(name="zzz") == []
    assert svc.search(status="Maintenance") and {s.station_id for s in svc.search(status="Maintenance")} == {5, 9}


# =================================================================== Sessions + Battery (Member 3)
def test_session_flow_and_state_rules():
    ss = SessionService()
    s = ss.create_session(1, 10, "DC-201", "D101", at(10), 60)
    with pytest.raises(ValueError, match="already exists"):
        ss.create_session(1, 11, "DC-201", "D102")
    with pytest.raises(InvalidSessionStateError, match="Cancelled"):
        ss.start_session(1, booking_status="Cancelled")
    with pytest.raises(InvalidSessionStateError, match="Occupied"):
        ss.start_session(1, charger_status="Occupied")
    with pytest.raises(InvalidSessionStateError, match="Active"):
        ss.complete_session(1, 10.0)
    ss.start_session(1, now=at(10, 5))
    assert s.status == "Active" and s.start_time == at(10, 5)
    ss.create_session(2, 11, "DC-201", "D102")
    with pytest.raises(InvalidSessionStateError, match="already occupied"):
        ss.start_session(2)
    for bad, exc in ((0, ValueError), (-3, ValueError), ("x", ValueError), (True, ValueError)):
        with pytest.raises(exc):
            ss.complete_session(1, bad, now=at(11))
    with pytest.raises(InvalidSessionStateError, match="before"):
        ss.complete_session(1, 10.0, now=at(10))
    ss.complete_session(1, 12.345, now=at(11, 5))
    assert s.duration_minutes == 60.0 and s.energy_delivered_kwh == 12.35 and s.status == "Completed"
    with pytest.raises(InvalidSessionStateError):
        ss.start_session(1)


def test_session_history_uses_merge_sort_and_filters():
    ss = SessionService()
    for i, (h, kwh) in enumerate([(12, 5), (9, 20), (15, 10)], start=1):
        ss.create_session(i, i, f"DC-20{i}", "D101", at(h), 60)
        ss.start_session(i, now=at(h)); ss.complete_session(i, kwh, now=at(h, 30) + timedelta(minutes=i * 10))
    ordered, comps = ss.sort_session_history("start_time", False)
    assert [s.session_id for s in ordered] == [2, 1, 3] and comps > 0
    assert [s.session_id for s in ss.sort_session_history("energy", True)[0]] == [2, 3, 1]
    assert len(ss.filter_sessions(user_id="D101")) == 3 and ss.filter_sessions(charger_id="DC-202")[0].session_id == 2
    with pytest.raises(ValueError):
        ss.sort_session_history("colour")


def test_battery_estimates_hand_calculation():
    est = BatteryService(60, 6.0).calculate_estimates(20, 80, 50)
    assert est["energy_needed_kwh"] == 36.0                    # 60 kWh x 60 %
    assert est["estimated_time_hours"] == 0.8                  # 36 / (50 x 0.9)
    assert est["estimated_range_km"] == 72.0                   # 12 kWh x 6 km/kWh
    assert BatteryService(60, 6).calculate_estimates(10, 20, 50)["low_battery_warning"] is True
    assert BatteryService(60, 6).calculate_estimates(20, 21, 50)["low_battery_warning"] is False


@pytest.mark.parametrize("args", [(-1, 50, 50), (101, 120, 50), (50, 40, 50), (50, 50, 50), (20, 101, 50),
                                  (20, 80, 0), (20, 80, -5), ("a", 80, 50), (True, 80, 50)])
def test_battery_validation(args):
    with pytest.raises(InvalidBatteryValueError):
        BatteryService(60, 6).calculate_estimates(*args)
    with pytest.raises(InvalidBatteryValueError):
        BatteryService(0, 6)


# =================================================================== Auth
@pytest.mark.parametrize("email", ["a.b@gmail.com", "sara+ev@mail.co.uk", "x_y@my-mail.org"])
def test_valid_emails_are_accepted_audit_5(email):
    from utils.validators import is_email
    assert is_email(email)


@pytest.mark.parametrize("email", ["plain", "a@b", "@x.com", "a b@x.com", "a@x.c"])
def test_invalid_emails_rejected(email):
    from utils.validators import is_email
    assert not is_email(email)


def good(**kw):
    d = dict(name="Sara Hassan", email="sara@mail.com", phone="01234567890", age="27", gender="female",
             governorate="giza", national_id="29001010100999", password="Password1", confirm_password="Password1",
             vehicle_model="BYD Atto 3")
    d.update(kw)
    return d


def test_register_login_and_password_is_never_plain_text(tmp_path):
    a = AuthService(tmp_path / "u.json", vehicle_models=["BYD Atto 3"])
    u = a.register(**good())
    assert u.role == "user" and u.driver_id == "D401" and u.can("book") and not u.can("manage_stations")
    assert "Password1" not in (tmp_path / "u.json").read_text()                     # audit #7 / checklist: no secrets
    assert a.login("SARA@mail.com", "Password1").email == "sara@mail.com"
    with pytest.raises(AuthError, match="Incorrect"):
        a.login("sara@mail.com", "wrong")
    with pytest.raises(AuthError, match="Incorrect"):
        a.login("nobody@mail.com", "Password1")                                      # same message: no user enumeration
    assert AuthService(tmp_path / "u.json").login("sara@mail.com", "Password1")      # survives a restart


def test_register_collects_all_errors_and_rejects_duplicates(tmp_path):
    a = AuthService(tmp_path / "u.json", vehicle_models=["BYD Atto 3"])
    with pytest.raises(ValidationError) as e:
        a.register(**good(name="ab", email="bad", phone="abcd", age="16", gender="x", national_id="123",
                          password="short", confirm_password="short"))
    for part in ("Name", "e-mail", "Phone", "Age", "Gender", "National ID", "Password"):
        assert part in str(e.value)
    a.register(**good())
    with pytest.raises(DuplicateIDError, match="e-mail"):                            # audit #8
        a.register(**good(national_id="29001010100888"))
    with pytest.raises(DuplicateIDError, match="national ID"):
        a.register(**good(email="other@mail.com"))
    with pytest.raises(ValidationError, match="vehicle"):
        a.register(**good(email="v@mail.com", national_id="29001010100777", vehicle_model="Tractor"))
    with pytest.raises(ValidationError, match="match"):
        a.register(**good(email="m@mail.com", national_id="29001010100666", confirm_password="Different1"))


def test_ages_over_55_can_register_audit_5(tmp_path):
    a = AuthService(tmp_path / "u.json")
    assert a.register(**good(age="70")).email == "sara@mail.com"


def test_driver_ids_are_unique_and_persisted(tmp_path):
    a = AuthService(tmp_path / "u.json", first_new_driver_number=500)
    ids = [a.register(**good(email=f"u{i}@mail.com", national_id=f"3000101010{i:04d}")).driver_id for i in range(3)]
    assert ids == ["D500", "D501", "D502"]
    assert AuthService(tmp_path / "u.json", first_new_driver_number=500).find_by_email("u1@mail.com")["driver_id"] == "D501"


def test_legacy_plain_text_users_are_upgraded(tmp_path):
    (tmp_path / "u.json").write_text(json.dumps([{"name": "Old User", "email": "old@x.com", "password": "secret123",
                                                  "role": "user", "national_id": "12345678912345"}]))
    a = AuthService(tmp_path / "u.json")
    assert "secret123" not in (tmp_path / "u.json").read_text() and a.login("old@x.com", "secret123").driver_id


def test_roles_and_permissions_are_polymorphic(tmp_path):
    a = AuthService(tmp_path / "u.json")
    admin, op, drv = (a.login(e, p) for e, p in (("admin@chargespot.com", "Admin1234"),
                                                 ("operator@chargespot.com", "Operator1234"), ("ahmed@gmail.com", "123456789")))
    assert admin.can("analytics") and admin.can("manage_stations") and not admin.can("book")
    assert op.can("manage_sessions") and not op.can("analytics") and not op.can("manage_stations")
    assert drv.can("book") and not drv.can("manage_sessions") and [admin.label, op.label, drv.label] == ["Administrator", "Station Operator", "Driver"]


def test_password_hash_helpers():
    h = hash_password("abc12345")
    assert verify_password("abc12345", h) and not verify_password("abc12346", h) and not verify_password("x", "broken")
    assert hash_password("abc12345") != h                                               # random salt
