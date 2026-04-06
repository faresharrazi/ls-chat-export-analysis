import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import requests
import streamlit as st

from livestorm_app.background_jobs import get_background_job_manager
from livestorm_app.config import (
    DEFAULT_OPENAI_MODEL,
    INPUT_MODE_OPTIONS,
    OUTPUT_LANGUAGE_MAP,
    apply_brand_styles,
    configure_page,
    get_runtime_secret,
    render_header,
)
from livestorm_app.db import (
    database_enabled,
    ensure_database_schema,
    fetch_cached_session,
    upsert_cached_session,
)
from livestorm_app.renderers import (
    render_analysis_block,
    render_chat_questions_block,
    render_content_repurpose_block,
    render_smart_recap_block,
    render_transcript_block,
)
from livestorm_app.services import (
    analyze_with_openai,
    build_analysis_prompt,
    build_chat_df_from_payload,
    build_smart_recap_prompt,
    build_compact_chat_payload_for_llm,
    build_compact_questions_payload_for_llm,
    build_compact_transcript_payload_for_llm,
    build_deep_analysis_prompt,
    build_derived_stats,
    build_questions_df_from_payload,
    build_transcript_plain_text,
    build_transcript_job_debug_details,
    build_event_session_options,
    build_http_error_debug_details,
    build_request_exception_debug_details,
    create_transcript_job,
    fetch_chat_and_questions_bundle,
    fetch_event_past_sessions,
    get_transcript_job,
    generate_content_repurpose_bundle_with_openai,
    format_generic_http_error,
    format_livestorm_http_error,
    mark_analysis_source_defaults,
    build_transcript_display_text,
    translate_content_repurpose_bundle_with_openai,
    translate_markdown_with_openai,
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
job_manager = get_background_job_manager()

TRANSCRIPT_POLL_INTERVAL_SECONDS = 1
SMART_RECAP_MAX_TRANSCRIPT_CHARS = 14000


def build_transcript_request_signature(session_id: str) -> str:
    return str(session_id).strip()


def build_smart_recap_source_text(transcript_payload: Dict[str, Any], max_chars: int = SMART_RECAP_MAX_TRANSCRIPT_CHARS) -> str:
    transcript_text = build_transcript_plain_text(transcript_payload)
    if len(transcript_text) <= max_chars:
        return transcript_text

    head_chars = int(max_chars * 0.7)
    tail_chars = max_chars - head_chars
    head_text = transcript_text[:head_chars].strip()
    tail_text = transcript_text[-tail_chars:].strip()
    if not head_text:
        return tail_text
    if not tail_text:
        return head_text
    return f"{head_text}\n\n{tail_text}"


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


def clear_background_notice() -> None:
    st.session_state["background_job_notice"] = ""


def set_background_notice(message: str) -> None:
    st.session_state["background_job_notice"] = message


def build_failed_job_result(message: str, *, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {"ok": False, "message": message, "details": details or {}}


def build_content_repurpose_md(bundle_by_language: Dict[str, Dict[str, str]]) -> str:
    if not isinstance(bundle_by_language, dict):
        return ""
    return "\n\n---\n\n".join(
        markdown.strip()
        for bundle in bundle_by_language.values()
        if isinstance(bundle, dict)
        for markdown in bundle.values()
        if isinstance(markdown, str) and markdown.strip()
    )


def _normalize_text_bundle(raw_bundle: Any, fallback_text: str = "", fallback_language: str = "English") -> Dict[str, str]:
    bundle = raw_bundle if isinstance(raw_bundle, dict) else {}
    normalized = {
        str(language): str(value).strip()
        for language, value in bundle.items()
        if isinstance(language, str) and isinstance(value, str) and str(value).strip()
    }
    fallback_text = str(fallback_text or "").strip()
    if fallback_text and fallback_language not in normalized:
        normalized[fallback_language] = fallback_text
    return normalized


def _get_alternate_language_text(bundle: Any, target_language: str) -> tuple[str, str]:
    if not isinstance(bundle, dict):
        return "", ""
    for language, value in bundle.items():
        if str(language) == str(target_language):
            continue
        text = str(value or "").strip()
        if text:
            return str(language), text
    return "", ""


def _get_alternate_language_bundle(bundle_by_language: Any, target_language: str) -> tuple[str, Dict[str, str]]:
    if not isinstance(bundle_by_language, dict):
        return "", {}
    for language, bundle in bundle_by_language.items():
        if str(language) == str(target_language) or not isinstance(bundle, dict):
            continue
        normalized_bundle = {
            key: str(value or "").strip()
            for key, value in bundle.items()
            if key in {"summary", "blog", "email", "social_media"}
        }
        if any(normalized_bundle.values()):
            return str(language), normalized_bundle
    return "", {}


def _normalize_smart_recap_bundle(raw_bundle: Any) -> Dict[str, str]:
    if not isinstance(raw_bundle, dict):
        return {}
    allowed_tones = {"professional", "hype", "surprise"}
    return {
        str(tone): str(markdown).strip()
        for tone, markdown in raw_bundle.items()
        if str(tone) in allowed_tones and isinstance(markdown, str) and str(markdown).strip()
    }


def load_cached_session_into_state(api_key: str, session_id: str, cached_session: Dict[str, Any]) -> None:
    if not isinstance(cached_session, dict):
        return

    clear_api_error_details()
    clear_background_notice()
    st.session_state["current_session_id"] = str(session_id or "")

    chat_payload = cached_session.get("chat_payload")
    questions_payload = cached_session.get("questions_payload")
    transcript_payload = cached_session.get("transcript_payload")
    analysis_bundle = _normalize_text_bundle(cached_session.get("analysis_bundle"), str(cached_session.get("analysis_md") or ""))
    deep_analysis_bundle = _normalize_text_bundle(cached_session.get("deep_analysis_bundle"), str(cached_session.get("deep_analysis_md") or ""))
    content_repurpose_bundle = cached_session.get("content_repurpose_bundle")
    smart_recap_bundle = _normalize_smart_recap_bundle(cached_session.get("smart_recap_bundle"))
    selected_analysis_language = str(st.session_state.get("analysis_language", "English"))

    if isinstance(chat_payload, dict):
        st.session_state["chat_payload"] = chat_payload
        st.session_state["chat_df"] = build_chat_df_from_payload(chat_payload)
        st.session_state["last_fetched_chat_session_id"] = str(session_id or "")
        mark_analysis_source_defaults(st.session_state, include_chat=True)
    if isinstance(questions_payload, dict):
        st.session_state["questions_payload"] = questions_payload
        st.session_state["questions_df"] = build_questions_df_from_payload(questions_payload)
        if isinstance(st.session_state.get("questions_df"), pd.DataFrame):
            mark_analysis_source_defaults(st.session_state, include_questions=True)

    if isinstance(transcript_payload, dict):
        transcript_text = build_transcript_display_text(transcript_payload)
        st.session_state["transcript_payload"] = transcript_payload
        st.session_state["transcript_text"] = transcript_text
        st.session_state["last_fetched_transcript_signature"] = build_transcript_request_signature(str(session_id or ""))
        mark_analysis_source_defaults(st.session_state, include_transcript=True)
        st.session_state["analysis_include_transcript_pending"] = True

    st.session_state["analysis_bundle"] = analysis_bundle
    st.session_state["analysis_md"] = str(analysis_bundle.get(selected_analysis_language) or "")
    st.session_state["analysis_ran"] = bool(st.session_state["analysis_md"].strip())
    st.session_state["deep_analysis_bundle"] = deep_analysis_bundle
    st.session_state["deep_analysis_md"] = str(deep_analysis_bundle.get(selected_analysis_language) or "")
    st.session_state["deep_analysis_ran"] = bool(st.session_state["deep_analysis_md"].strip())

    if isinstance(content_repurpose_bundle, dict):
        st.session_state["content_repurpose_bundle"] = content_repurpose_bundle
        st.session_state["content_repurpose_md"] = build_content_repurpose_md(content_repurpose_bundle)
        st.session_state["content_repurpose_ran"] = bool(st.session_state["content_repurpose_md"].strip())

    if smart_recap_bundle:
        st.session_state["smart_recap_bundle"] = smart_recap_bundle
        st.session_state["smart_recap_ran"] = bool(
            any(isinstance(value, str) and value.strip() for value in smart_recap_bundle.values())
        )


def persist_cached_session_safely(api_key: str, session_id: str, **fields: Any) -> None:
    try:
        upsert_cached_session(api_key, session_id, **fields)
    except Exception:
        logger.exception("Failed to persist cached session data", extra={"session_id": session_id, "field_names": list(fields.keys())})


def run_chat_questions_job(api_key: str, session_id: str) -> Dict[str, Any]:
    try:
        bundle = fetch_chat_and_questions_bundle(api_key, session_id)
        return {"ok": True, "session_id": session_id, **bundle}
    except requests.HTTPError as exc:
        logger.exception("Chat/questions background fetch failed", extra={"session_id": session_id})
        return build_failed_job_result(
            format_livestorm_http_error(exc, "Chat & Questions"),
            details=build_http_error_debug_details(exc, "Chat & Questions"),
        )
    except requests.RequestException as exc:
        logger.exception("Chat/questions background network error", extra={"session_id": session_id})
        return build_failed_job_result(
            f"Chat & Questions network error: {exc}",
            details=build_request_exception_debug_details(exc, "Chat & Questions"),
        )


def run_smart_recap_job(api_key: str, tone: str, transcript_text: str) -> Dict[str, Any]:
    started_at = time.perf_counter()
    try:
        prompt_text = build_smart_recap_prompt(tone)
        markdown = analyze_with_openai(
            api_key=api_key,
            model=DEFAULT_OPENAI_MODEL,
            system_prompt=prompt_text,
            output_language="English",
            selected_sources=[],
            derived_stats={},
            transcript_text=transcript_text,
            max_tokens=900,
        )
        return {
            "ok": True,
            "tone": tone,
            "markdown": markdown,
            "elapsed_seconds": round(time.perf_counter() - started_at, 2),
            "transcript_chars": len(transcript_text),
        }
    except requests.HTTPError as exc:
        logger.exception("Smart recap background request failed", extra={"tone": tone})
        return build_failed_job_result(
            format_generic_http_error(exc, "Smart Recap"),
            details=build_http_error_debug_details(exc, "Smart Recap"),
        )
    except requests.RequestException as exc:
        logger.exception("Smart recap background network error", extra={"tone": tone})
        return build_failed_job_result(
            f"Smart Recap network error: {exc}",
            details=build_request_exception_debug_details(exc, "Smart Recap"),
        )


def apply_smart_recap_job_result(job_result: Dict[str, Any]) -> None:
    if not job_result.get("ok"):
        set_api_error_details("Smart Recap", job_result.get("details"))
        set_api_error_message(str(job_result.get("message") or "Smart Recap request failed."))
        st.session_state["smart_recap_in_progress"] = False
        st.session_state["smart_recap_in_progress_tone"] = ""
        st.session_state["smart_recap_job_id"] = ""
        clear_background_notice()
        return

    smart_recap_bundle = _normalize_smart_recap_bundle(st.session_state.get("smart_recap_bundle", {}))

    tone = str(job_result.get("tone") or "").strip().lower()
    markdown = str(job_result.get("markdown") or "").strip()
    if tone in {"professional", "hype", "surprise"} and markdown:
        smart_recap_bundle[tone] = markdown

    st.session_state["smart_recap_bundle"] = smart_recap_bundle
    st.session_state["smart_recap_ran"] = bool(
        any(isinstance(value, str) and value.strip() for value in smart_recap_bundle.values())
    )
    st.session_state["smart_recap_in_progress"] = False
    st.session_state["smart_recap_in_progress_tone"] = ""
    st.session_state["smart_recap_job_id"] = ""

    current_session_id = str(st.session_state.get("current_session_id") or "").strip()
    api_key = st.session_state.get("api_key_input", os.getenv("LS_API_KEY", ""))
    if current_session_id and api_key and isinstance(smart_recap_bundle, dict) and smart_recap_bundle:
        persist_cached_session_safely(api_key, current_session_id, smart_recap_bundle=smart_recap_bundle)

    elapsed_seconds = job_result.get("elapsed_seconds")
    transcript_chars = job_result.get("transcript_chars")
    if isinstance(elapsed_seconds, (int, float)) and isinstance(transcript_chars, int):
        set_background_notice(
            f"Smart Recap ready in {elapsed_seconds:.2f}s using {transcript_chars:,} transcript characters."
        )
    else:
        clear_background_notice()


def apply_chat_questions_job_result(job_result: Dict[str, Any]) -> None:
    if not job_result.get("ok"):
        set_api_error_details("Chat & Questions", job_result.get("details"))
        set_api_error_message(str(job_result.get("message") or "Chat & Questions request failed."))
        st.session_state["fetch_in_progress"] = False
        st.session_state["fetch_data_in_progress"] = False
        st.session_state["chat_fetch_job_id"] = ""
        clear_background_notice()
        return

    clear_analysis_output()
    clear_api_error_details()
    clear_background_notice()
    st.session_state["chat_payload"] = job_result.get("chat_payload")
    st.session_state["chat_df"] = job_result.get("chat_df")
    st.session_state["questions_payload"] = job_result.get("questions_payload")
    st.session_state["questions_df"] = job_result.get("questions_df")
    st.session_state["current_session_id"] = job_result.get("session_id", "")
    st.session_state["last_fetched_chat_session_id"] = job_result.get("session_id", "")
    mark_analysis_source_defaults(st.session_state, include_chat=True)
    if isinstance(st.session_state.get("questions_df"), pd.DataFrame):
        mark_analysis_source_defaults(st.session_state, include_questions=True)
    st.session_state["fetch_in_progress"] = False
    st.session_state["chat_fetch_job_id"] = ""
    session_id = job_result.get("session_id", "")
    api_key = st.session_state.get("api_key_input", os.getenv("LS_API_KEY", ""))
    if session_id and api_key:
        persist_cached_session_safely(
            str(api_key),
            str(session_id),
            chat_payload=job_result.get("chat_payload"),
            questions_payload=job_result.get("questions_payload"),
        )
    if st.session_state.get("fetch_data_in_progress", False) and session_id:
        if isinstance(st.session_state.get("transcript_payload"), dict):
            st.session_state["fetch_data_in_progress"] = False
        else:
            start_transcript_fetch(str(session_id))


def apply_transcript_success(session_id: str, transcript_payload: Dict[str, Any]) -> None:
    clear_analysis_output()
    clear_api_error_details()
    clear_background_notice()
    transcript_text = build_transcript_display_text(transcript_payload)
    st.session_state["transcript_payload"] = transcript_payload
    st.session_state["transcript_text"] = transcript_text
    st.session_state["last_fetched_transcript_signature"] = build_transcript_request_signature(
        str(session_id or ""),
    )
    st.session_state["current_session_id"] = str(session_id or "")
    st.session_state["transcript_fetch_in_progress"] = False
    st.session_state["transcript_job_id"] = ""
    st.session_state["transcript_job_status"] = "completed"
    st.session_state["transcript_job_started_at"] = 0.0
    st.session_state["fetch_data_in_progress"] = False
    api_key = st.session_state.get("api_key_input", os.getenv("LS_API_KEY", ""))
    if session_id and api_key:
        persist_cached_session_safely(str(api_key), str(session_id), transcript_payload=transcript_payload)
    mark_analysis_source_defaults(st.session_state, include_transcript=True)
    st.session_state["analysis_include_transcript_pending"] = True


def start_transcript_fetch(session_id: str) -> None:
    transcript_api_key = get_runtime_secret("API_AUTH_KEY", "")
    if not transcript_api_key:
        st.error("Transcript fetch skipped: missing `API_AUTH_KEY` in environment.")
        st.session_state["fetch_data_in_progress"] = False
        return
    if not session_id:
        st.error("Please select a valid session before fetching the transcript.")
        st.session_state["fetch_data_in_progress"] = False
        return

    st.session_state["transcript_fetch_in_progress"] = True
    st.session_state["current_session_id"] = session_id
    st.session_state["transcript_payload"] = None
    st.session_state["transcript_text"] = ""
    try:
        job_payload = create_transcript_job(transcript_api_key, session_id, timestamped=True)
    except requests.HTTPError as exc:
        logger.exception(
            "Transcript job creation failed",
            extra={"session_id": session_id},
        )
        fail_transcript_job(
            format_generic_http_error(exc, "Transcript"),
            build_http_error_debug_details(exc, "Transcript"),
        )
        st.session_state["fetch_data_in_progress"] = False
        return
    except requests.RequestException as exc:
        logger.exception(
            "Transcript job creation network error",
            extra={"session_id": session_id},
        )
        fail_transcript_job(
            f"Transcript network error: {exc}",
            build_request_exception_debug_details(exc, "Transcript"),
        )
        st.session_state["fetch_data_in_progress"] = False
        return

    job_id = str(job_payload.get("job_id") or "").strip()
    if not job_id:
        fail_transcript_job(
            "Transcript job was created without a job ID.",
            build_transcript_job_debug_details(job_payload, "Transcript"),
        )
        st.session_state["fetch_data_in_progress"] = False
        return

    st.session_state["transcript_job_id"] = job_id
    st.session_state["transcript_job_status"] = str(job_payload.get("status") or "queued").strip().lower() or "queued"
    st.session_state["transcript_job_started_at"] = time.time()
    poll_transcript_job_if_needed()


def fail_transcript_job(message: str, details: Dict[str, Any] | None = None, *, status: str = "failed") -> None:
    set_api_error_details("Transcript", details)
    set_api_error_message(message)
    st.session_state["transcript_fetch_in_progress"] = False
    st.session_state["transcript_job_status"] = status
    st.session_state["transcript_job_id"] = ""
    st.session_state["transcript_job_started_at"] = 0.0
    st.session_state["fetch_data_in_progress"] = False
    clear_background_notice()


def render_background_jobs_panel() -> None:
    chat_job_id = str(st.session_state.get("chat_fetch_job_id") or "").strip()
    smart_recap_job_id = str(st.session_state.get("smart_recap_job_id") or "").strip()

    def render_panel() -> None:
        active_labels: List[str] = []

        if chat_job_id:
            snapshot = job_manager.get(chat_job_id)
            if snapshot and snapshot.get("done"):
                result = snapshot.get("result")
                if isinstance(result, dict):
                    apply_chat_questions_job_result(result)
                elif snapshot.get("exception") is not None:
                    apply_chat_questions_job_result(
                        build_failed_job_result(
                            "Chat & Questions background job failed unexpectedly.",
                            details={"exception_type": type(snapshot["exception"]).__name__, "message": str(snapshot["exception"])},
                        )
                    )
                job_manager.discard(chat_job_id)
                st.rerun()
            elif snapshot:
                active_labels.append("Fetching chat & questions...")
            else:
                st.session_state["fetch_in_progress"] = False
                st.session_state["chat_fetch_job_id"] = ""

        if smart_recap_job_id:
            snapshot = job_manager.get(smart_recap_job_id)
            if snapshot and snapshot.get("done"):
                result = snapshot.get("result")
                if isinstance(result, dict):
                    apply_smart_recap_job_result(result)
                elif snapshot.get("exception") is not None:
                    apply_smart_recap_job_result(
                        build_failed_job_result(
                            "Smart Recap background job failed unexpectedly.",
                            details={"exception_type": type(snapshot["exception"]).__name__, "message": str(snapshot["exception"])},
                        )
                    )
                job_manager.discard(smart_recap_job_id)
                st.rerun()
            elif snapshot:
                tone = str(st.session_state.get("smart_recap_in_progress_tone") or "smart recap").strip().title()
                active_labels.append(f"Generating {tone} recap...")
            else:
                st.session_state["smart_recap_in_progress"] = False
                st.session_state["smart_recap_in_progress_tone"] = ""
                st.session_state["smart_recap_job_id"] = ""

        for label in active_labels:
            with st.spinner(label):
                st.caption(" ")

        notice = str(st.session_state.get("background_job_notice") or "").strip()
        if notice:
            st.caption(notice)

    if hasattr(st, "fragment") and (chat_job_id or smart_recap_job_id):
        @st.fragment(run_every="2s")
        def _jobs_fragment() -> None:
            render_panel()

        _jobs_fragment()
    else:
        render_panel()


def poll_transcript_job_if_needed() -> None:
    if not st.session_state.get("transcript_fetch_in_progress", False):
        return

    transcript_api_key = get_runtime_secret("API_AUTH_KEY", "")
    job_id = str(st.session_state.get("transcript_job_id") or "").strip()
    session_id = str(st.session_state.get("current_session_id") or "").strip()
    if not transcript_api_key or not job_id:
        return

    started_at = float(st.session_state.get("transcript_job_started_at") or 0.0)
    if started_at and (time.time() - started_at) > (15 * 60):
        fail_transcript_job("Transcript job timed out after 15 minutes.", {"job_id": job_id, "status": "timeout"}, status="timeout")
        st.rerun()

    try:
        job_payload = get_transcript_job(transcript_api_key, job_id)
    except requests.HTTPError as exc:
        logger.exception("Transcript job polling failed", extra={"session_id": session_id, "job_id": job_id})
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code is not None and status_code < 500 and status_code not in (408, 429):
            fail_transcript_job(
                format_generic_http_error(exc, "Transcript"),
                build_http_error_debug_details(exc, "Transcript"),
            )
            st.rerun()
        return
    except requests.RequestException:
        return

    status = str(job_payload.get("status") or "").strip().lower()
    if status:
        st.session_state["transcript_job_status"] = status

    if status == "completed":
        result = job_payload.get("result")
        transcript = result.get("transcript") if isinstance(result, dict) else None
        transcription = result.get("transcription") if isinstance(result, dict) else None
        if isinstance(transcript, dict) or isinstance(transcription, dict):
            apply_transcript_success(session_id, job_payload)
        else:
            fail_transcript_job(
                "Transcript job completed without a supported transcript result.",
                build_transcript_job_debug_details(job_payload, "Transcript"),
            )
        st.rerun()

    if status == "failed":
        error = job_payload.get("error")
        message = error.get("message") if isinstance(error, dict) else "Transcript job failed."
        fail_transcript_job(message, build_transcript_job_debug_details(job_payload, "Transcript"))
        st.rerun()


def render_transcript_job_poller() -> None:
    if not st.session_state.get("transcript_fetch_in_progress", False):
        return
    if not str(st.session_state.get("transcript_job_id") or "").strip():
        return

    if hasattr(st, "fragment"):
        @st.fragment(run_every=f"{TRANSCRIPT_POLL_INTERVAL_SECONDS}s")
        def _transcript_poll_fragment() -> None:
            poll_transcript_job_if_needed()

        _transcript_poll_fragment()
    else:
        poll_transcript_job_if_needed()


configure_page()
apply_brand_styles()
init_session_state()
render_header()
try:
    ensure_database_schema()
except Exception:
    logger.exception("Database schema initialization failed")

has_chat_content = st.session_state.get("chat_df") is not None
has_questions_content = st.session_state.get("questions_df") is not None
has_transcript_content = st.session_state.get("transcript_payload") is not None
has_fetched_content = has_chat_content or has_questions_content or has_transcript_content

controls_col, main_col = st.columns([0.95, 3.05], gap="large")

fetch_data_button = False
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
)
form_locked = bool(st.session_state.get("transcript_fetch_in_progress", False))

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
            disabled=form_locked,
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
            disabled=(not has_any_connection_key) or form_locked,
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
                value=st.session_state.get("session_id_input", ""),
                help="Livestorm session ID",
                disabled=(not has_any_connection_key) or form_locked,
                key="session_id_input",
            )
            session_id_valid = bool(SESSION_ID_PATTERN.match(session_id.strip()))
        else:
            event_id = st.text_input(
                "Event ID",
                value=st.session_state.get("event_id_input", ""),
                help="Livestorm event ID",
                disabled=(not has_api_key) or form_locked,
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
                    disabled=(not has_api_key) or form_locked,
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
                    disabled=(not bool(options)) or form_locked,
                    key="selected_event_session_id",
                )
                if selected_session_from_event:
                    st.caption(f"Selected session: `{selected_session_from_event}`")

        active_session_id = get_active_session_id(input_mode, session_id, selected_session_from_event)
        current_transcript_signature = build_transcript_request_signature(
            active_session_id,
        )

        chat_request_already_fetched = (
            bool(active_session_id)
            and st.session_state.get("last_fetched_chat_session_id", "") == active_session_id
        )
        transcript_request_already_fetched = (
            bool(active_session_id)
            and st.session_state.get("last_fetched_transcript_signature", "") == current_transcript_signature
        )
        transcript_job_in_progress = bool(st.session_state.get("transcript_job_id", ""))
        chat_job_in_progress = bool(st.session_state.get("chat_fetch_job_id", ""))

        fetch_disabled = (
            (not has_api_key)
            or (not has_transcript_api_key)
            or (not bool(active_session_id))
            or (chat_request_already_fetched and transcript_request_already_fetched)
            or chat_job_in_progress
            or transcript_job_in_progress
            or form_locked
        )
        can_show_fetch_button = input_mode == "Session ID" or bool(active_session_id)

        if can_show_fetch_button:
            fetch_btn_placeholder = st.empty()
            if st.session_state.get("fetch_in_progress", False):
                fetch_btn_placeholder.button(
                    "Fetching Chat & Questions...",
                    type="primary",
                    disabled=True,
                    key="fetch_data_running_chat_btn",
                )
            elif st.session_state.get("transcript_fetch_in_progress", False):
                fetch_btn_placeholder.button(
                    "Fetching Transcript...",
                    type="primary",
                    disabled=True,
                    key="fetch_data_running_transcript_btn",
                )
            else:
                fetch_data_button = fetch_btn_placeholder.button(
                    "Fetch Data",
                    type="primary",
                    disabled=fetch_disabled,
                    key="fetch_data_run_btn",
                )
                if chat_request_already_fetched and transcript_request_already_fetched:
                    st.caption("Data already fetched for this session. Change the session to fetch again.")

        if not has_api_key and not has_transcript_api_key:
            st.caption("Add a Livestorm API key and set `API_AUTH_KEY` to fetch data.")
        elif has_transcript_api_key and not has_api_key:
            st.caption("Add a Livestorm API key to fetch chat/questions and load past sessions.")
        elif not has_transcript_api_key:
            st.caption("Set `API_AUTH_KEY` in `.env` or Streamlit secrets to enable transcript fetching.")
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

