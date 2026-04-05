import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_plotly_or_fallback


def render_interruptions_chart(insights):
    st.markdown("**Interruptions / Overlaps**")
    interruptions_df = insights.get("interruptions_df")
    if interruptions_df is None or interruptions_df.empty:
        st.info("No interruptions or overlaps were detected.")
        return
    chart_df = interruptions_df.groupby("speaker_pair", as_index=False).agg(count=("kind", "size"))
    fig = brand_bar_chart(
        chart_df,
        x_field="speaker_pair",
        y_field="count",
        x_title="Speaker switch",
        y_title="Interruptions",
        tooltip_fields=["speaker_pair", "count"],
    )
    render_plotly_or_fallback(fig, fallback_df=chart_df, fallback_columns=["speaker_pair", "count"])
