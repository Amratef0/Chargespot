"""Evidence for the algorithm report (Member 4): measured comparisons, not claims."""
from __future__ import annotations

import math
import random
import time

import pandas as pd

from algorithms.searching import binary_search, sequential_search
from algorithms.sorting import merge_sort_with_stats


def bubble_sort_comparisons(values):
    """Baseline for the comparison: bubble sort. Returns (sorted list, comparisons, swaps)."""
    a, comps, swaps = list(values), 0, 0
    for i in range(len(a) - 1):
        swapped = False
        for j in range(len(a) - 1 - i):
            comps += 1
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swaps += 1
                swapped = True
        if not swapped:
            break
    return a, comps, swaps


def sorting_experiment(sizes=(100, 500, 1000, 2000), seed: int = 0) -> pd.DataFrame:
    """Comparisons used by Merge Sort (team code) vs Bubble Sort on random data."""
    rng = random.Random(seed)
    rows = []
    for n in sizes:
        data = [rng.randint(0, 10 ** 6) for _ in range(n)]
        m = merge_sort_with_stats(data)
        _, bc, bs = bubble_sort_comparisons(data)
        assert m["sorted"] == sorted(data)                                   # correctness check
        rows.append({"size": n, "algorithm": "Merge Sort", "comparisons": m["comparisons"],
                     "recursive_calls": m["recursive_calls"], "reference": round(n * math.log2(n))})
        rows.append({"size": n, "algorithm": "Bubble Sort", "comparisons": bc, "swaps": bs,
                     "reference": n * (n - 1) // 2})
    return pd.DataFrame(rows)


def lookup_experiment(bookings: list, booking_id: int, hash_table) -> dict:
    """Find one booking by ID three ways. `bookings` must be ordered by booking_id."""
    key = lambda b: b.booking_id
    t = time.perf_counter(); si, sc = sequential_search(bookings, booking_id, key); t_seq = time.perf_counter() - t
    t = time.perf_counter(); bi, bc = binary_search(bookings, booking_id, key); t_bin = time.perf_counter() - t
    t = time.perf_counter(); found = hash_table.get(booking_id); t_hash = time.perf_counter() - t
    return {"found": found is not None and si == bi != -1, "n": len(bookings),
            "sequential": {"comparisons": sc, "ms": round(t_seq * 1000, 3)},
            "binary": {"comparisons": bc, "ms": round(t_bin * 1000, 3)},
            "hash": {"comparisons": hash_table.last_probes, "ms": round(t_hash * 1000, 3)}}
