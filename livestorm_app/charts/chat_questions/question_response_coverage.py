import pandas as pd
import streamlit as st

from livestorm_app.charts.common import PLOTLY_AVAILABLE, apply_default_layout, px, render_chart_fallback


def render_question_response_coverage_chart(df: pd.DataFrame, questions_df: pd.DataFrame | None):
    del df
    st.markdown("**Question Response Coverage**")
    if not isinstance(questions_df, pd.DataFrame) or questions_df.empty:
        st.info("No questions fetched yet.")
        return
    answered_count = 0
    if "response" in questions_df.columns:
        answered_count = int((questions_df["response"].fillna("").astype(str).str.strip() != "").sum())
    unanswered_count = max(int(len(questions_df.index)) - answered_count, 0)
    status_df = pd.DataFrame({"status": ["Answered", "Unanswered"], "count": [answered_count, unanswered_count]})
    if PLOTLY_AVAILABLE:
        fig = px.bar(
            status_df,
            x="status",
            y="count",
            color="status",
            color_discrete_map={"Answered": "#5AC77A", "Unanswered": "#F06D6D"},
            hover_data=["status", "count"],
        )
        apply_default_layout(fig, height=260, x_title="Status", y_title="Questions", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
        return
    render_chart_fallback("Install `plotly` to view charts.", status_df, ["status", "count"])
