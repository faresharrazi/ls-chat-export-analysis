import streamlit as st

from livestorm_app.charts.common import brand_line_chart, render_plotly_or_fallback


def render_clarity_score_chart(insights):
    st.markdown("**Clarity Score**")
    engagement_df = insights.get("engagement_df")
    if engagement_df is None or engagement_df.empty:
        st.info("Clarity data is not available.")
        return
    fig = brand_line_chart(
        engagement_df,
        x_field="bucket_start_seconds",
        y_field="clarity_score",
        x_title="Time (sec)",
        y_title="Clarity score",
        tooltip_fields=["bucket_label", "words_per_minute", "filler_count"],
    )
    render_plotly_or_fallback(fig, fallback_df=engagement_df, fallback_columns=["bucket_label", "clarity_score", "words_per_minute", "filler_count"])
