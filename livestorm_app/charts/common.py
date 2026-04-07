from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
except ModuleNotFoundError:  # pragma: no cover
    px = None
    go = None


PLOTLY_AVAILABLE = px is not None


@dataclass(frozen=True)
class ChartSpec:
    key: str
    label: str
    renderer: Callable[..., None]


def render_chart_fallback(message: str, data: Optional[pd.DataFrame] = None, columns: Optional[List[str]] = None) -> None:
    st.info(message)
    if isinstance(data, pd.DataFrame) and not data.empty:
        display_df = data
        if columns:
            keep_columns = [column for column in columns if column in display_df.columns]
            if keep_columns:
                display_df = display_df[keep_columns]
        st.dataframe(display_df, width="stretch", hide_index=True)


def apply_default_layout(fig, *, height: int, x_title: str, y_title: str, showlegend: bool = False):
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#EAF1F3"),
        xaxis_title=x_title,
        yaxis_title=y_title,
        showlegend=showlegend,
    )
    fig.update_xaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
    fig.update_yaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
    return fig


def brand_bar_chart(data: pd.DataFrame, x_field: str, y_field: str, x_title: str, y_title: str, tooltip_fields: List[str]):
    if not PLOTLY_AVAILABLE:
        return None
    fig = px.bar(
        data,
        x=x_field,
        y=y_field,
        color_discrete_sequence=["#8FD0DE"],
        hover_data=tooltip_fields,
    )
    return apply_default_layout(fig, height=280, x_title=x_title, y_title=y_title, showlegend=False)


def brand_line_chart(data: pd.DataFrame, x_field: str, y_field: str, x_title: str, y_title: str, tooltip_fields: List[str]):
    if not PLOTLY_AVAILABLE:
        return None
    fig = px.line(
        data,
        x=x_field,
        y=y_field,
        markers=True,
        color_discrete_sequence=["#8FD0DE"],
        hover_data=tooltip_fields,
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=7, color="#FFFFFF"))
    return apply_default_layout(fig, height=280, x_title=x_title, y_title=y_title, showlegend=False)


def render_plotly_or_fallback(fig, *, fallback_df: Optional[pd.DataFrame] = None, fallback_columns: Optional[List[str]] = None) -> None:
    if fig is not None and PLOTLY_AVAILABLE:
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "displaylogo": False})
        return
    render_chart_fallback("Install `plotly` to view charts.", fallback_df, fallback_columns)