if fetch_data_button:
    previous_session_id = st.session_state.get("current_session_id", "")
    clear_analysis_output()
    clear_api_error_details()
    clear_background_notice()
    if previous_session_id and previous_session_id != active_session_id:
        reset_chat_question_state()
        reset_transcript_state()

    if not api_key or not transcript_api_key or not active_session_id:
        st.error("Please provide the Livestorm API key, transcript API key, and a valid session selection.")
    else:
        st.session_state["current_session_id"] = active_session_id
        cached_session = None
        if database_enabled():
            try:
                cached_session = fetch_cached_session(api_key, active_session_id)
            except Exception:
                logger.exception("Failed to load cached session", extra={"session_id": active_session_id})

        if isinstance(cached_session, dict):
            load_cached_session_into_state(api_key, active_session_id, cached_session)

        has_cached_chat = isinstance(st.session_state.get("chat_payload"), dict)
        has_cached_questions = isinstance(st.session_state.get("questions_payload"), dict)
        has_cached_transcript = isinstance(st.session_state.get("transcript_payload"), dict)

        if has_cached_chat and has_cached_questions and has_cached_transcript:
            st.rerun()

        st.session_state["fetch_data_in_progress"] = True
        if not (has_cached_chat and has_cached_questions):
            st.session_state["fetch_in_progress"] = True
            st.session_state["chat_fetch_job_id"] = job_manager.submit(
                "chat_questions",
                run_chat_questions_job,
                context={"session_id": active_session_id},
                api_key=api_key,
                session_id=active_session_id,
            )
        elif not has_cached_transcript:
            start_transcript_fetch(active_session_id)
    st.rerun()

