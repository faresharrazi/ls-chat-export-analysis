import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_plotly_or_fallback


def render_filler_words_chart(insights):
    st.markdown("**Filler Words Frequency**")
    filler_df = insights.get("filler_df")
    if filler_df is None or filler_df.empty:
        st.info("No filler words detected.")
        return
    fig = brand_bar_chart(
        filler_df,
        x_field="filler",
        y_field="count",
        x_title="Filler",
        y_title="Count",
        tooltip_fields=["filler", "count", "per_1000_words"],
    )
    render_plotly_or_fallback(fig, fallback_df=filler_df, fallback_columns=["filler", "count", "per_1000_words"])
