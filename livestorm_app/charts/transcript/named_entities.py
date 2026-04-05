import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_plotly_or_fallback


def render_named_entities_chart(insights):
    st.markdown("**Named Entities Chart**")
    named_entities_df = insights.get("named_entities_df")
    if named_entities_df is None or named_entities_df.empty:
        st.info("No named entities were returned by the transcript API.")
        return
    entity_df = named_entities_df.head(12)
    fig = brand_bar_chart(
        entity_df,
        x_field="entity",
        y_field="count",
        x_title="Entity",
        y_title="Mentions",
        tooltip_fields=["entity", "entity_type", "count", "first_seen_label"],
    )
    render_plotly_or_fallback(fig, fallback_df=entity_df, fallback_columns=["entity", "entity_type", "count", "first_seen_label"])
