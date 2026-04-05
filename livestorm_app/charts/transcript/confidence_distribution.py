import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_plotly_or_fallback


def render_confidence_distribution_chart(insights):
    st.markdown("**Confidence Score Distribution**")
    confidence_distribution_df = insights.get("confidence_distribution_df")
    if confidence_distribution_df is None or confidence_distribution_df.empty:
        st.info("Confidence data is not available.")
        return
    fig = brand_bar_chart(
        confidence_distribution_df,
        x_field="confidence_bin",
        y_field="count",
        x_title="Confidence",
        y_title="Words",
        tooltip_fields=["confidence_bin", "count"],
    )
    render_plotly_or_fallback(fig, fallback_df=confidence_distribution_df, fallback_columns=["confidence_bin", "count"])
