import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
try:
    import plotly.express as px
except ModuleNotFoundError:  # pragma: no cover
    px = None

from livestorm_app.config import OUTPUT_LANGUAGE_LABELS
from livestorm_app.services import (
    analysis_markdown_to_pdf_bytes,
    build_cross_source_insights,
    build_transcript_insights,
    format_seconds_label,
)


PLOTLY_AVAILABLE = px is not None


def render_chart_fallback(message: str, data: Optional[pd.DataFrame] = None, columns: Optional[List[str]] = None) -> None:
    st.info(message)
    if isinstance(data, pd.DataFrame) and not data.empty:
        display_df = data
        if columns:
            keep_columns = [column for column in columns if column in display_df.columns]
            if keep_columns:
                display_df = display_df[keep_columns]
        st.dataframe(display_df, use_container_width=True, hide_index=True)


def brand_bar_chart(
    data: pd.DataFrame, x_field: str, y_field: str, x_title: str, y_title: str, tooltip_fields: List[str]
):
    if not PLOTLY_AVAILABLE:
        return None
    fig = px.bar(
        data,
        x=x_field,
        y=y_field,
        color_discrete_sequence=["#8FD0DE"],
        hover_data=tooltip_fields,
    )
    fig.update_layout(
        height=280,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#EAF1F3"),
        xaxis_title=x_title,
        yaxis_title=y_title,
        showlegend=False,
    )
    fig.update_xaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
    fig.update_yaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
    return fig


def brand_line_chart(
    data: pd.DataFrame, x_field: str, y_field: str, x_title: str, y_title: str, tooltip_fields: List[str]
):
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
    fig.update_layout(
        height=280,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#EAF1F3"),
        xaxis_title=x_title,
        yaxis_title=y_title,
        showlegend=False,
    )
    fig.update_xaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
    fig.update_yaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
    return fig


