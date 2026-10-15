import random

import pandas as pd
import pytest

from analytics import scheduling_optimizer as SO
from analytics.scheduling_optimizer import Request, _earliest_start


def two_chargers():
    return [{"charger_id": "CH1", "connector": "CCS"}, {"charger_id": "CH2", "connector": "CCS"}]


def random_instance(seed, n=7):
    rng = random.Random(seed)
    return [Request(f"R{i}", rng.choice(range(480, 600, 15)), rng.choice([30, 45, 60, 90, 120]), "CCS", i)
            for i in range(n)]


def assert_valid(plan, reqs, chargers, close_min, max_wait):
    byid = {r.req_id: r for r in reqs}
    assert sorted([a["req_id"] for a in plan.assignments] + plan.unserved) == sorted(byid)   # each exactly once
    per = {}
    for a in plan.assignments:
        r = byid[a["req_id"]]
        assert a["start"] >= r.desired_start and a["wait"] == a["start"] - r.desired_start
        assert a["wait"] <= max_wait and a["end"] <= close_min and a["end"] - a["start"] == r.duration
        per.setdefault(a["charger_id"], []).append((a["start"], a["end"]))
    for ivs in per.values():                                    # A.start < B.end and B.start < A.end must never hold
        ivs.sort()
        assert all(ivs[i][1] <= ivs[i + 1][0] for i in range(len(ivs) - 1))


def test_earliest_start_cases():
    assert _earliest_start([], 100, 30) == 100
    assert _earliest_start([(100, 160)], 100, 30) == 160              # pushed after
    assert _earliest_start([(100, 160)], 40, 60) == 40                # ends exactly when next starts -> allowed
    assert _earliest_start([(100, 160)], 40, 61) == 160               # one minute too long
    assert _earliest_start([(100, 160), (190, 250)], 100, 30) == 160  # fits the gap [160,190)
    assert _earliest_start([(100, 160), (180, 250)], 100, 30) == 250  # gap too small


def test_counter_example_fcfs_is_not_optimal():
    reqs, ch = SO.counter_example()
    f = SO.fcfs(reqs, ch, 1440, 1000)
    o = SO.optimal(reqs, ch, 1440, 1000)
    assert f.total_wait == 270 and o.total_wait == 90


@pytest.mark.parametrize("seed", range(12))
def test_all_plans_are_valid_and_optimal_is_a_lower_bound(seed):
    reqs, ch = random_instance(seed), two_chargers()
    summary, plans = SO.compare_strategies(reqs, ch, 1440, 90, include_optimal=True)
    for p in plans.values():
        assert_valid(p, reqs, ch, 1440, 90)
    best = plans["optimal"].cost
    assert all(p.cost >= best for p in plans.values())
    assert plans["local_search"].cost <= plans["best_heuristic"].cost <= plans["fcfs"].cost


def test_optimal_refuses_large_batches():
    with pytest.raises(ValueError, match="limited"):
        SO.optimal(random_instance(1, n=SO.MAX_EXACT + 1), two_chargers())


def test_max_wait_and_closing_time_make_requests_unserved():
    one = [{"charger_id": "CH1", "connector": "CCS"}]
    reqs = [Request("A", 600, 120, "CCS", 0), Request("B", 600, 30, "CCS", 1)]
    p = SO.fcfs(reqs, one, 1440, 60)                       # B would wait 120 > 60
    assert p.unserved == ["B"]
    p2 = SO.fcfs([Request("L", 1400, 60, "CCS", 0)], one, 1440, 90)   # ends 1460 > 1440
    assert p2.unserved == ["L"]


def test_no_compatible_charger_is_unserved():
    p = SO.fcfs([Request("X", 600, 30, "Type2", 0)], two_chargers())
    assert p.unserved == ["X"] and p.served == 0


def test_empty_batch_does_not_crash():
    summary, plans = SO.compare_strategies([], two_chargers())
    assert summary.empty and plans == {}


def test_connector_compatibility_respected():
    chargers = [{"charger_id": "CH1", "connector": "CCS"}, {"charger_id": "CH2", "connector": "Type2"}]
    reqs = [Request("A", 600, 60, "Type2", 0), Request("B", 600, 60, "CCS", 1)]
    p = SO.fcfs(reqs, chargers)
    got = {a["req_id"]: a["charger_id"] for a in p.assignments}
    assert got == {"A": "CH2", "B": "CH1"}


def test_custom_sort_function_is_used():
    calls = []

    def my_sort(items, key):
        calls.append(len(items))
        return sorted(items, key=key)

    SO.fcfs(random_instance(3), two_chargers(), sort_fn=my_sort)
    assert calls == [7]


def test_requests_from_bookings_subtracts_wait_for_queued():
    b = pd.DataFrame({
        "booking_id": ["BK00001", "BK00002", "BK00003", "BK00004"], "station_id": ["ST01"] * 4,
        "start_time": pd.to_datetime(["2026-01-05 10:00", "2026-01-05 11:00", "2026-01-05 12:00", "2026-01-06 09:00"]),
        "created_at": pd.to_datetime(["2026-01-05 08:00"] * 4), "duration_min": [60] * 4,
        "connector": ["CCS"] * 4, "status": ["Completed", "Completed", "Cancelled", "Completed"],
        "queued": [0, 1, 0, 0], "wait_min": [0, 30, 0, 0]})
    reqs = {r.req_id: r for r in SO.requests_from_bookings(b, "ST01", "2026-01-05")}
    assert set(reqs) == {"BK00001", "BK00002"}                 # voluntary cancel + other day excluded
    assert reqs["BK00001"].desired_start == 600 and reqs["BK00002"].desired_start == 630
    assert reqs["BK00001"].created == 480


def test_real_busy_day_local_search_never_worse_than_fcfs(small):
    b = small["bookings"]
    day = b[b["station_id"] == "9"]["start_time"].dt.normalize().value_counts().idxmax()
    reqs = SO.requests_from_bookings(b, "9", day)
    chs = SO.chargers_for_station(small["chargers"], "9")
    summary, plans = SO.compare_strategies(reqs, chs)
    for p in plans.values():
        assert_valid(p, reqs, chs, 1440, 90)
    assert plans["local_search"].cost <= plans["fcfs"].cost
