import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_plotly_or_fallback


def render_utterance_duration_distribution_chart(insights):
    st.markdown("**Distribution Of Utterance Length**")
    utterance_duration_df = insights.get("utterance_duration_distribution_df")
    if utterance_duration_df is None or utterance_duration_df.empty:
        st.info("Utterance duration data is not available.")
        return
    fig = brand_bar_chart(
        utterance_duration_df,
        x_field="duration_bin",
        y_field="count",
        x_title="Utterance duration",
        y_title="Count",
        tooltip_fields=["duration_bin", "count"],
    )
    render_plotly_or_fallback(
        fig,
        fallback_df=utterance_duration_df,
        fallback_columns=["duration_bin", "count"],
    )
