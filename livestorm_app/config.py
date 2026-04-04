import base64
import os
from pathlib import Path

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

API_BASE = "https://api.livestorm.co/v1"
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
TRANSCRIPT_API_URL = "https://ls-video-transcribe.onrender.com/api/transcribe"
TRANSCRIPT_JOBS_API_URL = f"{TRANSCRIPT_API_URL}/jobs"
DEFAULT_PAGE_SIZE = 100
MAX_PAGES = 1000
START_PAGE_NUMBER = 0
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
PROMPTS_DIR = Path("prompts")
ANALYSIS_BASE_PROMPT_PATH = PROMPTS_DIR / "analysis_base_prompt.txt"
ANALYSIS_CHAT_PROMPT_PATH = PROMPTS_DIR / "analysis_chat_prompt.txt"
ANALYSIS_QUESTIONS_PROMPT_PATH = PROMPTS_DIR / "analysis_questions_prompt.txt"
ANALYSIS_TRANSCRIPT_PROMPT_PATH = PROMPTS_DIR / "analysis_transcript_prompt.txt"
ANALYSIS_ALL_SOURCES_PROMPT_PATH = PROMPTS_DIR / "analysis_all_sources_prompt.txt"
ENV_PATH = Path(".env")
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
ICON_PATH = ICONS_DIR / "Icon-Livestorm-Primary.png"
HEADER_ICON_PATH = ICONS_DIR / "Icon-Livestorm-Tertiary-Light.png"
OUTPUT_LANGUAGE_MAP = {
    "English": "English",
    "French": "French",
}
OUTPUT_LANGUAGE_LABELS = {
    "English": "🇬🇧 English",
    "French": "🇫🇷 Français",
}
INPUT_MODE_OPTIONS = ["Session ID", "Event ID"]


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


def get_runtime_secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except StreamlitSecretNotFoundError:
        return os.getenv(name, default)


def configure_page() -> None:
    load_env_file()

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
          --ls-surface-soft: rgba(20, 38, 44, 0.8);
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

        [data-testid="stSidebar"]::after {
          content: "";
          position: absolute;
          top: 0;
          right: -1px;
          width: 1px;
          height: 100%;
          background: linear-gradient(180deg, rgba(255,255,255,0.12), rgba(143,208,222,0.35), rgba(255,255,255,0.12));
          pointer-events: none;
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

        [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"],
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
          background: var(--ls-surface-soft);
          border: 1px solid var(--ls-line);
          border-radius: 16px;
          overflow: hidden;
          margin-bottom: 0.9rem;
        }

        [data-testid="stExpander"] details summary p {
          font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
          font-size: 1rem;
        }

        [data-testid="stMarkdownContainer"] code {
          background: rgba(255,255,255,0.08);
          color: #D9EAF0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    if HEADER_ICON_PATH.exists():
        header_icon_b64 = base64.b64encode(HEADER_ICON_PATH.read_bytes()).decode("ascii")
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:12px; margin:0.2rem 0 0.6rem 0;">
              <img src="data:image/png;base64,{header_icon_b64}" style="width:42px; height:42px; object-fit:contain;" />
              <h1 style="margin:0; color:#FFFFFF; font-family:'Space Grotesk','IBM Plex Sans',sans-serif; letter-spacing:-0.02em;">
                Livestorm Chat, Questions & Transcript Analysis
              </h1>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.title("Livestorm Chat, Questions & Transcript Analysis")
