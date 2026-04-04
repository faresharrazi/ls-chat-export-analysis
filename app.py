import logging
import os
from typing import List

import pandas as pd
import requests
import streamlit as st

from livestorm_app.config import (
    DEFAULT_OPENAI_MODEL,
    INPUT_MODE_OPTIONS,
    OUTPUT_LANGUAGE_MAP,
    apply_brand_styles,
    configure_page,
    get_runtime_secret,
    render_header,
)
from livestorm_app.renderers import (
    render_analysis_block,
    render_chat_questions_block,
    render_transcript_block,
)
from livestorm_app.services import (
    analyze_with_openai,
    build_analysis_prompt,
    build_derived_stats,
    build_event_session_options,
    build_http_error_debug_details,
    build_request_exception_debug_details,
    clean_questions_table,
    clean_table_headers,
    drop_unwanted_columns,
    extract_included_people,
    extract_messages,
    extract_questions,
    fetch_chat_messages,
    fetch_event_past_sessions,
    fetch_session_questions,
    fetch_session_transcript,
    flatten_message,
    flatten_question,
    format_generic_http_error,
    format_livestorm_http_error,
    format_unix_datetime_columns,
    mark_analysis_source_defaults,
    build_transcript_display_text,
)
from livestorm_app.state import (
    EVENT_ID_PATTERN,
    SESSION_ID_PATTERN,
    clear_analysis_output,
    get_active_session_id,
    init_session_state,
    reset_chat_question_state,
    reset_transcript_state,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_transcript_request_signature(session_id: str, verbose: bool) -> str:
    return f"{str(session_id).strip()}::verbose={str(bool(verbose)).lower()}"


def set_api_error_details(resource_label: str, details: dict | None) -> None:
    st.session_state["last_api_error_details"] = {
        "resource": resource_label,
        **(details or {}),
    } if details is not None else {"resource": resource_label}


def set_api_error_message(message: str) -> None:
    st.session_state["last_api_error_message"] = message


def clear_api_error_details() -> None:
    st.session_state["last_api_error_details"] = None
    st.session_state["last_api_error_message"] = ""


def render_api_error_details() -> None:
    error_message = st.session_state.get("last_api_error_message", "")
    if error_message:
        st.error(error_message)
    details = st.session_state.get("last_api_error_details")
    if isinstance(details, dict) and details:
        with st.expander("Error details"):
            st.json(details)


configure_page()
apply_brand_styles()
init_session_state()
render_header()

has_chat_content = st.session_state.get("chat_df") is not None
has_questions_content = st.session_state.get("questions_df") is not None
has_transcript_content = st.session_state.get("transcript_payload") is not None
has_fetched_content = has_chat_content or has_questions_content or has_transcript_content

controls_col, main_col = st.columns([0.95, 3.05], gap="large")

fetch_button = False
fetch_transcript_button = False
load_event_sessions_button = False
selected_session_from_event = st.session_state.get("selected_event_session_id")
output_language_label = st.session_state.get("analysis_language", "English")

api_key = st.session_state.get("api_key_input", os.getenv("LS_API_KEY", ""))
has_api_key = bool(str(api_key).strip())
transcript_api_key = get_runtime_secret("API_AUTH_KEY", "")
has_transcript_api_key = bool(str(transcript_api_key).strip())
api_analysis_key = get_runtime_secret("OPENAI_API_KEY", "")
input_mode = st.session_state.get("input_mode", INPUT_MODE_OPTIONS[0])
session_id = st.session_state.get("session_id_input", "")
event_id = st.session_state.get("event_id_input", "")
session_id_valid = bool(SESSION_ID_PATTERN.match(str(session_id).strip()))
event_id_valid = bool(EVENT_ID_PATTERN.match(str(event_id).strip()))
active_session_id = get_active_session_id(input_mode, session_id, selected_session_from_event)
current_transcript_signature = build_transcript_request_signature(
    active_session_id,
    bool(st.session_state.get("transcript_verbose", False)),
)

if controls_col is not None:
    with controls_col:
        render_api_error_details()
        st.subheader("Connection")
        api_key = st.text_input(
            "Livestorm API key",
            value=st.session_state.get("api_key_input", os.getenv("LS_API_KEY", "")),
            type="password",
            help="Your Livestorm API key",
            key="api_key_input",
        )
        has_api_key = bool(api_key.strip())
        transcript_api_key = get_runtime_secret("API_AUTH_KEY", "")
        has_transcript_api_key = bool(str(transcript_api_key).strip())
        has_any_connection_key = has_api_key or has_transcript_api_key

        input_mode = st.radio(
            "Input type",
            options=INPUT_MODE_OPTIONS,
            index=0 if st.session_state.get("input_mode", INPUT_MODE_OPTIONS[0]) == INPUT_MODE_OPTIONS[0] else 1,
            horizontal=True,
            disabled=not has_any_connection_key,
            key="input_mode",
        )

        session_id = ""
        event_id = ""
        session_id_valid = False
        event_id_valid = False
        selected_session_from_event = None

        if input_mode == "Session ID":
            session_id = st.text_input(
                "Session ID",
                help="Livestorm session ID",
                disabled=not has_any_connection_key,
                key="session_id_input",
            )
            session_id_valid = bool(SESSION_ID_PATTERN.match(session_id.strip()))
        else:
            event_id = st.text_input(
                "Event ID",
                help="Livestorm event ID",
                disabled=not has_api_key,
                key="event_id_input",
            )
            event_id_valid = bool(EVENT_ID_PATTERN.match(event_id.strip()))
            if st.session_state.get("load_event_sessions_in_progress", False):
                st.button(
                    "Loading Past Sessions...",
                    key="load_sessions_running_btn",
                    type="primary",
                    disabled=True,
                )
            else:
                load_event_sessions_button = st.button(
                    "Load Past Sessions",
                    key="load_sessions_btn",
                    type="primary",
                    disabled=not has_api_key,
                )

            event_sessions = st.session_state.get("event_sessions", [])
            event_sessions_for = st.session_state.get("event_sessions_for", "")
            if event_sessions_for == event_id.strip() and event_sessions:
                options = [item["id"] for item in event_sessions if isinstance(item, dict) and "id" in item]
                session_labels = {
                    item["id"]: item.get("label", item["id"])
                    for item in event_sessions
                    if isinstance(item, dict) and "id" in item
                }
                selected_session_from_event = st.selectbox(
                    "Select a past session",
                    options=options,
                    format_func=lambda sid: session_labels.get(sid, sid),
                    disabled=not bool(options),
                    key="selected_event_session_id",
                )
                if selected_session_from_event:
                    st.caption(f"Selected session: `{selected_session_from_event}`")

        active_session_id = get_active_session_id(input_mode, session_id, selected_session_from_event)
        current_transcript_signature = build_transcript_request_signature(
            active_session_id,
            bool(st.session_state.get("transcript_verbose", False)),
        )

        chat_request_already_fetched = (
            bool(active_session_id)
            and st.session_state.get("last_fetched_chat_session_id", "") == active_session_id
        )
        transcript_request_already_fetched = (
            bool(active_session_id)
            and st.session_state.get("last_fetched_transcript_signature", "") == current_transcript_signature
        )

        fetch_disabled = (not has_api_key) or chat_request_already_fetched
        transcript_fetch_disabled = (not has_transcript_api_key) or (not bool(active_session_id)) or transcript_request_already_fetched
        can_show_fetch_button = input_mode == "Session ID" or bool(active_session_id)

        if can_show_fetch_button:
            fetch_btn_placeholder = st.empty()
            if st.session_state.get("fetch_in_progress", False):
                fetch_btn_placeholder.button(
                    "Fetching Chat & Questions...",
                    type="primary",
                    disabled=True,
                    key="fetch_running_btn",
                )
            else:
                fetch_button = fetch_btn_placeholder.button(
                    "Fetch Chat & Questions",
                    type="primary",
                    disabled=fetch_disabled,
                    key="fetch_run_btn",
                )
                if chat_request_already_fetched:
                    st.caption("Chat & questions already fetched for this session. Change the session to fetch again.")

            transcript_btn_placeholder = st.empty()
            if st.session_state.get("transcript_fetch_in_progress", False):
                transcript_btn_placeholder.button(
                    "Fetching Transcript...",
                    type="primary",
                    disabled=True,
                    key="transcript_running_btn",
                )
            else:
                st.checkbox(
                    "Verbose?",
                    key="transcript_verbose",
                    disabled=transcript_fetch_disabled,
                    help="When checked the transcript will be generated timestamped.",
                )
                fetch_transcript_button = transcript_btn_placeholder.button(
                    "Fetch Transcript",
                    type="primary",
                    disabled=transcript_fetch_disabled,
                    key="transcript_fetch_btn",
                )
                if transcript_request_already_fetched:
                    st.caption("Transcript already fetched for this session and verbose setting. Change one of them to fetch again.")

        if not has_api_key and not has_transcript_api_key:
            st.caption("Add a Livestorm API key or set `API_AUTH_KEY` to enable transcript fetches.")
        elif has_transcript_api_key and not has_api_key:
            st.caption("Transcript fetch is available by Session ID. Add a Livestorm API key to load past sessions or fetch chat/questions.")
        elif not has_transcript_api_key:
            st.caption("Set `API_AUTH_KEY` in `.env` or Streamlit secrets to enable transcript fetches.")
        elif input_mode == "Session ID" and session_id and not session_id_valid:
            st.caption("Session ID must be a valid UUID format.")
        elif input_mode == "Event ID" and event_id and not event_id_valid:
            st.caption("Event ID must be a valid UUID format.")
        elif input_mode == "Event ID" and event_id_valid and not active_session_id:
            st.caption("Load past sessions, then select one session before fetching.")

if load_event_sessions_button:
    st.session_state["load_event_sessions_in_progress"] = True
    st.rerun()

if st.session_state.get("load_event_sessions_in_progress", False):
    st.session_state["event_sessions"] = []
    st.session_state["event_sessions_for"] = ""
    if not api_key:
        st.error("Please provide your Livestorm API key.")
        st.session_state["load_event_sessions_in_progress"] = False
    elif not event_id:
        st.error("Please provide an event ID.")
        st.session_state["load_event_sessions_in_progress"] = False
    elif not EVENT_ID_PATTERN.match(event_id.strip()):
        st.error("Event ID must be a valid UUID format.")
        st.session_state["load_event_sessions_in_progress"] = False
    else:
        try:
            event_sessions_payload = fetch_event_past_sessions(api_key, event_id.strip())
        except requests.HTTPError as exc:
            logger.exception("Event sessions request failed", extra={"event_id": event_id.strip()})
            set_api_error_details("Event sessions", build_http_error_debug_details(exc, "Event sessions"))
            set_api_error_message(format_livestorm_http_error(exc, "Event sessions"))
            event_sessions_payload = None
        except requests.RequestException as exc:
            logger.exception("Event sessions network error", extra={"event_id": event_id.strip()})
            set_api_error_details("Event sessions", build_request_exception_debug_details(exc, "Event sessions"))
            set_api_error_message(f"Event sessions network error: {exc}")
            event_sessions_payload = None

        if isinstance(event_sessions_payload, dict):
            clear_api_error_details()
            options = build_event_session_options(event_sessions_payload)
            st.session_state["event_sessions"] = options
            st.session_state["event_sessions_for"] = event_id.strip()
            if options:
                st.success(
                    f"Loaded {len(options)} past sessions across "
                    f"{event_sessions_payload.get('pages_fetched', 1)} page(s)."
                )
            else:
                st.info("No past sessions were found for this event.")
            st.session_state["load_event_sessions_in_progress"] = False
            st.rerun()
    st.session_state["load_event_sessions_in_progress"] = False

if fetch_button:
    st.session_state["fetch_in_progress"] = True
    st.rerun()

if fetch_transcript_button:
    st.session_state["transcript_fetch_in_progress"] = True
    st.rerun()

if st.session_state.get("fetch_in_progress", False):
    previous_session_id = st.session_state.get("current_session_id", "")
    clear_analysis_output()
    if previous_session_id and previous_session_id != active_session_id:
        st.session_state["questions_payload"] = None
        st.session_state["questions_df"] = None
        reset_transcript_state()

    if not api_key or not active_session_id:
        st.error("Please provide API key and a valid session selection.")
        st.session_state["fetch_in_progress"] = False
        st.rerun()

    try:
        with st.spinner("Fetching chat messages..."):
            payload = fetch_chat_messages(api_key, active_session_id)
    except requests.HTTPError as exc:
        logger.exception("Chat fetch failed", extra={"session_id": active_session_id})
        set_api_error_details("Chat", build_http_error_debug_details(exc, "Chat"))
        set_api_error_message(format_livestorm_http_error(exc, "Chat"))
        st.session_state["fetch_in_progress"] = False
        st.rerun()
    except requests.RequestException as exc:
        logger.exception("Chat network error", extra={"session_id": active_session_id})
        set_api_error_details("Chat", build_request_exception_debug_details(exc, "Chat"))
        set_api_error_message(f"Chat network error: {exc}")
        st.session_state["fetch_in_progress"] = False
        st.rerun()

    messages = extract_messages(payload)
    fetched_successfully = False
    if not messages:
        st.warning("No messages found or unexpected response format.")
        st.json(payload)
    else:
        rows = [flatten_message(message) for message in messages]
        df = clean_table_headers(pd.DataFrame(rows))
        df = format_unix_datetime_columns(df)
        df = drop_unwanted_columns(df)
        st.session_state["chat_payload"] = payload
        st.session_state["chat_df"] = df
        st.session_state["current_session_id"] = active_session_id
        mark_analysis_source_defaults(st.session_state, include_chat=True)
        fetched_successfully = True
        clear_api_error_details()

    try:
        with st.spinner("Fetching session questions..."):
            raw_questions_payload = fetch_session_questions(api_key, active_session_id)
    except requests.HTTPError as exc:
        logger.exception("Questions fetch failed", extra={"session_id": active_session_id})
        set_api_error_details("Questions", build_http_error_debug_details(exc, "Questions"))
        set_api_error_message(format_livestorm_http_error(exc, "Questions"))
        raw_questions_payload = None
    except requests.RequestException as exc:
        logger.exception("Questions network error", extra={"session_id": active_session_id})
        set_api_error_details("Questions", build_request_exception_debug_details(exc, "Questions"))
        set_api_error_message(f"Questions network error: {exc}")
        raw_questions_payload = None

    if isinstance(raw_questions_payload, dict):
        raw_questions = extract_questions(raw_questions_payload)
        if not raw_questions:
            st.session_state["questions_payload"] = raw_questions_payload
            st.session_state["questions_df"] = pd.DataFrame()
        else:
            people_lookup = extract_included_people(raw_questions_payload)
            question_rows = [flatten_question(question, people_lookup) for question in raw_questions]
            qdf = clean_table_headers(pd.DataFrame(question_rows))
            qdf = format_unix_datetime_columns(qdf)
            qdf = clean_questions_table(qdf)
            st.session_state["questions_payload"] = raw_questions_payload
            st.session_state["questions_df"] = qdf
        if isinstance(st.session_state.get("questions_df"), pd.DataFrame):
            mark_analysis_source_defaults(st.session_state, include_questions=True)
        if fetched_successfully:
            st.session_state["last_fetched_chat_session_id"] = active_session_id

    st.session_state["fetch_in_progress"] = False
    if fetched_successfully:
        st.rerun()

if st.session_state.get("transcript_fetch_in_progress", False):
    previous_session_id = st.session_state.get("current_session_id", "")
    clear_analysis_output()
    if previous_session_id and previous_session_id != active_session_id:
        reset_chat_question_state()

    transcript_api_key = get_runtime_secret("API_AUTH_KEY", "")
    if not transcript_api_key:
        st.error("Transcript fetch skipped: missing `API_AUTH_KEY` in environment.")
        st.session_state["transcript_fetch_in_progress"] = False
        st.rerun()
    if not active_session_id:
        st.error("Please select a valid session before fetching the transcript.")
        st.session_state["transcript_fetch_in_progress"] = False
        st.rerun()

    try:
        transcript_payload = fetch_session_transcript(
            transcript_api_key,
            active_session_id,
            verbose=bool(st.session_state.get("transcript_verbose", False)),
        )
    except requests.HTTPError as exc:
        logger.exception(
            "Transcript fetch failed",
            extra={"session_id": active_session_id, "verbose": bool(st.session_state.get("transcript_verbose", False))},
        )
        set_api_error_details("Transcript", build_http_error_debug_details(exc, "Transcript"))
        set_api_error_message(format_generic_http_error(exc, "Transcript"))
        st.session_state["transcript_fetch_in_progress"] = False
        st.rerun()
    except requests.RequestException as exc:
        logger.exception(
            "Transcript network error",
            extra={"session_id": active_session_id, "verbose": bool(st.session_state.get("transcript_verbose", False))},
        )
        set_api_error_details("Transcript", build_request_exception_debug_details(exc, "Transcript"))
        set_api_error_message(f"Transcript network error: {exc}")
        st.session_state["transcript_fetch_in_progress"] = False
        st.rerun()

    transcript_text = build_transcript_display_text(transcript_payload)
    if not transcript_text:
        st.warning("Transcript response was received, but no transcript text was found.")

    st.session_state["transcript_payload"] = transcript_payload
    st.session_state["transcript_text"] = transcript_text
    st.session_state["last_fetched_transcript_signature"] = build_transcript_request_signature(
        active_session_id,
        bool(st.session_state.get("transcript_verbose", False)),
    )
    st.session_state["current_session_id"] = active_session_id
    mark_analysis_source_defaults(st.session_state, include_transcript=True)
    clear_api_error_details()
    st.session_state["transcript_fetch_in_progress"] = False
    st.rerun()

payload = st.session_state.get("chat_payload")
df = st.session_state.get("chat_df")
questions_payload = st.session_state.get("questions_payload")
questions_df = st.session_state.get("questions_df")
transcript_payload = st.session_state.get("transcript_payload")
transcript_text = st.session_state.get("transcript_text", "")
analysis_md = st.session_state.get("analysis_md", "")
analysis_ran = st.session_state.get("analysis_ran", False)
current_session_id = st.session_state.get("current_session_id") or active_session_id

with main_col:
    transcript_available = isinstance(transcript_payload, dict)
    chat_available = isinstance(df, pd.DataFrame)
    questions_available = isinstance(questions_df, pd.DataFrame)

    render_transcript_block(transcript_payload, transcript_text, current_session_id)
    render_chat_questions_block(df, questions_df, current_session_id)
    analyze_button = render_analysis_block(
        current_session_id=current_session_id,
        analysis_ran=analysis_ran,
        analysis_md=analysis_md,
        transcript_available=transcript_available,
        chat_available=chat_available,
        questions_available=questions_available,
        transcript_payload=transcript_payload,
        chat_df=df,
        questions_df=questions_df,
    )

if analyze_button:
    st.session_state["analysis_in_progress"] = True
    st.rerun()

if st.session_state.get("analysis_in_progress", False):
    payload = st.session_state.get("chat_payload")
    df = st.session_state.get("chat_df")
    questions_payload = st.session_state.get("questions_payload")
    questions_df = st.session_state.get("questions_df")
    transcript_payload = st.session_state.get("transcript_payload")
    selected_output_language = st.session_state.get("analysis_language", output_language_label)

    selected_sources: List[str] = []
    if st.session_state.get("analysis_include_transcript") and transcript_payload is not None:
        selected_sources.append("transcript")
    if st.session_state.get("analysis_include_chat_questions") and payload is not None and df is not None:
        selected_sources.append("chat")
        selected_sources.append("questions")

    if not selected_sources:
        st.warning("Select at least one available source before running analysis.")
        st.session_state["analysis_in_progress"] = False
        st.rerun()
    if not api_analysis_key:
        st.warning("Analysis skipped: missing `OPENAI_API_KEY` in environment.")
        st.session_state["analysis_in_progress"] = False
        st.rerun()

    prompt_text = build_analysis_prompt(selected_sources)
    derived_stats = build_derived_stats(
        chat_df=df if "chat" in selected_sources else None,
        questions_df=questions_df if "questions" in selected_sources else None,
        transcript_payload=transcript_payload if "transcript" in selected_sources else None,
    )

    try:
        analysis_md = analyze_with_openai(
            api_key=api_analysis_key,
            model=DEFAULT_OPENAI_MODEL,
            system_prompt=prompt_text,
            output_language=OUTPUT_LANGUAGE_MAP[selected_output_language],
            selected_sources=selected_sources,
            derived_stats=derived_stats,
            raw_payload=payload if "chat" in selected_sources else None,
            questions_payload=questions_payload if "questions" in selected_sources else None,
            transcript_payload=transcript_payload if "transcript" in selected_sources else None,
        )
    except requests.HTTPError as exc:
        st.error(f"Analysis API error: {exc}")
        analysis_md = ""
    except requests.RequestException as exc:
        st.error(f"Analysis network error: {exc}")
        analysis_md = ""

    st.session_state["analysis_md"] = analysis_md
    st.session_state["analysis_ran"] = True
    st.session_state["analysis_in_progress"] = False
    st.rerun()
