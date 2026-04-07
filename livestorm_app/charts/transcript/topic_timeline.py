import streamlit as st

from livestorm_app.charts.common import PLOTLY_AVAILABLE, apply_default_layout, px, render_chart_fallback


def render_topic_timeline_chart(insights):
    st.markdown("**Topic Timeline**")
    topic_timeline_df = insights.get("topic_timeline_df")
    if topic_timeline_df is None or topic_timeline_df.empty:
        st.info("Topic timeline is not available.")
        return
    if PLOTLY_AVAILABLE:
        fig = px.scatter(
            topic_timeline_df,
            x="bucket_start_seconds",
            y="topic",
            color="speaker",
            hover_data=["bucket_label", "topic", "speaker"],
            color_discrete_sequence=["#8FD0DE", "#F4B942", "#F06D6D", "#5AC77A", "#B8E986"],
        )
        apply_default_layout(fig, height=320, x_title="Time (sec)", y_title="Topic", showlegend=True)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "displaylogo": False})
        return
    render_chart_fallback("Install `plotly` to view charts.", topic_timeline_df, ["bucket_label", "topic", "speaker"])
