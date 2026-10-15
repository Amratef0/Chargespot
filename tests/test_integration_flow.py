"""End-to-end flows through ChargeSpotApp (the object the Streamlit pages use), with files on disk."""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from analytics import metrics as M
from analytics.cleaning import clean_bookings
from core.app_context import ChargeSpotApp
from models.charger import ACCharger
from models.exceptions import (ChargerInUseError, InvalidSessionStateError, NotFoundError, PermissionDeniedError,
                               ValidationError)
from tests.conftest import NOW

START = datetime(2026, 3, 3, 10, 0)


def new_driver(ctx, i):
    return ctx.auth.register(f"Driver Number{i}", f"d{i}@mail.com", "01234567890", "30", "male", "cairo",
                             f"3100101010{i:04d}", "Password1", "Password1", "BYD Atto 3")


@pytest.fixture()
def users(ctx):
    return ctx.auth.login("ahmed@gmail.com", "123456789"), new_driver(ctx, 1), new_driver(ctx, 2), \
        ctx.auth.login("admin@chargespot.com", "Admin1234"), ctx.auth.login("operator@chargespot.com", "Operator1234")


@pytest.fixture()
def st9(ctx):
    return ctx.stations.get_station(9)                     # 2 CCS2 chargers


def test_data_loaded_from_history_files(ctx, data_dir):
    n = len(pd.read_csv(data_dir / "bookings.csv"))
    assert len(ctx.bookings.bookings) == n and len(ctx.sessions.sessions) == len(pd.read_csv(data_dir / "sessions.csv"))
    assert len(ctx.stations.stations) == 16 and ctx.stations.get_charger("DC-201")


def test_booking_is_saved_and_survives_a_restart(ctx, users, st9, data_dir):
    ahmed = users[0]
    r = ctx.book_at_station(ahmed, st9, "CCS2", START, 60)
    assert r["status"] == "confirmed"
    b = r["booking"]
    assert str(b.booking_id) in set(pd.read_csv(data_dir / "bookings.csv", dtype=str)["booking_id"])
    again = ChargeSpotApp(data_dir, now_fn=lambda: NOW)
    b2 = again.bookings.get_booking(b.booking_id)
    assert (b2.driver_id, b2.charger_id, b2.start_time, b2.status) == ("D101", b.charger_id, START, "Confirmed")
    with pytest.raises(Exception):                                                  # the slot is still blocked after restart
        again.bookings.create_booking("D999", st9, again.stations.get_station(9).find_charger(b.charger_id), START, 60, now=NOW)


def test_conflict_alternatives_waiting_list_and_automatic_promotion(ctx, users, st9, data_dir):
    ahmed, d1, d2, *_ = users
    b1 = ctx.book_at_station(ahmed, st9, "CCS2", START, 60)["booking"]
    b2 = ctx.book_at_station(d1, st9, "CCS2", START, 60)["booking"]
    assert b1.charger_id != b2.charger_id                                           # two chargers, same time: both fit
    third = ctx.book_at_station(d2, st9, "CCS2", START, 60)
    assert third["status"] == "unavailable" and third["alternatives"][0].start_min == 11 * 60
    req = ctx.join_waiting_list(d2, st9, "CCS2", START, 60)
    assert req["position"] == 1 and len(ctx.waiting.queue) == 1
    assert len(pd.read_csv(data_dir / "waiting.csv")) == 1                         # saved
    assert ChargeSpotApp(data_dir, now_fn=lambda: NOW).waiting.position(req["request_id"]) == 1
    cancelled, promoted = ctx.cancel_booking(ahmed, b1.booking_id)
    assert cancelled.status == "Cancelled" and len(promoted) == 1
    pr, nb = promoted[0]
    assert pr["driver_id"] == d2.driver_id and nb.queued == 1 and nb.status == "Confirmed" and nb.charger_id == b1.charger_id
    assert len(ctx.waiting.queue) == 0 and len(pd.read_csv(data_dir / "waiting.csv")) == 0


def test_alternative_slot_can_be_booked(ctx, users, st9):
    ahmed, d1, d2, *_ = users
    for u in (ahmed, d1):
        ctx.book_at_station(u, st9, "CCS2", START, 60)
    alt = ctx.book_at_station(d2, st9, "CCS2", START, 60)["alternatives"][0]
    b = ctx.book_alternative(d2, st9, alt, "2026-03-03", 60)
    assert b.start_time == START + timedelta(hours=1)


