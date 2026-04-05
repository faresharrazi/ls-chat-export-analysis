import streamlit as st

from livestorm_app.charts.common import brand_line_chart, render_plotly_or_fallback


def render_engagement_score_chart(insights):
    st.markdown("**Engagement Score Over Time**")
    engagement_df = insights.get("engagement_df")
    if engagement_df is None or engagement_df.empty:
        st.info("Engagement data is not available.")
        return
    fig = brand_line_chart(
        engagement_df,
        x_field="bucket_start_seconds",
        y_field="engagement_score",
        x_title="Time (sec)",
        y_title="Engagement score",
        tooltip_fields=["bucket_label", "words_per_minute", "pause_seconds", "interruption_count"],
    )
    render_plotly_or_fallback(fig, fallback_df=engagement_df, fallback_columns=["bucket_label", "engagement_score", "words_per_minute", "pause_seconds"])
