"""Tests for the team's data structures and algorithms (algorithms/). Each audit finding has a test."""
import math
import random

import pytest

from algorithms.greedy_scheduler import earliest_free_start, pick_charger_greedy, suggest_alternatives
from algorithms.hash_table import HashTable
from algorithms.interval_utils import intervals_overlap, minutes_to_time, time_to_minutes
from algorithms.queue import Queue
from algorithms.searching import (binary_search, binary_search_trace, insertion_point, is_sorted,
                                  sequential_search)
from algorithms.sorting import merge_sort, merge_sort_with_stats
from algorithms.stack import Stack
from models.exceptions import UnsortedDataError, ValidationError


# ------------------------------------------------------------------ Stack
def test_stack_is_lifo_and_safe_when_empty():
    s = Stack()
    assert s.is_empty() and s.pop() is None and s.peek() is None
    for i in (1, 2, 3):
        s.push(i)
    assert s.peek() == 3 and [s.pop(), s.pop(), s.pop()] == [3, 2, 1] and s.is_empty()


# ------------------------------------------------------------------ Queue
def test_queue_is_fifo_with_positions():
    q = Queue()
    assert q.dequeue() is None and q.peek() is None and q.is_empty()
    assert [q.enqueue(x) for x in "abc"] == [1, 2, 3]
    assert q.peek() == "a" and q.position_of(lambda x: x == "c") == 3 and q.position_of(lambda x: x == "z") is None
    assert q.dequeue() == "a" and q.to_list() == ["b", "c"] and len(q) == 2


def test_queue_remove_from_middle_keeps_order():
    q = Queue()
    for i in range(5):
        q.enqueue(i)
    assert q.remove_where(lambda x: x == 2) == 2 and q.remove_where(lambda x: x == 99) is None
    assert q.to_list() == [0, 1, 3, 4]


def test_queue_compaction_after_many_dequeues():
    q = Queue()
    for i in range(200):
        q.enqueue(i)
    out = [q.dequeue() for _ in range(150)]
    assert out == list(range(150)) and q.to_list() == list(range(150, 200)) and len(q._items) <= 100


# ------------------------------------------------------------------ Hash table (audit #3)
def _colliding_pair(size=64):
    seen = {}
    for i in range(10_000):
        k = f"AC-{i}"
        slot = HashTable(size).hash(k)
        if slot in seen:
            return seen[slot], k
        seen[slot] = k


def test_hash_table_keeps_both_values_on_collision():
    """Audit #3: the original table overwrote the first key. Here two keys in one bucket both survive."""
    k1, k2 = _colliding_pair()
    h = HashTable(64)
    assert h.hash(k1) == h.hash(k2)
    h.put(k1, "one"); h.put(k2, "two")
    assert h.get(k1) == "one" and h.get(k2) == "two" and h.collisions == 1 and len(h) == 2
    assert h.stats()["longest_chain"] == 2


def test_tiny_table_resizes_instead_of_overloading():
    h = HashTable(1)
    h.put("BK1", "one"); h.put("BK2", "two")
    assert h.get("BK1") == "one" and h.get("BK2") == "two" and h.size > 1


def test_hash_table_missing_key_is_none_not_zero():
    assert HashTable(8).get("nope") is None and HashTable(8).get("nope", "x") == "x"


def test_hash_table_update_remove_contains_len():
    h = HashTable(8)
    h.put(1, "a"); h.put(1, "b")
    assert len(h) == 1 and h.get(1) == "b" and 1 in h
    assert h.remove(1) == "b" and h.remove(1) is None and 1 not in h and len(h) == 0


def test_hash_table_resizes_and_keeps_everything():
    h = HashTable(2)
    for i in range(500):
        h.put(f"AC-{i}", i)
    assert len(h) == 500 and h.size > 2 and all(h.get(f"AC-{i}") == i for i in range(500))
    assert h.stats()["load_factor"] <= 0.75


def test_hash_function_is_deterministic_and_in_range():
    a, b = HashTable(64), HashTable(64)
    assert all(a.hash(k) == b.hash(k) and 0 <= a.hash(k) < 64 for k in ("AC-101", 7, "x"))
    with pytest.raises(ValueError):
        HashTable(0)


def test_hash_table_distributes_realistic_ids():
    h = HashTable(64)
    for i in range(101, 160):
        h.put(f"AC-{i}", i)
    assert h.stats()["longest_chain"] <= 5


# ------------------------------------------------------------------ Merge sort
@pytest.mark.parametrize("seed", range(5))
def test_merge_sort_matches_builtin(seed):
    rng = random.Random(seed)
    data = [rng.randint(0, 50) for _ in range(rng.randint(0, 200))]
    assert merge_sort(data)[0] == sorted(data) and merge_sort(data, reverse=True)[0] == sorted(data, reverse=True)


def test_merge_sort_is_stable_and_uses_key():
    data = [("b", 1), ("a", 1), ("c", 0)]
    assert [x[0] for x in merge_sort(data, key=lambda x: x[1])[0]] == ["c", "b", "a"]


