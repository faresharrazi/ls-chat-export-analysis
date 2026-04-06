import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_chart_fallback, render_plotly_or_fallback


def render_pause_distribution_chart(insights):
    st.markdown("**Pause Histogram**")
    pause_distribution_df = insights.get("pause_distribution_df")
    if pause_distribution_df is None or pause_distribution_df.empty:
        st.info("No qualifying pauses were found.")
        return
    fig = brand_bar_chart(
        pause_distribution_df,
        x_field="duration_bin",
        y_field="count",
        x_title="Pause duration",
        y_title="Count",
        tooltip_fields=["duration_bin", "count"],
    )
    render_plotly_or_fallback(fig, fallback_df=pause_distribution_df, fallback_columns=["duration_bin", "count"])
