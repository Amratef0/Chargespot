import pandas as pd
import pytest

from ai.recommendation import Weights, recommend_stations

DIST = {"Home": {"Near St": 0.5, "Mid St": 6.0, "Far St": 25.0}, "Island": {"Far St": 3.0}}


def frames():
    stations = pd.DataFrame({
        "station_id": ["1", "2", "3"], "name": ["Near", "Mid", "Far"], "city": ["X"] * 3,
        "address": ["Near St", "Mid St", "Far St"], "lat": [0.0] * 3, "lon": [0.0] * 3,
        "open_hour": [6, 6, 6], "close_hour": [24, 24, 24], "price_per_kwh": [7.0, 6.0, 5.0]})
    chargers = pd.DataFrame({
        "charger_id": ["DC-201", "DC-202", "AC-101", "DC-203"], "station_id": ["1", "2", "2", "3"],
        "connector": ["CCS2", "CCS2", "Type 2", "CCS2"], "power_kw": [50, 150, 22, 100],
        "status": ["Available", "Available", "Available", "Occupied"]})
    bookings = pd.DataFrame({
        "station_id": ["1"] * 30 + ["2"] * 30 + ["3"] * 30, "connector": ["CCS2"] * 90,
        "start_time": pd.to_datetime(["2026-01-05 18:10"] * 90),
        "wait_min": [30] * 30 + [0] * 30 + [10] * 30})
    return stations, chargers, bookings


def rec(**kw):
    s, c, b = frames()
    args = dict(driver_area="Home", connector="CCS2", target_hour=18, distances=DIST)
    args.update(kw)
    return recommend_stations(s, c, b, **args)


def test_distance_only_picks_closest_and_price_only_picks_cheapest():
    assert rec(weights=Weights(1, 0, 0, 0, 0)).ranked.iloc[0]["name"] == "Near"
    assert rec(weights=Weights(0, 0, 1, 0, 0)).ranked.iloc[0]["name"] == "Far"


def test_distance_comes_from_the_teams_matrix():
    r = rec().ranked.set_index("name")
    assert r.loc["Near", "distance_km"] == 0.5 and r.loc["Far", "distance_km"] == 25.0


def test_wait_only_uses_booking_history():
    r = rec(weights=Weights(0, 1, 0, 0, 0)).ranked
    assert r.iloc[0]["name"] == "Mid" and r.set_index("name").loc["Near", "expected_wait_min"] == 30


def test_power_and_availability_criteria():
    assert rec(weights=Weights(0, 0, 0, 1, 0)).ranked.iloc[0]["name"] == "Mid"
    far = rec(weights=Weights(0, 0, 0, 0, 1)).ranked.set_index("name")
    assert far.loc["Far", "free_now"] == 0 and far.loc["Near", "free_now"] == 1


def test_incompatible_connector_is_excluded_with_reason():
    r = rec(connector="Type 2")
    assert list(r.ranked["name"]) == ["Mid"] and r.excluded["reason"].str.contains("no active Type 2").all()


def test_area_without_route_data_is_excluded():
    r = rec(driver_area="Island")
    assert list(r.ranked["name"]) == ["Far"]
    assert r.excluded["reason"].str.contains("no route data from Island").all()


def test_maintenance_charger_does_not_count():
    s, c, b = frames()
    c.loc[c["charger_id"] == "DC-201", "status"] = "Maintenance"
    assert "Near" not in set(recommend_stations(s, c, b, "Home", "CCS2", 18, DIST).ranked["name"])


def test_closed_station_is_excluded():
    s, c, b = frames()
    s.loc[0, "open_hour"] = 9
    r = recommend_stations(s, c, b, "Home", "CCS2", 7, DIST)
    assert "closed" in r.excluded[r.excluded["name"] == "Near"].iloc[0]["reason"]


def test_max_distance_excludes():
    r = rec(max_distance_km=10)
    assert set(r.ranked["name"]) == {"Near", "Mid"} and "km away" in r.excluded.iloc[0]["reason"]


def test_everything_excluded_returns_empty_not_crash():
    r = rec(connector="CHAdeMO")
    assert r.ranked.empty and len(r.excluded) == 3


def test_scores_bounded_sorted_and_points_add_up():
    r = rec().ranked
    assert r["score"].between(0, 100).all() and list(r["rank"]) == [1, 2, 3]
    assert list(r["score"]) == sorted(r["score"], reverse=True)
    pts = r[[c for c in r.columns if c.startswith("pts_")]].sum(axis=1)
    assert ((pts - r["score"]).abs() < 0.1).all()


def test_equal_criteria_do_not_crash():
    s, c, b = frames()
    s["price_per_kwh"] = 6.0
    assert not recommend_stations(s, c, b, "Home", "CCS2", 18, DIST).ranked.empty


@pytest.mark.parametrize("kw", [dict(connector="Tesla"), dict(target_hour=24), dict(target_hour=-1),
                                dict(driver_area="Mars"), dict(target_hour=7.5)])
def test_invalid_inputs_raise_value_error(kw):
    with pytest.raises(ValueError):
        rec(**kw)


@pytest.mark.parametrize("w", [Weights(-1, 1, 1, 1, 1), Weights(0, 0, 0, 0, 0)])
def test_invalid_weights_raise(w):
    with pytest.raises(ValueError):
        rec(weights=w)


def test_works_on_the_generated_team_dataset(small):
    import json
    dist = json.load(open("data/distances.json"))
    r = recommend_stations(small["stations"], small["chargers"], small["bookings"], "Nasr City", "CCS2", 18, dist)
    assert r.ranked.iloc[0]["name"].startswith("ChargeSpot Nasr City")      # the two Nasr City stations win
