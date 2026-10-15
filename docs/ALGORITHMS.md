# Algorithm explanations (DRAFT - each owner must rewrite their part in their own words)

Format required by the plan: purpose · input · output · workflow · complexity · limitations · why this one.
Measured evidence (comparisons on real data): **Algorithm Lab** page.

| Algorithm | File | Owner |
|---|---|---|
| Stack | `algorithms/stack.py` | Member 1 |
| Hash table | `algorithms/hash_table.py` | Member 1 (rebuilt during integration: read it!) |
| Sequential search | `algorithms/searching.py`, `Station.sequential_search_by_name` | Member 1 |
| Queue | `algorithms/queue.py` | Member 2 (new in integration) |
| Binary search | `algorithms/searching.py` | Member 2 (new in integration) |
| Overlap rule | `algorithms/interval_utils.py` | Member 2 |
| Greedy scheduling | `algorithms/greedy_scheduler.py`, `services/scheduler.py` | Member 2 |
| Merge Sort | `algorithms/sorting.py` | Member 3 |

## Stack (LIFO)
* **Purpose:** undo the last administrator change (add/remove/edit station or charger, status change).
* **Input/output:** `push(record)`; `pop()` returns the newest record or `None`.
* **Workflow:** every admin action pushes a record with the data needed to reverse it; Undo pops and reverses.
* **Complexity:** push/pop O(1). **Limit:** only the newest change can be undone first; undo is refused if a removed charger's ID was re-used.
* **Why:** "last change first" is exactly LIFO; a list/queue would need extra logic.

## Hash table (separate chaining)
* **Purpose:** find a station, charger or booking by ID without scanning everything (ID registries).
* **Input/output:** `put(key, value)`; `get(key, default=None)`; `remove`; `stats()`.
* **Workflow:** hash(key) → bucket index; keys that land in the same bucket are kept in a chain; the table doubles when load factor > 0.75.
* **Complexity:** average O(1), worst case O(n) if everything collides. **Limit:** not sorted, no range queries.
* **Why:** lookups by ID happen on every action. Measured on 28 000 bookings (Lab page): finding booking #28 255 took 28 255 comparisons sequentially, 13 with binary search and 1 with the hash table.
* **Bug history:** the first version overwrote colliding keys and was unused (see `TEAM_AUDIT.md` #4).

## Sequential search
* **Purpose:** search data that is **not** sorted (station names typed by the user).
* **Workflow:** compare one item after another until a match. **Complexity:** O(n). **Limit:** slow on large data.
* **Why:** names are unsorted and the list is small (16 stations).

## Binary search
* **Purpose:** (1) check whether a new booking overlaps the existing ones of one charger on one day; (2) find a booking by its ID in the ID-ordered list.
* **Input/output:** sorted list, target, optional key → `(index or -1, comparisons)`; raises `UnsortedDataError` on unsorted input.
* **Workflow:** compare with the middle element and discard half each step. For overlaps: busy intervals of a charger/day are kept sorted by start; binary search finds where the new start would go; because intervals never overlap, only its two neighbours can conflict.
* **Complexity:** O(log n). **Limit:** only valid on sorted data (the code checks this and refuses otherwise).
* **Why:** a charger can have many bookings per day; scanning all of them on every request would be O(n).

## Overlap rule
`A.start < B.end and B.start < A.end` - two bookings conflict if each starts before the other ends; back-to-back bookings (A.end == B.start) are allowed. (The first version only detected identical times.)

## Queue (FIFO)
* **Purpose:** the waiting list: the driver who waited longest is served first.
* **Operations:** `enqueue` (returns the position), `dequeue`, `peek`, `position_of`, `remove_where` (a driver can cancel from the middle).
* **Complexity:** enqueue/dequeue O(1) amortised; position/remove O(n). **Limit:** removal from the middle is linear.
* **Promotion:** when a slot frees up (cancellation or session end) the queue is scanned in FIFO order; every request that now fits is confirmed, a request that still does not fit is skipped (it does not block the ones behind it).

## Greedy scheduling
* **Purpose:** give a driver an answer immediately: the earliest free start at or after the requested time, on the compatible charger that can start soonest (ties: faster charger).
* **Input/output:** chargers, busy intervals, desired start, duration, closing time → `SlotOption(charger, start, wait)` or `None`; alternatives = the next free start times.
* **Workflow:** for each charger walk its sorted busy intervals pushing the start after every blocking booking; pick the best charger.
* **Complexity:** O(chargers × bookings of the day). **Limit:** never reconsiders earlier decisions, so it is **not always optimal**: a long session booked first can force several short ones to wait (counter-example in the app: FCFS 270 min of waiting vs 90 min for the best order).
* **Alternatives compared** (`analytics/scheduling_optimizer.py`): shortest-first, earliest-desired-first, local search, and exact backtracking (≤ 8 requests). On the five busiest station-days of the current data the local search lowered the total cost by 12-32 % versus FCFS (offline analysis: assumes all requests are known, so it is an upper bound).
* **Why greedy anyway:** a driver cannot wait for a batch optimisation; the greedy answer is instant and simple to explain.
* **Station choice (Member 2's rule):** among stations with a free compatible charger, the nearest first (distance matrix `distances.json`).

## Merge Sort
* **Purpose:** order session history and booking lists by start time, duration or energy.
* **Input/output:** list, `key`, `reverse` → `(sorted_list, comparisons)`; `merge_sort_with_stats` also returns recursive calls.
* **Workflow:** split in halves, sort each recursively, merge the two sorted halves.
* **Complexity:** O(n log n) always; extra O(n) memory; stable (equal keys keep their order). **Limit:** needs extra memory.
* **Why:** guaranteed n log n; bubble sort needs about n²/2 comparisons (measured in the Lab: 2 000 items → 1 998 769 comparisons vs 19 452 for Merge Sort).
