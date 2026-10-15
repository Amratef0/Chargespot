"""Admin Analytics dashboard (Member 4)."""
import json

import pandas as pd
import streamlit as st

from ai.analytics_assistant import SUGGESTIONS, AnalyticsAssistant
from ai.forecast import ForecastError, forecast_demand
from ai.llm_wording import default_client, rephrase
from ai.predictive_maintenance import (MaintenanceError, assess_chargers,
                                       evaluate_against_truth, inspection_list)
from analytics import charts as C
from analytics import insights as I
from analytics import metrics as M
from analytics.cleaning import (CleaningError, clean_bookings,
                                compare_with_manifest)
from analytics.search_experiment import (binary_search_trace, get_search_functions,
                                         is_sorted, run_search_experiment)
from analytics import scheduling_optimizer as SO
from core.data_store import DATA_DIR, load_health_truth, messy_path
from core.state import get_data, require_page

st.title("Admin Analytics")

require_page("analytics")

data = get_data()
stations, chargers = data["stations"], data["chargers"]


# ------------------------------------------------------------------ cached helpers
@st.cache_data(show_spinner=False)
def clean_cached(raw: pd.DataFrame, stations_df: pd.DataFrame):
    return clean_bookings(raw, stations_df)


@st.cache_data(show_spinner="Training the demand model...")
def forecast_cached(bookings_df: pd.DataFrame):
    return forecast_demand(bookings_df)


def read_manifest():
    p = DATA_DIR / "messy_defects_manifest.json"
    return json.loads(p.read_text())["injected"] if p.exists() else None


# ------------------------------------------------------------------ data source
st.sidebar.header("Data & filters")
source = st.sidebar.radio("Data source", ["Project dataset (clean)",
                                          "Raw messy file (auto-cleaned)",
                                          "Upload my own bookings CSV"])
report = None
if source == "Project dataset (clean)":
    bookings_all = data["bookings"]
elif source == "Raw messy file (auto-cleaned)":
    raw = pd.read_csv(messy_path(), dtype=str)
    bookings_all, report = clean_cached(raw, stations)
else:
    up = st.sidebar.file_uploader("Bookings CSV (see docs/SCHEMA.md)", type="csv")
    if up is None:
        st.info("Upload a bookings CSV in the sidebar. It will be cleaned automatically.")
        st.stop()
    try:
        bookings_all, report = clean_cached(pd.read_csv(up, dtype=str), stations)
    except CleaningError as e:
        st.error(f"Cannot use this file: {e}")
        st.stop()
    except Exception as e:                                   # unreadable / wrong format
        st.error(f"Could not read the file ({type(e).__name__}). Is it a valid CSV?")
        st.stop()

sessions_all = data["sessions"]
sessions_all = sessions_all[sessions_all["booking_id"].isin(bookings_all["booking_id"])]

if bookings_all.empty:
    st.warning("The selected data source has no usable rows after cleaning.")
    st.stop()

dmin, dmax = bookings_all["start_time"].min().date(), bookings_all["start_time"].max().date()
rng = st.sidebar.date_input("Date range", value=(dmin, dmax), min_value=dmin, max_value=dmax)
if not isinstance(rng, (tuple, list)) or len(rng) != 2:
    st.info("Pick an end date to apply the date filter.")
    st.stop()
names = stations.set_index("station_id")["name"].to_dict()
sel_names = st.sidebar.multiselect("Stations", list(names.values()), default=list(names.values()))
sel_ids = [k for k, v in names.items() if v in sel_names]
conns = st.sidebar.multiselect("Connector types", ["CCS2", "CHAdeMO", "Type 2"],
                               default=["CCS2", "CHAdeMO", "Type 2"])

bookings, sessions = M.filter_period(bookings_all, sessions_all, rng[0], rng[1], sel_ids, conns)
if bookings.empty:
    st.warning("No bookings match the current filters. Widen the date range or select more stations.")
    st.stop()

ch_sel = chargers[chargers["station_id"].isin(sel_ids)]
st_sel = stations[stations["station_id"].isin(sel_ids)]
util = M.station_utilization(sessions, ch_sel, st_sel, rng[0], rng[1])
kpi = M.kpi_summary(bookings, sessions, ch_sel, st_sel, rng[0], rng[1])

