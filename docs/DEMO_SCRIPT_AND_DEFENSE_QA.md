# Demo script (8-10 min) and defense questions

Open **three browser windows** (or log out/in): Driver `ahmed@gmail.com`, Operator, Administrator (passwords in the README).
Each member presents the part they own; everyone must be able to answer about any part.

## Flow
| Min | Who | Do this | Show / say |
|---|---|---|---|
| 0:00 | M4 | Problem, three roles, login | drivers waste trips; operators juggle manually; admins need data |
| 1:00 | M2 | Driver → **Smart Recommendation**, then **Bookings**: area *Nasr City*, tomorrow 10:00, 60 min → station list → **Confirm** | nearest available station first (greedy); booking saved to CSV |
| 2:00 | M2 | Book the **same slot** with the second account until full → alternatives → **Join the waiting list** | overlap rule, greedy alternatives, queue position |
| 3:00 | M2 | Cancel the first booking | the waiting driver is promoted automatically (FIFO Queue) |
| 4:00 | M3 | Operator → **Sessions**: pick tomorrow, **Start** (simulated time 10:10), then **Complete** | planned vs actual (delay 10 min), charger Occupied → Available, energy, history sorted by Merge Sort (comparison count) |
| 5:00 | M3 | Driver → **Driver Dashboard**: battery monitor, then type a target below the current % | estimates are labelled as estimates; validation message |
| 6:00 | M1 | Admin → **Stations**: search, filters, add a charger, try to remove a **booked** charger (refused), **Undo** | Stack; rules; Algorithm Lab → hash registry stats |
| 7:00 | M4 | Admin → **Analytics**: Data quality (messy file, "every injected defect detected"), Overview insights, Demand heatmap, Scheduling tab | Pandas; generated insights; "greedy is not always optimal" (270 vs 90) |
| 8:30 | all | **Algorithm Lab**: lookup of one booking among 28 000: sequential vs binary vs hash; sorting experiment | evidence, not claims |

## Questions to expect
| Question | Answer |
|---|---|
| Why a Queue for the waiting list? | first come, first served: the driver who waited longest gets the freed slot; `Queue` has enqueue/dequeue in O(1). |
| What happens when a booking is cancelled? | status → Cancelled, the interval leaves the charger's busy list, the queue is scanned in FIFO order and every request that now fits is confirmed. |
| What is the overlap rule and why does it allow back-to-back? | `A.start < B.end and B.start < A.end`; a booking ending at 11:00 and another starting at 11:00 do not share time. |
| Where is binary search used? | on every booking: the busy intervals of a charger/day are sorted by start; binary search finds the insertion point and only the two neighbours can conflict. It refuses unsorted data. |
| Why a hash table here, and what if two IDs collide? | ID lookups; colliding keys stay in a chain in the same bucket (the first version overwrote them - we found and fixed that). |
| Why Merge Sort, not bubble sort? | n log n guaranteed and stable; 2 000 items: 19 452 vs 1 998 769 comparisons. |
| Why is greedy not always optimal? | it never reconsiders; a long session booked first can block several short ones (270 vs 90 minutes of waiting in the app). |
| How do you prevent a charger from being removed while booked? | `StationService.remove_charger_with_undo` asks the booking service for active bookings first. |
| What does the Stack store? | one record per admin action with what is needed to reverse it. |
| Where is Streamlit state handled? | `core/state.py`: `cache_resource` = one shared app saved to CSV after every change; `session_state` = who is logged in. |
| What happens with invalid input? | validators/exceptions turn it into a message (`run_action`); tests cover it. |
| How was AI-generated code validated? | 278 automated tests + hand calculations (see the AI log; fill your own). |
| What was wrong in the first version? | `docs/TEAM_AUDIT.md`: 20 findings; be ready to explain the ones in your module. |

## Individual-check practice (you may be asked to change code live)
* M1: add a new filter (e.g. by price) in `Station`; trace `HashTable.put` for two colliding keys.
* M2: change the minimum duration to 30 minutes (which constant, which test?); trace `earliest_free_start([(600,660,1)], 600, 60, 1440)`.
* M3: add a sort key `"charger"` to `sort_session_history`; trace `merge_sort([5,2,9,1])`.
* M4: add a new insight in `analytics/insights.py`; explain why utilization divides by days.