def test_merge_sort_comparison_bound_and_edge_cases():
    data = list(range(1000, 0, -1))
    out, comps = merge_sort(data)
    assert out == sorted(data) and comps <= 1000 * math.ceil(math.log2(1000))
    assert merge_sort([]) == ([], 0) and merge_sort([5]) == ([5], 0)
    assert data == list(range(1000, 0, -1))                 # input is not modified


def test_merge_sort_stats_counts_recursive_calls():
    r = merge_sort_with_stats([5, 2, 9, 1, 7])
    assert r["sorted"] == [1, 2, 5, 7, 9] and r["recursive_calls"] == 9 and r["comparisons"] > 0


# ------------------------------------------------------------------ Searching
def test_sequential_search_on_unsorted_data():
    assert sequential_search([9, 4, 7, 1], 7) == (2, 3) and sequential_search([9, 4], 5) == (-1, 2)
    assert sequential_search([], 1) == (-1, 0)


def test_binary_search_matches_membership_and_is_logarithmic():
    data = list(range(0, 4000, 2))
    worst = max(binary_search(data, t, check_sorted=False)[1] for t in range(-1, 4001))
    assert worst <= math.floor(math.log2(len(data))) + 1
    assert binary_search(data, 1234)[0] == 617 and binary_search(data, 1235)[0] == -1


def test_binary_search_refuses_unsorted_data():
    with pytest.raises(UnsortedDataError, match="sorted"):
        binary_search([3, 1, 2], 2)
    with pytest.raises(ValueError):                                  # also a ValueError
        binary_search_trace([2, 1], 1)


def test_binary_search_edge_cases_and_key():
    assert binary_search([], 1) == (-1, 0) and binary_search([5], 5) == (0, 1)
    rows = [{"id": 1}, {"id": 4}, {"id": 9}]
    assert binary_search(rows, 4, key=lambda r: r["id"])[0] == 1 and is_sorted(rows, lambda r: r["id"])


def test_insertion_point():
    assert insertion_point([1, 3, 5, 7], 4)[0] == 2 and insertion_point([1, 3, 5], 0)[0] == 0
    assert insertion_point([1, 3, 5], 9)[0] == 3 and insertion_point([], 1)[0] == 0
    assert insertion_point([1, 3, 3, 5], 3)[0] == 1                  # first position with key >= target


def test_trace_ends_on_found():
    steps = binary_search_trace([1, 3, 5, 7, 9], 7)
    assert steps[-1]["action"] == "found" and len(steps) <= 3


# ------------------------------------------------------------------ Overlap rule (audit #2)
@pytest.mark.parametrize("a,b,expected", [
    ((600, 660), (630, 690), True),      # partial overlap  - the old code said False
    ((600, 720), (630, 660), True),      # one inside the other - the old code said False
    ((600, 660), (600, 660), True),      # identical
    ((600, 660), (660, 720), False),     # back to back is allowed
    ((600, 660), (700, 760), False),
])
def test_overlap_rule_from_the_project_plan(a, b, expected):
    assert intervals_overlap(*a, *b) is expected and intervals_overlap(*b, *a) is expected


def test_time_helpers_and_regex_validation():
    assert time_to_minutes("08:30") == 510 and minutes_to_time(510) == "08:30"
    for bad in ("8:30", "24:00", "12:60", "ab:cd", ""):
        with pytest.raises(ValidationError):
            time_to_minutes(bad)


# ------------------------------------------------------------------ Greedy
def test_earliest_free_start_cases():
    assert earliest_free_start([], 600, 60, 1440) == 600
    assert earliest_free_start([(600, 660, 1)], 600, 60, 1440) == 660            # pushed after
    assert earliest_free_start([(660, 720, 1)], 600, 60, 1440) == 600            # ends exactly at next start
    assert earliest_free_start([(660, 720, 1)], 600, 61, 1440) == 720
    assert earliest_free_start([(600, 660, 1), (700, 760, 2)], 600, 30, 1440) == 660     # fits the gap
    assert earliest_free_start([(600, 660, 1), (680, 760, 2)], 600, 30, 1440) == 760     # gap too small
    assert earliest_free_start([], 1400, 60, 1440) is None                                # after closing


CHS = [{"charger_id": "AC-101", "charger_power_kw": 22}, {"charger_id": "DC-201", "charger_power_kw": 120}]


def test_greedy_prefers_faster_charger_on_tie_and_respects_max_shift():
    assert pick_charger_greedy(CHS, lambda c: [], 600, 60, 1440).charger_id == "DC-201"
    busy = lambda c: [(600, 660, 1)]
    assert pick_charger_greedy(CHS, busy, 600, 60, 1440, max_shift=0) is None
    assert pick_charger_greedy(CHS, busy, 600, 60, 1440, max_shift=60).start_min == 660
    assert pick_charger_greedy(CHS, lambda c: [(600, 660, 1)] if c == "DC-201" else [], 600, 60, 1440).charger_id == "AC-101"


def test_suggest_alternatives_are_distinct_and_earliest_first():
    alts = suggest_alternatives(CHS[:1], lambda c: [(600, 660, 1)], 600, 60, 1440, n=3)
    assert [a.start_min for a in alts] == [660, 675, 690] and alts[0].wait_min == 60
