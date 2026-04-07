import streamlit as st

from livestorm_app.charts.common import PLOTLY_AVAILABLE, apply_default_layout, px, render_chart_fallback


def render_replay_navigation_chart(insights):
    st.markdown("**Replay Navigation Map**")
    replay_navigation_df = insights.get("replay_navigation_df")
    if replay_navigation_df is None or replay_navigation_df.empty:
        st.info("Replay navigation data is not available.")
        return
    if PLOTLY_AVAILABLE:
        fig = px.scatter(
            replay_navigation_df,
            x="bucket_start_seconds",
            y="highlight",
            size="engagement_score",
            color="highlight",
            hover_data=["bucket_label", "topic", "dominant_speaker", "pause_seconds", "clarity_score"],
            color_discrete_map={"Key moment": "#F4B942", "Low energy": "#F06D6D", "Steady": "#8FD0DE"},
        )
        apply_default_layout(fig, height=320, x_title="Time (sec)", y_title="Replay marker", showlegend=True)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "displaylogo": False})
        return
    render_chart_fallback("Install `plotly` to view charts.", replay_navigation_df, ["bucket_label", "topic", "dominant_speaker", "engagement_score", "pause_seconds", "highlight"])
