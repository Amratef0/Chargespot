
import pandas as pd
import streamlit as st

from ai.analytics_assistant import SUGGESTIONS, AnalyticsAssistant
from ai.forecast import ForecastError, forecast_demand
from ai.llm_wording import default_client, rephrase
from ai.predictive_maintenance import (
    MaintenanceError,
    assess_chargers,
    evaluate_against_truth,
    inspection_list,
)
from analytics import charts as C
from analytics import insights as I
from analytics import metrics as M
from analytics.cleaning import CleaningError, clean_bookings
from core.data_store import load_health_truth, messy_path
from core.state import get_data, require_page


# ============================================================
# Page setup
# ============================================================

st.title("Admin Analytics")
require_page("analytics")

data = get_data()

stations = data["stations"]
chargers = data["chargers"]


# ============================================================
# Cached helpers
# ============================================================

@st.cache_data(show_spinner=False)
def clean_cached(raw: pd.DataFrame, stations_df: pd.DataFrame):
    return clean_bookings(raw, stations_df)


@st.cache_data(show_spinner="Training the demand model...")
def forecast_cached(bookings_df: pd.DataFrame):
    return forecast_demand(bookings_df)


# ============================================================
# Data source
# ============================================================

st.sidebar.header("Data & filters")

source = st.sidebar.radio(
    "Data source",
    [
        "Chargespot dataset",
    ],
)

report = None

if source == "Chargespot dataset":
    bookings_all = data["bookings"]

else:
    uploaded_file = st.sidebar.file_uploader(
        "Bookings CSV (see docs/SCHEMA.md)",
        type="csv",
    )

    if uploaded_file is None:
        st.info(
            "Upload a bookings CSV in the sidebar. "
            "It will be cleaned automatically."
        )
        st.stop()

    try:
        raw = pd.read_csv(uploaded_file, dtype=str)
        bookings_all, report = clean_cached(raw, stations)

    except CleaningError as error:
        st.error(f"Cannot use this file: {error}")
        st.stop()

    except Exception as error:
        st.error(
            f"Could not read the file ({type(error).__name__}). "
            "Is it a valid CSV?"
        )
        st.stop()


# ============================================================
# Prepare data
# ============================================================

sessions_all = data["sessions"]

sessions_all = sessions_all[
    sessions_all["booking_id"].isin(bookings_all["booking_id"])
]

if bookings_all.empty:
    st.warning("The selected data source has no usable rows after cleaning.")
    st.stop()


# ============================================================
# Filters
# ============================================================

dmin = bookings_all["start_time"].min().date()
dmax = bookings_all["start_time"].max().date()

date_range = st.sidebar.date_input(
    "Date range",
    value=(dmin, dmax),
    min_value=dmin,
    max_value=dmax,
)

if not isinstance(date_range, (tuple, list)) or len(date_range) != 2:
    st.info("Pick an end date to apply the date filter.")
    st.stop()


station_names = stations.set_index("station_id")["name"].to_dict()

selected_names = st.sidebar.multiselect(
    "Stations",
    list(station_names.values()),
    default=list(station_names.values()),
)

selected_station_ids = [
    station_id
    for station_id, name in station_names.items()
    if name in selected_names
]

connectors = st.sidebar.multiselect(
    "Connector types",
    ["CCS2", "CHAdeMO", "Type 2"],
    default=["CCS2", "CHAdeMO", "Type 2"],
)


bookings, sessions = M.filter_period(
    bookings_all,
    sessions_all,
    date_range[0],
    date_range[1],
    selected_station_ids,
    connectors,
)

if bookings.empty:
    st.warning(
        "No bookings match the current filters. "
        "Widen the date range or select more stations."
    )
    st.stop()


selected_chargers = chargers[
    chargers["station_id"].isin(selected_station_ids)
]

selected_stations = stations[
    stations["station_id"].isin(selected_station_ids)
]

utilization = M.station_utilization(
    sessions,
    selected_chargers,
    selected_stations,
    date_range[0],
    date_range[1],
)

kpis = M.kpi_summary(
    bookings,
    sessions,
    selected_chargers,
    selected_stations,
    date_range[0],
    date_range[1],
)


# ============================================================
# Navigation: 5 tabs only
# ============================================================

tab_over, tab_dem, tab_st, tab_ai, tab_mnt = st.tabs(
    [
        "Overview",
        "Demand over time",
        "Stations & map",
        "AI Insights",
        "Predictive maintenance",
    ]
)


# ============================================================
# 1. Overview
# ============================================================

