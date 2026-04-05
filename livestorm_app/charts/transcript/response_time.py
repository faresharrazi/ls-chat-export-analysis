import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_plotly_or_fallback


def render_response_time_chart(insights):
    st.markdown("**Response Time Between Speakers**")
    response_time_df = insights.get("response_time_df")
    if response_time_df is None or response_time_df.empty:
        st.info("Response timing is not available.")
        return
    response_summary = response_time_df.groupby("speaker_pair", as_index=False).agg(avg_gap_seconds=("gap_seconds", "mean"))
    fig = brand_bar_chart(
        response_summary,
        x_field="speaker_pair",
        y_field="avg_gap_seconds",
        x_title="Speaker pair",
        y_title="Avg response time (sec)",
        tooltip_fields=["speaker_pair", "avg_gap_seconds"],
    )
    render_plotly_or_fallback(fig, fallback_df=response_summary, fallback_columns=["speaker_pair", "avg_gap_seconds"])