payload = st.session_state.get("chat_payload")
df = st.session_state.get("chat_df")
questions_payload = st.session_state.get("questions_payload")
questions_df = st.session_state.get("questions_df")
transcript_payload = st.session_state.get("transcript_payload")
transcript_text = st.session_state.get("transcript_text", "")
content_repurpose_md = st.session_state.get("content_repurpose_md", "")
content_repurpose_bundle = st.session_state.get("content_repurpose_bundle", {})
content_repurpose_ran = st.session_state.get("content_repurpose_ran", False)
smart_recap_bundle = st.session_state.get("smart_recap_bundle", {})
smart_recap_ran = st.session_state.get("smart_recap_ran", False)
current_session_id = st.session_state.get("current_session_id") or active_session_id
selected_analysis_language = st.session_state.get("analysis_language", output_language_label)
analysis_bundle = _normalize_text_bundle(st.session_state.get("analysis_bundle", {}), st.session_state.get("analysis_md", ""))
deep_analysis_bundle = _normalize_text_bundle(st.session_state.get("deep_analysis_bundle", {}), st.session_state.get("deep_analysis_md", ""))
analysis_md = str(analysis_bundle.get(selected_analysis_language) or "")
analysis_ran = bool(analysis_md.strip())
deep_analysis_md = str(deep_analysis_bundle.get(selected_analysis_language) or "")
deep_analysis_ran = bool(deep_analysis_md.strip())
st.session_state["analysis_bundle"] = analysis_bundle
st.session_state["deep_analysis_bundle"] = deep_analysis_bundle
st.session_state["analysis_md"] = analysis_md
st.session_state["analysis_ran"] = analysis_ran
st.session_state["deep_analysis_md"] = deep_analysis_md
st.session_state["deep_analysis_ran"] = deep_analysis_ran
transcript_loading = bool(st.session_state.get("transcript_fetch_in_progress", False) and st.session_state.get("transcript_job_id", ""))
chat_questions_loading = bool(st.session_state.get("fetch_in_progress", False) and st.session_state.get("chat_fetch_job_id", ""))

