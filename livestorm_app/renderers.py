from io import BytesIO
import base64
import html
import json
import re
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from livestorm_app.charts.chat_questions import CHAT_QUESTION_CHARTS
from livestorm_app.charts.common import brand_bar_chart, render_plotly_or_fallback
from livestorm_app.charts.common import ChartSpec
from livestorm_app.charts.cross import CROSS_CHARTS, DEFAULT_CROSS_CHART_KEYS
from livestorm_app.charts.transcript import (
    BURST_TRANSCRIPT_CHARTS,
    PACE_TRANSCRIPT_CHARTS,
    PAUSE_TRANSCRIPT_CHARTS,
    SPEAKER_TRANSCRIPT_CHARTS,
    TRANSCRIPT_CHART_CATEGORIES,
    TURN_TRANSCRIPT_CHARTS,
    UTTERANCE_DURATION_TRANSCRIPT_CHARTS,
    WORD_COUNT_TRANSCRIPT_CHARTS,
)
from livestorm_app.config import (
    OUTPUT_LANGUAGE_LABELS,
    SMART_RECAP_HYPE_ICON_PATH,
    SMART_RECAP_PROFESSIONAL_ICON_PATH,
    SMART_RECAP_SURPRISE_ICON_PATH,
)
from livestorm_app.session_overview import build_session_overview_data
from livestorm_app.services import (
    analysis_markdown_to_pdf_bytes,
    apply_speaker_name_map_to_insights,
    build_cross_source_insights,
    build_transcript_display_text,
    build_transcript_insights,
)


@st.cache_data(show_spinner=False)
def _read_file_base64(path_str: str) -> str:
    with open(path_str, "rb") as file_obj:
        return base64.b64encode(file_obj.read()).decode("ascii")


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


def _keep_analysis_panel_open() -> None:
    st.session_state["analysis_expander_open"] = True


def _activate_analysis_language(language: str) -> None:
    st.session_state["analysis_language"] = language
    _keep_analysis_panel_open()


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