with tab_over:
    metrics = st.columns(4)

    metrics[0].metric(
        "Bookings",
        f"{kpis['total_bookings']:,}",
    )

    metrics[1].metric(
        "Completion rate",
        f"{kpis['completion_rate_pct']}%",
    )

    metrics[2].metric(
        "Cancellation rate",
        f"{kpis['cancellation_rate_pct']}%",
    )

    metrics[3].metric(
        "Network utilization",
        f"{kpis['network_utilization_pct']}%",
    )

    metrics = st.columns(4)

    metrics[0].metric(
        "Peak hour",
        f"{kpis['peak_hour']:02d}:00",
    )

    metrics[1].metric(
        "Avg waiting time",
        f"{kpis['avg_wait_min']} min",
        help="Average over bookings that joined the waiting list",
    )

    metrics[2].metric(
        "Avg start delay",
        f"{kpis['avg_delay_min']} min",
    )

    metrics[3].metric(
        "Revenue (simulated)",
        f"{kpis['revenue_egp']:,.0f} EGP",
    )

    left, right = st.columns([3, 2])

    with left:
        st.subheader("Key insights")

        insights = I.generate_insights(
            bookings,
            sessions,
            selected_stations,
            selected_chargers,
            date_range[0],
            date_range[1],
        )

        for insight in insights:
            message = f"**{insight.title}.** {insight.text}"

            if insight.level == "warning":
                st.warning(message)
            elif insight.level == "success":
                st.success(message)
            else:
                st.info(message)

    with right:
        st.plotly_chart(
            C.status_distribution(bookings),
            width="stretch",
        )

    kpi_df = pd.DataFrame(
        {
            "metric": list(kpis.keys()),
            "value": list(kpis.values()),
        }
    )

    st.download_button(
        "⬇️ Download KPI summary (CSV)",
        kpi_df.to_csv(index=False),
        "chargespot_kpis.csv",
        "text/csv",
    )


# ============================================================
# 2. Demand over time
# ============================================================

with tab_dem:
    left, right = st.columns(2)

    left.plotly_chart(
        C.bookings_by_hour(bookings),
        width="stretch",
    )

    right.plotly_chart(
        C.weekday_demand(bookings),
        width="stretch",
    )

    st.plotly_chart(
        C.demand_heatmap(bookings),
        width="stretch",
    )

    st.plotly_chart(
        C.daily_trend(bookings),
        width="stretch",
    )

    with st.expander("Weekly totals"):
        st.dataframe(
            M.weekly_demand(bookings),
            hide_index=True,
            width="stretch",
        )


# ============================================================
# 3. Stations & map
# ============================================================

with tab_st:
    st.plotly_chart(
        C.utilization_by_station(utilization),
        width="stretch",
    )

    station_stats = M.station_booking_stats(
        bookings,
        selected_stations,
    )

    left, right = st.columns(2)

    left.plotly_chart(
        C.station_comparison(
            station_stats,
            "cancellation_rate_pct",
            "Cancellation rate by station",
            "%",
        ),
        width="stretch",
    )

    right.plotly_chart(
        C.station_comparison(
            station_stats,
            "avg_wait_min",
            "Average waiting time by station",
            "minutes",
        ),
        width="stretch",
    )

    st.subheader("Station map")

    map_data = utilization.merge(
        stations[["station_id", "lat", "lon"]],
        on="station_id",
    )

    map_data["size"] = 200 + map_data["utilization_pct"] * 25

    st.map(
        map_data,
        latitude="lat",
        longitude="lon",
        size="size",
    )

    st.caption("Bubble size = utilization.")

    st.subheader("Station comparison table")

    station_table = utilization[
        [
            "name",
            "city",
            "active_chargers",
            "sessions",
            "utilization_pct",
            "energy_kwh",
            "revenue_egp",
            "avg_delay_min",
        ]
    ].merge(
        station_stats[
            [
                "name",
                "cancellation_rate_pct",
                "avg_wait_min",
            ]
        ],
        on="name",
    )

    st.dataframe(
        station_table,
        hide_index=True,
        width="stretch",
    )

    st.download_button(
        "⬇️ Download station table (CSV)",
        station_table.to_csv(index=False),
        "chargespot_stations.csv",
        "text/csv",
    )


# ============================================================
# 4. AI Insights
# ============================================================

