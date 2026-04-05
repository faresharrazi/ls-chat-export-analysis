import streamlit as st

from livestorm_app.charts.common import PLOTLY_AVAILABLE, apply_default_layout, px, render_chart_fallback


def render_content_pace_and_activity_chart(cross_source):
    st.markdown("**Content Pace And Audience Activity**")
    combined_timeline_df = cross_source.get("combined_timeline_df")
    if combined_timeline_df is None or combined_timeline_df.empty:
        st.info("Chat/questions timestamps could not be aligned into a shared progress view.")
        return
    if PLOTLY_AVAILABLE:
        fig = px.line(
            combined_timeline_df,
            x="bucket_start_pct",
            y="transcript_wpm",
            markers=True,
            color_discrete_sequence=["#8FD0DE"],
            hover_data=None,
        )
        fig.update_traces(
            name="Transcript pace",
            line=dict(width=3),
            marker=dict(size=7),
            hovertemplate="WPM: %{y:.1f}<extra></extra>",
        )
        fig.add_bar(
            x=combined_timeline_df["bucket_start_pct"],
            y=combined_timeline_df["chat_messages"],
            name="Chat messages",
            marker_color="#F4B942",
            opacity=0.45,
            hovertemplate="Chat messages: %{y:.0f}<extra></extra>",
        )
        fig.add_scatter(
            x=combined_timeline_df["bucket_start_pct"],
            y=combined_timeline_df["question_count"],
            name="Questions",
            mode="markers+lines",
            marker=dict(color="#F06D6D", size=10, symbol="diamond"),
            line=dict(color="#F06D6D", width=2, dash="dot"),
            yaxis="y2",
            hovertemplate="Questions: %{y:.0f}<extra></extra>",
        )
        apply_default_layout(fig, height=360, x_title="Session timeline", y_title="Transcript pace (WPM)", showlegend=True)
        fig.update_layout(
            yaxis2=dict(
                title="Questions",
                overlaying="y",
                side="right",
                showgrid=False,
                rangemode="tozero",
            ),
            barmode="overlay",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
        return
    render_chart_fallback("Install `plotly` to view charts.", combined_timeline_df, ["bucket_start_pct", "transcript_wpm", "chat_messages", "question_count"])