def _render_readonly_text_block(title: str, value: str, *, height: int | None = None) -> None:
    safe_title = html.escape(title)
    safe_value = html.escape(value or "").replace("\n", "<br>")
    style_parts = [
        "background: #111827",
        "color: #f9fafb",
        "border: 1px solid #374151",
        "border-radius: 0.5rem",
        "padding: 0.85rem 1rem",
        "white-space: pre-wrap",
        "line-height: 1.5",
        "font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace",
        "font-size: 0.92rem",
    ]
    if height is not None:
        style_parts.extend(
            [
                f"max-height: {height}px",
                "overflow-y: auto",
            ]
        )
    container_style = "; ".join(style_parts)
    st.markdown(
        f"""
        <div style="margin: 0.25rem 0 1rem 0;">
          <div style="font-size: 0.95rem; font-weight: 600; margin-bottom: 0.35rem; color: #f5f7fa;">{safe_title}</div>
          <div style="{container_style}">{safe_value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_section_download_header(title: str, df: Optional[pd.DataFrame], filename: str, *, key: str) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        data_b64 = base64.b64encode(df.to_csv(index=False).encode("utf-8")).decode("ascii")
        st.markdown(
            f'**{title}** <a href="data:text/csv;base64,{data_b64}" download="{html.escape(filename)}">(CSV)</a>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"**{title}**")


def _render_text_download_header(title: str, label: str, data: bytes, filename: str, mime: str, *, key: str) -> None:
    data_b64 = base64.b64encode(data).decode("ascii")
    st.markdown(
        f'**{title}** <a href="data:{mime};base64,{data_b64}" download="{html.escape(filename)}">{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def _render_inline_download_links(title: str, downloads: List[Tuple[str, bytes, str, str]]) -> None:
    links: List[str] = []
    for label, data, filename, mime in downloads:
        data_b64 = base64.b64encode(data).decode("ascii")
        links.append(
            f'<a href="data:{mime};base64,{data_b64}" download="{html.escape(filename)}">{html.escape(label)}</a>'
        )
    links_html = " ".join(links)
    if links_html:
        st.markdown(f"**{title}** {links_html}", unsafe_allow_html=True)
    else:
        st.markdown(f"**{title}**")


def _render_csv_download_button(label: str, df: Optional[pd.DataFrame], filename: str, *, key: str) -> None:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return
    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


def _extract_title_and_description(markdown_text: str) -> Tuple[str, str]:
    if not isinstance(markdown_text, str) or not markdown_text.strip():
        return "", ""
    lines = [line.rstrip() for line in markdown_text.strip().splitlines()]
    title = ""
    description_lines: List[str] = []
    current_section = None

    def _normalize_heading_label(value: str) -> str:
        normalized = re.sub(r"^[#>*\-\s]+", "", value or "").strip()
        normalized = re.sub(r"^[^A-Za-z]+", "", normalized)
        normalized = re.sub(r"[*_`:\-]+$", "", normalized).strip().lower()
        return normalized

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_section == "description" and description_lines:
                description_lines.append("")
            continue
        if stripped.startswith("#"):
            heading = _normalize_heading_label(re.sub(r"^#+\s*", "", stripped))
            current_section = heading
            continue
        if re.fullmatch(r"[*_` ]*(title|description)[*_` ]*:?", stripped, flags=re.IGNORECASE):
            current_section = _normalize_heading_label(stripped)
            continue
        if current_section == "title" and stripped and not title:
            title = re.sub(r"^[*_`\"'“”]+|[*_`\"'“”]+$", "", stripped).strip()
            continue
        if current_section == "description":
            description_lines.append(line)
    if not title:
        fallback_lines = [line.strip() for line in lines if line.strip()]
        if fallback_lines:
            title = re.sub(r"^#+\s*", "", fallback_lines[0]).strip(" *_`\"'“”")
            description_lines = fallback_lines[1:]
    description = "\n".join(description_lines).strip()
    return title, description


def _normalize_markdown_for_display(markdown_text: str) -> str:
    if not isinstance(markdown_text, str) or not markdown_text.strip():
        return ""

    working_text = markdown_text.replace("\r\n", "\n")
    working_text = re.sub(r"```(?:[\w+-]+)?\n?", "", working_text)
    working_text = re.sub(r"`([^`]*)`", r"\1", working_text)
    working_text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", working_text)
    working_text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", working_text)
    working_text = re.sub(r"^\s*\|", "", working_text, flags=re.MULTILINE)
    working_text = re.sub(r"\|\s*$", "", working_text, flags=re.MULTILINE)
    working_text = re.sub(r"^\s*\|?[\-: ]+\|[\-:| ]*$", "", working_text, flags=re.MULTILINE)

    normalized_lines: List[str] = []
    for raw_line in working_text.splitlines():
        line = raw_line.rstrip()
        line = re.sub(r"^\s{0,3}#{1,6}\s+", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "• ", line)
        line = re.sub(r"^\s*\d+[.)]\s+", "", line)
        line = re.sub(r"^\s*>\s?", "", line)
        line = re.sub(r"[*_~#]+", "", line)
        line = re.sub(r"\s{2,}", " ", line)
        normalized_lines.append(line.strip())

    cleaned: List[str] = []
    previous_blank = False
    for line in normalized_lines:
        is_blank = not line
        if is_blank and previous_blank:
            continue
        cleaned.append(line)
        previous_blank = is_blank
    return "\n".join(cleaned).strip()


DEEP_ANALYSIS_SECTION_ORDER: List[Tuple[str, str]] = [
    ("executive_summary", "Executive Summary"),
    ("session_scores", "Session Scores"),
    ("key_moments", "Key Moments"),
    ("engagement_timeline", "Engagement Timeline"),
    ("technical_session_diagnostics", "Technical Diagnostics"),
    ("speaker_and_interaction_analysis", "Speaker Dynamics"),
    ("cognitive_load_analysis", "Cognitive Load"),
    ("audience_intent_analysis", "Audience Intent"),
    ("cross_source_synthesis", "Cross-Source Synthesis"),
    ("friction_and_risk_signals", "Friction And Risks"),
    ("business_signals_and_kpi_mentions", "Business Signals"),
    ("replay_optimization", "Replay Optimization"),
    ("actionable_recommendations", "Recommendations"),
    ("risks_ambiguities_and_data_quality_limits", "Limits And Uncertainty"),
]

UI_LABELS: Dict[str, Dict[str, str]] = {
    "English": {
        "overall_analysis": "Overall Analysis",
        "deeper_analysis": "Deeper Analysis",
        "summary": "Summary",
        "blog": "Blog Post",
        "email": "Email Follow-up",
        "social_media": "Social Media Posts",
        "overview": "Overview",
        "executive_summary": "Executive Summary",
        "session_scores": "Session Scores",
        "key_moments": "Key Moments",
        "engagement_timeline": "Engagement Timeline",
        "technical_session_diagnostics": "Technical Diagnostics",
        "speaker_and_interaction_analysis": "Speaker Dynamics",
        "cognitive_load_analysis": "Cognitive Load",
        "audience_intent_analysis": "Audience Intent",
        "cross_source_synthesis": "Cross-Source Synthesis",
        "friction_and_risk_signals": "Friction And Risks",
        "business_signals_and_kpi_mentions": "Business Signals",
        "replay_optimization": "Replay Optimization",
        "actionable_recommendations": "Recommendations",
        "risks_ambiguities_and_data_quality_limits": "Limits And Uncertainty",
    },
    "French": {
        "overall_analysis": "Analyse Globale",
        "deeper_analysis": "Analyse Approfondie",
        "summary": "Resume",
        "blog": "Article De Blog",
        "email": "Email De Suivi",
        "social_media": "Posts Reseaux Sociaux",
        "overview": "Vue D'Ensemble",
        "executive_summary": "Resume Executif",
        "session_scores": "Scores De Session",
        "key_moments": "Moments Cles",
        "engagement_timeline": "Chronologie De L'Engagement",
        "technical_session_diagnostics": "Diagnostic Technique",
        "speaker_and_interaction_analysis": "Dynamique Des Intervenants",
        "cognitive_load_analysis": "Charge Cognitive",
        "audience_intent_analysis": "Intentions De L'Audience",
        "cross_source_synthesis": "Synthese Croisee",
        "friction_and_risk_signals": "Friction Et Risques",
        "business_signals_and_kpi_mentions": "Signaux Business",
        "replay_optimization": "Optimisation Du Replay",
        "actionable_recommendations": "Recommandations",
        "risks_ambiguities_and_data_quality_limits": "Limites Et Incertitudes",
    },
}


def _ui_label(key: str, language: str = "English", fallback: str = "") -> str:
    localized = UI_LABELS.get(str(language), {})
    if key in localized:
        return localized[key]
    english = UI_LABELS.get("English", {})
    if key in english:
        return english[key]
    return fallback or key


def _normalize_section_key(value: str) -> str:
    normalized = re.sub(r"^\s*#+\s*", "", str(value or "").strip())
    normalized = re.sub(r"^\s*\d+[.)]\s*", "", normalized)
    normalized = normalized.strip().strip(":")
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized.lower())
    return normalized.strip("_")


def _parse_deep_analysis_sections(markdown_text: str, language: str = "English") -> List[Tuple[str, str, str]]:
    if not isinstance(markdown_text, str) or not markdown_text.strip():
        return []

    canonical_labels = {key: _ui_label(key, language, label) for key, label in DEEP_ANALYSIS_SECTION_ORDER}
    alias_map = {
        "technical_diagnostics": "technical_session_diagnostics",
        "technical_session_diagnostic": "technical_session_diagnostics",
        "speaker_interaction_analysis": "speaker_and_interaction_analysis",
        "speaker_and_interaction": "speaker_and_interaction_analysis",
        "speaker_dynamics": "speaker_and_interaction_analysis",
        "friction_and_risks": "friction_and_risk_signals",
        "friction_risk_signals": "friction_and_risk_signals",
        "business_signals": "business_signals_and_kpi_mentions",
        "data_quality_limits": "risks_ambiguities_and_data_quality_limits",
        "risks_ambiguities_and_limits": "risks_ambiguities_and_data_quality_limits",
    }

    sections: List[Tuple[str, str, str]] = []
    current_key = "overview"
    current_label = _ui_label("overview", language, "Overview")
    current_lines: List[str] = []

    def flush_current() -> None:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append((current_key, current_label, content))

    for raw_line in markdown_text.replace("\r\n", "\n").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        heading_match = re.match(r"^(?:#{1,6}\s+|\d+[.)]\s+)(.+?)\s*$", stripped)
        if heading_match:
            flush_current()
            heading_text = heading_match.group(1).strip()
            normalized_key = _normalize_section_key(heading_text)
            normalized_key = alias_map.get(normalized_key, normalized_key)
            current_key = normalized_key or "section"
            current_label = canonical_labels.get(current_key, heading_text)
            current_lines = []
            continue
        current_lines.append(line)
    flush_current()

    if not sections:
        return [("overview", _ui_label("overview", language, "Overview"), markdown_text.strip())]

    ordered: List[Tuple[str, str, str]] = []
    remaining = list(sections)
    for section_key, label in DEEP_ANALYSIS_SECTION_ORDER:
        for index, (key, _, content) in enumerate(remaining):
            if key == section_key:
                ordered.append((key, label, content))
                remaining.pop(index)
                break
    ordered.extend(remaining)
    return ordered


def _render_deep_analysis_sections(markdown_text: str, current_session_id: str, language: str = "English") -> None:
    sections = _parse_deep_analysis_sections(markdown_text, language=language)
    if not sections:
        st.markdown(markdown_text)
        return

    section_tabs = st.tabs([label for _, label, _ in sections])
    for tab, (_, _, content) in zip(section_tabs, sections):
        with tab:
            st.markdown(content)


def render_session_overview_block(
    session_payload: Optional[Dict[str, Any]],
    current_session_id: str,
    is_loading: bool = False,
) -> None:
    with st.expander("Session Overview", expanded=bool(session_payload) or is_loading):
        if is_loading:
            with st.spinner("Loading session overview..."):
                st.caption("Session overview is loading...")
        if not isinstance(session_payload, dict):
            if not is_loading:
                st.caption("Fetch session overview data to unlock high-level session context and attendee insights.")
            return

        overview = build_session_overview_data(session_payload)
        stats = overview.get("stats", {})
        overview_df = overview.get("overview_df", pd.DataFrame())
        people_df = overview.get("people_df", pd.DataFrame())
        country_df = overview.get("country_df", pd.DataFrame())
        role_df = overview.get("role_df", pd.DataFrame())
        attendance_distribution_df = overview.get("attendance_distribution_df", pd.DataFrame())
        engagement_top_df = overview.get("engagement_top_df", pd.DataFrame())

        registrants = int(stats.get("registrants_count") or 0)
        attendees = int(stats.get("attendees_count") or 0)
        replay_viewers = int(stats.get("replay_viewers_count") or 0)
        total_messages = int(stats.get("total_messages_count") or 0)
        total_questions = int(stats.get("total_questions_count") or 0)
        attendance_rate = stats.get("attendance_rate_pct")

        metric_col1, metric_col2, metric_col3, metric_col4, metric_col5, metric_col6 = st.columns(6)
        metric_col1.metric("Registrants", f"{registrants}")
        metric_col2.metric("Attendees", f"{attendees}")
        metric_col3.metric("Attendance Rate", f"{attendance_rate}%" if attendance_rate is not None else "n/a")
        metric_col4.metric("Replay Viewers", f"{replay_viewers}")
        metric_col5.metric("Chat Messages", f"{total_messages}")
        metric_col6.metric("Questions", f"{total_questions}")

        summary_tab, people_tab, charts_tab = st.tabs(["Summary", "People", "Charts"])

        with summary_tab:
            session_timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            _render_text_download_header(
                "Session payload",
                "(JSON)",
                data=json.dumps(session_payload, ensure_ascii=False, indent=2).encode("utf-8"),
                filename=f"livestorm-session-overview-{current_session_id}-{session_timestamp}.json",
                mime="application/json",
                key=f"session_overview_json_download_{current_session_id}",
            )
            if isinstance(overview_df, pd.DataFrame) and not overview_df.empty:
                st.dataframe(overview_df, use_container_width=True, hide_index=True)
            if isinstance(engagement_top_df, pd.DataFrame) and not engagement_top_df.empty:
                top_people_df = engagement_top_df[
                    [
                        column for column in [
                            "full_name",
                            "company",
                            "job_title",
                            "attendance_duration_label",
                            "messages_count",
                            "questions_count",
                            "up_votes_count",
                            "engagement_score",
                        ] if column in engagement_top_df.columns
                    ]
                ].copy()
                _render_section_download_header(
                    "Most Engaged People",
                    top_people_df,
                    f"livestorm-session-engagement-{current_session_id}.csv",
                    key=f"session_engagement_csv_{current_session_id}",
                )
                st.dataframe(top_people_df, use_container_width=True, hide_index=True)

        with people_tab:
            if isinstance(people_df, pd.DataFrame) and not people_df.empty:
                people_export_df = people_df[
                    [
                        column for column in [
                            "full_name",
                            "email",
                            "company",
                            "job_title",
                            "role",
                            "attended",
                            "attendance_rate",
                            "attendance_duration_label",
                            "has_viewed_replay",
                            "ip_country_name",
                            "ip_city",
                            "messages_count",
                            "questions_count",
                            "up_votes_count",
                        ] if column in people_df.columns
                    ]
                ].copy()
                _render_section_download_header(
                    "People",
                    people_export_df,
                    f"livestorm-session-people-{current_session_id}.csv",
                    key=f"session_people_csv_{current_session_id}",
                )
                st.dataframe(people_export_df, use_container_width=True, hide_index=True)
            else:
                st.caption("No people details are available in this session payload.")

        with charts_tab:
            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                if isinstance(country_df, pd.DataFrame) and not country_df.empty:
                    country_chart = brand_bar_chart(
                        country_df,
                        "ip_country_name",
                        "people_count",
                        "Country",
                        "People",
                        ["attendees"],
                    )
                    st.markdown("**Attendance By Country**")
                    render_plotly_or_fallback(
                        country_chart,
                        fallback_df=country_df,
                        fallback_columns=["ip_country_name", "people_count", "attendees"],
                    )
                else:
                    st.caption("Country data is not available for this session.")
            with chart_col2:
                if isinstance(role_df, pd.DataFrame) and not role_df.empty:
                    role_chart = brand_bar_chart(
                        role_df,
                        "role",
                        "people_count",
                        "Role",
                        "People",
                        [],
                    )
                    st.markdown("**People By Role**")
                    render_plotly_or_fallback(
                        role_chart,
                        fallback_df=role_df,
                        fallback_columns=["role", "people_count"],
                    )
                else:
                    st.caption("Role data is not available for this session.")

            if isinstance(attendance_distribution_df, pd.DataFrame) and not attendance_distribution_df.empty:
                attendance_chart = brand_bar_chart(
                    attendance_distribution_df,
                    "attendance_band",
                    "people_count",
                    "Attendance Band",
                    "People",
                    [],
                )
                st.markdown("**Attendance Rate Distribution**")
                render_plotly_or_fallback(
                    attendance_chart,
                    fallback_df=attendance_distribution_df,
                    fallback_columns=["attendance_band", "people_count"],
                )
            else:
                st.caption("Attendance distribution is not available for this session.")


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
                with st.popover("Edit Speaker Labels"):
                    with st.form(key=f"speaker_labels_form_{session_key}"):
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
                        save_speaker_labels = st.form_submit_button("Save")
                    if save_speaker_labels and updated_map != current_speaker_map:
                        session_speaker_names[session_key] = updated_map
                        st.session_state["transcript_speaker_names"] = session_speaker_names
                        current_speaker_map = updated_map
        transcript_insights = apply_speaker_name_map_to_insights(transcript_insights, current_speaker_map)
        summary = transcript_insights.get("summary", {})
        segments_df = transcript_insights.get("segments_df", pd.DataFrame())
        sentence_df = transcript_insights.get("sentence_df", pd.DataFrame())
        words_df = transcript_insights.get("words_df", pd.DataFrame())
        pace_df = transcript_insights.get("pace_df", pd.DataFrame())
        speaker_df = transcript_insights.get("speaker_df", pd.DataFrame())
        speaker_turns_df = transcript_insights.get("speaker_turns_df", pd.DataFrame())
        timeline_df = transcript_insights.get("timeline_df", pd.DataFrame())
        burst_df = transcript_insights.get("burst_df", pd.DataFrame())
        utterance_duration_distribution_df = transcript_insights.get("utterance_duration_distribution_df", pd.DataFrame())
        numbers_df = transcript_insights.get("numbers_df", pd.DataFrame())
        key_moments_df = transcript_insights.get("key_moments_df", pd.DataFrame())
        replay_navigation_df = transcript_insights.get("replay_navigation_df", pd.DataFrame())
        low_energy_df = transcript_insights.get("low_energy_df", pd.DataFrame())
        silence_df = transcript_insights.get("silence_df", pd.DataFrame())
        pause_distribution_df = transcript_insights.get("pause_distribution_df", pd.DataFrame())

        has_pause_timing = isinstance(silence_df, pd.DataFrame) and not silence_df.empty
        has_pace_timing = isinstance(pace_df, pd.DataFrame) and not pace_df.empty
        has_speaker_timing = isinstance(speaker_df, pd.DataFrame) and not speaker_df.empty and isinstance(speaker_turns_df, pd.DataFrame) and not speaker_turns_df.empty
        has_turn_data = isinstance(speaker_turns_df, pd.DataFrame) and not speaker_turns_df.empty
        has_utterance_data = isinstance(segments_df, pd.DataFrame) and not segments_df.empty
        has_word_count_data = isinstance(timeline_df, pd.DataFrame) and not timeline_df.empty and isinstance(speaker_df, pd.DataFrame) and not speaker_df.empty
        has_burst_data = isinstance(burst_df, pd.DataFrame) and not burst_df.empty

        if isinstance(segments_df, pd.DataFrame) and not segments_df.empty:
            transcript_lines = []
            for _, row in segments_df.iterrows():
                segment_text = str(row.get("text") or "").strip()
                if not segment_text:
                    continue
                prefix_parts = []
                start_label = str(row.get("start_label") or "").strip()
                speaker_label = str(row.get("speaker") or "").strip()
                if start_label:
                    prefix_parts.append(f"[{start_label}]")
                if speaker_label:
                    prefix_parts.append(speaker_label.upper())
                header_line = " ".join(prefix_parts).strip()
                if header_line:
                    transcript_lines.append(f"{header_line}\n{segment_text}")
                else:
                    transcript_lines.append(segment_text)
            if transcript_lines:
                effective_transcript_text = "\n\n".join(transcript_lines)

        if has_pause_timing or has_pace_timing or has_speaker_timing or has_turn_data or has_utterance_data or has_word_count_data or has_burst_data:
            transcript_tab, highlights_tab, *category_tabs = st.tabs(["Transcript", "Highlights"] + [label for label, _ in TRANSCRIPT_CHART_CATEGORIES])

            with transcript_tab:
                transcript_entries = [entry.strip() for entry in effective_transcript_text.split("\n\n") if entry.strip()]
                transcript_search = st.text_input(
                    "Search transcript",
                    key=f"transcript_search_{current_session_id}",
                    placeholder="Search by keyword",
                ).strip()
                if transcript_search:
                    search_pattern = re.compile(re.escape(transcript_search), re.IGNORECASE)
                    matching_entries = [entry for entry in transcript_entries if search_pattern.search(entry)]
                    st.caption(f"{len(matching_entries)} match(es) found for `{transcript_search}`")
                    if matching_entries:
                        _render_readonly_text_block("Matches", "\n\n".join(matching_entries), height=180)
                    else:
                        st.caption("No matches found in the visible transcript.")
                if effective_transcript_text:
                    transcript_timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
                    _render_text_download_header(
                        "Transcript text",
                        "(JSON)",
                        data=json.dumps(transcript_payload, ensure_ascii=False, indent=2).encode("utf-8"),
                        filename=f"livestorm-transcript-{current_session_id}-{transcript_timestamp}.json",
                        mime="application/json",
                        key=f"transcript_json_download_{current_session_id}",
                    )
                else:
                    st.markdown("**Transcript text**")
                _render_readonly_text_block("", effective_transcript_text, height=320)

            with highlights_tab:
                if not key_moments_df.empty:
                    _render_section_download_header(
                        "Key Moments",
                        key_moments_df,
                        f"livestorm-key-moments-{current_session_id}.csv",
                        key=f"key_moments_csv_{current_session_id}",
                    )
                    st.dataframe(
                        key_moments_df[["time_label", "speaker", "score", "reasons", "excerpt"]],
                        use_container_width=True,
                        hide_index=True,
                    )
                if not numbers_df.empty:
                    _render_section_download_header(
                        "Numbers & KPI Extraction",
                        numbers_df,
                        f"livestorm-numbers-kpis-{current_session_id}.csv",
                        key=f"numbers_csv_{current_session_id}",
                    )
                    number_columns = [
                        column for column in ["mention", "kind", "speaker", "time_label", "context"]
                        if column in numbers_df.columns
                    ]
                    st.dataframe(
                        numbers_df[number_columns].head(20),
                        use_container_width=True,
                        hide_index=True,
                    )
                if isinstance(segments_df, pd.DataFrame) and not segments_df.empty:
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
                        _render_section_download_header(
                            "Segments",
                            display_segments[keep_columns],
                            f"livestorm-segments-{current_session_id}.csv",
                            key=f"segments_csv_{current_session_id}",
                        )
                        st.dataframe(display_segments[keep_columns], use_container_width=True, hide_index=True)
                if isinstance(sentence_df, pd.DataFrame) and not sentence_df.empty:
                    sentence_display_df = sentence_df[["start_seconds", "speaker", "word_count", "confidence", "sentence"]].head(100)
                    _render_section_download_header(
                        "Sentences",
                        sentence_display_df,
                        f"livestorm-sentences-{current_session_id}.csv",
                        key=f"sentences_csv_{current_session_id}",
                    )
                    st.dataframe(
                        sentence_display_df,
                        use_container_width=True,
                        hide_index=True,
                    )

            category_tab_map = {
                label: tab for (label, _), tab in zip(TRANSCRIPT_CHART_CATEGORIES, category_tabs)
            }

            with category_tab_map["Silence / Pause Metrics"]:
                if has_pause_timing:
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    metric_col1.metric("Average Pause Duration", f"{summary.get('avg_pause_seconds', 0)}s")
                    metric_col2.metric("Longest Pause", f"{summary.get('longest_silence_seconds', 0)}s")
                    metric_col3.metric("Pauses > 1s", f"{summary.get('pause_count_over_1s', 0)}")
                    if summary.get("pause_timing_source") == "segment":
                        st.caption("Using segment timing because word-level timing is not available.")
                    _render_section_download_header(
                        "Pause Timeline & Histogram",
                        silence_df if isinstance(silence_df, pd.DataFrame) and not silence_df.empty else pause_distribution_df,
                        f"livestorm-pause-data-{current_session_id}.csv",
                        key=f"pause_data_csv_{current_session_id}",
                    )
                    _render_chart_grid(PAUSE_TRANSCRIPT_CHARTS, (transcript_insights,), columns=2)
                else:
                    st.caption("Pause metrics are available when transcript timing is included.")

            with category_tab_map["Speaking Pace"]:
                if has_pace_timing:
                    pace_col1, pace_col2, pace_col3 = st.columns(3)
                    pace_col1.metric("Average WPM", f"{summary.get('avg_words_per_minute', 0)}")
                    pace_col2.metric("Min WPM", f"{summary.get('min_wpm', 0)}")
                    pace_col3.metric("Max WPM", f"{summary.get('max_wpm', 0)}")
                    _render_section_download_header(
                        "Speaking Pace",
                        pace_df,
                        f"livestorm-speaking-pace-{current_session_id}.csv",
                        key=f"speaking_pace_csv_{current_session_id}",
                    )
                    _render_chart_grid(PACE_TRANSCRIPT_CHARTS, (transcript_insights,), columns=2)
                else:
                    st.caption("Speaking pace metrics are available when transcript timing is included.")

            with category_tab_map["Speaker Airtime"]:
                if has_speaker_timing:
                    _render_section_download_header(
                        "Speaker Metrics",
                        speaker_df,
                        f"livestorm-speaker-airtime-{current_session_id}.csv",
                        key=f"speaker_airtime_csv_{current_session_id}",
                    )
                    _render_chart_grid(SPEAKER_TRANSCRIPT_CHARTS, (transcript_insights,), columns=2)
                    st.dataframe(
                        speaker_df.rename(
                            columns={
                                "speaker": "Speaker",
                                "speaking_label": "Speaking Time",
                                "share_pct": "% Contribution",
                            }
                        )[["Speaker", "Speaking Time", "% Contribution"]],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.caption("Speaker airtime metrics are available when speaker labels and timing are included.")

            with category_tab_map["Speaker Turns"]:
                if has_turn_data:
                    turn_summary_df = (
                        speaker_turns_df.groupby("speaker", as_index=False)
                        .agg(
                            turn_count=("speaker", "size"),
                            avg_turn_duration_seconds=("duration_seconds", "mean"),
                        )
                        .sort_values(by=["turn_count", "avg_turn_duration_seconds"], ascending=[False, False])
                    )
                    turn_summary_df["avg_turn_duration_seconds"] = turn_summary_df["avg_turn_duration_seconds"].round(2)
                    _render_section_download_header(
                        "Speaker Turns",
                        turn_summary_df,
                        f"livestorm-speaker-turns-summary-{current_session_id}.csv",
                        key=f"speaker_turns_summary_csv_{current_session_id}",
                    )
                    _render_chart_grid(TURN_TRANSCRIPT_CHARTS, (transcript_insights,), columns=1)
                    st.dataframe(
                        turn_summary_df.rename(
                            columns={
                                "speaker": "Speaker",
                                "turn_count": "Number Of Turns",
                                "avg_turn_duration_seconds": "Avg Duration Per Turn (sec)",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.caption("Speaker turn metrics are available when consecutive timed utterances are included.")

            with category_tab_map["Utterance Duration"]:
                if has_utterance_data:
                    utterance_duration_df = segments_df["duration_seconds"].dropna()
                    utterance_col1, utterance_col2 = st.columns(2)
                    utterance_col1.metric("Avg Utterance Duration", f"{round(float(utterance_duration_df.mean()), 2) if not utterance_duration_df.empty else 0}s")
                    utterance_col2.metric("Longest Utterance", f"{round(float(utterance_duration_df.max()), 2) if not utterance_duration_df.empty else 0}s")
                    _render_section_download_header(
                        "Utterance Duration",
                        utterance_duration_distribution_df,
                        f"livestorm-utterance-duration-{current_session_id}.csv",
                        key=f"utterance_duration_csv_{current_session_id}",
                    )
                    _render_chart_grid(UTTERANCE_DURATION_TRANSCRIPT_CHARTS, (transcript_insights,), columns=1)
                else:
                    st.caption("Utterance duration metrics are available when utterance timing is included.")

            with category_tab_map["Words Count"]:
                if has_word_count_data:
                    st.metric("Total Words", f"{summary.get('total_words', 0)}")
                    _render_section_download_header(
                        "Words Count",
                        speaker_df[["speaker", "words"]] if isinstance(speaker_df, pd.DataFrame) and not speaker_df.empty else timeline_df,
                        f"livestorm-words-count-{current_session_id}.csv",
                        key=f"words_count_csv_{current_session_id}",
                    )
                    _render_chart_grid(WORD_COUNT_TRANSCRIPT_CHARTS, (transcript_insights,), columns=2)
                    st.dataframe(
                        speaker_df.rename(columns={"speaker": "Speaker", "words": "Words"})[["Speaker", "Words"]],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.caption("Word count metrics are available when transcript timing is included.")

            with category_tab_map["Speaking Segments"]:
                if has_burst_data:
                    burst_durations = burst_df["duration_seconds"].dropna()
                    burst_col1, burst_col2 = st.columns(2)
                    burst_col1.metric("Avg Speaking Burst", f"{round(float(burst_durations.mean()), 2) if not burst_durations.empty else 0}s")
                    burst_col2.metric("Longest Continuous Speech", f"{round(float(burst_durations.max()), 2) if not burst_durations.empty else 0}s")
                    _render_section_download_header(
                        "Speaking Segments",
                        burst_df,
                        f"livestorm-speaking-bursts-{current_session_id}.csv",
                        key=f"speaking_bursts_csv_{current_session_id}",
                    )
                    _render_chart_grid(BURST_TRANSCRIPT_CHARTS, (transcript_insights,), columns=1)
                else:
                    st.caption("Speaking segment metrics are available when pause-derived burst data is included.")
        elif isinstance(segments_df, pd.DataFrame) and not segments_df.empty:
            st.info("This transcript has segment text, but not enough timing detail to render the current transcript categories.")
            _render_readonly_text_block("Transcript text", effective_transcript_text, height=320)
        elif effective_transcript_text:
            _render_readonly_text_block("Transcript text", effective_transcript_text, height=320)
        else:
            st.info("Transcript payload fetched successfully, but there is no transcript text to display.")


def render_chat_questions_block(
    df: Optional[pd.DataFrame],
    questions_df: Optional[pd.DataFrame],
    current_session_id: str,
    is_loading: bool = False,
) -> None:
    with st.expander("Chat & Questions", expanded=isinstance(df, pd.DataFrame) or isinstance(questions_df, pd.DataFrame) or is_loading):
        if is_loading:
            with st.spinner("Loading chat & questions..."):
                st.caption("Chat & Questions loading...")
        if not isinstance(df, pd.DataFrame):
            if is_loading:
                return
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

        chat_tab, questions_tab, contributors_tab, activity_tab, coverage_tab = st.tabs(
            ["Chat", "Questions", "Top Contributors", "Activity Over Time", "Question Response Coverage"]
        )
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
        with contributors_tab:
            CHAT_QUESTION_CHARTS[0].renderer(df, questions_df)
        with activity_tab:
            CHAT_QUESTION_CHARTS[1].renderer(df, questions_df)
        with coverage_tab:
            CHAT_QUESTION_CHARTS[2].renderer(df, questions_df)


def render_analysis_block(
    current_session_id: str,
    analysis_ran: bool,
    analysis_md: str,
    deep_analysis_ran: bool,
    deep_analysis_md: str,
    transcript_available: bool,
    chat_available: bool,
    questions_available: bool,
    transcript_payload: Optional[Dict[str, Any]] = None,
    chat_df: Optional[pd.DataFrame] = None,
    questions_df: Optional[pd.DataFrame] = None,
) -> Tuple[bool, bool]:
    analysis_expander_open = bool(
        st.session_state.get("analysis_expander_open", analysis_ran or deep_analysis_ran)
    )
    with st.expander("Analysis", expanded=analysis_expander_open):
        chat_questions_available = chat_available and questions_available
        analysis_available = bool(transcript_available or chat_questions_available)
        deep_analysis_available = bool(transcript_available and chat_available and questions_available)
        analysis_bundle = st.session_state.get("analysis_bundle", {})
        deep_analysis_bundle = st.session_state.get("deep_analysis_bundle", {})
        analyze_button = False
        deep_analysis_button = False
        available_languages = [
            language
            for language in OUTPUT_LANGUAGE_LABELS.keys()
            if str(analysis_bundle.get(language) or "").strip() or str(deep_analysis_bundle.get(language) or "").strip()
        ]
        all_languages_available = len(available_languages) == len(OUTPUT_LANGUAGE_LABELS)
        tab_languages = available_languages if all_languages_available and available_languages else list(OUTPUT_LANGUAGE_LABELS.keys())
        language_tabs = st.tabs([OUTPUT_LANGUAGE_LABELS.get(language, language) for language in tab_languages])

        for language_tab, language in zip(language_tabs, tab_languages):
            with language_tab:
                language_analysis_md = str(analysis_bundle.get(language) or "")
                language_deep_analysis_md = str(deep_analysis_bundle.get(language) or "")

                overall_tab, deeper_tab = st.tabs(
                    [
                        _ui_label("overall_analysis", language, "Overall Analysis"),
                        _ui_label("deeper_analysis", language, "Deeper Analysis"),
                    ]
                )

                with overall_tab:
                    if transcript_available and chat_questions_available:
                        st.caption("Uses the transcript, chat messages, and submitted questions to generate the overall analysis.")
                    elif transcript_available:
                        st.caption("Uses the transcript to generate the overall analysis.")
                    elif chat_questions_available:
                        st.caption("Uses chat messages and submitted questions to generate the overall analysis.")
                    else:
                        st.caption("No analysis inputs are available yet.")
                    has_analysis_for_language = bool(language_analysis_md.strip())
                    if has_analysis_for_language:
                        current_analyze_button = False
                    elif st.session_state.get("analysis_in_progress", False) and st.session_state.get("analysis_language") == language:
                        st.button(
                            "Running Analysis...",
                            key=f"analysis_running_btn_{language}",
                            type="primary",
                            disabled=True,
                        )
                        current_analyze_button = False
                    else:
                        current_analyze_button = st.button(
                            "Run analysis",
                            key=f"analysis_run_btn_{language}",
                            type="primary",
                            disabled=not analysis_available,
                            on_click=_activate_analysis_language,
                            args=(language,),
                        )
                    analyze_button = analyze_button or current_analyze_button

                    if has_analysis_for_language:
                        st.markdown(language_analysis_md)
                        analysis_bytes = language_analysis_md.encode("utf-8")
                        analysis_ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
                        with st.columns([1.1, 2.9])[0]:
                            download_format = st.selectbox(
                                "Download As",
                                options=["PDF", "Markdown"],
                                index=0,
                                key=f"analysis_download_format_{current_session_id}_{language}",
                            )
                            if download_format == "Markdown":
                                st.download_button(
                                    label="Download Analysis",
                                    data=analysis_bytes,
                                    file_name=f"livestorm-analysis-{language.lower()}-{current_session_id}-{analysis_ts}.md",
                                    mime="text/markdown",
                                    use_container_width=True,
                                )
                            else:
                                try:
                                    pdf_bytes = analysis_markdown_to_pdf_bytes(language_analysis_md, title="Livestorm Session Analysis")
                                    st.download_button(
                                        label="Download Analysis",
                                        data=pdf_bytes,
                                        file_name=f"livestorm-analysis-{language.lower()}-{current_session_id}-{analysis_ts}.pdf",
                                        mime="application/pdf",
                                        use_container_width=True,
                                    )
                                except RuntimeError as exc:
                                    st.caption(str(exc))
                    elif analysis_ran and st.session_state.get("analysis_language") == language:
                        st.info("Analysis finished, but no markdown output was returned.")

                with deeper_tab:
                    st.caption("Uses the full detailed transcript JSON, chat, and questions to generate a deeper analysis.")
                    should_render_cross_source = bool(
                        transcript_available
                        and chat_questions_available
                        and isinstance(transcript_payload, dict)
                    )
                    has_deep_analysis_for_language = bool(language_deep_analysis_md.strip())
                    if has_deep_analysis_for_language:
                        current_deep_analysis_button = False
                    elif st.session_state.get("deep_analysis_in_progress", False) and st.session_state.get("analysis_language") == language:
                        st.button(
                            "Running Deeper Analysis...",
                            key=f"deep_analysis_running_btn_{language}",
                            type="primary",
                            disabled=True,
                        )
                        current_deep_analysis_button = False
                    else:
                        current_deep_analysis_button = st.button(
                            "Deeper Analysis",
                            key=f"deep_analysis_run_btn_{language}",
                            type="primary",
                            disabled=not deep_analysis_available,
                            on_click=_activate_analysis_language,
                            args=(language,),
                        )
                    deep_analysis_button = deep_analysis_button or current_deep_analysis_button

                    if not deep_analysis_available:
                        st.caption("Fetch Data to enable deep analysis.")

                    if should_render_cross_source and has_deep_analysis_for_language:
                        transcript_insights = build_transcript_insights(transcript_payload)
                        if not transcript_insights.get("segments_df", pd.DataFrame()).empty:
                            cross_source = build_cross_source_insights(chat_df, questions_df, transcript_payload)
                            if CROSS_CHARTS:
                                CROSS_CHARTS[0].renderer(
                                    cross_source,
                                    chart_key=f"cross_chart_{current_session_id}_{language}",
                                )
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

                    if has_deep_analysis_for_language:
                        _render_deep_analysis_sections(language_deep_analysis_md, current_session_id, language=language)
                        deep_analysis_bytes = language_deep_analysis_md.encode("utf-8")
                        deep_analysis_ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
                        with st.columns([1.1, 2.9])[0]:
                            download_format = st.selectbox(
                                "Download As",
                                options=["PDF", "Markdown"],
                                index=0,
                                key=f"deep_analysis_download_format_{current_session_id}_{language}",
                            )
                            if download_format == "Markdown":
                                st.download_button(
                                    label="Download Deep Analysis",
                                    data=deep_analysis_bytes,
                                    file_name=f"livestorm-deep-analysis-{language.lower()}-{current_session_id}-{deep_analysis_ts}.md",
                                    mime="text/markdown",
                                    use_container_width=True,
                                )
                            else:
                                try:
                                    pdf_bytes = analysis_markdown_to_pdf_bytes(language_deep_analysis_md, title="Livestorm Deep Analysis")
                                    st.download_button(
                                        label="Download Deep Analysis",
                                        data=pdf_bytes,
                                        file_name=f"livestorm-deep-analysis-{language.lower()}-{current_session_id}-{deep_analysis_ts}.pdf",
                                        mime="application/pdf",
                                        use_container_width=True,
                                    )
                                except RuntimeError as exc:
                                    st.caption(str(exc))
                    elif deep_analysis_ran and st.session_state.get("analysis_language") == language:
                        st.info("Deep analysis finished, but no markdown output was returned.")

        return analyze_button, deep_analysis_button


def render_content_repurpose_block(
    current_session_id: str,
    transcript_available: bool,
    chat_available: bool,
    questions_available: bool,
    content_repurpose_bundle: Dict[str, Dict[str, str]],
    content_repurpose_ran: bool,
) -> bool:
    with st.expander("Content Repurposing", expanded=content_repurpose_ran):
        all_languages_generated = bool(
            isinstance(content_repurpose_bundle, dict)
            and all(
                isinstance(content_repurpose_bundle.get(language), dict)
                and any(str(value or "").strip() for value in content_repurpose_bundle.get(language, {}).values())
                for language in OUTPUT_LANGUAGE_LABELS.keys()
            )
        )
        if not all_languages_generated:
            st.radio(
                "Output Language",
                options=list(OUTPUT_LANGUAGE_LABELS.keys()),
                format_func=lambda choice: OUTPUT_LANGUAGE_LABELS.get(choice, choice),
                horizontal=True,
                key="content_repurpose_language",
            )
        selected_language = st.session_state.get("content_repurpose_language", "English")
        language_bundle = content_repurpose_bundle.get(selected_language, {}) if isinstance(content_repurpose_bundle, dict) else {}
        language_already_generated = bool(isinstance(language_bundle, dict) and any(str(value or "").strip() for value in language_bundle.values()))

        repurpose_available = bool(transcript_available)
        if language_already_generated:
            generate_button = False
        elif st.session_state.get("content_repurpose_in_progress", False):
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
                disabled=not repurpose_available or language_already_generated,
            )

        if not repurpose_available:
            st.caption("Fetch Data to enable content repurposing.")
        elif language_already_generated:
            st.caption(f"Content has already been generated for {selected_language}. Switch language to generate the other version.")

        content_items = [
            ("summary", "summary"),
            ("blog", "blog"),
            ("email", "email"),
            ("social_media", "social_media"),
        ]
        available_languages = []
        if isinstance(content_repurpose_bundle, dict):
            for language in OUTPUT_LANGUAGE_LABELS.keys():
                bundle = content_repurpose_bundle.get(language, {})
                if isinstance(bundle, dict) and any(str(value or "").strip() for value in bundle.values()):
                    available_languages.append(language)

        if content_repurpose_ran and available_languages:
            language_tabs = st.tabs([OUTPUT_LANGUAGE_LABELS.get(language, language) for language in available_languages])
            for language_tab, language in zip(language_tabs, available_languages):
                with language_tab:
                    bundle = content_repurpose_bundle.get(language, {})
                    available_items = [
                        (key, _ui_label(label_key, language), str(bundle.get(key) or "").strip())
                        for key, label_key in content_items
                    ]
                    available_items = [(key, label, markdown) for key, label, markdown in available_items if markdown]
                    if not available_items:
                        st.caption("No generated content is available for this language.")
                        continue
                    content_tabs = st.tabs([label for _, label, _ in available_items])
                    for tab, (_, label, markdown) in zip(content_tabs, available_items):
                        with tab:
                            content_ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
                            downloads: List[Tuple[str, bytes, str, str]] = [
                                (
                                    "(MD)",
                                    markdown.encode("utf-8"),
                                    f"livestorm-content-{language.lower()}-{label.lower().replace(' ', '-')}-{current_session_id}-{content_ts}.md",
                                    "text/markdown",
                                )
                            ]
                            try:
                                pdf_bytes = analysis_markdown_to_pdf_bytes(markdown, title=f"{language} - {label}")
                                downloads.append(
                                    (
                                        "(PDF)",
                                        pdf_bytes,
                                        f"livestorm-content-{language.lower()}-{label.lower().replace(' ', '-')}-{current_session_id}-{content_ts}.pdf",
                                        "application/pdf",
                                    )
                                )
                            except RuntimeError:
                                pass
                            _render_inline_download_links(label, downloads)
                            _render_readonly_text_block("", _normalize_markdown_for_display(markdown), height=520)
        elif content_repurpose_ran:
            st.info("Content generation finished, but no saved content is available yet.")

        return generate_button


def render_smart_recap_block(
    current_session_id: str,
    transcript_available: bool,
    smart_recap_bundle: Dict[str, str],
    smart_recap_ran: bool,
) -> Optional[str]:
    with st.expander("Smart Recap", expanded=smart_recap_ran):
        if not transcript_available:
            st.caption("Fetch Data to enable Smart Recap.")

        recap_items = [
            ("professional", "Professional", SMART_RECAP_PROFESSIONAL_ICON_PATH),
            ("hype", "Hype", SMART_RECAP_HYPE_ICON_PATH),
            ("surprise", "Suprise Me!", SMART_RECAP_SURPRISE_ICON_PATH),
        ]
        if SMART_RECAP_SURPRISE_ICON_PATH.exists():
            surprise_icon_b64 = _read_file_base64(str(SMART_RECAP_SURPRISE_ICON_PATH))
            st.markdown(
                f"""
                <style>
                .st-key-smart_recap_run_btn_surprise button,
                .st-key-smart_recap_running_btn_surprise button {{
                    width: 250px;
                    height: 250px;
                    padding: 0;
                    border: none;
                    background: transparent url("data:image/png;base64,{surprise_icon_b64}") center center / contain no-repeat !important;
                    color: transparent !important;
                    box-shadow: none !important;
                }}
                .st-key-smart_recap_run_btn_surprise button:hover,
                .st-key-smart_recap_run_btn_surprise button:focus,
                .st-key-smart_recap_run_btn_surprise button:active {{
                    border: none !important;
                    box-shadow: none !important;
                    transform: scale(1.01);
                }}
                .st-key-smart_recap_run_btn_surprise button p,
                .st-key-smart_recap_running_btn_surprise button p {{
                    opacity: 0 !important;
                }}
                </style>
                """,
                unsafe_allow_html=True,
            )
        requested_tone: Optional[str] = None
        tone_in_progress = str(st.session_state.get("smart_recap_in_progress_tone") or "").strip().lower()
        recap_tabs = st.tabs([label for _, label, _ in recap_items])

        for tab, (key, label, icon_path) in zip(recap_tabs, recap_items):
            with tab:
                try:
                    markdown = str(smart_recap_bundle.get(key) or "").strip()
                    is_generating_this_tone = bool(
                        st.session_state.get("smart_recap_in_progress", False)
                        and tone_in_progress == key
                    )
                    if not markdown:
                        button_col, _ = st.columns([0.26, 0.74])
                        with button_col:
                            if is_generating_this_tone:
                                st.button(
                                    f"Generating {label} Recap",
                                    key=f"smart_recap_running_btn_{key}",
                                    type="primary",
                                    disabled=True,
                                )
                            else:
                                clicked = st.button(
                                    "Generate",
                                    key=f"smart_recap_run_btn_{key}",
                                    type="primary",
                                    disabled=not transcript_available or bool(st.session_state.get("smart_recap_in_progress", False)),
                                )
                                if clicked:
                                    requested_tone = key
                        if is_generating_this_tone:
                            st.caption(f"Generating {label} Recap...")

                    if markdown:
                        title, description = _extract_title_and_description(markdown)
                        plain_description = _normalize_markdown_for_display(description)
                        plain_body = plain_description or _normalize_markdown_for_display(markdown)
                        pdf_title = title.strip() if title.strip() else "Smart Recap"
                        md_filename = f"livestorm-smart-recap-{label.lower()}-{current_session_id}.md"
                        pdf_filename = f"livestorm-smart-recap-{label.lower()}-{current_session_id}.pdf"
                        pdf_state_key = f"smart_recap_pdf_bytes_{current_session_id}_{key}"
                        pdf_button_key = f"smart_recap_prepare_pdf_{current_session_id}_{key}"

                        download_links: List[Tuple[str, bytes, str, str]] = [
                            ("(MD)", markdown.encode("utf-8"), md_filename, "text/markdown")
                        ]
                        if title:
                            _render_inline_download_links(title, download_links)
                        else:
                            _render_inline_download_links(label, download_links)

                        prepare_pdf = st.button(
                            "Prepare PDF",
                            key=pdf_button_key,
                            type="secondary",
                        )
                        if prepare_pdf and pdf_state_key not in st.session_state:
                            pdf_source = plain_body if plain_body else _normalize_markdown_for_display(markdown)
                            try:
                                st.session_state[pdf_state_key] = analysis_markdown_to_pdf_bytes(pdf_source, title=pdf_title)
                            except RuntimeError:
                                st.info("PDF export is unavailable until `reportlab` is installed.")

                        pdf_bytes = st.session_state.get(pdf_state_key)
                        if isinstance(pdf_bytes, bytes) and pdf_bytes:
                            st.download_button(
                                "Download PDF",
                                data=pdf_bytes,
                                file_name=pdf_filename,
                                mime="application/pdf",
                                key=f"smart_recap_download_pdf_{current_session_id}_{key}",
                            )
                        _render_readonly_text_block("", re.sub(r"^\s*Description\s*:?\s*", "", plain_body, flags=re.IGNORECASE))
                except Exception:
                    st.error(f"{label} recap could not be displayed.")

        return requested_tone
