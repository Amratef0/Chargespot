
from models.exceptions import UnsortedDataError


def sequential_search(items, target, key=lambda x: x):
    """Scan one by one. Works on unsorted data. O(n). Returns (index or -1, comparisons)."""
    comparisons = 0
    for i, item in enumerate(items):
        comparisons += 1
        if key(item) == target:
            return i, comparisons
    return -1, comparisons


def is_sorted(items, key=lambda x: x):
    return all(key(items[i]) <= key(items[i + 1]) for i in range(len(items) - 1))


def binary_search(items, target, key=lambda x: x, check_sorted=True):
    """Halve the range each step. ONLY valid on data sorted by `key`. O(log n).

    Raises UnsortedDataError instead of returning a wrong answer on unsorted input.
    Returns (index or -1, comparisons).
    """
    if check_sorted and not is_sorted(items, key):
        raise UnsortedDataError("binary_search requires sorted data")
    low, high, comparisons = 0, len(items) - 1, 0
    while low <= high:
        mid = (low + high) // 2
        comparisons += 1
        value = key(items[mid])
        if value == target:
            return mid, comparisons
        if value < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1, comparisons


def insertion_point(items, target, key=lambda x: x):
    """Binary search for the index where `target` must be inserted to keep `items` sorted
    (first position whose key is >= target). Returns (index, comparisons)."""
    low, high, comparisons = 0, len(items), 0
    while low < high:
        mid = (low + high) // 2
        comparisons += 1
        if key(items[mid]) < target:
            low = mid + 1
        else:
            high = mid
    return low, comparisons


def binary_search_trace(items, target, key=lambda x: x):
    """Step-by-step trace (for the demo): list of dicts."""
    if not is_sorted(items, key):
        raise UnsortedDataError("binary_search requires sorted data")
    steps, low, high = [], 0, len(items) - 1
    while low <= high:
        mid = (low + high) // 2
        v = key(items[mid])
        action = "found" if v == target else ("go right" if v < target else "go left")
        steps.append({"step": len(steps) + 1, "low": low, "mid": mid, "high": high,
                      "value_at_mid": v, "action": action})
        if v == target:
            break
        low, high = (mid + 1, high) if v < target else (low, mid - 1)
    return steps
