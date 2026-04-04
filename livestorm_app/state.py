import re

import streamlit as st

SESSION_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
EVENT_ID_PATTERN = SESSION_ID_PATTERN

SESSION_DEFAULTS = {
    "analysis_in_progress": False,
    "fetch_in_progress": False,
    "chat_payload": None,
    "chat_df": None,
    "analysis_md": "",
    "analysis_ran": False,
    "questions_payload": None,
    "questions_df": None,
    "event_sessions": [],
    "event_sessions_for": "",
    "current_session_id": "",
    "session_id_input": "",
    "event_id_input": "",
    "selected_event_session_id": None,
    "transcript_payload": None,
    "transcript_text": "",
    "transcript_fetch_in_progress": False,
    "analysis_include_chat": False,
    "analysis_include_questions": False,
    "analysis_include_chat_questions": False,
    "analysis_include_transcript": False,
    "transcript_verbose": False,
    "analysis_language": "English",
    "load_event_sessions_in_progress": False,
}


def init_session_state() -> None:
    for key, value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_active_session_id(input_mode: str, session_id: str, selected_session_from_event: str | None) -> str:
    if input_mode == "Session ID":
        return str(session_id).strip()
    return selected_session_from_event or ""


def clear_analysis_output() -> None:
    st.session_state["analysis_md"] = ""
    st.session_state["analysis_ran"] = False


def reset_chat_question_state() -> None:
    st.session_state["chat_payload"] = None
    st.session_state["chat_df"] = None
    st.session_state["questions_payload"] = None
    st.session_state["questions_df"] = None
    st.session_state["analysis_include_chat"] = False
    st.session_state["analysis_include_questions"] = False
    st.session_state["analysis_include_chat_questions"] = False


def reset_transcript_state() -> None:
    st.session_state["transcript_payload"] = None
    st.session_state["transcript_text"] = ""
    st.session_state["analysis_include_transcript"] = False