(tab_over, tab_dem, tab_st, tab_dq, tab_alg, tab_ai, tab_sch, tab_mnt) = st.tabs(
    ["Overview", "Demand over time", "Stations & map", "Data quality", "Algorithms", "AI",
     "Scheduling optimizer", "Predictive maintenance"])

# ------------------------------------------------------------------ overview
with tab_over:
    c = st.columns(4)
    c[0].metric("Bookings", f"{kpi['total_bookings']:,}")
    c[1].metric("Completion rate", f"{kpi['completion_rate_pct']}%")
    c[2].metric("Cancellation rate", f"{kpi['cancellation_rate_pct']}%")
    c[3].metric("Network utilization", f"{kpi['network_utilization_pct']}%")
    c = st.columns(4)
    c[0].metric("Peak hour", f"{kpi['peak_hour']:02d}:00")
    c[1].metric("Avg waiting time", f"{kpi['avg_wait_min']} min",
                help="Average over bookings that joined the waiting list")
    c[2].metric("Avg start delay", f"{kpi['avg_delay_min']} min")
    c[3].metric("Revenue (simulated)", f"{kpi['revenue_egp']:,.0f} EGP")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Key insights")
        for ins in I.generate_insights(bookings, sessions, st_sel, ch_sel, rng[0], rng[1]):
            box = {"warning": st.warning, "success": st.success}.get(ins.level, st.info)
            box(f"**{ins.title}.** {ins.text}")
    with right:
        st.plotly_chart(C.status_distribution(bookings), width="stretch")

    kpi_df = pd.DataFrame({"metric": list(kpi.keys()), "value": list(kpi.values())})
    st.download_button("⬇️ Download KPI summary (CSV)", kpi_df.to_csv(index=False),
                       "chargespot_kpis.csv", "text/csv")

# ------------------------------------------------------------------ demand
with tab_dem:
    a, b = st.columns(2)
    a.plotly_chart(C.bookings_by_hour(bookings), width="stretch")
    b.plotly_chart(C.weekday_demand(bookings), width="stretch")
    st.plotly_chart(C.demand_heatmap(bookings), width="stretch")
    st.plotly_chart(C.daily_trend(bookings), width="stretch")
    with st.expander("Weekly totals (table)"):
        st.dataframe(M.weekly_demand(bookings), hide_index=True, width="stretch")

# ------------------------------------------------------------------ stations
with tab_st:
    st.plotly_chart(C.utilization_by_station(util), width="stretch")
    sb = M.station_booking_stats(bookings, st_sel)
    a, b = st.columns(2)
    a.plotly_chart(C.station_comparison(sb, "cancellation_rate_pct", "Cancellation rate by station", "%"),
                   width="stretch")
    b.plotly_chart(C.station_comparison(sb, "avg_wait_min", "Average waiting time by station", "minutes"),
                   width="stretch")
    st.subheader("Station map")
    mp = util.merge(stations[["station_id", "lat", "lon"]], on="station_id")
    mp["size"] = 200 + mp["utilization_pct"] * 25
    st.map(mp, latitude="lat", longitude="lon", size="size")
    st.caption("Bubble size = utilization.")
    st.subheader("Station comparison table")
    table = util[["name", "city", "active_chargers", "sessions", "utilization_pct",
                  "energy_kwh", "revenue_egp", "avg_delay_min"]].merge(
        sb[["name", "cancellation_rate_pct", "avg_wait_min"]], on="name")
    st.dataframe(table, hide_index=True, width="stretch")
    st.download_button("⬇️ Download station table (CSV)", table.to_csv(index=False),
                       "chargespot_stations.csv", "text/csv")

