import streamlit as st

from livestorm_app.charts.common import brand_line_chart, render_plotly_or_fallback


def render_cognitive_load_chart(insights):
    st.markdown("**Cognitive Load Index**")
    engagement_df = insights.get("engagement_df")
    if engagement_df is None or engagement_df.empty:
        st.info("Cognitive load data is not available.")
        return
    fig = brand_line_chart(
        engagement_df,
        x_field="bucket_start_seconds",
        y_field="cognitive_load_index",
        x_title="Time (sec)",
        y_title="Cognitive load",
        tooltip_fields=["bucket_label", "pause_seconds", "filler_count"],
    )
    render_plotly_or_fallback(fig, fallback_df=engagement_df, fallback_columns=["bucket_label", "cognitive_load_index", "pause_seconds", "filler_count"])
