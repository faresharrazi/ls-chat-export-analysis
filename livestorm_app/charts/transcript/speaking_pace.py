import streamlit as st

from livestorm_app.charts.common import PLOTLY_AVAILABLE, apply_default_layout, px, render_chart_fallback


def render_speaking_pace_chart(insights):
    st.markdown("**Speaking Pace Over Time**")
    pace_df = insights.get("pace_df")
    if pace_df is None or pace_df.empty:
        st.info("No pace data is available for this transcript.")
        return
    if PLOTLY_AVAILABLE:
        fig = px.line(
            pace_df,
            x="time_seconds",
            y="segment_wpm",
            markers=True,
            color_discrete_sequence=["#8FD0DE"],
            hover_data=["time_label", "duration_seconds", "word_count", "text"],
        )
        fig.update_traces(line=dict(width=3), marker=dict(size=7, color="#F4B942"), line_shape="spline")
        apply_default_layout(fig, height=300, x_title="Time (sec)", y_title="WPM", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
        return
    render_chart_fallback("Install `plotly` to view charts.", pace_df, ["time_label", "segment_wpm", "word_count"])
