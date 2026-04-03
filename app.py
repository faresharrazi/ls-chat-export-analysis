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


page_config = {"page_title": "Livestorm Chat Export/Analysis", "layout": "wide"}
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

        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"],
        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"] p,
        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"] span,
        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"] label,
        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"] li,
        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"] div {
          color: var(--ls-text);
        }

        h1, h2, h3 {
          font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
          color: var(--ls-white);
          letter-spacing: -0.02em;
        }

        [data-testid="stSidebar"] {
          background: linear-gradient(180deg, #12262B 0%, #1A353C 100%);
          border-right: 1px solid rgba(255,255,255,0.12);
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
            Livestorm Chat Export/Analysis
          </h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.title("Livestorm Chat Export/Analysis")

st.write(
    "Fetch chat messages for a Livestorm session, export as CSV, and optionally run a "
    "chat analysis."
)

with st.sidebar:
    st.header("Connection")
    api_key = st.text_input(
        "Livestorm API key",
        value=os.getenv("LS_API_KEY", ""),
        type="password",
        help="Your Livestorm API key",
    )
    session_id = st.text_input("Session ID", help="Livestorm session ID")
    fetch_button = st.button("Fetch chat messages", type="primary")

    st.header("Analysis")
    api_analysis_key = get_runtime_secret("OPENAI_API_KEY", "")
    output_language_label = st.radio(
        "Model output language",
        options=list(OUTPUT_LANGUAGE_MAP.keys()),
        index=0,
        horizontal=True,
        format_func=lambda lang: OUTPUT_LANGUAGE_LABELS.get(lang, lang),
    )
    analyze_button = st.button("Run analysis")


def build_headers(key: str) -> Dict[str, str]:
    return {
        "Authorization": key,
        "accept": "application/vnd.api+json",
    }


def extract_messages(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload, list):
        return payload
    return []


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


def clean_table_headers(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [
        col.replace("attr.", "").replace("rel.", "").replace(".", "_") for col in cleaned.columns
    ]
    return cleaned


def format_unix_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for col in ("created_at", "updated_at"):
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


def load_analysis_prompt(path: Path = ANALYSIS_PROMPT_PATH) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()

    return (
        "You are a data analyst. Analyze the provided Livestorm chat JSON and derived stats. "
        "Return concise markdown with: overall sentiment, key themes, notable moments, participant "
        "engagement signals, and 5 actionable recommendations."
    )


def build_derived_stats(df: pd.DataFrame) -> Dict[str, Any]:
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


def render_visual_dashboard(df: pd.DataFrame) -> None:
    st.subheader("Visual Dashboard")

    total_messages = int(len(df.index))
    unique_authors = int(df["author_id"].nunique()) if "author_id" in df.columns else 0
    avg_chars = (
        float(round(df["text_content"].fillna("").astype(str).str.len().mean(), 1))
        if "text_content" in df.columns
        else 0.0
    )
    top_author_messages = (
        int(df["author_id"].value_counts().max()) if "author_id" in df.columns and total_messages else 0
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Messages", f"{total_messages}")
    col2.metric("Unique Authors", f"{unique_authors}")
    col3.metric("Avg Message Length", f"{avg_chars} chars")
    col4.metric("Top Author Volume", f"{top_author_messages}")

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("**Top Participants**")
        if "author_id" in df.columns:
            top_authors = (
                df["author_id"]
                .value_counts()
                .head(12)
                .rename_axis("author_id")
                .reset_index(name="messages")
            )
            if not top_authors.empty:
                chart = brand_bar_chart(
                    top_authors,
                    x_field="author_id",
                    y_field="messages",
                    x_title="Author ID",
                    y_title="Messages",
                    tooltip_fields=["author_id", "messages"],
                )
                st.plotly_chart(
                    chart,
                    use_container_width=True,
                    config={"displayModeBar": False, "displaylogo": False},
                )
            else:
                st.info("No author data to chart.")
        else:
            st.info("No author data to chart.")

        st.markdown("**Common Terms**")
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
        st.markdown("**Messages Over Time (UTC)**")
        if "created_at" in df.columns:
            ts = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
            timeline = (
                pd.DataFrame({"created_at": ts})
                .dropna()
                .assign(minute=lambda d: d["created_at"].dt.floor("min"))
                .groupby("minute")
                .size()
                .reset_index(name="messages")
            )
            if not timeline.empty:
                chart = brand_line_chart(
                    timeline,
                    x_field="minute",
                    y_field="messages",
                    x_title="Time (UTC)",
                    y_title="Messages",
                    tooltip_fields=["minute", "messages"],
                )
                st.plotly_chart(
                    chart,
                    use_container_width=True,
                    config={"displayModeBar": False, "displaylogo": False},
                )
            else:
                st.info("No valid timestamp data to chart.")
        else:
            st.info("No timestamp data to chart.")

        st.markdown("**Message Length Distribution**")
        if "text_content" in df.columns:
            lengths = df["text_content"].fillna("").astype(str).str.len()
            bins = pd.cut(
                lengths,
                bins=[-1, 20, 50, 100, 200, 500, 10000],
                labels=["0-20", "21-50", "51-100", "101-200", "201-500", "500+"],
            )
            dist = bins.value_counts().sort_index().rename_axis("length_bin").reset_index(name="messages")
            chart = brand_bar_chart(
                dist,
                x_field="length_bin",
                y_field="messages",
                x_title="Length Bucket",
                y_title="Messages",
                tooltip_fields=["length_bin", "messages"],
            )
            st.plotly_chart(
                chart,
                use_container_width=True,
                config={"displayModeBar": False, "displaylogo": False},
            )
        else:
            st.info("No text content to chart.")


def analyze_with_openai(
    api_key: str,
    model: str,
    system_prompt: str,
    output_language: str,
    raw_payload: Dict[str, Any],
    derived_stats: Dict[str, Any],
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

if fetch_button:
    st.session_state["analysis_md"] = ""
    st.session_state["analysis_ran"] = False
    if not api_key or not session_id:
        st.error("Please provide both API key and session ID.")
    else:
        with st.spinner("Fetching messages..."):
            try:
                payload = fetch_chat_messages(api_key, session_id)
            except requests.HTTPError as exc:
                st.error(f"API request failed: {exc}")
                st.stop()
            except requests.RequestException as exc:
                st.error(f"Network error: {exc}")
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
            st.session_state["analysis_md"] = ""
            st.session_state["analysis_ran"] = False

if analyze_button:
    payload = st.session_state.get("chat_payload")
    df = st.session_state.get("chat_df")
    if payload is None or df is None:
        st.warning("No fetched messages found. Click 'Fetch chat messages' first.")
    elif not api_analysis_key:
        st.warning("Analysis skipped: missing API key in environment.")
    else:
        with st.spinner("Running analysis..."):
            prompt_text = load_analysis_prompt()
            derived_stats = build_derived_stats(df)
            try:
                analysis_md = analyze_with_openai(
                    api_key=api_analysis_key,
                    model=DEFAULT_OPENAI_MODEL,
                    system_prompt=prompt_text,
                    output_language=OUTPUT_LANGUAGE_MAP[output_language_label],
                    raw_payload=payload,
                    derived_stats=derived_stats,
                )
            except requests.HTTPError as exc:
                st.error(f"Analysis API error: {exc}")
                analysis_md = ""
            except requests.RequestException as exc:
                st.error(f"Analysis network error: {exc}")
                analysis_md = ""
        st.session_state["analysis_md"] = analysis_md
        st.session_state["analysis_ran"] = True

payload = st.session_state.get("chat_payload")
df = st.session_state.get("chat_df")
analysis_md = st.session_state.get("analysis_md", "")
analysis_ran = st.session_state.get("analysis_ran", False)

if payload is not None and df is not None:
    messages = extract_messages(payload)
    st.caption(
        f"Fetched {len(messages)} messages across {payload.get('pages_fetched', 1)} page(s) "
        f"(page size={payload.get('requested_page_size', DEFAULT_PAGE_SIZE)})."
    )

    render_visual_dashboard(df)

    if analysis_ran and analysis_md:
        st.subheader("Chat Analysis")
        st.markdown(analysis_md)

        analysis_bytes = analysis_md.encode("utf-8")
        analysis_ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        st.download_button(
            label="Download Analysis (Markdown)",
            data=analysis_bytes,
            file_name=f"livestorm-analysis-{session_id}-{analysis_ts}.md",
            mime="text/markdown",
        )

    st.subheader("Chat messages")
    st.dataframe(df, use_container_width=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download CSV",
        data=csv_bytes,
        file_name=f"livestorm-chat-{session_id}-{timestamp}.csv",
        mime="text/csv",
    )

    with st.expander("Raw API response"):
        st.code(json.dumps(payload, indent=2))
