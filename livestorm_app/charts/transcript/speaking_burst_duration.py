import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_plotly_or_fallback


def render_speaking_burst_duration_chart(insights):
    st.markdown("**Speaking Duration Before Pause**")
    burst_df = insights.get("burst_df")
    if burst_df is None or burst_df.empty:
        st.info("Speaking burst data is not available.")
        return
    chart_df = burst_df[["start_label", "duration_seconds"]].copy()
    fig = brand_bar_chart(
        chart_df,
        x_field="start_label",
        y_field="duration_seconds",
        x_title="Burst start",
        y_title="Duration (sec)",
        tooltip_fields=["start_label", "duration_seconds"],
    )
    render_plotly_or_fallback(
        fig,
        fallback_df=chart_df,
        fallback_columns=["start_label", "duration_seconds"],
    )
