from typing import List

import pandas as pd
import streamlit as st

from livestorm_app.charts.common import PLOTLY_AVAILABLE, apply_default_layout, px, render_chart_fallback


def render_activity_timeline_chart(df: pd.DataFrame, questions_df: pd.DataFrame | None):
    st.markdown("**Activity Over Time (UTC)**")
    timeline_frames: List[pd.DataFrame] = []
    if "created_at" in df.columns:
        msg_ts = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
        msg_timeline = pd.DataFrame({"created_at": msg_ts}).dropna().assign(
            minute=lambda data: data["created_at"].dt.floor("min")
        ).groupby("minute").size().reset_index(name="count")
        if not msg_timeline.empty:
            msg_timeline["kind"] = "Messages"
            timeline_frames.append(msg_timeline)

    question_time_col = None
    if isinstance(questions_df, pd.DataFrame):
        if "asked_at" in questions_df.columns:
            question_time_col = "asked_at"
        elif "created_at" in questions_df.columns:
            question_time_col = "created_at"
    if isinstance(questions_df, pd.DataFrame) and question_time_col is not None:
        q_ts = pd.to_datetime(questions_df[question_time_col], utc=True, errors="coerce")
        q_timeline = pd.DataFrame({"created_at": q_ts}).dropna().assign(
            minute=lambda data: data["created_at"].dt.floor("min")
        ).groupby("minute").size().reset_index(name="count")
        if not q_timeline.empty:
            q_timeline["kind"] = "Questions"
            timeline_frames.append(q_timeline)

    if not timeline_frames:
        st.info("No valid timestamp data to chart.")
        return
    timeline = pd.concat(timeline_frames, ignore_index=True)
    if PLOTLY_AVAILABLE:
        fig = px.line(
            timeline,
            x="minute",
            y="count",
            color="kind",
            markers=True,
            color_discrete_map={"Messages": "#8FD0DE", "Questions": "#F4B942"},
            hover_data=["minute", "count", "kind"],
        )
        apply_default_layout(fig, height=300, x_title="Time (UTC)", y_title="Count", showlegend=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
        return
    render_chart_fallback("Install `plotly` to view charts.", timeline, ["minute", "count", "kind"])