with tab_ai:
    st.subheader("Demand prediction")

    st.caption(
        "Predicts bookings per station per hour. "
        "Compared with simple baselines on the last 14 days "
        "that the model never saw. Data is simulated, so "
        "accuracy is illustrative only."
    )

    if st.button("Train & forecast"):
        st.session_state["fc_requested"] = True

    if st.session_state.get("fc_requested"):
        try:
            forecast_result = forecast_cached(bookings)

        except ForecastError as error:
            st.warning(str(error))

        else:
            station_ids = sorted(
                forecast_result.test_predictions["station_id"].unique()
            )

            if not station_ids:
                st.info("No station predictions are available.")

            else:
                selected_forecast_station = st.selectbox(
                    "Station",
                    station_ids,
                    format_func=lambda station_id: (
                        f"{station_id} - "
                        f"{station_names.get(station_id, station_id)}"
                    ),
                )

                left, right = st.columns(2)

                left.plotly_chart(
                    C.forecast_vs_actual(
                        forecast_result.test_predictions,
                        selected_forecast_station,
                    ),
                    width="stretch",
                )

                right.plotly_chart(
                    C.forecast_next_days(
                        forecast_result.future,
                        selected_forecast_station,
                    ),
                    width="stretch",
                )

    st.divider()

    st.subheader("Analytics assistant")

    st.caption(
        "Rule-based assistant that answers using computed numbers. "
        "Supports English and Arabic."
    )

    assistant = AnalyticsAssistant(
        bookings,
        sessions,
        selected_stations,
        selected_chargers,
    )

    llm_client = default_client()

    use_llm = st.checkbox(
        "Reword answers with an LLM (optional; numbers are verified)",
        value=False,
        disabled=llm_client is None,
        help=(
            "Only the question and the already-computed answer text "
            "are sent. No booking rows are sent."
        ),
    )

    if llm_client is None:
        st.caption(
            "LLM wording is disabled. Set ANTHROPIC_API_KEY in your "
            "environment or Streamlit secrets to enable it. "
            "Rule-based answers work without it."
        )

    if "chat" not in st.session_state:
        st.session_state["chat"] = []

    question = None

    suggestion_columns = st.columns(3)

    for index, suggestion in enumerate(SUGGESTIONS[:3]):
        if suggestion_columns[index].button(
            suggestion,
            key=f"analytics_suggestion_{index}",
        ):
            question = suggestion

    typed_question = st.chat_input(
        "Ask about demand, stations, cancellations..."
    )

    question = typed_question or question

    if question:
        answer = assistant.ask(question)
        note = ""

        if use_llm:
            with st.spinner("Rewording answer..."):
                result = rephrase(
                    answer,
                    question,
                    llm_client,
                )

            answer = result.text

            if result.used_llm:
                note = "✨ Reworded by LLM - numbers verified"
            else:
                note = (
                    f"ℹ️ Original answer shown ({result.reason})"
                )

        st.session_state["chat"].append(
            {
                "role": "user",
                "content": question,
            }
        )

        st.session_state["chat"].append(
            {
                "role": "assistant",
                "content": answer,
                "note": note,
            }
        )

    for message in st.session_state["chat"][-10:]:
        with st.chat_message(message["role"]):
            st.write(message["content"])

            if message.get("note"):
                st.caption(message["note"])


# ============================================================
# 5. Predictive maintenance
# ============================================================

with tab_mnt:
    st.subheader("Which chargers should be inspected?")

    st.caption(
        "Compares each charger's last 14 days with its own "
        "previous 30 days using power output, errors, and temperature. "
        "Readings are simulated, so results are illustrative only. "
        "This analysis uses the latest readings, independently "
        "of the selected date range."
    )

    health = data.get("charger_health")

    if health is None or health.empty:
        st.info("No charger health data available.")

    else:
        health_selected = health[
            health["charger_id"].isin(
                selected_chargers["charger_id"]
            )
        ]

        if health_selected.empty:
            st.info(
                "No charger health readings match the selected stations."
            )

        else:
            try:
                assessment = assess_chargers(
                    health_selected,
                    selected_chargers,
                    selected_stations,
                )

            except MaintenanceError as error:
                st.warning(str(error))

            else:
                risk_levels = assessment["risk_level"].value_counts()

                metrics = st.columns(4)

                metrics[0].metric(
                    "🔴 High risk",
                    int(risk_levels.get("High", 0)),
                )

                metrics[1].metric(
                    "🟠 Medium risk",
                    int(risk_levels.get("Medium", 0)),
                )

                metrics[2].metric(
                    "🟢 Low risk",
                    int(risk_levels.get("Low", 0)),
                )

                metrics[3].metric(
                    "Chargers assessed",
                    len(assessment),
                )

                inspection = inspection_list(assessment)

                left, right = st.columns([3, 2])

                with left:
                    columns = [
                        "charger_id",
                        "station",
                        "risk_level",
                        "risk_score",
                        "reasons",
                    ]

                    if not inspection.empty:
                        st.dataframe(
                            inspection[columns],
                            hide_index=True,
                            width="stretch",
                        )

                        st.download_button(
                            "⬇️ Download inspection list (CSV)",
                            inspection.to_csv(index=False),
                            "inspection_list.csv",
                            "text/csv",
                        )

                    else:
                        st.success(
                            "No charger needs inspection right now."
                        )

                with right:
                    st.plotly_chart(
                        C.risk_bar(assessment),
                        width="stretch",
                    )

                if not assessment.empty:
                    selected_charger = st.selectbox(
                        "Look at one charger",
                        assessment["charger_id"].tolist(),
                    )

                    st.plotly_chart(
                        C.health_timeseries(
                            health_selected,
                            selected_charger,
                        ),
                        width="stretch",
                    )