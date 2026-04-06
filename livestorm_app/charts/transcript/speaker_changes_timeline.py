import streamlit as st

from livestorm_app.charts.common import PLOTLY_AVAILABLE, apply_default_layout, px, render_chart_fallback


def render_speaker_changes_timeline_chart(insights):
    st.markdown("**Timeline Of Speaker Changes**")
    speaker_turns_df = insights.get("speaker_turns_df")
    if speaker_turns_df is None or speaker_turns_df.empty:
        st.info("Speaker changes are not available.")
        return

    change_df = speaker_turns_df.copy().reset_index(drop=True)
    change_df["turn_number"] = change_df.index + 1
    if PLOTLY_AVAILABLE:
        fig = px.scatter(
            change_df,
            x="start_seconds",
            y="speaker",
            color="speaker",
            hover_data=["turn_number", "start_label", "duration_seconds", "excerpt"],
            color_discrete_sequence=["#8FD0DE", "#F4B942", "#F06D6D", "#5AC77A", "#B8E986", "#F2A7A7"],
        )
        fig.update_traces(marker=dict(size=11))
        apply_default_layout(fig, height=300, x_title="Time (sec)", y_title="Speaker", showlegend=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
        return

    render_chart_fallback(
        "Install `plotly` to view charts.",
        change_df,
        ["turn_number", "speaker", "start_label", "duration_seconds", "excerpt"],
    )