def test_booking_rules_are_enforced_by_the_app(ctx, users, st9):
    ahmed, *_, admin, op = users
    with pytest.raises(ValidationError, match="past"):
        ctx.book_at_station(ahmed, st9, "CCS2", datetime(2026, 3, 1, 10), 60)
    with pytest.raises(ValidationError, match="multiple"):
        ctx.book_at_station(ahmed, st9, "CCS2", START, 50)
    with pytest.raises(ValidationError, match="no working"):
        ctx.book_at_station(ahmed, ctx.stations.get_station(6), "CHAdeMO", START, 60)    # station 6 has no CHAdeMO
    with pytest.raises(PermissionDeniedError):                       # only drivers hold the "book" permission
        ctx.book_at_station(admin, st9, "CCS2", START, 60)


def test_only_the_owner_or_admin_can_cancel(ctx, users, st9):
    ahmed, d1, _, admin, op = users
    b = ctx.book_at_station(ahmed, st9, "CCS2", START, 60)["booking"]
    with pytest.raises(ValidationError, match="own"):
        ctx.cancel_booking(d1, b.booking_id)
    with pytest.raises(ValidationError, match="owner"):                # regression: operators have no driver_id
        ctx.cancel_booking(op, b.booking_id)
    assert ctx.cancel_booking(admin, b.booking_id)[0].status == "Cancelled"
    with pytest.raises(NotFoundError):
        ctx.cancel_booking(admin, 99999999)


def test_waiting_cancel_permissions(ctx, users, st9):
    ahmed, d1, *_, op = users
    req = ctx.join_waiting_list(ahmed, st9, "CCS2", START, 60)
    with pytest.raises(ValidationError, match="own"):
        ctx.cancel_waiting(d1, req["request_id"])
    assert ctx.cancel_waiting(op, req["request_id"])["request_id"] == req["request_id"]       # operators manage the queue
    with pytest.raises(NotFoundError):
        ctx.cancel_waiting(ahmed, req["request_id"])


def test_full_session_lifecycle(ctx, users, st9, data_dir):
    ahmed, d1, *_ = users
    b = ctx.book_at_station(ahmed, st9, "CCS2", START, 60)["booking"]
    s = ctx.start_session(users[4], b.booking_id, START + timedelta(minutes=10))
    station, c = ctx.stations.get_charger(b.charger_id)
    assert c["charger_status"] == "Occupied" and s.status == "Active"
    assert ctx.frames()["chargers"].set_index("charger_id").loc[b.charger_id, "status"] == "Occupied"
    other = ctx.book_at_station(d1, st9, "CCS2", START + timedelta(hours=1), 60)["booking"]
    ctx.bookings.get_booking(other.booking_id).charger_id = b.charger_id                    # same (now occupied) charger
    n = len(ctx.sessions.sessions)
    with pytest.raises(InvalidSessionStateError):
        ctx.start_session(users[4], other.booking_id, START + timedelta(hours=1))
    assert len(ctx.sessions.sessions) == n                                                  # no half-created session left behind
    sess, promoted = ctx.complete_session(users[4], s.session_id, 25.0, START + timedelta(minutes=70))
    assert sess.status == "Completed" and sess.duration_minutes == 60.0
    assert ctx.bookings.get_booking(b.booking_id).status == "Completed" and c["charger_status"] == "Available"
    row = pd.read_csv(data_dir / "sessions.csv", dtype=str).iloc[-1]
    assert row["booking_id"] == str(b.booking_id) and float(row["energy_kwh"]) == 25.0 and int(row["delay_min"]) == 10
    price = station.price_per_kwh
    assert float(row["cost_egp"]) == pytest.approx(25.0 * price, abs=0.01)
    again = ChargeSpotApp(data_dir, now_fn=lambda: NOW)
    assert again.sessions.get_session(s.session_id).energy_delivered_kwh == 25.0
    assert again.stations.get_charger(b.charger_id)[1]["charger_status"] == "Available"


def test_complete_uses_a_suggested_energy_when_none_given(ctx, users, st9):
    b = ctx.book_at_station(users[0], st9, "CCS2", START, 60)["booking"]
    s = ctx.start_session(users[4], b.booking_id, START)
    sess, _ = ctx.complete_session(users[4], s.session_id, None, START + timedelta(minutes=60))
    assert 1.0 <= sess.energy_delivered_kwh <= 0.8 * 70


