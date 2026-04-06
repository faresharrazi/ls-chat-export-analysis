import streamlit as st

from livestorm_app.charts.common import go, render_chart_fallback


def render_speaker_turn_timeline_chart(insights):
    st.markdown("**Timeline Per Speaker**")
    speaker_turns_df = insights.get("speaker_turns_df")
    if speaker_turns_df is None or speaker_turns_df.empty:
        st.info("Speaker turns are not available.")
        return
    if go is not None:
        fig = go.Figure()
        speaker_colors = ["#8FD0DE", "#F4B942", "#F06D6D", "#5AC77A", "#B8E986", "#F2A7A7"]
        speaker_map = {
            speaker: speaker_colors[index % len(speaker_colors)]
            for index, speaker in enumerate(speaker_turns_df["speaker"].astype(str).drop_duplicates().tolist())
        }
        for speaker, speaker_slice in speaker_turns_df.groupby("speaker"):
            fig.add_trace(
                go.Bar(
                    x=speaker_slice["duration_seconds"],
                    y=speaker_slice["speaker"],
                    base=speaker_slice["start_seconds"],
                    orientation="h",
                    marker_color=speaker_map.get(str(speaker), "#8FD0DE"),
                    name=str(speaker),
                    customdata=speaker_slice[["start_label", "duration_seconds", "excerpt"]].values,
                    hovertemplate="Start: %{customdata[0]}<br>Duration: %{customdata[1]:.2f}s<br>%{customdata[2]}<extra></extra>",
                )
            )
        fig.update_layout(
            barmode="overlay",
            height=320,
            margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#EAF1F3"),
            xaxis_title="Transcript time (sec)",
            yaxis_title="Speaker",
            legend_title_text="Speaker",
        )
        fig.update_xaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
        fig.update_yaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
        return
    render_chart_fallback("Speaker turns are available in table form below.", speaker_turns_df, ["speaker", "start_label", "duration_seconds", "excerpt"])
