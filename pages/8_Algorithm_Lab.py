import pandas as pd
import streamlit as st

from algorithms.hash_table import HashTable
from algorithms.searching import binary_search_trace
from analytics import algorithm_lab as L
from analytics import charts as C
from analytics import scheduling_optimizer as SO
from core.state import get_app, require_page

require_page("lab")
app = get_app()
st.title("Algorithm Lab")
st.caption("Every algorithm in the project is written by the team (no built-in sort/search in the required parts). "
        "This page measures them on the real data.")
t_hash, t_stack, t_sort, t_search, t_greedy = st.tabs(["Hash table", "Stack & Queue", "Sorting", "Searching", "Greedy"])

with t_hash:
    st.write("**Where it is used:** ID registries for stations, chargers and bookings (`algorithms/hash_table.py`). "
            "Separate chaining, own hash function, automatic resize.")
    rows = [("Stations", app.stations.station_index), ("Chargers", app.stations.charger_index),
            ("Bookings", app.bookings._by_id)]
    st.dataframe(pd.DataFrame([{"Registry": n, **t.stats()} for n, t in rows]), hide_index=True, width="stretch")
    st.subheader("Collision demo")
    keys = st.text_input("Keys (comma separated)", "AC-101, DC-201, AC-102, DC-202, AC-103, DC-203, AC-104")
    size = st.slider("Table size", 2, 16, 4)
    demo = HashTable(size)
    demo.size, demo.buckets = size, [[] for _ in range(size)]
    for k in [k.strip() for k in keys.split(",") if k.strip()]:
        b = demo.buckets[demo.hash(k)]
        demo.collisions += bool(b)
        b.append([k, 1])
    st.dataframe(pd.DataFrame({"bucket": range(size), "keys (chain)": [", ".join(k for k, _ in b) or "-" for b in demo.buckets]}),
                hide_index=True, width="stretch")
    st.caption(f"Collisions: {demo.collisions}. Keys in the same bucket are kept in a chain, so nothing is overwritten "
            "(the original version lost one of them).")

with t_stack:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Stack: admin undo history")
        acts = [f"{a['action']}" for a in reversed(app.stations.admin_stack.stack)]
        st.write(acts or "Empty. Make a change on the Stations page, then come back.")
        st.caption("LIFO: the last change is the first one undone.")
    with c2:
        st.subheader("Queue: waiting list")
        st.write([f"#{r['request_id']} {r['driver_id']}" for r in app.waiting.queue] or "Empty.")
        st.caption("FIFO: the driver who waited longest is promoted first when a slot frees up.")

with t_sort:
    sizes = st.multiselect("Sizes", [100, 500, 1000, 2000, 4000], default=[100, 500, 1000, 2000])
    if sizes and st.button("Run sorting experiment"):
        st.session_state["sort_df"] = L.sorting_experiment(tuple(sorted(sizes)))
    if "sort_df" in st.session_state:
        df = st.session_state["sort_df"]
        import plotly.express as px
        fig = px.line(df, x="size", y="comparisons", color="algorithm", markers=True, log_y=True)
        fig.update_layout(title="Comparisons: Merge Sort vs Bubble Sort (log scale)", height=360)
        st.plotly_chart(fig, width="stretch")
        st.dataframe(df, hide_index=True, width="stretch")

with t_search:
    n = len(app.bookings.bookings)
    st.write(f"Find one booking among **{n:,}** by its ID: sequential scan, binary search (IDs are sorted) and hash lookup.")
    bid = st.number_input("Booking ID", 1, max(n, 1), min(n, 20000))
    res = L.lookup_experiment(app.bookings.bookings, int(bid), app.bookings._by_id)
    st.dataframe(pd.DataFrame([{"method": k, **res[k]} for k in ("sequential", "binary", "hash")]), hide_index=True, width="stretch")
    st.caption(f"The booking service also uses binary search on every booking: it checks overlaps against the sorted busy list "
                f"of one charger/day ({app.bookings.search_comparisons:,} comparisons so far).")
    items = st.text_input("Binary search trace on numbers", "3, 8, 15, 21, 34, 42, 57, 63, 78, 91")
    tgt = st.number_input("Search for", value=42, step=1)
    try:
        nums = [int(x) for x in items.split(",") if x.strip()]
        st.dataframe(pd.DataFrame(binary_search_trace(nums, int(tgt))), hide_index=True, width="stretch")
    except ValueError as e:
        st.error("Binary search needs sorted whole numbers: " + str(e))

with t_greedy:
    st.write("**Greedy rule (`algorithms/greedy_scheduler.py`):** earliest free start on the compatible charger that "
            "can start soonest. Fast and simple, but it never reconsiders earlier choices.")
    reqs, ch = SO.counter_example()
    summary, _ = SO.compare_strategies(reqs, ch, close_min=1440, max_wait=1000, include_optimal=True)
    st.write("Counter-example (one charger, a long session booked first, two short ones after it):")
    st.dataframe(summary[["strategy", "total_wait_min", "avg_wait_min", "max_wait_min"]], hide_index=True, width="stretch")
    st.caption("See Admin Analytics → Scheduling optimizer for the same comparison on a real busy day.")