# ------------------------------------------------------------------ data quality
with tab_dq:
    st.subheader("Cleaning report")
    st.caption("Raw file with deliberately injected defects -> cleaned with `analytics/cleaning.py`.")
    shown = report
    if shown is None:                                       # always show the messy-file evidence
        shown = clean_cached(pd.read_csv(messy_path(), dtype=str), stations)[1]
    c = st.columns(4)
    c[0].metric("Rows before", f"{shown.rows_before:,}")
    c[1].metric("Rows after", f"{shown.rows_after:,}")
    c[2].metric("Rows removed", f"{shown.rows_removed:,}")
    c[3].metric("Retention", f"{shown.retention_pct:.1f}%")
    rf = shown.to_frame()
    if rf.empty:
        st.success("No defects found - the data was already clean.")
    else:
        a, b = st.columns([2, 3])
        a.dataframe(rf, hide_index=True, width="stretch")
        b.plotly_chart(C.defects_chart(rf), width="stretch")
    man = read_manifest()
    if man and source == "Raw messy file (auto-cleaned)":
        st.subheader("Validation against the known injected defects")
        cmp_df = compare_with_manifest(shown, man)
        st.dataframe(cmp_df, hide_index=True, width="stretch")
        if cmp_df["match"].all():
            st.success("Every injected defect type was detected exactly.")
    st.subheader("Cleaned bookings (sample)")
    st.dataframe(bookings_all.head(50), hide_index=True, width="stretch")
    st.download_button("⬇️ Download cleaned bookings (CSV)", bookings_all.to_csv(index=False),
                       "bookings_cleaned.csv", "text/csv")

# ------------------------------------------------------------------ algorithms
with tab_alg:
    st.subheader("Sequential vs binary search")
    _, _, src = get_search_functions()
    st.caption(f"Implementation in use: **{src}**. Sequential runs on unsorted data, "
               "binary search only on sorted data.")
    a, b = st.columns([2, 1])
    sizes = a.multiselect("Dataset sizes", [100, 500, 1000, 5000, 10000, 50000],
                          default=[100, 1000, 10000])
    trials = b.slider("Searches per size", 50, 500, 200, 50)
    if st.button("Run experiment", disabled=not sizes):
        st.session_state["search_df"] = run_search_experiment(tuple(sorted(sizes)), trials)
    if "search_df" in st.session_state:
        sdf = st.session_state["search_df"]
        st.plotly_chart(C.search_comparison(sdf), width="stretch")
        st.dataframe(sdf, hide_index=True, width="stretch")

    st.subheader("Trace binary search step by step")
    txt = st.text_input("Numbers (comma separated)", "3, 8, 15, 21, 34, 42, 57, 63, 78, 91")
    target = st.number_input("Search for", value=42, step=1)
    try:
        items = [int(x) for x in txt.split(",") if x.strip()]
        if not items:
            st.info("Enter at least one number.")
        elif not is_sorted(items):
            st.error("Binary search requires SORTED data - this list is not sorted, so the search is refused. "
                     "Use sequential search instead.")
        else:
            steps = binary_search_trace(items, int(target))
            st.dataframe(pd.DataFrame(steps), hide_index=True, width="stretch")
            found = steps[-1]["action"] == "found"
            (st.success if found else st.warning)(
                f"{'Found' if found else 'Not found'} after {len(steps)} comparison(s); "
                f"sequential search would need up to {len(items)}.")
    except ValueError:
        st.error("Please enter whole numbers separated by commas, e.g. 3, 8, 15.")

# ------------------------------------------------------------------ AI
with tab_ai:
    st.subheader("Demand prediction")
    st.caption("Predicts bookings per station per hour. Compared with simple baselines on the last "
               "14 days that the model never saw. Data is simulated, so accuracy is illustrative only.")
    if st.button("Train & forecast"):
        st.session_state["fc_requested"] = True
    if st.session_state.get("fc_requested"):
        try:
            fc = forecast_cached(bookings)
        except ForecastError as e:
            st.warning(str(e))
        else:
            st.dataframe(fc.metrics, hide_index=True, width="stretch")
            best = fc.metrics.loc[fc.metrics["MAE"].idxmin(), "method"]
            st.info(f"Lowest error on the hold-out period: **{best}**. Differences are small when "
                    "the data is mostly random noise - that is expected and honest.")
            sid = st.selectbox("Station", sorted(fc.test_predictions["station_id"].unique()),
                               format_func=lambda s: f"{s} - {names.get(s, s)}")
            a, b = st.columns(2)
            a.plotly_chart(C.forecast_vs_actual(fc.test_predictions, sid), width="stretch")
            b.plotly_chart(C.forecast_next_days(fc.future, sid), width="stretch")
            with st.expander("What drives the prediction? (permutation importance)"):
                st.dataframe(fc.importances, hide_index=True, width="stretch")
            st.caption(fc.note)

    st.divider()
    st.subheader("Analytics assistant (rule-based, offline)")
    st.caption("Answers only from computed numbers. English or Arabic.")
    asst = AnalyticsAssistant(bookings, sessions, st_sel, ch_sel)
    llm_client = default_client()
    use_llm = st.checkbox("Reword answers with an LLM (optional; numbers are verified)", value=False,
                          disabled=llm_client is None,
                          help="Only the question and the already-computed answer text are sent - no booking rows.")
    if llm_client is None:
        st.caption("LLM wording is off: set the ANTHROPIC_API_KEY environment variable or "
                   "`.streamlit/secrets.toml` to enable it. The rule-based answers work without it.")
    question = None
    cols = st.columns(3)
    for i, s in enumerate(SUGGESTIONS[:3]):
        if cols[i].button(s, key=f"sugg{i}"):
            question = s
    typed = st.chat_input("Ask about demand, stations, cancellations...")
    question = typed or question
    if question:
        answer, note = asst.ask(question), ""
        if use_llm:
            with st.spinner("Rewording..."):
                rr = rephrase(answer, question, llm_client)
            answer = rr.text
            note = "✨ reworded by LLM - numbers verified" if rr.used_llm else f"ℹ️ original answer shown ({rr.reason})"
        st.session_state["chat"].append({"role": "user", "content": question})
        st.session_state["chat"].append({"role": "assistant", "content": answer, "note": note})
    for m in st.session_state["chat"][-10:]:
        with st.chat_message(m["role"]):
            st.write(m["content"])
            if m.get("note"):
                st.caption(m["note"])


