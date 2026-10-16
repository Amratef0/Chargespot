
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
