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
    "deep_analysis_md": "",
    "deep_analysis_ran": False,
    "content_repurpose_md": "",
    "content_repurpose_bundle": {},
    "content_repurpose_ran": False,
    "content_repurpose_history": [],
    "smart_recap_bundle": {},
    "smart_recap_ran": False,
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
    "chat_fetch_job_id": "",
    "fetch_data_in_progress": False,
    "analysis_include_chat": False,
    "analysis_include_questions": False,
    "analysis_include_chat_questions": False,
    "analysis_include_transcript": False,
    "analysis_include_transcript_pending": False,
    "transcript_job_id": "",
    "transcript_job_status": "",
    "transcript_job_started_at": 0.0,
    "background_job_notice": "",
    "analysis_language": "English",
    "deep_analysis_in_progress": False,
    "content_repurpose_in_progress": False,
    "content_repurpose_language": "English",
    "smart_recap_in_progress": False,
    "smart_recap_in_progress_tone": "",
    "transcript_speaker_names": {},
    "load_event_sessions_in_progress": False,
    "last_fetched_chat_session_id": "",
    "last_fetched_transcript_signature": "",
    "last_api_error_details": None,
    "last_api_error_message": "",
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
    st.session_state["analysis_in_progress"] = False
    st.session_state["deep_analysis_md"] = ""
    st.session_state["deep_analysis_ran"] = False
    st.session_state["deep_analysis_in_progress"] = False
    st.session_state["content_repurpose_md"] = ""
    st.session_state["content_repurpose_bundle"] = {}
    st.session_state["content_repurpose_ran"] = False
    st.session_state["content_repurpose_in_progress"] = False
    st.session_state["content_repurpose_history"] = []
    st.session_state["smart_recap_bundle"] = {}
    st.session_state["smart_recap_ran"] = False
    st.session_state["smart_recap_in_progress"] = False
    st.session_state["smart_recap_in_progress_tone"] = ""


def reset_chat_question_state() -> None:
    st.session_state["chat_payload"] = None
    st.session_state["chat_df"] = None
    st.session_state["questions_payload"] = None
    st.session_state["questions_df"] = None
    st.session_state["analysis_include_chat"] = False
    st.session_state["analysis_include_questions"] = False
    st.session_state["analysis_include_chat_questions"] = False
    st.session_state["last_fetched_chat_session_id"] = ""
    st.session_state["chat_fetch_job_id"] = ""


def reset_transcript_state() -> None:
    st.session_state["transcript_payload"] = None
    st.session_state["transcript_text"] = ""
    st.session_state["analysis_include_transcript"] = False
    st.session_state["analysis_include_transcript_pending"] = False
    st.session_state["last_fetched_transcript_signature"] = ""
    st.session_state["transcript_job_id"] = ""
    st.session_state["transcript_job_status"] = ""
    st.session_state["transcript_job_started_at"] = 0.0