with main_col:
    render_transcript_job_poller()
    render_background_jobs_panel()
    transcript_available = isinstance(transcript_payload, dict)
    chat_available = isinstance(df, pd.DataFrame)
    questions_available = isinstance(questions_df, pd.DataFrame)

    render_transcript_block(
        transcript_payload,
        transcript_text,
        current_session_id,
        is_loading=transcript_loading,
    )
    render_chat_questions_block(df, questions_df, current_session_id, is_loading=chat_questions_loading)
    content_repurpose_button = render_content_repurpose_block(
        current_session_id=current_session_id,
        transcript_available=transcript_available,
        chat_available=chat_available,
        questions_available=questions_available,
        content_repurpose_bundle=content_repurpose_bundle,
        content_repurpose_ran=content_repurpose_ran,
    )
    analyze_button, deep_analysis_button = render_analysis_block(
        current_session_id=current_session_id,
        analysis_ran=analysis_ran,
        analysis_md=analysis_md,
        deep_analysis_ran=deep_analysis_ran,
        deep_analysis_md=deep_analysis_md,
        transcript_available=transcript_available,
        chat_available=chat_available,
        questions_available=questions_available,
        transcript_payload=transcript_payload,
        chat_df=df,
        questions_df=questions_df,
    )
    smart_recap_button = render_smart_recap_block(
        current_session_id=current_session_id,
        transcript_available=transcript_available,
        smart_recap_bundle=smart_recap_bundle,
        smart_recap_ran=smart_recap_ran,
    )