# ------------------------------------------------------------------ scheduling optimizer
with tab_sch:
    st.subheader("Batch re-planning: can a smarter order reduce waiting?")
    st.caption("Takes all requests of one station-day and places them with different ORDERING strategies. "
               "Cost = total wait + max-wait penalty for every driver turned away. "
               "Offline analysis: it assumes all requests are known in advance, so real-time gains would be smaller.")
    a, b, c = st.columns(3)
    sch_sid = a.selectbox("Station", sel_ids, format_func=lambda x: names.get(x, x), key="sch_station")
    sb_days = bookings[bookings["station_id"] == sch_sid]["start_time"].dt.normalize()
    if sb_days.empty:
        st.info("No bookings for this station in the current filters.")
    else:
        day_counts = sb_days.value_counts()
        days_sorted = sorted(day_counts.index)
        sch_day = b.selectbox("Day", days_sorted, index=days_sorted.index(day_counts.idxmax()),
                              format_func=lambda x: f"{x.date()} ({day_counts[x]} bookings)", key="sch_day")
        max_wait = c.slider("Longest wait a driver accepts (min)", 30, 180, 90, 15, key="sch_wait")
        close_min = int(stations.set_index("station_id").loc[sch_sid, "close_hour"]) * 60
        reqs = SO.requests_from_bookings(bookings, sch_sid, sch_day)
        chs = SO.chargers_for_station(chargers, sch_sid)
        if not reqs or not chs:
            st.info("No schedulable requests for this station and day.")
        else:
            summary, plans = SO.compare_strategies(reqs, chs, close_min, max_wait)
            fc = summary.set_index("strategy")
            best_name = summary.loc[summary["cost"].idxmin(), "strategy"]
            m = st.columns(4)
            m[0].metric("Requests", len(reqs))
            m[1].metric("Best strategy", best_name)
            m[2].metric("Cost saved vs FCFS", f"{fc.loc[best_name, 'cost_saved_vs_fcfs_pct']}%")
            m[3].metric("Drivers served (vs FCFS)", int(fc.loc[best_name, "served"]),
                        delta=int(fc.loc[best_name, "served"] - fc.loc["fcfs", "served"]))
            left, right = st.columns([3, 2])
            left.plotly_chart(C.scheduling_cost(summary), width="stretch")
            right.dataframe(summary, hide_index=True, width="stretch")
            pick = st.selectbox("Show timeline of", list(plans), index=list(plans).index(best_name))
            pf = SO.plan_to_frame(plans[pick], sch_day)
            if pf.empty:
                st.info("This plan serves no requests.")
            else:
                st.plotly_chart(C.schedule_timeline(pf, f"{pick}: charger timeline, {sch_day.date()}"),
                                width="stretch")
            if plans[pick].unserved:
                st.caption(f"Unserved requests in this plan: {', '.join(plans[pick].unserved[:12])}"
                           f"{' ...' if len(plans[pick].unserved) > 12 else ''}")

            st.subheader("Exact solver on a small sample (backtracking)")
            st.caption(f"Exhaustive search over all request orders, limited to {SO.MAX_EXACT} requests "
                       "because it grows as n!. Shows how far the heuristics are from the best possible plan.")
            if st.button("Run exact solver on 7 random requests from this day"):
                import random as _r
                sample = _r.Random(len(reqs)).sample(reqs, min(7, len(reqs)))
                ex_sum, _ = SO.compare_strategies(sample, chs, close_min, max_wait, include_optimal=True)
                st.session_state["exact_demo"] = ex_sum
            if "exact_demo" in st.session_state:
                st.dataframe(st.session_state["exact_demo"], hide_index=True, width="stretch")

        st.subheader("Why greedy (FCFS) is not always optimal")
        ce_reqs, ce_ch = SO.counter_example()
        ce_sum, _ = SO.compare_strategies(ce_reqs, ce_ch, close_min=1440, max_wait=1000, include_optimal=True)
        f_cost = int(ce_sum.set_index("strategy").loc["fcfs", "total_wait_min"])
        o_cost = int(ce_sum.set_index("strategy").loc["optimal", "total_wait_min"])
        st.write(f"One charger, three drivers who all want to start at 10:00: a 120-min session that booked first "
                 f"and two 30-min sessions. First-come-first-served makes the short ones wait → **{f_cost} min** "
                 f"of total waiting. Serving the short ones first needs only **{o_cost} min**.")
        st.dataframe(ce_sum[["strategy", "total_wait_min", "avg_wait_min", "max_wait_min"]],
                     hide_index=True, width="stretch")

