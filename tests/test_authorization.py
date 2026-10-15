"""Authorization: the application layer refuses wrong roles itself (not only the Streamlit pages), the sidebar is
derived from the same permissions, and no page bypasses the guarded methods."""
import re
from datetime import datetime
from pathlib import Path

import pytest

from models.charger import ACCharger
from models.exceptions import PermissionDeniedError, ValidationError
from models.user import Admin, Driver, StationOperator
from services.authz import PAGE_ACCESS, allowed_pages, authorize, can_open

ROOT = Path(__file__).resolve().parents[1]
START = datetime(2026, 3, 3, 10, 0)


@pytest.fixture()
def who(ctx):
    return {"driver": ctx.auth.login("ahmed@gmail.com", "123456789"),
            "operator": ctx.auth.login("operator@chargespot.com", "Operator1234"),
            "admin": ctx.auth.login("admin@chargespot.com", "Admin1234"), "nobody": None}


def denied(fn, *args, **kw):
    with pytest.raises(PermissionDeniedError):
        fn(*args, **kw)


# ----------------------------------------------------------------- the menu and the page guard share one table
OLD_ROLE_PAGES = {   # what app.py used to hard-code: the derived menu must be identical
    "user": {"home", "recommend", "bookings", "waiting", "driver", "stations"},
    "operator": {"home", "stations", "bookings", "waiting", "sessions"},
    "admin": {"home", "stations", "bookings", "waiting", "sessions", "driver", "recommend", "analytics", "lab"}}


@pytest.mark.parametrize("cls,role", [(Driver, "user"), (StationOperator, "operator"), (Admin, "admin")])
def test_menu_is_derived_from_permissions(cls, role):
    u = cls("N", "n@x.com")
    assert set(allowed_pages(u, PAGE_ACCESS)) == OLD_ROLE_PAGES[role]


def test_unknown_page_and_anonymous_are_closed_by_default():
    assert not can_open(None, "home") and not can_open(Driver("N", "n@x.com"), "no_such_page")
    denied(authorize, None)
    denied(authorize, Driver("N", "n@x.com"), "manage_stations")
    assert authorize(Admin("N", "n@x.com"), "manage_stations")


# ----------------------------------------------------------------- the application layer enforces roles itself
@pytest.mark.parametrize("who_key", ["driver", "nobody"])
def test_session_actions_need_manage_sessions(ctx, who, who_key):
    u = who[who_key]
    denied(ctx.start_session, u, 1)
    denied(ctx.complete_session, u, 1, 5.0)
    denied(ctx.mark_no_show, u, 1)


@pytest.mark.parametrize("who_key", ["driver", "nobody"])
def test_operator_actions_refuse_drivers_and_anonymous(ctx, who, who_key):
    st9 = ctx.stations.get_station(9)
    cid = st9.chargers[0]["charger_id"]
    denied(ctx.update_charger_status, who[who_key], st9, cid, "Maintenance")
    assert st9.find_charger(cid)["charger_status"] == "Available"             # nothing changed


@pytest.mark.parametrize("who_key", ["driver", "operator", "nobody"])
def test_admin_actions_refuse_everyone_else(ctx, who, who_key):
    u, st9 = who[who_key], ctx.stations.get_station(9)
    n_st, n_ch = len(ctx.stations.stations), len(st9.chargers)
    denied(ctx.add_charger, u, 9, ACCharger("AC-199", 22))
    denied(ctx.remove_charger, u, st9, st9.chargers[0]["charger_id"])
    denied(ctx.add_station, u, 77, "Test station", "Cairo", "Somewhere")
    denied(ctx.edit_station, u, 9, price_per_kwh=9.0)
    denied(ctx.remove_station, u, 9)
    denied(ctx.undo_last_admin_action, u)
    denied(ctx.reload_from_disk, u)
    assert len(ctx.stations.stations) == n_st and len(st9.chargers) == n_ch and not ctx.stations.admin_stack.stack


def test_allowed_roles_can_do_their_actions(ctx, who):
    st9 = ctx.stations.get_station(9)
    cid = st9.chargers[0]["charger_id"]
    v0 = ctx.version
    assert ctx.update_charger_status(who["operator"], st9, cid, "Maintenance") and ctx.version > v0
    ctx.add_charger(who["admin"], 9, ACCharger("AC-199", 22))
    ctx.edit_station(who["admin"], 9, price_per_kwh=9.5)
    assert "edit" in ctx.undo_last_admin_action(who["admin"])


def test_only_drivers_can_book_or_join_the_waiting_list(ctx, who):
    st9 = ctx.stations.get_station(9)
    for u in (who["operator"], who["admin"], None):
        denied(ctx.book_at_station, u, st9, "CCS2", START, 60)
        denied(ctx.join_waiting_list, u, st9, "CCS2", START, 60)
    denied(ctx.cancel_booking, None, 1)
    denied(ctx.cancel_waiting, None, 1)


def test_driver_data_is_private_unless_view_any_driver(ctx, who):
    assert ctx.resolve_driver_id(who["driver"]) == "D101" and ctx.resolve_driver_id(who["driver"], "D101") == "D101"
    denied(ctx.resolve_driver_id, who["driver"], "D102")                      # another driver's dashboard
    denied(ctx.resolve_driver_id, who["operator"])
    denied(ctx.resolve_driver_id, None)
    assert ctx.resolve_driver_id(who["admin"], "D102") == "D102"
    with pytest.raises(ValidationError):                                      # admin has no own driver data
        ctx.resolve_driver_id(who["admin"])


# ----------------------------------------------------------------- pages must go through the guarded methods
MUTATORS = ("update_charger_status", "add_charger", "remove_charger_with_undo", "add_station", "edit_station",
            "remove_station", "undo_last_admin_action", "start_session", "complete_session", "mark_no_show")


@pytest.mark.parametrize("page", sorted((ROOT / "pages").glob("*.py")), ids=lambda p: p.name)
def test_pages_do_not_call_unguarded_mutators(page):
    src = page.read_text(encoding="utf-8")
    for m in MUTATORS:
        for hit in re.finditer(rf"\b(svc|stations|sessions)\.{m}\b", src):
            pytest.fail(f"{page.name} calls {hit.group(0)} directly; use the guarded method on `app`.")
    assert 'st.session_state["user"]' not in src, f"{page.name} must use require_page(...) to get the user"
    assert "require_page(" in src
    assert re.search(r"^from core\.state import .*\brequire_page\b", src, re.M), f"{page.name} uses require_page but does not import it"