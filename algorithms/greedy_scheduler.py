"""Greedy slot assignment (Member 2's greedy idea, made charger-level and date-aware).

Greedy rule: give the driver the EARLIEST free start at or after the requested time, on the
compatible charger that can start soonest (ties: faster charger, then lower ID).

Why greedy fits: each decision is local and immediate (a driver is waiting for an answer).
Why it is not always globally optimal: it never reconsiders earlier choices, so a long session
placed first can block several short ones (see analytics/scheduling_optimizer.counter_example).

`busy_of(charger_id)` must return that charger's busy intervals for the day, SORTED by start:
a list of (start_min, end_min, booking_id).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SlotOption:
    charger_id: str
    start_min: int
    wait_min: int           # start - requested start


def earliest_free_start(busy, desired, duration, close_min):
    """Earliest t >= desired with [t, t+duration) free and t+duration <= close_min, else None."""
    t = desired
    for s, e, _ in busy:
        if t + duration <= s:
            break                       # fits in the gap before this booking
        if e > t:
            t = e                       # blocked -> try right after it
    return t if t + duration <= close_min else None


def pick_charger_greedy(chargers, busy_of, desired, duration, close_min, max_shift=0):
    """Best SlotOption among `chargers` (list of dicts), or None. max_shift = longest wait allowed (min)."""
    best = None
    for c in chargers:
        t = earliest_free_start(busy_of(c["charger_id"]), desired, duration, close_min)
        if t is None or t - desired > max_shift:
            continue
        rank = (t, -c.get("charger_power_kw", 0), c["charger_id"])
        if best is None or rank < best[0]:
            best = (rank, SlotOption(c["charger_id"], t, t - desired))
    return None if best is None else best[1]


def suggest_alternatives(chargers, busy_of, desired, duration, close_min, n=3, step=15, horizon=360):
    """Up to n distinct start times (earliest first) at/after `desired`, each with its best charger."""
    out, seen = [], set()
    for shift in range(0, horizon + 1, step):
        opt = pick_charger_greedy(chargers, busy_of, desired + shift, duration, close_min, max_shift=0)
        if opt and opt.start_min not in seen:
            seen.add(opt.start_min)
            out.append(SlotOption(opt.charger_id, opt.start_min, opt.start_min - desired))
            if len(out) == n:
                break
    return out
