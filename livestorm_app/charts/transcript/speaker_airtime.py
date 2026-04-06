import streamlit as st

from livestorm_app.charts.common import PLOTLY_AVAILABLE, px, render_chart_fallback


def render_speaker_airtime_chart(insights):
    st.markdown("**Pie Chart Per Speaker**")
    speaker_df = insights.get("speaker_df")
    if speaker_df is None or speaker_df.empty:
        st.info("Speaker airtime is not available.")
        return
    if PLOTLY_AVAILABLE:
        fig = px.pie(
            speaker_df,
            names="speaker",
            values="speaking_seconds",
            hover_data=["share_pct", "speaking_label", "words"],
            color_discrete_sequence=["#8FD0DE", "#F4B942", "#F06D6D", "#5AC77A", "#B8E986"],
        )
        fig.update_layout(
            height=320,
            margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#EAF1F3"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
        return
    render_chart_fallback("Install `plotly` to view charts.", speaker_df, ["speaker", "share_pct", "speaking_label", "words"])
