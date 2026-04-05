import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from livestorm_app.charts.chat_questions import CHAT_QUESTION_CHARTS, DEFAULT_CHAT_QUESTION_CHART_KEYS
from livestorm_app.charts.common import ChartSpec
from livestorm_app.charts.cross import CROSS_CHARTS, DEFAULT_CROSS_CHART_KEYS
from livestorm_app.charts.transcript import DEFAULT_TRANSCRIPT_CHART_KEYS, TRANSCRIPT_CHARTS
from livestorm_app.config import OUTPUT_LANGUAGE_LABELS
from livestorm_app.services import (
    analysis_markdown_to_pdf_bytes,
    apply_speaker_name_map_to_insights,
    build_cross_source_insights,
    build_transcript_display_text,
    build_transcript_insights,
)


def _render_chart_picker(title: str, chart_specs: List[ChartSpec], default_keys: List[str], key: str) -> List[ChartSpec]:
    st.caption(title)
    options = {chart.label: chart for chart in chart_specs}
    default_labels = [chart.label for chart in chart_specs if chart.key in default_keys]
    selected_labels = st.multiselect(
        "Choose charts",
        options=list(options.keys()),
        default=default_labels,
        key=key,
        label_visibility="collapsed",
    )
    return [options[label] for label in selected_labels if label in options]


def _render_chart_grid(selected_specs: List[ChartSpec], renderer_args: Tuple[Any, ...], columns: int = 2) -> None:
    if not selected_specs:
        st.info("Choose at least one chart to display.")
        return
    for index in range(0, len(selected_specs), columns):
        row_specs = selected_specs[index:index + columns]
        row_columns = st.columns(len(row_specs))
        for column, spec in zip(row_columns, row_specs):
            with column:
                spec.renderer(*renderer_args)


