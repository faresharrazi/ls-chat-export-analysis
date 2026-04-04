import json
import math
import re
import sys
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from livestorm_app.config import (
    ANALYSIS_ALL_SOURCES_PROMPT_PATH,
    ANALYSIS_BASE_PROMPT_PATH,
    ANALYSIS_CHAT_PROMPT_PATH,
    ANALYSIS_QUESTIONS_PROMPT_PATH,
    ANALYSIS_TRANSCRIPT_PROMPT_PATH,
    API_BASE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGES,
    OPENAI_CHAT_COMPLETIONS_URL,
    START_PAGE_NUMBER,
    TRANSCRIPT_API_URL,
)


COMMON_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can", "do", "does", "did",
    "for", "from", "had", "has", "have", "hello", "how", "i", "if", "in", "into", "is", "it",
    "it's", "its", "just", "let", "let's", "ll", "look", "me", "my", "not", "now", "of", "okay",
    "on", "one", "or", "our", "ours", "please", "right", "so", "some", "still", "such", "than",
    "that", "that's", "the", "their", "them", "then", "there", "thing", "things", "think",
    "these", "they", "this", "those", "to", "too", "up", "us", "very", "was", "we", "well",
    "what", "when", "where", "which", "who", "why", "with", "would", "yeah", "you", "your",
    "yours", "ah", "eh", "first", "go", "going", "get", "got", "know", "like", "through", "back", "live",
    "will", "work", "working", "really", "also", "make", "made", "want", "need", "maybe",
    "s", "t", "re", "ve", "m", "d",
    "bonjour", "merci", "pour", "avec", "dans", "tout", "tous", "les", "des", "une", "est",
    "que", "qui", "sur", "pas", "oui", "franchement", "ca", "ça", "va",
}


def build_headers(key: str) -> Dict[str, str]:
    return {
        "Authorization": key,
        "accept": "application/vnd.api+json",
    }


def build_transcript_headers(key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {key}",
        "X-API-Key": key,
        "accept": "application/json",
    }


def format_livestorm_http_error(exc: requests.HTTPError, resource_label: str) -> str:
    response = exc.response
    status_code = response.status_code if response is not None else None
    details = ""

    if response is not None:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                if isinstance(payload.get("error"), str):
                    details = payload["error"]
                elif isinstance(payload.get("message"), str):
                    details = payload["message"]
        except ValueError:
            details = ""

    if status_code == 400:
        return (
            f"{resource_label} request is invalid (HTTP 400). "
            "Please verify the provided ID and request parameters."
        )
    if status_code in (401, 403):
        return (
            f"{resource_label} request was unauthorized (HTTP {status_code}). "
            "Please check your Livestorm API key permissions."
        )
    if status_code == 404:
        return (
            "Resource not found (HTTP 404). "
            "Please verify the provided Session ID/Event ID exists in your Livestorm workspace."
        )
    if status_code == 429:
        return f"{resource_label} rate limited (HTTP 429). Please wait a few seconds and try again."
    if status_code is not None and status_code >= 500:
        return (
            f"Livestorm server error while fetching {resource_label.lower()} (HTTP {status_code}). "
            "Please retry shortly."
        )
    if details:
        return f"{resource_label} API request failed (HTTP {status_code}): {details}"
    if status_code is not None:
        return f"{resource_label} API request failed (HTTP {status_code})."
    return f"{resource_label} API request failed."


def format_generic_http_error(exc: requests.HTTPError, resource_label: str) -> str:
    response = exc.response
    status_code = response.status_code if response is not None else None
    details = ""

    if response is not None:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                for key in ("error", "message", "detail"):
                    if isinstance(payload.get(key), str):
                        details = payload[key]
                        break
        except ValueError:
            details = ""

    if status_code in (401, 403):
        return (
            f"{resource_label} request was unauthorized (HTTP {status_code}). "
            "Please check the configured transcript API token."
        )
    if status_code == 404:
        return (
            f"{resource_label} not found (HTTP 404). "
            "Please verify the selected session has an available recording/transcript."
        )
    if status_code == 429:
        return f"{resource_label} rate limited (HTTP 429). Please retry in a moment."
    if status_code is not None and status_code >= 500:
        return f"{resource_label} server error (HTTP {status_code}). Please retry shortly."
    if details and status_code is not None:
        return f"{resource_label} request failed (HTTP {status_code}): {details}"
    if status_code is not None:
        return f"{resource_label} request failed (HTTP {status_code})."
    return f"{resource_label} request failed."


def extract_messages(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload, list):
        return payload
    return []


def extract_questions(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload, list):
        return payload
    return []


def extract_sessions(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload, list):
        return payload
    return []


def _format_unix_label(value: Any) -> str:
    try:
        if value in (None, "", 0):
            return "n/a"
        ts = pd.to_datetime(value, unit="s", utc=True, errors="coerce")
        if pd.isna(ts):
            return "n/a"
        return ts.strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError):
        return "n/a"


