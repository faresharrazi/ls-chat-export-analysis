import pandas as pd
import streamlit as st

from livestorm_app.charts.common import PLOTLY_AVAILABLE, apply_default_layout, px, render_chart_fallback


def render_top_contributors_chart(df: pd.DataFrame, questions_df: pd.DataFrame | None):
    st.markdown("**Top Contributors (Messages vs Questions)**")
    top_chatters = pd.DataFrame(columns=["person_id", "count", "kind"])
    top_askers = pd.DataFrame(columns=["person_id", "count", "kind"])
    if "author_id" in df.columns:
        top_chatters = df["author_id"].value_counts().head(10).rename_axis("person_id").reset_index(name="count")
        top_chatters["kind"] = "Messages"
    if isinstance(questions_df, pd.DataFrame) and "asked_by" in questions_df.columns:
        top_askers = questions_df["asked_by"].value_counts().head(10).rename_axis("person_id").reset_index(name="count")
        top_askers["kind"] = "Questions"
    elif isinstance(questions_df, pd.DataFrame) and "question_author_id" in questions_df.columns:
        top_askers = questions_df["question_author_id"].value_counts().head(10).rename_axis("person_id").reset_index(name="count")
        top_askers["kind"] = "Questions"

    combined_top = pd.concat([top_chatters, top_askers], ignore_index=True)
    if combined_top.empty:
        st.info("Not enough contributor data to chart.")
        return
    if PLOTLY_AVAILABLE:
        fig = px.bar(
            combined_top,
            x="person_id",
            y="count",
            color="kind",
            barmode="group",
            color_discrete_map={"Messages": "#8FD0DE", "Questions": "#F4B942"},
            hover_data=["person_id", "count", "kind"],
        )
        apply_default_layout(fig, height=300, x_title="Author / Asker ID", y_title="Count", showlegend=True)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "displaylogo": False})
        return
    render_chart_fallback("Install `plotly` to view charts.", combined_top, ["person_id", "count", "kind"])