def render_transcript_block(
    transcript_payload: Optional[Dict[str, Any]],
    transcript_text: str,
    current_session_id: str,
    is_loading: bool = False,
) -> None:
    with st.expander("Transcript", expanded=bool(transcript_payload) or is_loading):
        if is_loading:
            with st.spinner("Loading transcript..."):
                st.caption("Transcript is loading...")
        if not isinstance(transcript_payload, dict):
            if not is_loading:
                st.caption("Fetch a transcript to view the transcript text.")
            return

        transcript_insights = build_transcript_insights(transcript_payload)
        effective_transcript_text = transcript_text.strip() if isinstance(transcript_text, str) else ""
        if not effective_transcript_text:
            effective_transcript_text = build_transcript_display_text(transcript_payload).strip()
        base_segments_df = transcript_insights.get("segments_df", pd.DataFrame())
        session_speaker_names = st.session_state.get("transcript_speaker_names", {})
        if not isinstance(session_speaker_names, dict):
            session_speaker_names = {}
        session_key = str(current_session_id or "")
        current_speaker_map = session_speaker_names.get(session_key, {}) if isinstance(session_speaker_names.get(session_key, {}), dict) else {}
        if isinstance(base_segments_df, pd.DataFrame) and not base_segments_df.empty and "speaker" in base_segments_df.columns:
            unique_speakers = sorted(base_segments_df["speaker"].dropna().astype(str).unique().tolist())
            if unique_speakers:
                st.markdown("**Speaker Labels**")
                speaker_cols = st.columns(min(3, len(unique_speakers)))
                updated_map = dict(current_speaker_map)
                for index, speaker in enumerate(unique_speakers):
                    column = speaker_cols[index % len(speaker_cols)]
                    with column:
                        label_value = st.text_input(
                            f"{speaker}",
                            value=str(current_speaker_map.get(speaker, "")),
                            key=f"speaker_name_{session_key}_{speaker}",
                            placeholder=f"Rename {speaker}",
                        ).strip()
                        if label_value:
                            updated_map[speaker] = label_value
                        else:
                            updated_map.pop(speaker, None)
                if updated_map != current_speaker_map:
                    session_speaker_names[session_key] = updated_map
                    st.session_state["transcript_speaker_names"] = session_speaker_names
                    current_speaker_map = updated_map
        transcript_insights = apply_speaker_name_map_to_insights(transcript_insights, current_speaker_map)
        summary = transcript_insights.get("summary", {})
        segments_df = transcript_insights.get("segments_df", pd.DataFrame())
        sentence_df = transcript_insights.get("sentence_df", pd.DataFrame())
        numbers_df = transcript_insights.get("numbers_df", pd.DataFrame())
        key_moments_df = transcript_insights.get("key_moments_df", pd.DataFrame())
        replay_navigation_df = transcript_insights.get("replay_navigation_df", pd.DataFrame())
        low_energy_df = transcript_insights.get("low_energy_df", pd.DataFrame())

        has_timed_transcript = isinstance(segments_df, pd.DataFrame) and not segments_df.empty
        if has_timed_transcript:
            metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
            metric_col1.metric("Words", f"{summary.get('total_words', 0)}")
            metric_col2.metric("Global WPM", f"{summary.get('global_wpm', 0)}")
            metric_col3.metric("Silences", f"{summary.get('silence_count', 0)}")
            metric_col4.metric("Longest Pause", f"{summary.get('longest_silence_seconds', 0)}s")
            metric_col5.metric("Avg Pause", f"{summary.get('avg_pause_seconds', 0)}s")

            selected_charts = _render_chart_picker(
                "Select transcript charts to display.",
                TRANSCRIPT_CHARTS,
                DEFAULT_TRANSCRIPT_CHART_KEYS,
                key=f"transcript_chart_selection_{current_session_id}",
            )
            _render_chart_grid(selected_charts, (transcript_insights,), columns=2)

            info_tabs = st.tabs(["Highlights", "Transcript"])
            with info_tabs[0]:
                if not key_moments_df.empty:
                    st.markdown("**Key Moments**")
                    st.dataframe(
                        key_moments_df[["time_label", "speaker", "score", "reasons", "excerpt"]],
                        use_container_width=True,
                        hide_index=True,
                    )
                if not numbers_df.empty:
                    st.markdown("**Numbers & KPI Extraction**")
                    st.dataframe(
                        numbers_df[["mention", "kind", "speaker", "time_label", "context"]].head(20),
                        use_container_width=True,
                        hide_index=True,
                    )
                if not low_energy_df.empty:
                    st.markdown("**Low-Energy Zones**")
                    st.dataframe(
                        low_energy_df[["bucket_label", "engagement_score", "pause_seconds", "words_per_minute", "energy_label"]],
                        use_container_width=True,
                        hide_index=True,
                    )
                if not replay_navigation_df.empty:
                    st.markdown("**Replay Map Data**")
                    st.dataframe(
                        replay_navigation_df[["bucket_label", "topic", "dominant_speaker", "engagement_score", "pause_seconds", "highlight"]],
                        use_container_width=True,
                        hide_index=True,
                    )
            with info_tabs[1]:
                insight_bits = []
                if summary.get("top_term"):
                    insight_bits.append(f"Top meaningful term: `{summary['top_term']}`")
                if summary.get("total_silence_seconds"):
                    insight_bits.append(f"Total silence: `{summary['total_silence_seconds']}s`")
                if summary.get("avg_engagement_score"):
                    insight_bits.append(f"Avg engagement: `{summary['avg_engagement_score']}`")
                if summary.get("avg_clarity_score"):
                    insight_bits.append(f"Avg clarity: `{summary['avg_clarity_score']}`")
                if insight_bits:
                    st.caption(" | ".join(insight_bits))
                st.text_area(
                    "Transcript text",
                    value=effective_transcript_text,
                    height=320,
                    disabled=True,
                    key=f"transcript_text_{current_session_id}",
                )
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
                if keep_columns:
                    st.markdown("**Segments**")
                    st.dataframe(display_segments[keep_columns], use_container_width=True, hide_index=True)
                if not sentence_df.empty:
                    st.markdown("**Sentences**")
                    st.dataframe(
                        sentence_df[["start_seconds", "speaker", "word_count", "confidence", "sentence"]].head(100),
                        use_container_width=True,
                        hide_index=True,
                    )
        elif effective_transcript_text:
            st.text_area(
                "Transcript text",
                value=effective_transcript_text,
                height=320,
                disabled=True,
                key=f"transcript_text_plain_{current_session_id}",
            )
        else:
            st.info("Transcript payload fetched successfully, but there is no transcript text to display.")

        if effective_transcript_text:
            transcript_timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            st.download_button(
                label="Download Transcript JSON",
                data=json.dumps(transcript_payload, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"livestorm-transcript-{current_session_id}-{transcript_timestamp}.json",
                mime="application/json",
            )


def render_chat_questions_block(
    df: Optional[pd.DataFrame],
    questions_df: Optional[pd.DataFrame],
    current_session_id: str,
) -> None:
    with st.expander("Chat & Questions", expanded=isinstance(df, pd.DataFrame) or isinstance(questions_df, pd.DataFrame)):
        if not isinstance(df, pd.DataFrame):
            st.caption("Fetch chat and questions to unlock engagement charts, tables, and exports.")
            return

        total_messages = int(len(df.index))
        total_questions = int(len(questions_df.index)) if isinstance(questions_df, pd.DataFrame) else 0
        unique_authors = int(df["author_id"].nunique()) if "author_id" in df.columns else 0
        unique_askers = 0
        if isinstance(questions_df, pd.DataFrame):
            if "asked_by" in questions_df.columns:
                unique_askers = int(questions_df["asked_by"].nunique())
            elif "question_author_id" in questions_df.columns:
                unique_askers = int(questions_df["question_author_id"].nunique())
        avg_chars = float(round(df["text_content"].fillna("").astype(str).str.len().mean(), 1)) if "text_content" in df.columns and total_messages else 0.0

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Messages", f"{total_messages}")
        col2.metric("Unique Chatters", f"{unique_authors}")
        col3.metric("Avg Msg Length", f"{avg_chars} chars")
        col4.metric("Questions", f"{total_questions}")
        col5.metric("Unique Askers", f"{unique_askers}")

        selected_charts = _render_chart_picker(
            "Select chat/questions charts to display.",
            CHAT_QUESTION_CHARTS,
            DEFAULT_CHAT_QUESTION_CHART_KEYS,
            key=f"chat_question_chart_selection_{current_session_id}",
        )
        _render_chart_grid(selected_charts, (df, questions_df), columns=2)

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
    with st.expander("Analysis", expanded=analysis_ran):
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

        with st.columns([1.2, 1.8])[0]:
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
            st.button("Running Analysis...", key="analysis_running_btn", type="primary", disabled=True)
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
            if not transcript_insights.get("segments_df", pd.DataFrame()).empty:
                cross_source = build_cross_source_insights(chat_df, questions_df, transcript_payload)
                st.markdown("**Cross-Source Preview**")
                st.caption("Select which cross-source charts to display.")
                selected_charts = _render_chart_picker(
                    "Cross-source charts.",
                    CROSS_CHARTS,
                    DEFAULT_CROSS_CHART_KEYS,
                    key=f"cross_chart_selection_{current_session_id}",
                )
                _render_chart_grid(selected_charts, (cross_source,), columns=1)
                reaction_moments_df = cross_source.get("reaction_moments_df", pd.DataFrame())
                if not reaction_moments_df.empty:
                    st.markdown("**Segments With The Most Reactions**")
                    st.dataframe(
                        reaction_moments_df[["session_stage", "start_label", "excerpt", "chat_messages", "question_count"]],
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.caption("Cross-source preview requires transcript segments with timing data.")

        if analysis_ran and analysis_md:
            st.markdown("**Analysis**")
            st.markdown(analysis_md)
            analysis_bytes = analysis_md.encode("utf-8")
            analysis_ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            with st.columns([1.1, 2.9])[0]:
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


def render_deep_analysis_block(
    current_session_id: str,
    deep_analysis_ran: bool,
    deep_analysis_md: str,
    transcript_available: bool,
    chat_available: bool,
    questions_available: bool,
) -> bool:
    with st.expander("Deeper Analysis", expanded=deep_analysis_ran):
        deep_analysis_available = bool(transcript_available and chat_available and questions_available)
        st.caption("Runs a deeper technical analysis using transcript JSON, chat, and questions with a dedicated prompt.")

        if st.session_state.get("deep_analysis_in_progress", False):
            st.button("Running Deeper Analysis...", key="deep_analysis_running_btn", type="primary", disabled=True)
            deep_analysis_button = False
        else:
            deep_analysis_button = st.button(
                "Deeper Analysis",
                key="deep_analysis_run_btn",
                type="primary",
                disabled=not deep_analysis_available,
            )

        if not deep_analysis_available:
            st.caption("Fetch transcript, chat, and questions to enable deep analysis.")

        if deep_analysis_ran and deep_analysis_md:
            st.markdown(deep_analysis_md)
            deep_analysis_bytes = deep_analysis_md.encode("utf-8")
            deep_analysis_ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            with st.columns([1.1, 2.9])[0]:
                download_format = st.selectbox(
                    "Download As",
                    options=["PDF", "Markdown"],
                    index=0,
                    key=f"deep_analysis_download_format_{current_session_id}",
                )
                if download_format == "Markdown":
                    st.download_button(
                        label="Download Deep Analysis",
                        data=deep_analysis_bytes,
                        file_name=f"livestorm-deep-analysis-{current_session_id}-{deep_analysis_ts}.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )
                else:
                    try:
                        pdf_bytes = analysis_markdown_to_pdf_bytes(deep_analysis_md, title="Livestorm Deep Analysis")
                        st.download_button(
                            label="Download Deep Analysis",
                            data=pdf_bytes,
                            file_name=f"livestorm-deep-analysis-{current_session_id}-{deep_analysis_ts}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    except RuntimeError as exc:
                        st.caption(str(exc))
        elif deep_analysis_ran:
            st.info("Deep analysis finished, but no markdown output was returned.")

        return deep_analysis_button


def render_content_repurpose_block(
    current_session_id: str,
    transcript_available: bool,
    chat_available: bool,
    questions_available: bool,
    content_repurpose_md: str,
    content_repurpose_ran: bool,
) -> bool:
    with st.expander("Content Repurposing", expanded=content_repurpose_ran):
        st.caption("Generate derivative content from the fetched sources and translate it into the selected output language.")

        content_options = {
            "summary": "Summary",
            "email": "Email Follow-up",
            "blog": "Blog Post",
            "social_media": "Social Media Posts",
        }
        st.selectbox(
            "Content Type",
            options=list(content_options.keys()),
            format_func=lambda value: content_options.get(value, value),
            key="content_repurpose_type",
        )
        st.radio(
            "Output Language",
            options=list(OUTPUT_LANGUAGE_LABELS.keys()),
            format_func=lambda choice: OUTPUT_LANGUAGE_LABELS.get(choice, choice),
            horizontal=True,
            key="content_repurpose_language",
        )

        repurpose_available = bool(transcript_available)
        if st.session_state.get("content_repurpose_in_progress", False):
            st.button(
                "Generating Content...",
                key="content_repurpose_running_btn",
                type="primary",
                disabled=True,
            )
            generate_button = False
        else:
            generate_button = st.button(
                "Generate Content",
                key="content_repurpose_run_btn",
                type="primary",
                disabled=not repurpose_available,
            )

        if not repurpose_available:
            st.caption("Fetch a transcript to enable content repurposing. Chat and questions are included automatically when available.")

        history = st.session_state.get("content_repurpose_history", [])
        if isinstance(history, list) and history:
            st.markdown("**Generated Content**")
            for index, item in enumerate(reversed(history), start=1):
                if not isinstance(item, dict):
                    continue
                item_type = str(item.get("type") or "content").replace("_", " ").title()
                item_language = str(item.get("language") or "")
                item_created_at = str(item.get("created_at") or "")
                item_markdown = str(item.get("markdown") or "")
                item_ts = str(item.get("timestamp") or datetime.utcnow().strftime("%Y%m%d-%H%M%S"))
                header_bits = [item_type]
                if item_language:
                    header_bits.append(item_language)
                if item_created_at:
                    header_bits.append(item_created_at)
                with st.expander(" | ".join(header_bits), expanded=(index == 1)):
                    st.markdown(item_markdown)
                    download_col1, download_col2 = st.columns(2)
                    with download_col1:
                        st.download_button(
                            label="Download Markdown",
                            data=item_markdown.encode("utf-8"),
                            file_name=f"livestorm-{str(item.get('type') or 'content')}-{current_session_id}-{item_ts}.md",
                            mime="text/markdown",
                            key=f"content_repurpose_md_download_{item_ts}_{index}",
                            use_container_width=True,
                        )
                    with download_col2:
                        try:
                            pdf_bytes = analysis_markdown_to_pdf_bytes(item_markdown, title=f"Livestorm {item_type}")
                            st.download_button(
                                label="Download PDF",
                                data=pdf_bytes,
                                file_name=f"livestorm-{str(item.get('type') or 'content')}-{current_session_id}-{item_ts}.pdf",
                                mime="application/pdf",
                                key=f"content_repurpose_pdf_download_{item_ts}_{index}",
                                use_container_width=True,
                            )
                        except RuntimeError as exc:
                            st.caption(str(exc))
        elif content_repurpose_ran and content_repurpose_md:
            st.markdown(content_repurpose_md)
        elif content_repurpose_ran:
            st.info("Content generation finished, but no markdown output was returned.")

        return generate_button
