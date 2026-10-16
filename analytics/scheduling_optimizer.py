"""Smart scheduling optimization (optional AI feature, Member 4).

Problem: a station has several chargers and a BATCH of charging requests
(desired start, duration, connector). Give each request a charger and a start
time so that fewer drivers are turned away and the total waiting is smallest.

    wait of a request = assigned start - desired start
    two bookings on one charger overlap if  A.start < B.end and B.start < A.end
    a request is UNSERVED if it would wait more than `max_wait` or end after closing

Everything here is "list scheduling": requests are placed ONE BY ONE, each at
the earliest free slot (>= desired start) on the compatible charger that
starts it soonest. The ORDER of the requests is what we optimise:

    fcfs               order of booking time              <- the greedy baseline
    shortest_first     short sessions first               <- classic rule for low total waiting
    earliest_desired   earliest desired start first
    best_heuristic     best of the three above
    local_search       start from best_heuristic, swap pairs while it improves
    optimal            exhaustive backtracking with pruning (only for <= 8 requests)

Objective (one number, lower is better):
    cost = total wait of served requests + max_wait x (number of unserved requests)
i.e. turning a driver away counts as the longest wait we accept. Comparing total wait
alone would be misleading: a plan can look "faster" simply by serving fewer drivers.

HONEST LIMITS
* `optimal` is optimal over all request ORDERS (so over all list schedules); it
is exponential: refused above MAX_EXACT requests.
* Re-planning a whole day offline assumes all requests are known in advance.
In real time you cannot know future requests, so the gain is an upper bound.
* The ordering uses a `sort_fn` argument (default Python `sorted`) because this
is not one of the course's required manual-sorting parts; pass Member 3's
merge_sort at integration time to use the team's own implementation.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from algorithms.greedy_scheduler import earliest_free_start

MAX_EXACT = 8
STRATEGIES = ("fcfs", "shortest_first", "earliest_desired", "best_heuristic", "local_search")


@dataclass(frozen=True)
class Request:
    req_id: str
    desired_start: int          # minutes after midnight
    duration: int               # minutes
    connector: str
    created: float = 0.0        # booking time in minutes (any consistent scale); FCFS order


@dataclass
class Plan:
    strategy: str
    assignments: list = field(default_factory=list)   # dicts: req_id, charger_id, start, end, wait
    unserved: list = field(default_factory=list)      # req_ids
    penalty: int = 90                                 # minutes charged per unserved request (= max_wait)

    @property
    def served(self) -> int: return len(self.assignments)

    @property
    def total_wait(self) -> int: return sum(a["wait"] for a in self.assignments)

    @property
    def avg_wait(self) -> float: return self.total_wait / self.served if self.served else 0.0

    @property
    def max_wait(self) -> int: return max((a["wait"] for a in self.assignments), default=0)

    @property
    def cost(self) -> int: return self.total_wait + self.penalty * len(self.unserved)

    def objective(self) -> int:
        return self.cost


# ---------------------------------------------------------------- placement core
def _earliest_start(busy: list, desired: int, dur: int) -> int:
    """Earliest t >= desired such that [t, t+dur) overlaps nothing in `busy` (sorted (start, end) pairs).
    This IS the team's greedy rule (algorithms/greedy_scheduler.earliest_free_start), reused here so the
    FCFS baseline is exactly what the booking service does."""
    return earliest_free_start([(s, e, None) for s, e in busy], desired, dur, close_min=10 ** 9)


def _place(req: Request, busy: dict, chargers: list, close_min: int, max_wait: int):
    """Best (start, charger_id) for one request, or None if it cannot be served."""
    best = None
    for c in chargers:
        if c["connector"] != req.connector:
            continue
        t = _earliest_start(busy[c["charger_id"]], req.desired_start, req.duration)
        if best is None or t < best[0]:
            best = (t, c["charger_id"])
    if best is None:
        return None
    t, cid = best
    if t - req.desired_start > max_wait or t + req.duration > close_min:
        return None
    return best


def schedule_in_order(ordered: list[Request], chargers: list[dict], close_min: int = 1440,
                    max_wait: int = 90, strategy: str = "custom") -> Plan:
    busy = {c["charger_id"]: [] for c in chargers}
    plan = Plan(strategy, penalty=max_wait)
    for r in ordered:
        got = _place(r, busy, chargers, close_min, max_wait)
        if got is None:
            plan.unserved.append(r.req_id)
            continue
        t, cid = got
        bisect.insort(busy[cid], (t, t + r.duration))
        plan.assignments.append({"req_id": r.req_id, "charger_id": cid, "start": t,
                                "end": t + r.duration, "wait": t - r.desired_start})
    return plan


# ---------------------------------------------------------------- orderings
def _order(requests: list[Request], key, sort_fn: Callable = sorted) -> list[Request]:
    return sort_fn(requests, key=key)


def fcfs(requests, chargers, close_min=1440, max_wait=90, sort_fn=sorted) -> Plan:
    o = _order(requests, lambda r: (r.created, r.req_id), sort_fn)
    return schedule_in_order(o, chargers, close_min, max_wait, "fcfs")


def shortest_first(requests, chargers, close_min=1440, max_wait=90, sort_fn=sorted) -> Plan:
    o = _order(requests, lambda r: (r.duration, r.desired_start, r.req_id), sort_fn)
    return schedule_in_order(o, chargers, close_min, max_wait, "shortest_first")


def earliest_desired(requests, chargers, close_min=1440, max_wait=90, sort_fn=sorted) -> Plan:
    o = _order(requests, lambda r: (r.desired_start, r.duration, r.req_id), sort_fn)
    return schedule_in_order(o, chargers, close_min, max_wait, "earliest_desired")


def best_heuristic(requests, chargers, close_min=1440, max_wait=90, sort_fn=sorted) -> Plan:
    plans = [f(requests, chargers, close_min, max_wait, sort_fn) for f in (fcfs, shortest_first, earliest_desired)]
    best = min(plans, key=lambda p: p.objective())
    best.strategy = "best_heuristic"
    return best


def local_search(requests, chargers, close_min=1440, max_wait=90, sort_fn=sorted,
                max_passes: int = 4) -> Plan:
    """Hill climbing: start from the best heuristic order, swap pairs while the objective improves."""
    start = best_heuristic(requests, chargers, close_min, max_wait, sort_fn)
    by_id = {r.req_id: r for r in requests}
    order = [by_id[a["req_id"]] for a in sorted(start.assignments, key=lambda a: (a["start"], a["req_id"]))]
    order += [by_id[i] for i in start.unserved]
    best = schedule_in_order(order, chargers, close_min, max_wait, "local_search")
    for _ in range(max_passes):
        improved = False
        for i in range(len(order) - 1):
            for j in range(i + 1, min(i + 6, len(order))):          # only nearby swaps -> keeps it fast
                order[i], order[j] = order[j], order[i]
                cand = schedule_in_order(order, chargers, close_min, max_wait, "local_search")
                if cand.objective() < best.objective():
                    best, improved = cand, True
                else:
                    order[i], order[j] = order[j], order[i]          # undo
        if not improved:
            break
    return best


def optimal(requests, chargers, close_min=1440, max_wait=90) -> Plan:
    """Exhaustive search over all request orders with branch-and-bound pruning."""
    n = len(requests)
    if n > MAX_EXACT:
        raise ValueError(f"Exact search is limited to {MAX_EXACT} requests (got {n}); "
                        "it grows as n! - use local_search for bigger batches.")
    reqs = list(requests)
    best = {"obj": 10 ** 12, "assign": None, "unserved": None}
    busy = {c["charger_id"]: [] for c in chargers}

    def rec(remaining, assigned, unserved, wait):
        cost = wait + max_wait * len(unserved)
        if cost >= best["obj"]:
            return                                                  # prune: cost only grows, cannot beat best
        if not remaining:
            best.update(obj=cost, assign=list(assigned), unserved=list(unserved))
            return
        for k, r in enumerate(remaining):
            rest = remaining[:k] + remaining[k + 1:]
            got = _place(r, busy, chargers, close_min, max_wait)
            if got is None:
                rec(rest, assigned, unserved + [r.req_id], wait)
                continue
            t, cid = got
            iv = (t, t + r.duration)
            bisect.insort(busy[cid], iv)
            assigned.append({"req_id": r.req_id, "charger_id": cid, "start": t,
                            "end": t + r.duration, "wait": t - r.desired_start})
            rec(rest, assigned, unserved, wait + (t - r.desired_start))
            assigned.pop()
            busy[cid].remove(iv)

    rec(reqs, [], [], 0)
    return Plan("optimal", best["assign"] or [], best["unserved"] or [], penalty=max_wait)


# ---------------------------------------------------------------- comparison
def compare_strategies(requests: list[Request], chargers: list[dict], close_min: int = 1440,
                    max_wait: int = 90, include_optimal: bool = False, sort_fn=sorted):
    """Run all strategies. Returns (summary DataFrame, {strategy: Plan})."""
    if not requests:
        return pd.DataFrame(columns=["strategy", "served", "unserved", "total_wait_min",
                                    "avg_wait_min", "max_wait_min", "cost", "cost_saved_vs_fcfs_pct"]), {}
    plans = {
        "fcfs": fcfs(requests, chargers, close_min, max_wait, sort_fn),
        "shortest_first": shortest_first(requests, chargers, close_min, max_wait, sort_fn),
        "earliest_desired": earliest_desired(requests, chargers, close_min, max_wait, sort_fn),
        "best_heuristic": best_heuristic(requests, chargers, close_min, max_wait, sort_fn),
        "local_search": local_search(requests, chargers, close_min, max_wait, sort_fn),
    }
    if include_optimal and len(requests) <= MAX_EXACT:
        plans["optimal"] = optimal(requests, chargers, close_min, max_wait)
    base = plans["fcfs"]
    rows = []
    for name, p in plans.items():
        saved = 100 * (base.cost - p.cost) / base.cost if base.cost else 0.0
        rows.append({"strategy": name, "served": p.served, "unserved": len(p.unserved),
                    "total_wait_min": p.total_wait, "avg_wait_min": round(p.avg_wait, 1),
                    "max_wait_min": p.max_wait, "cost": p.cost,
                    "cost_saved_vs_fcfs_pct": round(saved, 1)})
    return pd.DataFrame(rows), plans


def counter_example():
    """Classic case where the greedy FCFS order is NOT optimal (one charger).

    A long session books first, two short ones right after. FCFS makes both short
    sessions wait for the long one; serving the short ones first cuts total waiting.
    """
    chargers = [{"charger_id": "DC-201", "connector": "CCS2"}]
    reqs = [Request("A-long", 600, 120, "CCS2", 0), Request("B-short", 600, 30, "CCS2", 1),
            Request("C-short", 600, 30, "CCS2", 2)]
    return reqs, chargers


def plan_to_frame(plan: Plan, day, requests: list[Request] | None = None) -> pd.DataFrame:
    """Plan as a DataFrame with real datetimes (for a timeline chart)."""
    day = pd.Timestamp(day).normalize()
    df = pd.DataFrame(plan.assignments, columns=["req_id", "charger_id", "start", "end", "wait"])
    if df.empty:
        return df.assign(start_dt=pd.NaT, end_dt=pd.NaT)
    df["start_dt"] = day + pd.to_timedelta(df["start"], unit="m")
    df["end_dt"] = day + pd.to_timedelta(df["end"], unit="m")
    return df


def requests_from_bookings(bookings: pd.DataFrame, station_id: str, day) -> list[Request]:
    """Build the request batch of one station-day from the booking table.

    Includes bookings that were served (Completed / No-Show) and ones that gave up
    while waiting. The desired start of a queued booking is its start minus the wait.
    """
    day = pd.Timestamp(day).normalize()
    b = bookings[(bookings["station_id"] == station_id)
                & (bookings["start_time"] >= day) & (bookings["start_time"] < day + pd.Timedelta(days=1))]
    b = b[b["status"].isin(["Completed", "No-Show"]) | (b["queued"] == 1)]
    out = []
    for r in b.itertuples(index=False):
        start_min = r.start_time.hour * 60 + r.start_time.minute
        desired = max(0, start_min - (int(r.wait_min) if r.queued == 1 and r.status != "Cancelled" else 0))
        created = (r.created_at - day).total_seconds() / 60
        out.append(Request(r.booking_id, int(desired), int(r.duration_min), r.connector, float(created)))
    return out


def chargers_for_station(chargers: pd.DataFrame, station_id: str) -> list[dict]:
    c = chargers[(chargers["station_id"] == station_id) & (chargers["status"] != "Maintenance")]
    return c[["charger_id", "connector"]].to_dict("records")