def test_no_show_keeps_the_slot_blocked_and_cannot_start(ctx, users, st9):
    b = ctx.book_at_station(users[0], st9, "CCS2", START, 60)["booking"]
    assert ctx.mark_no_show(users[4], b.booking_id).status == "No-Show"
    with pytest.raises(InvalidSessionStateError, match="No-Show"):
        ctx.start_session(users[4], b.booking_id, START)


def test_cannot_start_a_cancelled_booking(ctx, users, st9):
    b = ctx.book_at_station(users[0], st9, "CCS2", START, 60)["booking"]
    ctx.cancel_booking(users[0], b.booking_id)
    with pytest.raises(InvalidSessionStateError, match="Cancelled"):      # PDF: block "start a cancelled booking"
        ctx.start_session(users[4], b.booking_id, START)
    assert not ctx.sessions.sessions[-1:] or ctx.sessions.sessions[-1].status != "Planned"


def test_removing_a_booked_charger_is_blocked_then_allowed_after_cancel(ctx, users, st9):
    ahmed = users[0]
    b = ctx.book_at_station(ahmed, st9, "CCS2", START, 60)["booking"]
    with pytest.raises(ChargerInUseError):
        ctx.stations.remove_charger_with_undo(st9, b.charger_id)
    ctx.cancel_booking(ahmed, b.booking_id)
    assert ctx.stations.remove_charger_with_undo(st9, b.charger_id) is True
    assert "restored" in ctx.stations.undo_last_admin_action()


def test_operator_status_change_is_saved_but_not_undoable(ctx, st9, data_dir):
    cid = st9.chargers[0]["charger_id"]
    ctx.stations.update_charger_status(st9, cid, "Maintenance", record=False)
    assert not ctx.stations.admin_stack.stack
    assert ChargeSpotApp(data_dir, now_fn=lambda: NOW).stations.get_charger(cid)[1]["charger_status"] == "Maintenance"


def test_frames_feed_the_analytics_and_use_string_ids(ctx, users, st9):
    ctx.book_at_station(users[0], st9, "CCS2", START, 60)
    f = ctx.frames()
    for t in ("stations", "chargers", "bookings", "sessions"):
        assert all(f[t][c].map(type).eq(str).all() for c in f[t].columns if c.endswith("_id") and f[t][c].notna().all())
    assert f["bookings"]["booking_id"].is_unique and set(f["bookings"]["station_id"]) <= set(f["stations"]["station_id"])
    k = M.kpi_summary(f["bookings"], f["sessions"], f["chargers"], f["stations"])
    assert k["total_bookings"] == len(f["bookings"]) and k["peak_hour"] is not None
    dump = f["bookings"].copy()
    for c in ("created_at", "start_time", "end_time"):
        dump[c] = dump[c].dt.strftime("%Y-%m-%d %H:%M")
    _, rep = clean_bookings(dump, f["stations"])
    assert rep.dropped == {} and rep.fixed == {}                                    # our own data passes our own cleaner


def test_frames_are_cached_until_something_changes(ctx, users, st9):
    f1 = ctx.frames()
    assert ctx.frames() is f1
    ctx.book_at_station(users[0], st9, "CCS2", START, 60)
    f2 = ctx.frames()
    assert f2 is not f1 and len(f2["bookings"]) == len(f1["bookings"]) + 1


def test_registered_users_appear_in_drivers_frame_and_vehicles(ctx, users):
    d = ctx.frames()["drivers"]
    assert users[1].driver_id in set(d["driver_id"]) and ctx.vehicle_of_driver(users[1].driver_id)["vehicle_model"] == "BYD Atto 3"
    assert ctx.battery_for(users[1].driver_id).capacity_kwh == 60.0
    with pytest.raises(ValidationError):
        ctx.battery_for("D99999")


def test_expired_waiting_requests_are_dropped_on_load(ctx, users, st9, data_dir):
    ctx.join_waiting_list(users[0], st9, "CCS2", START, 60)
    later = ChargeSpotApp(data_dir, now_fn=lambda: START + timedelta(hours=2))
    assert len(later.waiting.queue) == 0


def test_demo_driver_owns_the_same_car_as_in_the_history(ctx):
    hist = ctx.history_drivers.set_index("driver_id")["vehicle_model"]
    assert ctx.vehicle_of_driver("D101")["vehicle_model"] == hist["D101"]


def test_adding_a_charger_makes_it_bookable(ctx, users, st9):
    ctx.stations.add_charger(9, ACCharger("AC-190", 22))
    assert ctx.book_at_station(users[0], st9, "Type 2", START, 60)["status"] == "confirmed"