if analyze_button:
    st.session_state["analysis_in_progress"] = True
    st.rerun()

if deep_analysis_button:
    st.session_state["deep_analysis_in_progress"] = True
    st.rerun()

if content_repurpose_button:
    st.session_state["content_repurpose_in_progress"] = True
    st.rerun()

if smart_recap_button:
    transcript_payload = st.session_state.get("transcript_payload")
    requested_tone = str(smart_recap_button or "").strip().lower()
    if transcript_payload is None:
        st.warning("Smart Recap requires a transcript.")
    elif not api_analysis_key:
        st.warning("Smart Recap skipped: missing `OPENAI_API_KEY` in environment.")
    elif requested_tone not in {"professional", "hype", "surprise"}:
        st.warning("Please select a valid Smart Recap type.")
    else:
        clear_api_error_details()
        clear_background_notice()
        st.session_state["smart_recap_in_progress"] = True
        st.session_state["smart_recap_in_progress_tone"] = requested_tone
        st.session_state["smart_recap_job_id"] = job_manager.submit(
            "smart_recap",
            run_smart_recap_job,
            context={"tone": requested_tone},
            api_key=api_analysis_key,
            tone=requested_tone,
            transcript_text=build_smart_recap_source_text(transcript_payload),
        )
    st.rerun()

