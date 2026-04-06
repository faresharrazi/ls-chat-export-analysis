import streamlit as st

from livestorm_app.charts.common import PLOTLY_AVAILABLE, apply_default_layout, px, render_chart_fallback


def render_silence_timeline_chart(insights):
    st.markdown("**Pause Timeline**")
    silence_df = insights.get("silence_df")
    if silence_df is None or silence_df.empty:
        st.info("No pauses above 0.75 seconds were detected from word timing.")
        return
    if PLOTLY_AVAILABLE:
        fig = px.bar(
            silence_df,
            x="silence_start_seconds",
            y="gap_seconds",
            color="pause_type",
            color_discrete_map={
                "Thinking pause": "#F4B942",
                "Hesitation": "#F06D6D",
                "Strong silence": "#8FD0DE",
            },
            hover_data=["silence_start_label", "silence_end_label", "speaker_transition"],
        )
        apply_default_layout(fig, height=300, x_title="Time (sec)", y_title="Pause duration (sec)", showlegend=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
        return
    render_chart_fallback("Install `plotly` to view charts.", silence_df, ["silence_start_label", "gap_seconds", "pause_type"])
