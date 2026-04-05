import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_plotly_or_fallback


def render_sentence_length_distribution_chart(insights):
    st.markdown("**Sentence Length Distribution**")
    sentence_length_df = insights.get("sentence_length_df")
    if sentence_length_df is None or sentence_length_df.empty:
        st.info("Sentence data is not available.")
        return
    fig = brand_bar_chart(
        sentence_length_df,
        x_field="sentence_length_bin",
        y_field="count",
        x_title="Words per sentence",
        y_title="Count",
        tooltip_fields=["sentence_length_bin", "count"],
    )
    render_plotly_or_fallback(fig, fallback_df=sentence_length_df, fallback_columns=["sentence_length_bin", "count"])
