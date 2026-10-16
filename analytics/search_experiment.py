"""Sequential vs Binary search comparison experiment (Member 4).

Uses the team's algorithms/searching.py: both functions return (index or -1, comparisons).
If a replacement implementation returns only an index, comparisons are counted from the outside
with `CountedInt` (every ==, <, > ... = 1).

Fairness rule: sequential search runs on UNSORTED data, binary search only on
SORTED data (it refuses unsorted input).
"""
from __future__ import annotations

import math
import random

import pandas as pd


# the algorithms themselves live in algorithms/searching.py (team code); re-exported here for the page
from algorithms.searching import (binary_search, binary_search_trace, is_sorted,  # noqa: E402,F401
                                sequential_search)


# ------------------------------------------------------------ external counting
class CountedInt:
    """int wrapper that counts every comparison (used to measure any implementation)."""
    count = 0

    def __init__(self, v):
        self.v = v

    def _c(self):
        CountedInt.count += 1

    def __eq__(self, o): self._c(); return self.v == o.v
    def __lt__(self, o): self._c(); return self.v < o.v
    def __le__(self, o): self._c(); return self.v <= o.v
    def __gt__(self, o): self._c(); return self.v > o.v
    def __ge__(self, o): self._c(); return self.v >= o.v
    def __hash__(self): return hash(self.v)


def get_search_functions():
    """Return (sequential, binary, source_label): the team's code in algorithms/searching.py."""
    return sequential_search, binary_search, "team code: algorithms/searching.py"


def _measure(fn, items, target):
    """Run fn and return (index, comparisons) whatever the return style is."""
    res = fn(items, target)
    if isinstance(res, tuple) and len(res) == 2:
        return res
    CountedInt.count = 0                                    # index only -> count externally
    wrapped = [CountedInt(x) for x in items]
    idx = fn(wrapped, CountedInt(target))
    idx = idx[0] if isinstance(idx, tuple) else idx
    return idx, CountedInt.count


# ------------------------------------------------------------ the experiment
def run_search_experiment(sizes=(100, 1000, 10000), trials: int = 200, seed: int = 0) -> pd.DataFrame:
    """Average / worst-case comparisons for both algorithms on several sizes.

    Half of the targets exist in the list, half do not (worst case for both).
    """
    seq, binary, _ = get_search_functions()
    rng = random.Random(seed)
    rows = []
    for n in sizes:
        sorted_ids = sorted(rng.sample(range(0, n * 10, 2), n))          # even numbers only
        shuffled = sorted_ids[:]
        rng.shuffle(shuffled)
        targets = [rng.choice(sorted_ids) if t % 2 == 0 else rng.randrange(1, n * 10, 2)
                for t in range(trials)]                               # odd = not present
        s_cnt, b_cnt = [], []
        for t in targets:
            i, c = _measure(seq, shuffled, t)
            s_cnt.append(c)
            i2, c2 = _measure(binary, sorted_ids, t)
            b_cnt.append(c2)
            assert (i == -1) == (i2 == -1), "algorithms disagree"        # correctness check
        for name, cnt, theory in (("Sequential", s_cnt, n), ("Binary", b_cnt, math.floor(math.log2(n)) + 1)):
            rows.append({"size": n, "algorithm": name,
                        "avg_comparisons": round(sum(cnt) / len(cnt), 1),
                        "worst_comparisons": max(cnt),
                        "theoretical_worst": theory})
    return pd.DataFrame(rows)
