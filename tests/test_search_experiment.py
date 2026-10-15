import math
import random

import pytest

from analytics.search_experiment import (CountedInt, _measure, binary_search,
                                         binary_search_trace, run_search_experiment,
                                         sequential_search)


def test_sequential_finds_in_unsorted_list():
    data = [9, 4, 7, 1]
    assert sequential_search(data, 7) == (2, 3)
    assert sequential_search(data, 5) == (-1, 4)


def test_binary_matches_list_index_on_random_sorted_data():
    rng = random.Random(1)
    data = sorted(rng.sample(range(1000), 200))
    for t in rng.sample(range(1000), 100):
        idx, _ = binary_search(data, t)
        assert (idx == -1) == (t not in data)
        if idx != -1:
            assert data[idx] == t


def test_binary_refuses_unsorted_data():
    with pytest.raises(ValueError, match="sorted"):
        binary_search([3, 1, 2], 2)


def test_binary_comparisons_bounded_by_log2():
    data = list(range(0, 2000, 2))
    worst = max(binary_search(data, t)[1] for t in range(-1, 2001))
    assert worst <= math.floor(math.log2(len(data))) + 1


def test_edge_cases_empty_and_single():
    assert binary_search([], 1) == (-1, 0)
    assert sequential_search([], 1) == (-1, 0)
    assert binary_search([5], 5) == (0, 1)


def test_trace_ends_on_found_and_refuses_unsorted():
    steps = binary_search_trace([1, 3, 5, 7, 9], 7)
    assert steps[-1]["action"] == "found" and steps[-1]["value_at_mid"] == 7
    with pytest.raises(ValueError):
        binary_search_trace([2, 1], 1)


def test_experiment_shows_binary_much_cheaper():
    df = run_search_experiment(sizes=(100, 1000), trials=60)
    for n in (100, 1000):
        seq = df[(df["size"] == n) & (df["algorithm"] == "Sequential")]["avg_comparisons"].iloc[0]
        bin_ = df[(df["size"] == n) & (df["algorithm"] == "Binary")]["avg_comparisons"].iloc[0]
        assert bin_ < seq / 5


def test_external_counting_for_index_only_implementations():
    def idx_only(a, t):
        for i, x in enumerate(a):
            if x == t:
                return i
        return -1
    idx, comps = _measure(idx_only, [5, 3, 9], 9)
    assert idx == 2 and comps == 3
