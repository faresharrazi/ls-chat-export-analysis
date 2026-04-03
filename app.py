import json
import os
import re
import base64
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

API_BASE = "https://api.livestorm.co/v1"
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_PAGE_SIZE = 100
MAX_PAGES = 1000
START_PAGE_NUMBER = 0
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
ANALYSIS_PROMPT_PATH = Path("prompts/openai_chat_analysis_prompt.txt")
ENV_PATH = Path(".env")
ICON_PATH = Path("/Users/fares/Code/chat-analysis/Icon-Livestorm-Primary.png")
HEADER_ICON_PATH = Path("/Users/fares/Code/chat-analysis/Icon-Livestorm-Tertiary-Light.png")
OUTPUT_LANGUAGE_MAP = {
    "English": "English",
    "French": "French",
}
OUTPUT_LANGUAGE_LABELS = {
    "English": "🇬🇧 English",
    "French": "🇫🇷 Français",
}
INPUT_MODE_OPTIONS = ["Session ID", "Event ID"]
SESSION_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
EVENT_ID_PATTERN = SESSION_ID_PATTERN


def load_env_file(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()


def get_runtime_secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except StreamlitSecretNotFoundError:
        return os.getenv(name, default)


page_config = {"page_title": "Livestorm Chat & Questions Export/Analysis", "layout": "wide"}
if ICON_PATH.exists():
    page_config["page_icon"] = str(ICON_PATH)
st.set_page_config(**page_config)


def apply_brand_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

        :root {
          --ls-ink: #12262B;
          --ls-white: #FFFFFF;
          --ls-mist: #1B2C31;
          --ls-line: #2A4047;
          --ls-bg: #0F1D21;
          --ls-surface: #14262C;
          --ls-text: #EAF1F3;
          --ls-muted: #AFC1C7;
        }

        html, body, [class*="css"] {
          font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
        }

        [data-testid="stAppViewContainer"] {
          background:
            radial-gradient(80rem 35rem at 120% -20%, #1D353C 0%, rgba(29,53,60,0) 65%),
            radial-gradient(60rem 30rem at -20% 110%, #1A3036 0%, rgba(26,48,54,0) 70%),
            var(--ls-bg);
        }

        /* Hide Streamlit top chrome (toolbar/menu/decoration) */
        #MainMenu,
        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"] {
          display: none !important;
        }

        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"],
        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"] p,
        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"] span,
        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"] label,
        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"] li,
        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"] div {
          color: var(--ls-text);
        }

        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"] {
          padding-top: 0rem;
        }

        h1, h2, h3 {
          font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
          color: var(--ls-white);
          letter-spacing: -0.02em;
        }

        [data-testid="stSidebar"] {
          background: linear-gradient(180deg, #12262B 0%, #1A353C 100%);
          border-right: 1px solid rgba(255,255,255,0.12);
          min-width: 440px !important;
          max-width: 440px !important;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stMarkdown {
          color: #FFFFFF !important;
        }

        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {
          background: #FFFFFF !important;
          color: #12262B !important;
          border-radius: 10px !important;
          border: 1px solid #D8E4E7 !important;
        }

        [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
          color: #12262B !important;
        }

        [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] span,
        [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] div,
        [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] input {
          color: #12262B !important;
        }

        [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] svg {
          fill: #12262B !important;
          color: #12262B !important;
          opacity: 1 !important;
        }

        [data-testid="stSidebar"] input::placeholder {
          color: #6A7E84 !important;
        }

        [data-testid="stSidebar"] .stTextInput [data-testid="stBaseButton-secondary"] {
          width: 1.65rem !important;
          min-width: 1.65rem !important;
          height: 1.65rem !important;
          padding: 0 !important;
          margin-right: 0.2rem !important;
          opacity: 0.75;
        }

        [data-testid="stSidebar"] .stTextInput [data-testid="stBaseButton-secondary"]:hover {
          opacity: 1;
        }

        .stButton > button {
          background: #12262B;
          color: #FFFFFF;
          border: 1px solid #2D4B54;
          border-radius: 10px;
          font-weight: 600;
        }

        .stButton > button:hover {
          border-color: #0D1D21;
          background: #0D1D21;
          color: #FFFFFF;
        }

        [data-testid="stMetric"] {
          background: rgba(20, 38, 44, 0.92);
          border: 1px solid var(--ls-line);
          border-radius: 14px;
          padding: 0.55rem 0.75rem;
          box-shadow: 0 10px 24px rgba(0, 0, 0, 0.28);
        }

        [data-testid="stDataFrame"] {
          border: 1px solid var(--ls-line);
          border-radius: 12px;
          overflow: hidden;
          background: var(--ls-surface);
        }

        [data-testid="stDataFrame"] * {
          color: var(--ls-text) !important;
        }

        [data-testid="stExpander"] {
          background: rgba(20, 38, 44, 0.8);
          border: 1px solid var(--ls-line);
          border-radius: 10px;
        }

        [data-testid="stMarkdownContainer"] code {
          background: rgba(255,255,255,0.08);
          color: #D9EAF0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


apply_brand_styles()

if HEADER_ICON_PATH.exists():
    header_icon_b64 = base64.b64encode(HEADER_ICON_PATH.read_bytes()).decode("ascii")
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:12px; margin:0.2rem 0 0.6rem 0;">
          <img src="data:image/png;base64,{header_icon_b64}" style="width:42px; height:42px; object-fit:contain;" />
          <h1 style="margin:0; color:#FFFFFF; font-family:'Space Grotesk','IBM Plex Sans',sans-serif; letter-spacing:-0.02em;">
            Livestorm Chat & Questions Export/Analysis
          </h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.title("Livestorm Chat & Questions Export/Analysis")

has_fetched_content = st.session_state.get("chat_df") is not None

if "show_controls_panel" not in st.session_state:
    st.session_state["show_controls_panel"] = True
if "analysis_in_progress" not in st.session_state:
    st.session_state["analysis_in_progress"] = False

show_controls_panel = st.session_state.get("show_controls_panel", True)
controls_col = None
if show_controls_panel:
    controls_col, main_col = st.columns([0.95, 3.05], gap="large")
else:
    show_col, main_col = st.columns([0.35, 3.65], gap="large")
    with show_col:
        if st.button("Show Panel", key="show_controls_panel_btn"):
            st.session_state["show_controls_panel"] = True
            st.rerun()

analyze_button = False
output_language_label = "English"
api_key = st.session_state.get("api_key_input", os.getenv("LS_API_KEY", ""))
has_api_key = bool(str(api_key).strip())
input_mode = st.session_state.get("input_mode", INPUT_MODE_OPTIONS[0])
session_id = st.session_state.get("session_id_input", "")
event_id = st.session_state.get("event_id_input", "")
session_id_valid = bool(SESSION_ID_PATTERN.match(str(session_id).strip()))
event_id_valid = bool(EVENT_ID_PATTERN.match(str(event_id).strip()))
load_event_sessions_button = False
selected_session_from_event = st.session_state.get("selected_event_session_id")
fetch_button = False
api_analysis_key = get_runtime_secret("OPENAI_API_KEY", "")

if controls_col is not None:
    with controls_col:
        if st.button("Hide Panel", key="hide_controls_panel_btn"):
            st.session_state["show_controls_panel"] = False
            st.rerun()
        st.subheader("Connection")
        api_key = st.text_input(
            "Livestorm API key",
            value=os.getenv("LS_API_KEY", ""),
            type="password",
            help="Your Livestorm API key",
            key="api_key_input",
        )
        has_api_key = bool(api_key.strip())
        input_mode = st.radio(
            "Input type",
            options=INPUT_MODE_OPTIONS,
            index=0 if st.session_state.get("input_mode", INPUT_MODE_OPTIONS[0]) == INPUT_MODE_OPTIONS[0] else 1,
            horizontal=True,
            disabled=not has_api_key,
            key="input_mode",
        )

        session_id = ""
        event_id = ""
        session_id_valid = False
        event_id_valid = False
        load_event_sessions_button = False
        selected_session_from_event = None

        if input_mode == "Session ID":
            session_id = st.text_input(
                "Session ID",
                help="Livestorm session ID",
                disabled=not has_api_key,
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
            load_event_sessions_button = st.button(
                "Load Past Sessions",
                disabled=not (has_api_key and event_id_valid),
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

        active_session_id = session_id.strip()
        if input_mode == "Event ID":
            active_session_id = selected_session_from_event or ""

        fetch_disabled = not has_api_key
        if input_mode == "Session ID":
            fetch_disabled = fetch_disabled or (not session_id_valid)
        else:
            fetch_disabled = fetch_disabled or (not bool(active_session_id))

        fetch_button = st.button(
            "Fetch Chat & Questions",
            type="primary",
            disabled=fetch_disabled,
        )
        if not has_api_key:
            st.caption("Add a Livestorm API key to enable ID inputs.")
        elif input_mode == "Session ID" and session_id and not session_id_valid:
            st.caption("Session ID must be a valid UUID format.")
        elif input_mode == "Event ID" and event_id and not event_id_valid:
            st.caption("Event ID must be a valid UUID format.")
        elif input_mode == "Event ID" and event_id_valid and not active_session_id:
            st.caption("Load past sessions, then select one session before fetching.")

        api_analysis_key = get_runtime_secret("OPENAI_API_KEY", "")
        if has_fetched_content:
            st.subheader("Analysis")
            output_language_label = st.radio(
                "Model output language",
                options=list(OUTPUT_LANGUAGE_MAP.keys()),
                index=0,
                horizontal=True,
                format_func=lambda lang: OUTPUT_LANGUAGE_LABELS.get(lang, lang),
                key="analysis_language",
            )
            analysis_btn_placeholder = st.empty()
            if st.session_state.get("analysis_in_progress", False):
                analysis_btn_placeholder.button("Running analysis...", disabled=True, key="analysis_running_btn")
                analyze_button = False
            else:
                analyze_button = analysis_btn_placeholder.button("Run analysis", key="analysis_run_btn")

if input_mode == "Session ID":
    active_session_id = str(session_id).strip()
else:
    active_session_id = selected_session_from_event or ""

with main_col:
    if not has_fetched_content:
        st.markdown(
            "1. Add your Livestorm API key "
            "([How to access the Public API panel](https://support.livestorm.co/article/321-access-public-api-panel))\n"
            "2. Choose whether you want to fetch by Session ID or Event ID.\n"
            "3. Add the Session ID "
            "([How to copy the Session ID](https://support.livestorm.co/article/247-id#copy-the-session-id)) "
            "or add the Event ID "
            "([How to copy the Event ID](https://support.livestorm.co/article/247-id#copy-the-event-id))."
        )


def build_headers(key: str) -> Dict[str, str]:
    return {
        "Authorization": key,
        "accept": "application/vnd.api+json",
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
        return (
            f"{resource_label} rate limited (HTTP 429). "
            "Please wait a few seconds and try again."
        )
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
        session_id = row["id"]
        attrs = row["attributes"]
        name = str(attrs.get("name") or "").strip()
        attendees = attrs.get("attendees_count", "n/a")
        started_label = _format_unix_label(attrs.get("started_at") or attrs.get("estimated_started_at"))
        title = name if name else "Untitled session"
        label = f"{started_label} - {title} ({attendees} attendees)"
        options.append({"id": session_id, "label": label})

    return options


def extract_included_people(payload: Dict[str, Any]) -> Dict[str, str]:
    people_lookup: Dict[str, str] = {}
    if not isinstance(payload, dict):
        return people_lookup

    included = payload.get("included")
    if not isinstance(included, list):
        return people_lookup

    for item in included:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "people":
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
        full_name = f"{first_name} {last_name}".strip()
        people_lookup[person_id] = full_name or person_id

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

    if next_page is None:
        return None
    if isinstance(next_page, bool):
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
    # Flatten JSON:API-ish shapes into a single row
    base = {}
    if not isinstance(msg, dict):
        return base

    base.update({"id": msg.get("id"), "type": msg.get("type")})

    attrs = msg.get("attributes")
    if isinstance(attrs, dict):
        for k, v in attrs.items():
            base[k] = v

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
        for k, v in attrs.items():
            base[k] = v

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
    columns_to_remove = ["type", "from_guest_speaker", "from_team_member", "html_content"]
    existing = [col for col in columns_to_remove if col in cleaned.columns]
    if existing:
        cleaned = cleaned.drop(columns=existing)
    return cleaned


def clean_questions_table(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    columns_to_remove = [
        "type",
        "session_id",
        "event_id",
        "question_author_id",
        "response_author_id",
        "responded_orally",
        "updated_at",
    ]
    existing = [col for col in columns_to_remove if col in cleaned.columns]
    if existing:
        cleaned = cleaned.drop(columns=existing)

    if "created_at" in cleaned.columns:
        cleaned = cleaned.rename(columns={"created_at": "asked_at"})

    preferred_order = [
        "id",
        "question",
        "response",
        "asked_by",
        "answered_by",
        "asked_at",
        "responded_at",
    ]
    cols = [c for c in preferred_order if c in cleaned.columns] + [
        c for c in cleaned.columns if c not in preferred_order
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

        params = {
            "page[number]": page_number,
            "page[size]": page_size,
        }
        resp = requests.get(url, headers=headers, params=params, timeout=30)
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

        # Fallback when pagination metadata is absent:
        # if we got fewer items than page size, we reached the end.
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

        params = {
            "page[number]": page_number,
            "page[size]": page_size,
            "include": "asker,responder",
        }
        resp = requests.get(url, headers=headers, params=params, timeout=30)
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
                if not included_id or not included_type:
                    continue
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

        params = {
            "page[number]": page_number,
            "page[size]": page_size,
            "filter[status]": "past",
        }
        resp = requests.get(url, headers=headers, params=params, timeout=30)
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


def load_analysis_prompt(path: Path = ANALYSIS_PROMPT_PATH) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()

    return (
        "You are a data analyst. Analyze the provided Livestorm chat JSON and derived stats. "
        "Return concise markdown with: overall sentiment, key themes, notable moments, participant "
        "engagement signals, and 5 actionable recommendations."
    )


def build_question_stats(questions_df: pd.DataFrame) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "total_questions": int(len(questions_df.index)),
    }

    asker_col = None
    if "asked_by" in questions_df.columns:
        asker_col = "asked_by"
    elif "question_author_id" in questions_df.columns:
        asker_col = "question_author_id"

    if asker_col is not None:
        stats["unique_askers"] = int(questions_df[asker_col].nunique())
        top_askers = questions_df[asker_col].value_counts().head(10)
        stats["top_askers_by_question_count"] = {str(idx): int(val) for idx, val in top_askers.items()}

    if "response" in questions_df.columns:
        has_response = questions_df["response"].fillna("").astype(str).str.strip() != ""
        stats["answered_questions"] = int(has_response.sum())
        stats["unanswered_questions"] = int((~has_response).sum())

    return stats


def build_derived_stats(df: pd.DataFrame, questions_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "total_messages": int(len(df.index)),
        "unique_authors": int(df["author_id"].nunique()) if "author_id" in df.columns else 0,
    }

    if "created_at" in df.columns:
        series = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
        valid = series.dropna()
        if not valid.empty:
            stats["time_range_utc"] = {
                "start": valid.min().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "end": valid.max().strftime("%Y-%m-%d %H:%M:%S UTC"),
            }

    if "author_id" in df.columns:
        top_authors = df["author_id"].value_counts().head(10)
        stats["top_authors_by_message_count"] = {
            str(idx): int(val) for idx, val in top_authors.items()
        }

    if "text_content" in df.columns:
        text_lengths = df["text_content"].fillna("").astype(str).str.len()
        stats["text_length"] = {
            "avg_chars": float(round(text_lengths.mean(), 2)),
            "median_chars": float(round(text_lengths.median(), 2)),
            "max_chars": int(text_lengths.max()) if len(text_lengths.index) else 0,
        }

    if questions_df is not None:
        stats["questions"] = build_question_stats(questions_df)

    return stats


def extract_common_terms(df: pd.DataFrame, top_n: int = 12) -> pd.DataFrame:
    if "text_content" not in df.columns:
        return pd.DataFrame(columns=["term", "count"])

    stopwords = {
        "the",
        "and",
        "for",
        "that",
        "with",
        "this",
        "you",
        "are",
        "was",
        "have",
        "from",
        "your",
        "all",
        "but",
        "not",
        "can",
        "just",
        "hello",
        "bonjour",
        "merci",
        "pour",
        "avec",
        "dans",
        "tout",
        "tous",
        "les",
        "des",
        "une",
        "est",
        "que",
        "qui",
        "sur",
        "pas",
        "oui",
    }

    text = " ".join(df["text_content"].fillna("").astype(str).tolist()).lower()
    terms = re.findall(r"\b[\w']{3,}\b", text)
    filtered = [t for t in terms if t not in stopwords and not t.isdigit()]
    counts = Counter(filtered).most_common(top_n)
    if not counts:
        return pd.DataFrame(columns=["term", "count"])
    return pd.DataFrame(counts, columns=["term", "count"])


def brand_bar_chart(
    data: pd.DataFrame, x_field: str, y_field: str, x_title: str, y_title: str, tooltip_fields: List[str]
):
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


def render_visual_dashboard(df: pd.DataFrame, questions_df: Optional[pd.DataFrame] = None) -> None:
    st.subheader("Session Insights")

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
        answered_mask = questions_df["response"].fillna("").astype(str).str.strip() != ""
        answered_count = int(answered_mask.sum())
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
            top_chatters = (
                df["author_id"]
                .value_counts()
                .head(10)
                .rename_axis("person_id")
                .reset_index(name="count")
            )
            top_chatters["kind"] = "Messages"
        if isinstance(questions_df, pd.DataFrame) and "asked_by" in questions_df.columns:
            top_askers = (
                questions_df["asked_by"]
                .value_counts()
                .head(10)
                .rename_axis("person_id")
                .reset_index(name="count")
            )
            top_askers["kind"] = "Questions"
        elif isinstance(questions_df, pd.DataFrame) and "question_author_id" in questions_df.columns:
            top_askers = (
                questions_df["question_author_id"]
                .value_counts()
                .head(10)
                .rename_axis("person_id")
                .reset_index(name="count")
            )
            top_askers["kind"] = "Questions"

        combined_top = pd.concat([top_chatters, top_askers], ignore_index=True)
        if not combined_top.empty:
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
            st.plotly_chart(
                top_chart,
                use_container_width=True,
                config={"displayModeBar": False, "displaylogo": False},
            )
        else:
            st.info("Not enough contributor data to chart.")

        st.markdown("**Common Terms (Chat Messages)**")
        terms_df = extract_common_terms(df)
        if not terms_df.empty:
            chart = brand_bar_chart(
                terms_df,
                x_field="term",
                y_field="count",
                x_title="Term",
                y_title="Count",
                tooltip_fields=["term", "count"],
            )
            st.plotly_chart(
                chart,
                use_container_width=True,
                config={"displayModeBar": False, "displaylogo": False},
            )
        else:
            st.info("Not enough textual data for term analysis.")

    with chart_col2:
        st.markdown("**Activity Over Time (UTC)**")
        timeline_frames: List[pd.DataFrame] = []
        if "created_at" in df.columns:
            msg_ts = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
            msg_timeline = (
                pd.DataFrame({"created_at": msg_ts})
                .dropna()
                .assign(minute=lambda d: d["created_at"].dt.floor("min"))
                .groupby("minute")
                .size()
                .reset_index(name="count")
            )
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
            q_timeline = (
                pd.DataFrame({"created_at": q_ts})
                .dropna()
                .assign(minute=lambda d: d["created_at"].dt.floor("min"))
                .groupby("minute")
                .size()
                .reset_index(name="count")
            )
            if not q_timeline.empty:
                q_timeline["kind"] = "Questions"
                timeline_frames.append(q_timeline)

        if timeline_frames:
            timeline = pd.concat(timeline_frames, ignore_index=True)
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
            st.plotly_chart(
                timeline_chart,
                use_container_width=True,
                config={"displayModeBar": False, "displaylogo": False},
            )
        else:
            st.info("No valid timestamp data to chart.")

        st.markdown("**Question Response Coverage**")
        if total_questions > 0:
            status_df = pd.DataFrame(
                {"status": ["Answered", "Unanswered"], "count": [answered_count, unanswered_count]}
            )
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
            st.plotly_chart(
                status_chart,
                use_container_width=True,
                config={"displayModeBar": False, "displaylogo": False},
            )
        else:
            st.info("No questions fetched yet.")


def analyze_with_openai(
    api_key: str,
    model: str,
    system_prompt: str,
    output_language: str,
    raw_payload: Dict[str, Any],
    derived_stats: Dict[str, Any],
    questions_payload: Optional[Dict[str, Any]] = None,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    user_payload = {
        "task": "Analyze this Livestorm chat export.",
        "derived_stats": derived_stats,
        "raw_api_response": raw_payload,
    }
    if questions_payload is not None:
        user_payload["questions_api_response"] = questions_payload

    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"Respond only in {output_language}."},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }

    resp = requests.post(OPENAI_CHAT_COMPLETIONS_URL, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    payload = resp.json()

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return "No analysis returned by model."

    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()

    return "No analysis text returned by model."


if "chat_payload" not in st.session_state:
    st.session_state["chat_payload"] = None
if "chat_df" not in st.session_state:
    st.session_state["chat_df"] = None
if "analysis_md" not in st.session_state:
    st.session_state["analysis_md"] = ""
if "analysis_ran" not in st.session_state:
    st.session_state["analysis_ran"] = False
if "questions_payload" not in st.session_state:
    st.session_state["questions_payload"] = None
if "questions_df" not in st.session_state:
    st.session_state["questions_df"] = None
if "event_sessions" not in st.session_state:
    st.session_state["event_sessions"] = []
if "event_sessions_for" not in st.session_state:
    st.session_state["event_sessions_for"] = ""
if "current_session_id" not in st.session_state:
    st.session_state["current_session_id"] = ""
if "session_id_input" not in st.session_state:
    st.session_state["session_id_input"] = ""
if "event_id_input" not in st.session_state:
    st.session_state["event_id_input"] = ""
if "selected_event_session_id" not in st.session_state:
    st.session_state["selected_event_session_id"] = None

if load_event_sessions_button:
    st.session_state["event_sessions"] = []
    st.session_state["event_sessions_for"] = ""
    if not api_key or not event_id:
        st.error("Please provide both API key and event ID.")
    else:
        with st.spinner("Loading past sessions..."):
            try:
                event_sessions_payload = fetch_event_past_sessions(api_key, event_id.strip())
            except requests.HTTPError as exc:
                st.error(format_livestorm_http_error(exc, "Event sessions"))
                event_sessions_payload = None
            except requests.RequestException as exc:
                st.error(f"Event sessions network error: {exc}")
                event_sessions_payload = None

        if isinstance(event_sessions_payload, dict):
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
            st.rerun()

if fetch_button:
    fetched_successfully = False
    st.session_state["analysis_md"] = ""
    st.session_state["analysis_ran"] = False
    st.session_state["questions_payload"] = None
    st.session_state["questions_df"] = None
    if not api_key or not active_session_id:
        st.error("Please provide API key and a valid session selection.")
    else:
        with st.spinner("Fetching chat messages and questions..."):
            try:
                payload = fetch_chat_messages(api_key, active_session_id)
            except requests.HTTPError as exc:
                st.error(format_livestorm_http_error(exc, "Chat"))
                st.stop()
            except requests.RequestException as exc:
                st.error(f"Chat network error: {exc}")
                st.stop()

        messages = extract_messages(payload)
        if not messages:
            st.warning("No messages found or unexpected response format.")
            st.json(payload)
        else:
            rows = [flatten_message(m) for m in messages]
            df = pd.DataFrame(rows)
            df = clean_table_headers(df)
            df = format_unix_datetime_columns(df)
            df = drop_unwanted_columns(df)
            st.session_state["chat_payload"] = payload
            st.session_state["chat_df"] = df
            st.session_state["current_session_id"] = active_session_id
            st.session_state["analysis_md"] = ""
            st.session_state["analysis_ran"] = False
            fetched_successfully = True

        try:
            raw_questions_payload = fetch_session_questions(api_key, active_session_id)
        except requests.HTTPError as exc:
            st.warning(format_livestorm_http_error(exc, "Questions"))
            raw_questions_payload = None
        except requests.RequestException as exc:
            st.warning(f"Questions network error: {exc}")
            raw_questions_payload = None

        if isinstance(raw_questions_payload, dict):
            raw_questions = extract_questions(raw_questions_payload)
            if not raw_questions:
                st.session_state["questions_payload"] = raw_questions_payload
                st.session_state["questions_df"] = pd.DataFrame()
            else:
                people_lookup = extract_included_people(raw_questions_payload)
                question_rows = [flatten_question(q, people_lookup) for q in raw_questions]
                qdf = pd.DataFrame(question_rows)
                qdf = clean_table_headers(qdf)
                qdf = format_unix_datetime_columns(qdf)
                qdf = clean_questions_table(qdf)
                st.session_state["questions_payload"] = raw_questions_payload
                st.session_state["questions_df"] = qdf

        if fetched_successfully:
            st.rerun()

if analyze_button:
    st.session_state["analysis_in_progress"] = True
    st.rerun()

if st.session_state.get("analysis_in_progress", False):
    payload = st.session_state.get("chat_payload")
    df = st.session_state.get("chat_df")
    questions_payload = st.session_state.get("questions_payload")
    questions_df = st.session_state.get("questions_df")
    selected_output_language = st.session_state.get("analysis_language", output_language_label)
    if payload is None or df is None:
        st.warning("No fetched messages found. Click 'Fetch Chat & Questions' first.")
        st.session_state["analysis_in_progress"] = False
        st.rerun()
    elif not api_analysis_key:
        st.warning("Analysis skipped: missing API key in environment.")
        st.session_state["analysis_in_progress"] = False
        st.rerun()
    else:
        prompt_text = load_analysis_prompt()
        derived_stats = build_derived_stats(df, questions_df=questions_df)
        try:
            analysis_md = analyze_with_openai(
                api_key=api_analysis_key,
                model=DEFAULT_OPENAI_MODEL,
                system_prompt=prompt_text,
                output_language=OUTPUT_LANGUAGE_MAP[selected_output_language],
                raw_payload=payload,
                derived_stats=derived_stats,
                questions_payload=questions_payload,
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

payload = st.session_state.get("chat_payload")
df = st.session_state.get("chat_df")
analysis_md = st.session_state.get("analysis_md", "")
analysis_ran = st.session_state.get("analysis_ran", False)
questions_payload = st.session_state.get("questions_payload")
questions_df = st.session_state.get("questions_df")
current_session_id = st.session_state.get("current_session_id") or active_session_id

with main_col:
    if payload is not None and df is not None:
        render_visual_dashboard(df, questions_df=questions_df)

        if analysis_ran and analysis_md:
            st.subheader("Chat Analysis")
            st.markdown(analysis_md)

            analysis_bytes = analysis_md.encode("utf-8")
            analysis_ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            st.download_button(
                label="Download Analysis (Markdown)",
                data=analysis_bytes,
                file_name=f"livestorm-analysis-{current_session_id}-{analysis_ts}.md",
                mime="text/markdown",
            )

        st.subheader("Chat messages")
        st.dataframe(df, use_container_width=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        csv_bytes = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download CSV",
            data=csv_bytes,
            file_name=f"livestorm-chat-{current_session_id}-{timestamp}.csv",
            mime="text/csv",
        )

        if isinstance(questions_df, pd.DataFrame) and not questions_df.empty:
            st.subheader("Questions")
            st.dataframe(questions_df, use_container_width=True)
            questions_csv_bytes = questions_df.to_csv(index=False).encode("utf-8")
            questions_timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            st.download_button(
                label="Download Questions CSV",
                data=questions_csv_bytes,
                file_name=f"livestorm-questions-{current_session_id}-{questions_timestamp}.csv",
                mime="text/csv",
            )
        elif isinstance(questions_df, pd.DataFrame) and questions_df.empty:
            st.info(
                "No questions were found for this session. "
                "This can happen when attendees did not submit questions or the session has no Q&A data."
            )