if st.session_state.get("analysis_in_progress", False):
    payload = st.session_state.get("chat_payload")
    df = st.session_state.get("chat_df")
    questions_payload = st.session_state.get("questions_payload")
    questions_df = st.session_state.get("questions_df")
    transcript_payload = st.session_state.get("transcript_payload")
    selected_output_language = st.session_state.get("analysis_language", output_language_label)
    chat_questions_available = bool(payload is not None and isinstance(df, pd.DataFrame) and questions_payload is not None and isinstance(questions_df, pd.DataFrame))
    transcript_available = isinstance(transcript_payload, dict)

    selected_sources: List[str] = []
    if transcript_available:
        selected_sources.append("transcript")
    if chat_questions_available:
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

    analysis_bundle = _normalize_text_bundle(st.session_state.get("analysis_bundle", {}), st.session_state.get("analysis_md", ""))
    source_language, source_analysis_md = _get_alternate_language_text(analysis_bundle, selected_output_language)

    try:
        if source_analysis_md:
            analysis_md = translate_markdown_with_openai(
                api_key=api_analysis_key,
                model=DEFAULT_OPENAI_MODEL,
                source_markdown=source_analysis_md,
                source_language=OUTPUT_LANGUAGE_MAP.get(source_language, source_language),
                target_language=OUTPUT_LANGUAGE_MAP[selected_output_language],
            )
        else:
            prompt_text = build_analysis_prompt(selected_sources)
            derived_stats = build_derived_stats(
                chat_df=df if "chat" in selected_sources else None,
                questions_df=questions_df if "questions" in selected_sources else None,
                transcript_payload=transcript_payload if "transcript" in selected_sources else None,
            )
            analysis_md = analyze_with_openai(
                api_key=api_analysis_key,
                model=DEFAULT_OPENAI_MODEL,
                system_prompt=prompt_text,
                output_language=OUTPUT_LANGUAGE_MAP[selected_output_language],
                selected_sources=selected_sources,
                derived_stats=derived_stats,
                raw_payload=build_compact_chat_payload_for_llm(df) if "chat" in selected_sources and isinstance(df, pd.DataFrame) else None,
                questions_payload=build_compact_questions_payload_for_llm(questions_df) if "questions" in selected_sources and isinstance(questions_df, pd.DataFrame) else None,
                transcript_payload=build_compact_transcript_payload_for_llm(transcript_payload) if "transcript" in selected_sources and isinstance(transcript_payload, dict) else None,
            )
    except requests.HTTPError as exc:
        st.error(f"Analysis API error: {exc}")
        analysis_md = ""
    except requests.RequestException as exc:
        st.error(f"Analysis network error: {exc}")
        analysis_md = ""

    analysis_bundle = _normalize_text_bundle(st.session_state.get("analysis_bundle", {}), st.session_state.get("analysis_md", ""))
    if analysis_md.strip():
        analysis_bundle[selected_output_language] = analysis_md
    st.session_state["analysis_bundle"] = analysis_bundle
    st.session_state["analysis_md"] = str(analysis_bundle.get(selected_output_language) or "")
    st.session_state["analysis_ran"] = bool(st.session_state["analysis_md"].strip())
    if analysis_md.strip() and current_session_id and api_key:
        persist_cached_session_safely(
            api_key,
            current_session_id,
            analysis_md=analysis_md,
            analysis_bundle=analysis_bundle,
        )
    st.session_state["analysis_in_progress"] = False
    st.rerun()

