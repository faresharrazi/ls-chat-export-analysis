import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_plotly_or_fallback


def render_speaking_burst_chart(insights):
    st.markdown("**Speaking Burst Analysis**")
    burst_distribution_df = insights.get("burst_distribution_df")
    if burst_distribution_df is None or burst_distribution_df.empty:
        st.info("Burst data is not available.")
        return
    fig = brand_bar_chart(
        burst_distribution_df,
        x_field="burst_duration_bin",
        y_field="count",
        x_title="Continuous speaking span",
        y_title="Burst count",
        tooltip_fields=["burst_duration_bin", "count"],
    )
    render_plotly_or_fallback(fig, fallback_df=burst_distribution_df, fallback_columns=["burst_duration_bin", "count"])