def build_event_session_options(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    session_items = extract_sessions(payload)
    options: List[Dict[str, str]] = []
    sortable: List[Dict[str, Any]] = []
    for item in session_items:
        if not isinstance(item, dict):
            continue
        session_id = str(item.get("id") or "").strip()
        if not session_id:
            continue
        attrs = item.get("attributes")
        attrs = attrs if isinstance(attrs, dict) else {}
        started_at = attrs.get("started_at") or attrs.get("estimated_started_at") or 0
        sortable.append({"id": session_id, "attributes": attrs, "started_at": started_at})

    sortable.sort(key=lambda row: row.get("started_at") or 0, reverse=True)
    for row in sortable:
        attrs = row["attributes"]
        name = str(attrs.get("name") or "").strip()
        attendees = attrs.get("attendees_count", "n/a")
        started_label = _format_unix_label(attrs.get("started_at") or attrs.get("estimated_started_at"))
        title = name if name else "Untitled session"
        options.append({"id": row["id"], "label": f"{started_label} - {title} ({attendees} attendees)"})
    return options


def extract_included_people(payload: Dict[str, Any]) -> Dict[str, str]:
    people_lookup: Dict[str, str] = {}
    included = payload.get("included")
    if not isinstance(included, list):
        return people_lookup

    for item in included:
        if not isinstance(item, dict) or item.get("type") != "people":
            continue
        person_id = str(item.get("id") or "").strip()
        if not person_id:
            continue
        attrs = item.get("attributes")
        if not isinstance(attrs, dict):
            people_lookup[person_id] = person_id
            continue
        first_name = str(attrs.get("first_name") or "").strip()
        last_name = str(attrs.get("last_name") or "").strip()
        people_lookup[person_id] = f"{first_name} {last_name}".strip() or person_id

    return people_lookup


def _extract_pagination(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        pagination = metadata.get("pagination")
        if isinstance(pagination, dict):
            return pagination
        return metadata

    meta = payload.get("meta")
    if isinstance(meta, dict):
        pagination = meta.get("pagination")
        if isinstance(pagination, dict):
            return pagination
        return meta

    return {}


def _extract_next_page(payload: Dict[str, Any]) -> Optional[int]:
    pagination = _extract_pagination(payload)
    next_page = pagination.get("next_page")

    if next_page is None or isinstance(next_page, bool):
        return None
    if isinstance(next_page, int):
        return next_page
    if isinstance(next_page, str):
        raw = next_page.strip()
        if not raw or raw.lower() == "null":
            return None
        if raw.isdigit():
            return int(raw)
    return None


def flatten_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    base: Dict[str, Any] = {}
    if not isinstance(msg, dict):
        return base

    base.update({"id": msg.get("id"), "type": msg.get("type")})
    attrs = msg.get("attributes")
    if isinstance(attrs, dict):
        for key, value in attrs.items():
            base[key] = value

    rels = msg.get("relationships")
    if isinstance(rels, dict):
        for rel_name, rel_val in rels.items():
            if isinstance(rel_val, dict) and "data" in rel_val:
                rel_data = rel_val.get("data")
                if isinstance(rel_data, dict):
                    base[f"rel.{rel_name}.id"] = rel_data.get("id")
                    base[f"rel.{rel_name}.type"] = rel_data.get("type")
                elif isinstance(rel_data, list):
                    base[f"rel.{rel_name}.ids"] = ",".join(
                        [str(item.get("id")) for item in rel_data if isinstance(item, dict)]
                    )
    return base


def flatten_question(question: Dict[str, Any], people_lookup: Dict[str, str]) -> Dict[str, Any]:
    base: Dict[str, Any] = {}
    if not isinstance(question, dict):
        return base

    base.update({"id": question.get("id"), "type": question.get("type")})
    attrs = question.get("attributes")
    if isinstance(attrs, dict):
        for key, value in attrs.items():
            base[key] = value

    asker_id = str(base.get("question_author_id") or "").strip()
    responder_id = str(base.get("response_author_id") or "").strip()
    base["asked_by"] = people_lookup.get(asker_id, asker_id) if asker_id else None
    base["answered_by"] = people_lookup.get(responder_id, responder_id) if responder_id else None
    return base


def clean_table_headers(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [
        col.replace("attr.", "").replace("rel.", "").replace(".", "_") for col in cleaned.columns
    ]
    return cleaned


def format_unix_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for col in ("created_at", "updated_at", "responded_at"):
        if col in formatted.columns:
            formatted[col] = pd.to_datetime(formatted[col], unit="s", utc=True, errors="coerce")
            formatted[col] = formatted[col].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    return formatted


def drop_unwanted_columns(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    existing = [col for col in ["type", "from_guest_speaker", "from_team_member", "html_content"] if col in cleaned.columns]
    if existing:
        cleaned = cleaned.drop(columns=existing)
    return cleaned


def clean_questions_table(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    existing = [
        col
        for col in [
            "type",
            "session_id",
            "event_id",
            "question_author_id",
            "response_author_id",
            "responded_orally",
            "updated_at",
        ]
        if col in cleaned.columns
    ]
    if existing:
        cleaned = cleaned.drop(columns=existing)

    if "created_at" in cleaned.columns:
        cleaned = cleaned.rename(columns={"created_at": "asked_at"})

    preferred_order = ["id", "question", "response", "asked_by", "answered_by", "asked_at", "responded_at"]
    cols = [col for col in preferred_order if col in cleaned.columns] + [
        col for col in cleaned.columns if col not in preferred_order
    ]
    return cleaned[cols]


def fetch_chat_messages(key: str, session: str, page_size: int = DEFAULT_PAGE_SIZE) -> Dict[str, Any]:
    url = f"{API_BASE}/sessions/{session}/chat_messages"
    headers = build_headers(key)

    page_number = START_PAGE_NUMBER
    pages_fetched = 0
    seen_pages = set()
    all_messages: List[Dict[str, Any]] = []
    final_payload: Dict[str, Any] = {}

    while pages_fetched < MAX_PAGES:
        if page_number in seen_pages:
            break
        seen_pages.add(page_number)

        resp = requests.get(
            url,
            headers=headers,
            params={"page[number]": page_number, "page[size]": page_size},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict):
            payload = {"data": extract_messages(payload)}

        final_payload = payload
        messages = extract_messages(payload)
        all_messages.extend(messages)
        pages_fetched += 1

        next_page = _extract_next_page(payload)
        if next_page is not None:
            if next_page in seen_pages:
                break
            page_number = next_page
            continue
        if len(messages) < page_size:
            break
        page_number += 1

    final_payload["data"] = all_messages
    final_payload["pages_fetched"] = pages_fetched
    final_payload["requested_page_size"] = page_size
    return final_payload


def fetch_session_questions(key: str, session: str, page_size: int = DEFAULT_PAGE_SIZE) -> Dict[str, Any]:
    url = f"{API_BASE}/sessions/{session}/questions"
    headers = build_headers(key)

    page_number = START_PAGE_NUMBER
    pages_fetched = 0
    seen_pages = set()
    all_questions: List[Dict[str, Any]] = []
    all_included: Dict[str, Dict[str, Any]] = {}
    final_payload: Dict[str, Any] = {}

    while pages_fetched < MAX_PAGES:
        if page_number in seen_pages:
            break
        seen_pages.add(page_number)

        resp = requests.get(
            url,
            headers=headers,
            params={"page[number]": page_number, "page[size]": page_size, "include": "asker,responder"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict):
            payload = {"data": extract_questions(payload)}

        final_payload = payload
        page_questions = extract_questions(payload)
        all_questions.extend(page_questions)
        pages_fetched += 1

        included = payload.get("included")
        if isinstance(included, list):
            for item in included:
                if not isinstance(item, dict):
                    continue
                included_id = str(item.get("id") or "")
                included_type = str(item.get("type") or "")
                if included_id and included_type:
                    all_included[f"{included_type}:{included_id}"] = item

        next_page = _extract_next_page(payload)
        if next_page is not None:
            if next_page in seen_pages:
                break
            page_number = next_page
            continue
        if len(page_questions) < page_size:
            break
        page_number += 1

    final_payload["data"] = all_questions
    final_payload["included"] = list(all_included.values())
    final_payload["pages_fetched"] = pages_fetched
    final_payload["requested_page_size"] = page_size
    return final_payload


def fetch_event_past_sessions(key: str, event: str, page_size: int = DEFAULT_PAGE_SIZE) -> Dict[str, Any]:
    url = f"{API_BASE}/events/{event}/sessions"
    headers = build_headers(key)

    page_number = START_PAGE_NUMBER
    pages_fetched = 0
    seen_pages = set()
    all_sessions: List[Dict[str, Any]] = []
    final_payload: Dict[str, Any] = {}

    while pages_fetched < MAX_PAGES:
        if page_number in seen_pages:
            break
        seen_pages.add(page_number)

        resp = requests.get(
            url,
            headers=headers,
            params={"page[number]": page_number, "page[size]": page_size, "filter[status]": "past"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict):
            payload = {"data": extract_sessions(payload)}

        final_payload = payload
        page_sessions = extract_sessions(payload)
        all_sessions.extend(page_sessions)
        pages_fetched += 1

        next_page = _extract_next_page(payload)
        if next_page is not None:
            if next_page in seen_pages:
                break
            page_number = next_page
            continue
        if len(page_sessions) < page_size:
            break
        page_number += 1

    final_payload["data"] = all_sessions
    final_payload["pages_fetched"] = pages_fetched
    final_payload["requested_page_size"] = page_size
    return final_payload


def fetch_session_transcript(key: str, session: str, verbose: bool = False) -> Dict[str, Any]:
    resp = requests.get(
        TRANSCRIPT_API_URL,
        headers=build_transcript_headers(key),
        params={"session_id": session, "verbose": str(verbose).lower()},
        timeout=180,
    )
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, dict):
        return {"transcript": payload}
    return payload


def load_analysis_prompt(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def build_analysis_prompt(selected_sources: List[str]) -> str:
    prompt_parts = [load_analysis_prompt(ANALYSIS_BASE_PROMPT_PATH)]
    if "chat" in selected_sources:
        prompt_parts.append(load_analysis_prompt(ANALYSIS_CHAT_PROMPT_PATH))
    if "questions" in selected_sources:
        prompt_parts.append(load_analysis_prompt(ANALYSIS_QUESTIONS_PROMPT_PATH))
    if "transcript" in selected_sources:
        prompt_parts.append(load_analysis_prompt(ANALYSIS_TRANSCRIPT_PROMPT_PATH))
    if set(selected_sources) == {"chat", "questions", "transcript"}:
        prompt_parts.append(load_analysis_prompt(ANALYSIS_ALL_SOURCES_PROMPT_PATH))

    prompt = "\n\n".join(part for part in prompt_parts if part.strip())
    if prompt.strip():
        return prompt

    return (
        "You are a senior analyst. Review the selected Livestorm session sources and return concise, "
        "evidence-based markdown with an executive summary, key themes, engagement insights, risks, "
        "and actionable recommendations. Clearly state any limits caused by missing sources."
    )


def analysis_markdown_to_pdf_bytes(markdown_text: str, title: str) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise RuntimeError(
            f"PDF export unavailable. Install with: `{sys.executable} -m pip install reportlab`"
        ) from exc

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#0F1D21"),
    )
    heading_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=16,
        textColor=colors.HexColor("#12262B"),
        spaceBefore=8,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
    )

    story = [Paragraph(title, title_style), Spacer(1, 8)]
    for line in [line.strip() for line in markdown_text.splitlines()]:
        if not line:
            story.append(Spacer(1, 5))
            continue
        escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if escaped.startswith("### "):
            story.append(Paragraph(escaped[4:], heading_style))
        elif escaped.startswith("## "):
            story.append(Paragraph(escaped[3:], heading_style))
        elif escaped.startswith("# "):
            story.append(Paragraph(escaped[2:], heading_style))
        elif escaped.startswith("- "):
            story.append(Paragraph(f"&bull; {escaped[2:]}", body_style))
        else:
            story.append(Paragraph(escaped, body_style))

    doc.build(story)
    return buffer.getvalue()


def build_question_stats(questions_df: pd.DataFrame) -> Dict[str, Any]:
    stats: Dict[str, Any] = {"total_questions": int(len(questions_df.index))}
    asker_col = "asked_by" if "asked_by" in questions_df.columns else "question_author_id" if "question_author_id" in questions_df.columns else None

    if asker_col is not None:
        stats["unique_askers"] = int(questions_df[asker_col].nunique())
        top_askers = questions_df[asker_col].value_counts().head(10)
        stats["top_askers_by_question_count"] = {str(idx): int(val) for idx, val in top_askers.items()}

    if "response" in questions_df.columns:
        has_response = questions_df["response"].fillna("").astype(str).str.strip() != ""
        stats["answered_questions"] = int(has_response.sum())
        stats["unanswered_questions"] = int((~has_response).sum())

    return stats


def build_transcript_stats(transcript_payload: Dict[str, Any]) -> Dict[str, Any]:
    transcript = _extract_transcript_object(transcript_payload)
    text = str(transcript.get("text") or "")
    stats: Dict[str, Any] = {
        "word_count": len(re.findall(r"\S+", text)),
        "character_count": len(text),
        "model": transcript.get("model"),
        "requested_model": transcript.get("requested_model"),
        "language": transcript.get("language"),
        "timestamped": bool(transcript.get("timestamped")),
        "created_at": transcript.get("created_at"),
        "duration_seconds": transcript.get("duration_seconds"),
    }

    usage = transcript.get("usage")
    if isinstance(usage, dict):
        stats["usage"] = usage
    recording = transcript.get("recording")
    if isinstance(recording, dict):
        stats["recording"] = {
            "id": recording.get("id"),
            "event_id": recording.get("event_id"),
            "file_type": recording.get("file_type"),
            "mime_type": recording.get("mime_type"),
            "file_size": recording.get("file_size"),
            "file_name": recording.get("file_name"),
        }
    return stats


def _coerce_seconds(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_seconds_label(value: Optional[float]) -> str:
    if value is None:
        return ""
    total_seconds = max(int(value), 0)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _extract_transcript_object(transcript_payload: Dict[str, Any]) -> Dict[str, Any]:
    transcript = transcript_payload.get("transcript")
    if isinstance(transcript, dict):
        return transcript
    return transcript_payload if isinstance(transcript_payload, dict) else {}


def _extract_transcript_segments(transcript: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("segments", "timestamps", "utterances", "chunks"):
        value = transcript.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _get_segment_start_value(segment: Dict[str, Any]) -> Any:
    start_value = segment.get("start")
    if start_value is None:
        start_value = segment.get("start_time")
    if start_value is None:
        start_value = segment.get("offset")
    if start_value is None and segment.get("start_ms") is not None:
        start_seconds = _coerce_seconds(segment.get("start_ms"))
        start_value = start_seconds / 1000 if start_seconds is not None else None
    return start_value


def _get_segment_end_value(segment: Dict[str, Any]) -> Any:
    end_value = segment.get("end")
    if end_value is None:
        end_value = segment.get("end_time")
    if end_value is None:
        end_value = segment.get("offset_end")
    if end_value is None and segment.get("end_ms") is not None:
        end_seconds = _coerce_seconds(segment.get("end_ms"))
        end_value = end_seconds / 1000 if end_seconds is not None else None
    return end_value


def build_transcript_display_text(transcript_payload: Dict[str, Any]) -> str:
    transcript = _extract_transcript_object(transcript_payload)
    segments = _extract_transcript_segments(transcript)
    if segments:
        lines: List[str] = []
        for segment in segments:
            segment_text = str(segment.get("text") or "").strip()
            if not segment_text:
                continue
            start_value = _get_segment_start_value(segment)
            timestamp_label = format_seconds_label(_coerce_seconds(start_value))
            lines.append(f"[{timestamp_label}] {segment_text}" if timestamp_label else segment_text)
        if lines:
            return "\n".join(lines)
    return str(transcript.get("text") or "").strip()


def build_transcript_segments_df(transcript_payload: Dict[str, Any]) -> pd.DataFrame:
    transcript = _extract_transcript_object(transcript_payload)
    segments = _extract_transcript_segments(transcript)
    if not segments:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    for segment in segments:
        text = str(segment.get("text") or "").strip()
        start_value = _get_segment_start_value(segment)
        end_value = _get_segment_end_value(segment)
        speaker = (
            segment.get("speaker")
            or segment.get("speaker_name")
            or segment.get("speaker_label")
            or segment.get("speaker_id")
            or segment.get("participant")
            or segment.get("author")
        )

        start_seconds = _coerce_seconds(start_value)
        end_seconds = _coerce_seconds(end_value)
        duration_seconds = max(end_seconds - start_seconds, 0.0) if start_seconds is not None and end_seconds is not None else None
        word_count = len(re.findall(r"\S+", text))
        rows.append(
            {
                "segment_id": segment.get("id"),
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "start_label": format_seconds_label(start_seconds),
                "duration_seconds": duration_seconds,
                "text": text,
                "speaker": str(speaker).strip() if speaker else "Unknown speaker",
                "word_count": word_count,
                "words_per_second": round(word_count / duration_seconds, 2) if duration_seconds and duration_seconds > 0 else None,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty and "start_seconds" in df.columns:
        df["minute_bucket"] = df["start_seconds"].fillna(0).astype(float).floordiv(60).astype(int)
        df["minute_label"] = df["minute_bucket"].apply(lambda value: format_seconds_label(value * 60))
    return df


def extract_common_terms_from_series(text_series: pd.Series, top_n: int = 12) -> pd.DataFrame:
    def normalize_term(term: str) -> str:
        cleaned = term.lower().strip("'")
        if len(cleaned) > 5 and cleaned.endswith("ing"):
            cleaned = cleaned[:-3]
        elif len(cleaned) > 4 and cleaned.endswith("ed"):
            cleaned = cleaned[:-2]
        elif len(cleaned) > 4 and cleaned.endswith("es"):
            cleaned = cleaned[:-2]
        elif len(cleaned) > 3 and cleaned.endswith("s"):
            cleaned = cleaned[:-1]
        if cleaned.endswith("'"):
            cleaned = cleaned[:-1]
        return cleaned

    text = " ".join(text_series.fillna("").astype(str).tolist()).lower()
    raw_terms = re.findall(r"\b[\w']{3,}\b", text)
    normalized_terms = [normalize_term(term) for term in raw_terms]
    filtered = [
        term for term in normalized_terms
        if term
        and term not in COMMON_STOPWORDS
        and not term.isdigit()
        and len(term) >= 3
    ]
    counts = Counter(filtered).most_common(top_n)
    return pd.DataFrame(counts, columns=["term", "count"]) if counts else pd.DataFrame(columns=["term", "count"])


def extract_raw_terms_from_series(text_series: pd.Series, top_n: int = 10) -> pd.DataFrame:
    text = " ".join(text_series.fillna("").astype(str).tolist()).lower()
    normalized_text = text.replace("’", "'")
    terms = [
        term.strip("'") for term in re.findall(r"\b[\w']+\b", normalized_text)
        if term
        and not term.isdigit()
        and term.strip("'") not in COMMON_STOPWORDS
        and len(term.strip("'")) >= 3
    ]
    counts = Counter(terms).most_common(top_n)
    return pd.DataFrame(counts, columns=["term", "count"]) if counts else pd.DataFrame(columns=["term", "count"])


def extract_meaningful_terms_from_series(text_series: pd.Series, top_n: int = 10) -> pd.DataFrame:
    normalized_segments = text_series.fillna("").astype(str).str.lower().str.replace("’", "'", regex=False)
    token_pattern = re.compile(r"\b[\w']+\b")

    term_counts: Counter[str] = Counter()
    segment_counts: Counter[str] = Counter()
    total_segments = 0

    for segment_text in normalized_segments:
        tokens = [token.strip("'") for token in token_pattern.findall(segment_text)]
        filtered_tokens = [
            token for token in tokens
            if token
            and len(token) >= 3
            and not token.isdigit()
            and token not in COMMON_STOPWORDS
            and "'" not in token
        ]
        if not filtered_tokens:
            continue
        total_segments += 1
        term_counts.update(filtered_tokens)
        segment_counts.update(set(filtered_tokens))

    if not term_counts or total_segments == 0:
        return pd.DataFrame(columns=["term", "count", "segment_count", "score"])

    scored_rows: List[Dict[str, Any]] = []
    for term, count in term_counts.items():
        doc_freq = int(segment_counts.get(term, 0))
        if doc_freq <= 0:
            continue
        coverage_ratio = doc_freq / total_segments
        if coverage_ratio >= 0.8:
            continue
        score = count * math.log1p(total_segments / doc_freq)
        scored_rows.append(
            {
                "term": term,
                "count": int(count),
                "segment_count": doc_freq,
                "score": round(score, 3),
            }
        )

    if not scored_rows:
        return pd.DataFrame(columns=["term", "count", "segment_count", "score"])

    scored_df = pd.DataFrame(scored_rows).sort_values(
        by=["score", "count", "segment_count", "term"],
        ascending=[False, False, True, True],
    )
    return scored_df.head(top_n).reset_index(drop=True)


def build_transcript_insights(transcript_payload: Dict[str, Any]) -> Dict[str, Any]:
    segments_df = build_transcript_segments_df(transcript_payload)
    if segments_df.empty:
        return {
            "segments_df": segments_df,
            "timeline_df": pd.DataFrame(),
            "pace_df": pd.DataFrame(),
            "silence_df": pd.DataFrame(),
            "segment_mix_df": pd.DataFrame(),
            "terms_df": pd.DataFrame(),
            "summary": {},
        }

    transcript = _extract_transcript_object(transcript_payload)
    ordered_df = segments_df.sort_values(by=["start_seconds", "end_seconds"], na_position="last").reset_index(drop=True)

    timeline_rows: List[Dict[str, Any]] = []
    for _, row in ordered_df.iterrows():
        start_seconds = row.get("start_seconds")
        end_seconds = row.get("end_seconds")
        duration_seconds = row.get("duration_seconds")
        word_count = int(row.get("word_count") or 0)

        if pd.isna(start_seconds):
            continue

        if pd.isna(end_seconds) or pd.isna(duration_seconds) or float(duration_seconds) <= 0:
            minute_bucket = int(float(start_seconds) // 60)
            timeline_rows.append(
                {
                    "minute_bucket": minute_bucket,
                    "word_count": word_count,
                    "speaking_seconds": 0.0,
                    "segment_count": 1,
                }
            )
            continue

        start_seconds = float(start_seconds)
        end_seconds = float(end_seconds)
        duration_seconds = float(duration_seconds)
        current_minute = int(start_seconds // 60)
        last_minute = int(max(end_seconds - 1e-9, start_seconds) // 60)

        for minute_bucket in range(current_minute, last_minute + 1):
            bucket_start = minute_bucket * 60
            bucket_end = bucket_start + 60
            overlap_seconds = max(0.0, min(end_seconds, bucket_end) - max(start_seconds, bucket_start))
            if overlap_seconds <= 0:
                continue
            timeline_rows.append(
                {
                    "minute_bucket": minute_bucket,
                    "word_count": (word_count * overlap_seconds) / duration_seconds if duration_seconds > 0 else word_count,
                    "speaking_seconds": overlap_seconds,
                    "segment_count": 1,
                }
            )

    timeline_df = pd.DataFrame(timeline_rows)
    if not timeline_df.empty:
        timeline_df = (
            timeline_df.groupby("minute_bucket", as_index=False)
            .agg(
                word_count=("word_count", "sum"),
                speaking_seconds=("speaking_seconds", "sum"),
                segment_count=("segment_count", "sum"),
            )
        )
        timeline_df["word_count"] = timeline_df["word_count"].round(1)
        timeline_df["minute_label"] = timeline_df["minute_bucket"].apply(lambda value: format_seconds_label(value * 60))
    else:
        timeline_df = pd.DataFrame(columns=["minute_bucket", "word_count", "speaking_seconds", "segment_count", "minute_label"])

    timeline_df["words_per_minute"] = timeline_df.apply(
        lambda row: round((row["word_count"] / row["speaking_seconds"]) * 60, 1)
        if pd.notna(row["speaking_seconds"]) and row["speaking_seconds"] and row["speaking_seconds"] > 0
        else 0.0,
        axis=1,
    )

    pace_df = ordered_df.copy()
    pace_df["time_seconds"] = pace_df["start_seconds"]
    pace_df["time_label"] = pace_df["time_seconds"].apply(format_seconds_label)
    pace_df["segment_wpm"] = pace_df["words_per_second"].apply(
        lambda value: round(float(value) * 60, 1) if pd.notna(value) else 0.0
    )

    silence_rows: List[Dict[str, Any]] = []
    pause_threshold_seconds = 0.75
    transcript_duration_seconds = _coerce_seconds(transcript.get("duration_seconds"))
    first_start = ordered_df["start_seconds"].dropna().min() if "start_seconds" in ordered_df.columns else None
    last_end = ordered_df["end_seconds"].dropna().max() if "end_seconds" in ordered_df.columns else None

    if first_start is not None and not pd.isna(first_start) and float(first_start) >= pause_threshold_seconds:
        silence_rows.append(
            {
                "silence_start_seconds": 0.0,
                "silence_end_seconds": float(first_start),
                "silence_start_label": format_seconds_label(0.0),
                "silence_end_label": format_seconds_label(float(first_start)),
                "gap_seconds": round(float(first_start), 2),
            }
        )

    for idx in range(1, len(ordered_df.index)):
        previous_end = ordered_df.loc[idx - 1, "end_seconds"]
        current_start = ordered_df.loc[idx, "start_seconds"]
        if pd.isna(previous_end) or pd.isna(current_start):
            continue
        gap_seconds = float(current_start) - float(previous_end)
        if gap_seconds >= pause_threshold_seconds:
            silence_rows.append(
                {
                    "silence_start_seconds": float(previous_end),
                    "silence_end_seconds": float(current_start),
                    "silence_start_label": format_seconds_label(float(previous_end)),
                    "silence_end_label": format_seconds_label(float(current_start)),
                    "gap_seconds": round(gap_seconds, 2),
                }
            )
    if (
        transcript_duration_seconds is not None
        and last_end is not None
        and not pd.isna(last_end)
        and float(transcript_duration_seconds) - float(last_end) >= pause_threshold_seconds
    ):
        silence_rows.append(
            {
                "silence_start_seconds": float(last_end),
                "silence_end_seconds": float(transcript_duration_seconds),
                "silence_start_label": format_seconds_label(float(last_end)),
                "silence_end_label": format_seconds_label(float(transcript_duration_seconds)),
                "gap_seconds": round(float(transcript_duration_seconds) - float(last_end), 2),
            }
        )
    silence_df = pd.DataFrame(silence_rows)

    segment_mix_df = ordered_df.copy()
    segment_mix_df["segment_style"] = segment_mix_df["duration_seconds"].apply(
        lambda value: "Quick hits" if pd.notna(value) and float(value) < 5
        else "Steady beats" if pd.notna(value) and float(value) < 10
        else "Long stretches"
    )
    segment_mix_df = (
        segment_mix_df.groupby("segment_style", as_index=False)
        .agg(
            segments=("text", "size"),
            words=("word_count", "sum"),
            speaking_seconds=("duration_seconds", "sum"),
        )
    )
    segment_style_order = ["Quick hits", "Steady beats", "Long stretches"]
    if not segment_mix_df.empty:
        segment_mix_df["segment_style"] = pd.Categorical(
            segment_mix_df["segment_style"],
            categories=segment_style_order,
            ordered=True,
        )
        segment_mix_df = segment_mix_df.sort_values("segment_style").reset_index(drop=True)

    total_words = int(ordered_df["word_count"].sum())
    if not segment_mix_df.empty:
        segment_mix_df["word_share_pct"] = segment_mix_df["words"].apply(
            lambda value: round((float(value) / total_words) * 100, 1) if total_words > 0 else 0.0
        )
        segment_mix_df["speaking_seconds"] = segment_mix_df["speaking_seconds"].fillna(0.0)
        segment_mix_df["speaking_time_label"] = segment_mix_df["speaking_seconds"].apply(format_seconds_label)

    terms_df = extract_meaningful_terms_from_series(ordered_df["text"], top_n=10)

    duration_values = ordered_df["duration_seconds"].dropna()
    total_speaking_seconds = float(duration_values.sum()) if not duration_values.empty else 0.0
    full_span_seconds = 0.0
    valid_starts = ordered_df["start_seconds"].dropna()
    valid_ends = ordered_df["end_seconds"].dropna()
    if not valid_starts.empty and not valid_ends.empty:
        full_span_seconds = max(float(valid_ends.max()) - float(valid_starts.min()), 0.0)

    summary = {
        "total_segments": int(len(ordered_df.index)),
        "total_words": total_words,
        "avg_words_per_minute": round((total_words / total_speaking_seconds) * 60, 1) if total_speaking_seconds > 0 else 0.0,
        "total_speaking_seconds": round(total_speaking_seconds, 2),
        "full_span_seconds": round(full_span_seconds, 2),
        "silence_count": int(len(silence_df.index)),
        "total_silence_seconds": round(float(silence_df["gap_seconds"].sum()), 2) if not silence_df.empty else 0.0,
        "longest_silence_seconds": round(float(silence_df["gap_seconds"].max()), 2) if not silence_df.empty else 0.0,
        "top_term": terms_df.iloc[0]["term"] if not terms_df.empty else None,
        "dominant_segment_style": segment_mix_df.iloc[0]["segment_style"] if not segment_mix_df.empty else None,
    }

    return {
        "segments_df": ordered_df,
        "timeline_df": timeline_df,
        "pace_df": pace_df,
        "silence_df": silence_df,
        "segment_mix_df": segment_mix_df,
        "terms_df": terms_df,
        "summary": summary,
    }


def _normalize_series_to_progress(series: pd.Series) -> pd.Series:
    timestamps = pd.to_datetime(series, utc=True, errors="coerce")
    valid = timestamps.dropna()
    if valid.empty:
        return pd.Series([None] * len(series), index=series.index, dtype="float64")
    min_ts = valid.min()
    max_ts = valid.max()
    duration_seconds = (max_ts - min_ts).total_seconds()
    if duration_seconds <= 0:
        return pd.Series([50.0 if pd.notna(value) else None for value in timestamps], index=series.index, dtype="float64")
    return timestamps.apply(
        lambda value: round(((value - min_ts).total_seconds() / duration_seconds) * 100, 2) if pd.notna(value) else None
    )


def _format_session_stage_label(start_pct: float, end_pct: float) -> str:
    midpoint = (float(start_pct) + float(end_pct)) / 2
    if midpoint < 15:
        stage = "Opening"
    elif midpoint < 35:
        stage = "Early"
    elif midpoint < 65:
        stage = "Middle"
    elif midpoint < 85:
        stage = "Late"
    else:
        stage = "Closing"
    return f"{stage} ({int(start_pct)}-{int(min(end_pct, 100))}%)"


def build_cross_source_insights(
    chat_df: Optional[pd.DataFrame],
    questions_df: Optional[pd.DataFrame],
    transcript_payload: Optional[Dict[str, Any]],
    bucket_size_pct: int = 10,
) -> Dict[str, Any]:
    if not isinstance(chat_df, pd.DataFrame) or not isinstance(questions_df, pd.DataFrame) or not isinstance(transcript_payload, dict):
        return {"combined_timeline_df": pd.DataFrame(), "reaction_moments_df": pd.DataFrame()}

    transcript_insights = build_transcript_insights(transcript_payload)
    segments_df = transcript_insights.get("segments_df", pd.DataFrame())
    if segments_df.empty:
        return {"combined_timeline_df": pd.DataFrame(), "reaction_moments_df": pd.DataFrame()}

    transcript_duration = float(segments_df["end_seconds"].dropna().max()) if not segments_df["end_seconds"].dropna().empty else 0.0
    if transcript_duration <= 0:
        return {"combined_timeline_df": pd.DataFrame(), "reaction_moments_df": pd.DataFrame()}

    working_segments = segments_df.copy()
    working_segments["progress_pct"] = working_segments["start_seconds"].apply(
        lambda value: round((float(value) / transcript_duration) * 100, 2) if pd.notna(value) and transcript_duration > 0 else None
    )
    working_segments["bucket_start_pct"] = working_segments["progress_pct"].apply(
        lambda value: int((float(value) // bucket_size_pct) * bucket_size_pct) if pd.notna(value) else None
    )

    combined_frames: List[pd.DataFrame] = []

    transcript_bins = (
        working_segments.dropna(subset=["bucket_start_pct"])
        .groupby("bucket_start_pct", as_index=False)
        .agg(
            transcript_words=("word_count", "sum"),
            transcript_segments=("text", "size"),
            transcript_pace=("words_per_second", "mean"),
        )
    )
    if not transcript_bins.empty:
        transcript_bins["transcript_wpm"] = transcript_bins["transcript_pace"].apply(
            lambda value: round(float(value) * 60, 1) if pd.notna(value) else 0.0
        )
        combined_frames.append(transcript_bins[["bucket_start_pct", "transcript_words", "transcript_segments", "transcript_wpm"]])

    if "created_at" in chat_df.columns:
        chat_progress = _normalize_series_to_progress(chat_df["created_at"])
        chat_working = chat_df.copy()
        chat_working["progress_pct"] = chat_progress
        chat_working["bucket_start_pct"] = chat_working["progress_pct"].apply(
            lambda value: int((float(value) // bucket_size_pct) * bucket_size_pct) if pd.notna(value) else None
        )
        chat_bins = (
            chat_working.dropna(subset=["bucket_start_pct"])
            .groupby("bucket_start_pct", as_index=False)
            .agg(chat_messages=("text_content", "size"))
        )
        if not chat_bins.empty:
            combined_frames.append(chat_bins)
    else:
        chat_working = chat_df.copy()

    question_time_col = "asked_at" if "asked_at" in questions_df.columns else "created_at" if "created_at" in questions_df.columns else None
    if question_time_col is not None:
        question_progress = _normalize_series_to_progress(questions_df[question_time_col])
        question_working = questions_df.copy()
        question_working["progress_pct"] = question_progress
        question_working["bucket_start_pct"] = question_working["progress_pct"].apply(
            lambda value: int((float(value) // bucket_size_pct) * bucket_size_pct) if pd.notna(value) else None
        )
        question_bins = (
            question_working.dropna(subset=["bucket_start_pct"])
            .groupby("bucket_start_pct", as_index=False)
            .agg(question_count=("question", "size"))
        )
        if not question_bins.empty:
            combined_frames.append(question_bins)
    else:
        question_working = questions_df.copy()

    if combined_frames:
        combined_timeline_df = combined_frames[0]
        for frame in combined_frames[1:]:
            combined_timeline_df = combined_timeline_df.merge(frame, on="bucket_start_pct", how="outer")
        all_buckets_df = pd.DataFrame({"bucket_start_pct": list(range(0, 100, bucket_size_pct))})
        combined_timeline_df = (
            all_buckets_df.merge(combined_timeline_df, on="bucket_start_pct", how="left")
            .fillna(0)
            .sort_values("bucket_start_pct")
            .reset_index(drop=True)
        )
        combined_timeline_df["bucket_end_pct"] = combined_timeline_df["bucket_start_pct"] + bucket_size_pct
        combined_timeline_df["progress_window"] = combined_timeline_df.apply(
            lambda row: f"{int(row['bucket_start_pct'])}-{int(min(row['bucket_end_pct'], 100))}%",
            axis=1,
        )
        combined_timeline_df["session_stage"] = combined_timeline_df.apply(
            lambda row: _format_session_stage_label(row["bucket_start_pct"], row["bucket_end_pct"]),
            axis=1,
        )
        for column in ("chat_messages", "question_count", "transcript_words", "transcript_segments"):
            if column in combined_timeline_df.columns:
                combined_timeline_df[column] = combined_timeline_df[column].astype(float)
        for column in ("chat_messages", "question_count", "transcript_words", "transcript_segments", "transcript_wpm"):
            if column not in combined_timeline_df.columns:
                combined_timeline_df[column] = 0.0
    else:
        combined_timeline_df = pd.DataFrame()

    reaction_windows: List[Dict[str, Any]] = []
    if not combined_timeline_df.empty:
        grouped_segments = (
            working_segments.dropna(subset=["bucket_start_pct"])
            .groupby("bucket_start_pct", as_index=False)
            .agg(
                start_seconds=("start_seconds", "min"),
                start_label=("start_label", "first"),
                transcript_excerpt=("text", lambda values: " ".join([str(v).strip() for v in values if str(v).strip()])),
                transcript_segments=("text", "size"),
                transcript_words=("word_count", "sum"),
            )
        )
        reaction_moments_df = combined_timeline_df.merge(grouped_segments, on="bucket_start_pct", how="left")
        reaction_moments_df["chat_messages"] = reaction_moments_df["chat_messages"].fillna(0.0)
        reaction_moments_df["question_count"] = reaction_moments_df["question_count"].fillna(0.0)
        reaction_moments_df = reaction_moments_df[
            ((reaction_moments_df["chat_messages"] > 0) | (reaction_moments_df["question_count"] > 0))
            & reaction_moments_df["transcript_excerpt"].fillna("").astype(str).str.strip().ne("")
        ].copy()
        if not reaction_moments_df.empty:
            reaction_moments_df["excerpt"] = reaction_moments_df["transcript_excerpt"].apply(
                lambda value: str(value)[:120] + ("..." if len(str(value)) > 120 else "")
            )
            reaction_moments_df = reaction_moments_df.sort_values(
                by=["question_count", "chat_messages", "bucket_start_pct"],
                ascending=[False, False, True],
            ).head(8).reset_index(drop=True)
    else:
        reaction_moments_df = pd.DataFrame()

    return {"combined_timeline_df": combined_timeline_df, "reaction_moments_df": reaction_moments_df}


def mark_analysis_source_defaults(
    session_state: Any,
    include_chat: bool = False,
    include_questions: bool = False,
    include_transcript: bool = False,
) -> None:
    if include_chat:
        session_state["analysis_include_chat"] = True
        session_state["analysis_include_chat_questions"] = True
    if include_questions:
        session_state["analysis_include_questions"] = True
        session_state["analysis_include_chat_questions"] = True
    if include_transcript:
        session_state["analysis_include_transcript"] = True


def build_derived_stats(
    chat_df: Optional[pd.DataFrame] = None,
    questions_df: Optional[pd.DataFrame] = None,
    transcript_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stats: Dict[str, Any] = {}

    if isinstance(chat_df, pd.DataFrame):
        chat_stats: Dict[str, Any] = {
            "total_messages": int(len(chat_df.index)),
            "unique_authors": int(chat_df["author_id"].nunique()) if "author_id" in chat_df.columns else 0,
        }
        if "created_at" in chat_df.columns:
            series = pd.to_datetime(chat_df["created_at"], utc=True, errors="coerce").dropna()
            if not series.empty:
                chat_stats["time_range_utc"] = {
                    "start": series.min().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "end": series.max().strftime("%Y-%m-%d %H:%M:%S UTC"),
                }
        if "author_id" in chat_df.columns:
            top_authors = chat_df["author_id"].value_counts().head(10)
            chat_stats["top_authors_by_message_count"] = {str(idx): int(val) for idx, val in top_authors.items()}
        if "text_content" in chat_df.columns:
            text_lengths = chat_df["text_content"].fillna("").astype(str).str.len()
            chat_stats["text_length"] = {
                "avg_chars": float(round(text_lengths.mean(), 2)),
                "median_chars": float(round(text_lengths.median(), 2)),
                "max_chars": int(text_lengths.max()) if len(text_lengths.index) else 0,
            }
        stats["chat"] = chat_stats

    if isinstance(questions_df, pd.DataFrame):
        stats["questions"] = build_question_stats(questions_df)
    if isinstance(transcript_payload, dict):
        stats["transcript"] = build_transcript_stats(transcript_payload)
    return stats


def extract_common_terms(df: pd.DataFrame, top_n: int = 12) -> pd.DataFrame:
    if "text_content" not in df.columns:
        return pd.DataFrame(columns=["term", "count"])
    return extract_common_terms_from_series(df["text_content"], top_n=top_n)


def analyze_with_openai(
    api_key: str,
    model: str,
    system_prompt: str,
    output_language: str,
    selected_sources: List[str],
    derived_stats: Dict[str, Any],
    raw_payload: Optional[Dict[str, Any]] = None,
    questions_payload: Optional[Dict[str, Any]] = None,
    transcript_payload: Optional[Dict[str, Any]] = None,
) -> str:
    user_payload = {
        "task": "Analyze this Livestorm session export.",
        "selected_sources": selected_sources,
        "derived_stats": derived_stats,
    }
    if raw_payload is not None:
        user_payload["chat_api_response"] = raw_payload
    if questions_payload is not None:
        user_payload["questions_api_response"] = questions_payload
    if transcript_payload is not None:
        user_payload["transcript_api_response"] = transcript_payload

    resp = requests.post(
        OPENAI_CHAT_COMPLETIONS_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": f"Respond only in {output_language}."},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        },
        timeout=120,
    )
    resp.raise_for_status()
    payload = resp.json()
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return "No analysis returned by model."
    message = choices[0].get("message", {})
    content = message.get("content")
    return content.strip() if isinstance(content, str) else "No analysis text returned by model."