if st.session_state.get("deep_analysis_in_progress", False):
    payload = st.session_state.get("chat_payload")
    df = st.session_state.get("chat_df")
    questions_payload = st.session_state.get("questions_payload")
    questions_df = st.session_state.get("questions_df")
    transcript_payload = st.session_state.get("transcript_payload")
    selected_output_language = st.session_state.get("analysis_language", output_language_label)

    if transcript_payload is None or payload is None or df is None or questions_payload is None or questions_df is None:
        st.warning("Deep analysis requires transcript, chat, and questions.")
        st.session_state["deep_analysis_in_progress"] = False
        st.rerun()
    if not api_analysis_key:
        st.warning("Deep analysis skipped: missing `OPENAI_API_KEY` in environment.")
        st.session_state["deep_analysis_in_progress"] = False
        st.rerun()

    deep_analysis_bundle = _normalize_text_bundle(st.session_state.get("deep_analysis_bundle", {}), st.session_state.get("deep_analysis_md", ""))
    source_language, source_deep_analysis_md = _get_alternate_language_text(deep_analysis_bundle, selected_output_language)

    try:
        if source_deep_analysis_md:
            deep_analysis_md = translate_markdown_with_openai(
                api_key=api_analysis_key,
                model=DEFAULT_OPENAI_MODEL,
                source_markdown=source_deep_analysis_md,
                source_language=OUTPUT_LANGUAGE_MAP.get(source_language, source_language),
                target_language=OUTPUT_LANGUAGE_MAP.get(selected_output_language, selected_output_language),
                max_tokens=8000,
            )
        else:
            prompt_text = build_deep_analysis_prompt()
            derived_stats = build_derived_stats(
                chat_df=df,
                questions_df=questions_df,
                transcript_payload=transcript_payload,
            )
            deep_analysis_md = analyze_with_openai(
                api_key=api_analysis_key,
                model="gpt-4o",
                system_prompt=prompt_text,
                output_language=OUTPUT_LANGUAGE_MAP.get(selected_output_language, selected_output_language),
                selected_sources=["chat", "questions", "transcript"],
                derived_stats=derived_stats,
                raw_payload=build_compact_chat_payload_for_llm(df, max_rows=80),
                questions_payload=build_compact_questions_payload_for_llm(questions_df, max_rows=40),
                transcript_payload=build_compact_transcript_payload_for_llm(transcript_payload, max_segments=60),
                max_tokens=2200,
            )
    except requests.HTTPError as exc:
        logger.exception("Deep analysis request failed")
        set_api_error_details("Deep analysis", build_http_error_debug_details(exc, "Deep analysis"))
        set_api_error_message(format_generic_http_error(exc, "Deep analysis"))
        deep_analysis_md = ""
    except requests.RequestException as exc:
        logger.exception("Deep analysis network error")
        set_api_error_details("Deep analysis", build_request_exception_debug_details(exc, "Deep analysis"))
        set_api_error_message(f"Deep analysis network error: {exc}")
        deep_analysis_md = ""

    deep_analysis_bundle = _normalize_text_bundle(st.session_state.get("deep_analysis_bundle", {}), st.session_state.get("deep_analysis_md", ""))
    if deep_analysis_md.strip():
        deep_analysis_bundle[selected_output_language] = deep_analysis_md
    st.session_state["deep_analysis_bundle"] = deep_analysis_bundle
    st.session_state["deep_analysis_md"] = str(deep_analysis_bundle.get(selected_output_language) or "")
    st.session_state["deep_analysis_ran"] = bool(st.session_state["deep_analysis_md"].strip())
    if deep_analysis_md.strip() and current_session_id and api_key:
        persist_cached_session_safely(
            api_key,
            current_session_id,
            deep_analysis_md=deep_analysis_md,
            deep_analysis_bundle=deep_analysis_bundle,
        )
    st.session_state["deep_analysis_in_progress"] = False
    st.rerun()

