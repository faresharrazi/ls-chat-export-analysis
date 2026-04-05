import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_plotly_or_fallback


def render_top_keywords_chart(insights):
    st.markdown("**Top Keywords**")
    terms_df = insights.get("terms_df")
    if terms_df is None or terms_df.empty:
        st.info("Not enough transcript text to extract meaningful terms.")
        return
    fig = brand_bar_chart(
        terms_df,
        x_field="term",
        y_field="count",
        x_title="Keyword",
        y_title="Count",
        tooltip_fields=["term", "count"],
    )
    render_plotly_or_fallback(fig, fallback_df=terms_df, fallback_columns=["term", "count"])
