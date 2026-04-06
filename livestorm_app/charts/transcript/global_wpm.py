import pandas as pd
import streamlit as st

from livestorm_app.charts.common import brand_bar_chart, render_chart_fallback, render_plotly_or_fallback


def render_global_wpm_chart(insights):
    st.markdown("**Words Per Minute (Global)**")
    summary = insights.get("summary", {}) if isinstance(insights, dict) else {}
    global_wpm = float(summary.get("global_wpm", 0.0) or 0.0)
    global_wpm_df = pd.DataFrame(
        [
            {
                "scope": "Overall session",
                "wpm": round(global_wpm, 1),
            }
        ]
    )
    fig = brand_bar_chart(
        global_wpm_df,
        x_field="scope",
        y_field="wpm",
        x_title="Scope",
        y_title="WPM",
        tooltip_fields=["scope", "wpm"],
    )
    render_plotly_or_fallback(fig, fallback_df=global_wpm_df, fallback_columns=["scope", "wpm"])