if st.session_state.get("content_repurpose_in_progress", False):
    transcript_payload = st.session_state.get("transcript_payload")
    selected_output_language = st.session_state.get("content_repurpose_language", output_language_label)

    if transcript_payload is None:
        st.warning("Content repurposing requires a transcript.")
        st.session_state["content_repurpose_in_progress"] = False
        st.rerun()
    if not api_analysis_key:
        st.warning("Content repurposing skipped: missing `OPENAI_API_KEY` in environment.")
        st.session_state["content_repurpose_in_progress"] = False
        st.rerun()
    existing_bundles = st.session_state.get("content_repurpose_bundle", {})
    if isinstance(existing_bundles, dict):
        existing_language_bundle = existing_bundles.get(selected_output_language, {})
        if isinstance(existing_language_bundle, dict) and any(str(value or "").strip() for value in existing_language_bundle.values()):
            st.session_state["content_repurpose_in_progress"] = False
            st.rerun()

    all_bundles = st.session_state.get("content_repurpose_bundle", {})
    if not isinstance(all_bundles, dict):
        all_bundles = {}
    content_repurpose_bundle = {}
    source_language, source_content_bundle = _get_alternate_language_bundle(all_bundles, selected_output_language)
    try:
        if source_content_bundle:
            content_repurpose_bundle = translate_content_repurpose_bundle_with_openai(
                api_key=api_analysis_key,
                model=DEFAULT_OPENAI_MODEL,
                source_bundle=source_content_bundle,
                source_language=OUTPUT_LANGUAGE_MAP.get(source_language, source_language),
                target_language=OUTPUT_LANGUAGE_MAP.get(selected_output_language, selected_output_language),
            )
        else:
            transcript_text_for_repurpose = build_transcript_plain_text(transcript_payload)
            content_repurpose_bundle = generate_content_repurpose_bundle_with_openai(
                api_key=api_analysis_key,
                model=DEFAULT_OPENAI_MODEL,
                output_language=OUTPUT_LANGUAGE_MAP.get(selected_output_language, selected_output_language),
                transcript_text=transcript_text_for_repurpose,
            )
    except requests.HTTPError as exc:
        logger.exception("Content repurposing request failed")
        set_api_error_details("Content repurposing", build_http_error_debug_details(exc, "Content repurposing"))
        set_api_error_message(format_generic_http_error(exc, "Content repurposing"))
        content_repurpose_bundle = {}
    except requests.RequestException as exc:
        logger.exception("Content repurposing network error")
        set_api_error_details("Content repurposing", build_request_exception_debug_details(exc, "Content repurposing"))
        set_api_error_message(f"Content repurposing network error: {exc}")
        content_repurpose_bundle = {}

    has_generated_content = any(
        isinstance(markdown, str) and markdown.strip()
        for markdown in content_repurpose_bundle.values()
    )
    if has_generated_content:
        all_bundles[selected_output_language] = content_repurpose_bundle
    else:
        all_bundles.pop(selected_output_language, None)
    content_repurpose_md = "\n\n---\n\n".join(
        markdown.strip()
        for bundle in all_bundles.values()
        if isinstance(bundle, dict)
        for markdown in bundle.values()
        if isinstance(markdown, str) and markdown.strip()
    )
    st.session_state["content_repurpose_md"] = content_repurpose_md
    st.session_state["content_repurpose_bundle"] = all_bundles
    st.session_state["content_repurpose_ran"] = bool(content_repurpose_md.strip())
    st.session_state["content_repurpose_history"] = []
    if current_session_id and api_key and isinstance(all_bundles, dict) and all_bundles:
        persist_cached_session_safely(api_key, current_session_id, content_repurpose_bundle=all_bundles)
    st.session_state["content_repurpose_in_progress"] = False
    st.rerun()
