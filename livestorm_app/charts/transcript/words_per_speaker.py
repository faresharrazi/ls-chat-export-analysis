import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_plotly_or_fallback


def render_words_per_speaker_chart(insights):
    st.markdown("**Words Per Speaker**")
    speaker_df = insights.get("speaker_df")
    if speaker_df is None or speaker_df.empty:
        st.info("Speaker word counts are not available.")
        return
    chart_df = speaker_df[["speaker", "words"]].copy()
    fig = brand_bar_chart(
        chart_df,
        x_field="speaker",
        y_field="words",
        x_title="Speaker",
        y_title="Words",
        tooltip_fields=["speaker", "words"],
    )
    render_plotly_or_fallback(fig, fallback_df=chart_df, fallback_columns=["speaker", "words"])