def render_chat_questions_dashboard(df: pd.DataFrame, questions_df: Optional[pd.DataFrame] = None) -> None:
    total_messages = int(len(df.index)) if isinstance(df, pd.DataFrame) else 0
    total_questions = int(len(questions_df.index)) if isinstance(questions_df, pd.DataFrame) else 0
    unique_authors = int(df["author_id"].nunique()) if "author_id" in df.columns else 0
    unique_askers = 0
    if isinstance(questions_df, pd.DataFrame):
        if "asked_by" in questions_df.columns:
            unique_askers = int(questions_df["asked_by"].nunique())
        elif "question_author_id" in questions_df.columns:
            unique_askers = int(questions_df["question_author_id"].nunique())
    avg_chars = (
        float(round(df["text_content"].fillna("").astype(str).str.len().mean(), 1))
        if "text_content" in df.columns and total_messages
        else 0.0
    )

    answered_count = 0
    if isinstance(questions_df, pd.DataFrame) and "response" in questions_df.columns:
        answered_count = int((questions_df["response"].fillna("").astype(str).str.strip() != "").sum())
    unanswered_count = max(total_questions - answered_count, 0)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Messages", f"{total_messages}")
    col2.metric("Unique Chatters", f"{unique_authors}")
    col3.metric("Avg Msg Length", f"{avg_chars} chars")
    col4.metric("Questions", f"{total_questions}")
    col5.metric("Unique Askers", f"{unique_askers}")

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
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
        if not combined_top.empty:
            if PLOTLY_AVAILABLE:
                top_chart = px.bar(
                    combined_top,
                    x="person_id",
                    y="count",
                    color="kind",
                    barmode="group",
                    color_discrete_map={"Messages": "#8FD0DE", "Questions": "#F4B942"},
                    hover_data=["person_id", "count", "kind"],
                )
                top_chart.update_layout(
                    height=300,
                    margin=dict(l=8, r=8, t=8, b=8),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#EAF1F3"),
                    xaxis_title="Author / Asker ID",
                    yaxis_title="Count",
                    legend_title_text="Series",
                )
                top_chart.update_xaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
                top_chart.update_yaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
                st.plotly_chart(top_chart, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
            else:
                render_chart_fallback("Install `plotly` to view charts.", combined_top, ["person_id", "count", "kind"])
        else:
            st.info("Not enough contributor data to chart.")

    with chart_col2:
        st.markdown("**Activity Over Time (UTC)**")
        timeline_frames: List[pd.DataFrame] = []
        if "created_at" in df.columns:
            msg_ts = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
            msg_timeline = pd.DataFrame({"created_at": msg_ts}).dropna().assign(
                minute=lambda d: d["created_at"].dt.floor("min")
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
                minute=lambda d: d["created_at"].dt.floor("min")
            ).groupby("minute").size().reset_index(name="count")
            if not q_timeline.empty:
                q_timeline["kind"] = "Questions"
                timeline_frames.append(q_timeline)

        if timeline_frames:
            timeline = pd.concat(timeline_frames, ignore_index=True)
            if PLOTLY_AVAILABLE:
                timeline_chart = px.line(
                    timeline,
                    x="minute",
                    y="count",
                    color="kind",
                    markers=True,
                    color_discrete_map={"Messages": "#8FD0DE", "Questions": "#F4B942"},
                    hover_data=["minute", "count", "kind"],
                )
                timeline_chart.update_layout(
                    height=300,
                    margin=dict(l=8, r=8, t=8, b=8),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#EAF1F3"),
                    xaxis_title="Time (UTC)",
                    yaxis_title="Count",
                    legend_title_text="Series",
                )
                timeline_chart.update_xaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
                timeline_chart.update_yaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
                st.plotly_chart(timeline_chart, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
            else:
                render_chart_fallback("Install `plotly` to view charts.", timeline, ["minute", "count", "kind"])
        else:
            st.info("No valid timestamp data to chart.")

        st.markdown("**Question Response Coverage**")
        if total_questions > 0:
            status_df = pd.DataFrame({"status": ["Answered", "Unanswered"], "count": [answered_count, unanswered_count]})
            if PLOTLY_AVAILABLE:
                status_chart = px.bar(
                    status_df,
                    x="status",
                    y="count",
                    color="status",
                    color_discrete_map={"Answered": "#5AC77A", "Unanswered": "#F06D6D"},
                    hover_data=["status", "count"],
                )
                status_chart.update_layout(
                    height=260,
                    margin=dict(l=8, r=8, t=8, b=8),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#EAF1F3"),
                    xaxis_title="Status",
                    yaxis_title="Questions",
                    showlegend=False,
                )
                status_chart.update_xaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
                status_chart.update_yaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
                st.plotly_chart(status_chart, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
            else:
                render_chart_fallback("Install `plotly` to view charts.", status_df, ["status", "count"])
        else:
            st.info("No questions fetched yet.")


def render_transcript_block(
    transcript_payload: Optional[Dict[str, Any]],
    transcript_text: str,
    current_session_id: str,
    is_loading: bool = False,
) -> None:
    label = "Transcript (loading...)" if is_loading else "Transcript"
    with st.expander(label, expanded=bool(transcript_payload) or is_loading):
        if is_loading:
            with st.spinner("Loading transcript..."):
                st.caption("Transcript is loading...")
        if not isinstance(transcript_payload, dict):
            if not is_loading:
                st.caption("Fetch a transcript to view the transcript text.")
            return

        transcript_insights = build_transcript_insights(transcript_payload)
        summary = transcript_insights.get("summary", {})
        segments_df = transcript_insights.get("segments_df", pd.DataFrame())
        pace_df = transcript_insights.get("pace_df", pd.DataFrame())
        terms_df = transcript_insights.get("terms_df", pd.DataFrame())
        transcript = transcript_payload.get("transcript") if isinstance(transcript_payload.get("transcript"), dict) else transcript_payload
        is_timestamped = bool(transcript.get("timestamped")) if isinstance(transcript, dict) else False

        if is_timestamped and isinstance(segments_df, pd.DataFrame) and not segments_df.empty:
            metric_col1, metric_col2 = st.columns(2)
            metric_col1.metric("Words", f"{summary.get('total_words', 0)}")
            metric_col2.metric("Avg Pace", f"{summary.get('avg_words_per_minute', 0)} wpm")

            with st.container():
                st.markdown("**Speaking Pace Curve**")
                if not pace_df.empty:
                    if PLOTLY_AVAILABLE:
                        pace_chart = px.line(
                            pace_df,
                            x="time_seconds",
                            y="segment_wpm",
                            markers=True,
                            color_discrete_sequence=["#8FD0DE"],
                            hover_data=["time_label", "duration_seconds", "word_count", "text"],
                        )
                        pace_chart.update_traces(line=dict(width=3), marker=dict(size=7, color="#F4B942"), line_shape="spline")
                        pace_chart.update_layout(
                            height=290,
                            margin=dict(l=8, r=8, t=8, b=8),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#EAF1F3"),
                            xaxis_title="Transcript time (sec)",
                            yaxis_title="Words per minute",
                        )
                        pace_chart.update_xaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
                        pace_chart.update_yaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
                        st.plotly_chart(pace_chart, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
                    else:
                        render_chart_fallback("Install `plotly` to view charts.", pace_df, ["time_label", "segment_wpm", "word_count"])
                else:
                    st.info("Verbose transcript timing is required to chart speaking pace.")

                st.markdown("**Meaningful Words**")
                if not terms_df.empty:
                    terms_chart = brand_bar_chart(
                        terms_df,
                        x_field="term",
                        y_field="count",
                        x_title="Word",
                        y_title="Count",
                        tooltip_fields=["term", "count"],
                    )
                    if terms_chart is not None:
                        st.plotly_chart(
                            terms_chart,
                            use_container_width=True,
                            config={"displayModeBar": False, "displaylogo": False},
                        )
                    else:
                        render_chart_fallback("Install `plotly` to view charts.", terms_df, ["term", "count"])
                else:
                    st.info("Not enough transcript text to extract meaningful terms.")

            insight_bits = []
            if summary.get("top_term"):
                insight_bits.append(f"Top meaningful term: `{summary['top_term']}`")
            if insight_bits:
                st.caption(" | ".join(insight_bits))
        elif transcript_text:
            st.caption("Charts are available for verbose transcripts only.")

        if transcript_text:
            transcript_timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            st.download_button(
                label="Download Transcript JSON",
                data=json.dumps(transcript_payload, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"livestorm-transcript-{current_session_id}-{transcript_timestamp}.json",
                mime="application/json",
            )
            if is_timestamped and isinstance(segments_df, pd.DataFrame) and not segments_df.empty:
                transcript_tab, segments_tab = st.tabs(["Transcript", "Segments"])
                with transcript_tab:
                    st.text_area(
                        "Transcript text",
                        value=transcript_text,
                        height=320,
                        disabled=True,
                        key=f"transcript_text_tab_{current_session_id}",
                    )
                with segments_tab:
                    display_segments = segments_df.copy()
                    keep_columns = [
                        col for col in [
                            "start_label",
                            "speaker",
                            "duration_seconds",
                            "word_count",
                            "words_per_second",
                            "text",
                        ] if col in display_segments.columns
                    ]
                    st.dataframe(display_segments[keep_columns], use_container_width=True, hide_index=True)
            else:
                st.text_area(
                    "Transcript text",
                    value=transcript_text,
                    height=320,
                    disabled=True,
                    key=f"transcript_text_{current_session_id}",
                )
        else:
            st.info("Transcript payload fetched successfully, but there is no transcript text to display.")


def render_chat_questions_block(
    df: Optional[pd.DataFrame],
    questions_df: Optional[pd.DataFrame],
    current_session_id: str,
) -> None:
    with st.expander("Chat & Questions", expanded=isinstance(df, pd.DataFrame) or isinstance(questions_df, pd.DataFrame)):
        if not isinstance(df, pd.DataFrame):
            st.caption("Fetch chat and questions to unlock engagement charts, tables, and exports.")
            return

        render_chat_questions_dashboard(df, questions_df=questions_df)

        chat_tab, questions_tab = st.tabs(["Chat", "Questions"])
        with chat_tab:
            st.dataframe(df, use_container_width=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            st.download_button(
                label="Download Chat CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=f"livestorm-chat-{current_session_id}-{timestamp}.csv",
                mime="text/csv",
            )

        with questions_tab:
            if isinstance(questions_df, pd.DataFrame) and not questions_df.empty:
                st.dataframe(questions_df, use_container_width=True)
                questions_timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
                st.download_button(
                    label="Download Questions CSV",
                    data=questions_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"livestorm-questions-{current_session_id}-{questions_timestamp}.csv",
                    mime="text/csv",
                )
            elif isinstance(questions_df, pd.DataFrame):
                st.info(
                    "No questions were found for this session. "
                    "This can happen when attendees did not submit questions or the session has no Q&A data."
                )
            else:
                st.caption("Questions have not been fetched yet.")


def render_analysis_block(
    current_session_id: str,
    analysis_ran: bool,
    analysis_md: str,
    transcript_available: bool,
    chat_available: bool,
    questions_available: bool,
    transcript_payload: Optional[Dict[str, Any]] = None,
    chat_df: Optional[pd.DataFrame] = None,
    questions_df: Optional[pd.DataFrame] = None,
) -> bool:
    with st.expander("Analysis", expanded=analysis_ran or analysis_md == ""):
        chat_questions_available = chat_available and questions_available

        if not chat_available and st.session_state.get("analysis_include_chat"):
            st.session_state["analysis_include_chat"] = False
        if not questions_available and st.session_state.get("analysis_include_questions"):
            st.session_state["analysis_include_questions"] = False
        if not chat_questions_available and st.session_state.get("analysis_include_chat_questions"):
            st.session_state["analysis_include_chat_questions"] = False
        if not transcript_available and st.session_state.get("analysis_include_transcript"):
            st.session_state["analysis_include_transcript"] = False
        if transcript_available and st.session_state.get("analysis_include_transcript_pending"):
            st.session_state["analysis_include_transcript"] = True
            st.session_state["analysis_include_transcript_pending"] = False

        st.caption("Choose the data sources to include before running the analysis.")
        st.checkbox("Transcript", key="analysis_include_transcript", disabled=not transcript_available)
        include_chat_questions = st.checkbox(
            "Chat & Questions",
            key="analysis_include_chat_questions",
            disabled=not chat_questions_available,
        )
        st.session_state["analysis_include_chat"] = bool(include_chat_questions and chat_available)
        st.session_state["analysis_include_questions"] = bool(include_chat_questions and questions_available)

        controls_col1, controls_col2 = st.columns([1.2, 1.8])
        with controls_col1:
            st.radio(
                "Output Language",
                options=list(OUTPUT_LANGUAGE_LABELS.keys()),
                format_func=lambda choice: OUTPUT_LANGUAGE_LABELS.get(choice, choice),
                horizontal=True,
                key="analysis_language",
            )

        should_render_cross_source = bool(
            st.session_state.get("analysis_include_transcript")
            and st.session_state.get("analysis_include_chat_questions")
            and transcript_available
            and chat_questions_available
            and isinstance(transcript_payload, dict)
        )

        if st.session_state.get("analysis_in_progress", False):
            st.button(
                "Running Analysis...",
                key="analysis_running_btn",
                type="primary",
                disabled=True,
            )
            analyze_button = False
        else:
            analyze_button = st.button(
                "Run analysis",
                key="analysis_run_btn",
                type="primary",
                disabled=not (transcript_available or chat_questions_available),
            )

        if should_render_cross_source and analysis_ran:
            transcript_insights = build_transcript_insights(transcript_payload)
            has_verbose_segments = not transcript_insights.get("segments_df", pd.DataFrame()).empty
            if has_verbose_segments:
                cross_source = build_cross_source_insights(chat_df, questions_df, transcript_payload)
                combined_timeline_df = cross_source.get("combined_timeline_df", pd.DataFrame())
                reaction_moments_df = cross_source.get("reaction_moments_df", pd.DataFrame())
                st.markdown("**Cross-Source Preview**")
                st.caption("This preview aligns transcript progression with chat and question activity. It appears below the analysis button when both sources are selected.")

                st.markdown("**Content Pace And Audience Activity**")
                if not combined_timeline_df.empty:
                    if PLOTLY_AVAILABLE:
                        activity_chart = px.line(
                            combined_timeline_df,
                            x="bucket_start_pct",
                            y="transcript_wpm",
                            markers=True,
                            color_discrete_sequence=["#8FD0DE"],
                            hover_data=None,
                        )
                        activity_chart.update_traces(
                            name="Transcript pace",
                            line=dict(width=3),
                            marker=dict(size=7),
                            hovertemplate="WPM: %{y:.1f}<extra></extra>",
                        )
                        activity_chart.add_bar(
                            x=combined_timeline_df["bucket_start_pct"],
                            y=combined_timeline_df["chat_messages"],
                            name="Chat messages",
                            marker_color="#F4B942",
                            opacity=0.45,
                            hovertemplate="Chat messages: %{y:.0f}<extra></extra>",
                        )
                        activity_chart.add_scatter(
                            x=combined_timeline_df["bucket_start_pct"],
                            y=combined_timeline_df["question_count"],
                            name="Questions",
                            mode="markers+lines",
                            marker=dict(color="#F06D6D", size=10, symbol="diamond"),
                            line=dict(color="#F06D6D", width=2, dash="dot"),
                            yaxis="y2",
                            hovertemplate="Questions: %{y:.0f}<extra></extra>",
                        )
                        activity_chart.update_layout(
                            height=360,
                            margin=dict(l=8, r=8, t=8, b=8),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#EAF1F3"),
                            xaxis_title="Session timeline",
                            yaxis_title="Transcript pace (WPM)",
                            yaxis2=dict(
                                title="Questions",
                                overlaying="y",
                                side="right",
                                showgrid=False,
                                rangemode="tozero",
                            ),
                            legend=dict(orientation="h", y=1.08, x=0),
                            barmode="overlay",
                        )
                        activity_chart.update_xaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
                        activity_chart.update_yaxes(gridcolor="#2F4B53", zerolinecolor="#2F4B53")
                        st.plotly_chart(activity_chart, use_container_width=True, config={"displayModeBar": False, "displaylogo": False})
                    else:
                        render_chart_fallback(
                            "Install `plotly` to view charts.",
                            combined_timeline_df,
                            ["bucket_start_pct", "transcript_wpm", "chat_messages", "question_count"],
                        )
                else:
                    st.info("Chat/questions timestamps could not be aligned into a shared progress view.")

                if not reaction_moments_df.empty:
                    st.markdown("**Segments With The Most Reactions**")
                    st.dataframe(
                        reaction_moments_df[["session_stage", "start_label", "excerpt", "chat_messages", "question_count"]],
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.caption("Cross-source preview requires a verbose transcript with timestamped segments.")

        if analysis_ran and analysis_md:
            st.markdown(analysis_md)
            analysis_bytes = analysis_md.encode("utf-8")
            analysis_ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            download_col, _ = st.columns([1.1, 2.9])
            with download_col:
                download_format = st.selectbox(
                    "Download As",
                    options=["PDF", "Markdown"],
                    index=0,
                    key=f"analysis_download_format_{current_session_id}",
                )
                if download_format == "Markdown":
                    st.download_button(
                        label="Download Analysis",
                        data=analysis_bytes,
                        file_name=f"livestorm-analysis-{current_session_id}-{analysis_ts}.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )
                else:
                    try:
                        pdf_bytes = analysis_markdown_to_pdf_bytes(analysis_md, title="Livestorm Session Analysis")
                        st.download_button(
                            label="Download Analysis",
                            data=pdf_bytes,
                            file_name=f"livestorm-analysis-{current_session_id}-{analysis_ts}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    except RuntimeError as exc:
                        st.caption(str(exc))
        elif analysis_ran:
            st.info("Analysis finished, but no markdown output was returned.")

        return analyze_button