# ------------------------------------------------------------------ predictive maintenance
with tab_mnt:
    st.subheader("Which chargers should be inspected?")
    st.caption("Compares each charger's last 14 days with its own previous 30 days (power output, errors, "
               "temperature). **The readings are simulated, so results are illustrative only.** "
               "Ignores the date filter: always uses the latest readings.")
    health = data.get("charger_health")
    if health is None or health.empty:
        st.info("No charger health data available.")
    else:
        health_sel = health[health["charger_id"].isin(ch_sel["charger_id"])]
        try:
            assess = assess_chargers(health_sel, ch_sel, st_sel)
        except MaintenanceError as e:
            st.warning(str(e))
            st.stop()
        lv = assess["risk_level"].value_counts()
        m = st.columns(4)
        m[0].metric("🔴 High risk", int(lv.get("High", 0)))
        m[1].metric("🟠 Medium risk", int(lv.get("Medium", 0)))
        m[2].metric("🟢 Low risk", int(lv.get("Low", 0)))
        m[3].metric("Chargers assessed", len(assess))
        insp = inspection_list(assess)
        left, right = st.columns([3, 2])
        left.dataframe(insp[["charger_id", "station", "risk_level", "risk_score", "reasons"]]
                       if not insp.empty else insp, hide_index=True, width="stretch")
        if insp.empty:
            left.success("No charger needs inspection right now.")
        right.plotly_chart(C.risk_bar(assess), width="stretch")
        st.download_button("⬇️ Download inspection list (CSV)", insp.to_csv(index=False),
                           "inspection_list.csv", "text/csv")
        pick = st.selectbox("Look at one charger", assess["charger_id"].tolist())
        st.plotly_chart(C.health_timeseries(health_sel, pick), width="stretch")
        with st.expander("How good is the model? (evaluation against the simulation's ground truth)"):
            truth = load_health_truth()
            if truth is None:
                st.info("Ground-truth file not found.")
            else:
                ev = evaluate_against_truth(assess, truth)
                a, b = st.columns(2)
                a.metric("Precision", ev["precision"] if ev["precision"] is not None else "n/a")
                b.metric("Recall", ev["recall"] if ev["recall"] is not None else "n/a")
                st.dataframe(ev["confusion"], width="stretch")
                st.dataframe(ev["by_class"], width="stretch")
                st.caption("The data was generated to match the model's assumptions, so high scores here do "
                           "not prove real-world accuracy. On 60 simulated fleets: medium-risk threshold 20 caught "
                           "all degrading chargers with ~2% false alarms; threshold 30 would have missed ~13%.")
