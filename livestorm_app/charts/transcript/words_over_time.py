import streamlit as st

from livestorm_app.charts.common import brand_line_chart, render_plotly_or_fallback


def render_words_over_time_chart(insights):
    st.markdown("**Words Over Time**")
    timeline_df = insights.get("timeline_df")
    if timeline_df is None or timeline_df.empty:
        st.info("Word timeline data is not available.")
        return
    fig = brand_line_chart(
        timeline_df,
        x_field="minute_label",
        y_field="word_count",
        x_title="Time",
        y_title="Words",
        tooltip_fields=["minute_label", "word_count", "speaking_seconds"],
    )
    render_plotly_or_fallback(fig, fallback_df=timeline_df, fallback_columns=["minute_label", "word_count"])
