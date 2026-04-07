# Livestorm Session Workspace

Vue + FastAPI workspace to:
- Fetch Livestorm session overview, chat, questions, and transcript data
- Cache fetched sessions in Postgres by `session_id`
- Explore each major area in its own routed frontend view
- Run overall analysis, deep analysis, smart recap, and content repurposing workflows
- Persist speaker labels alongside the cached session

## Quickstart

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Backend API

The FastAPI backend exposes JSON endpoints for:
- loading past event sessions
- fetching and caching a session workspace
- saving speaker labels
- running overall analysis
- running deep analysis
- generating smart recap output
- generating content repurposing bundles

## Project Structure

```text
assets/
  icons/
frontend/
  src/
livestorm_app/
  api_logic.py
  config.py
  db.py
  services.py
  session_overview.py
prompts/
app.py
README.md
requirements.txt
```

## Frontend Routes

- `/session-overview`
- `/transcript`
- `/chat-questions`
- `/analysis`
- `/smart-recap`
- `/content-repurposing`

## Editable Prompt

You can change the analysis instructions without code edits:

- `prompts/analysis_base_prompt.txt`
- `prompts/analysis_chat_prompt.txt`
- `prompts/analysis_questions_prompt.txt`
- `prompts/analysis_transcript_prompt.txt`
- `prompts/analysis_all_sources_prompt.txt`
- `prompts/analysis_deep_prompt.txt`
- `prompts/content_repurpose_summary_prompt.txt`
- `prompts/content_repurpose_email_prompt.txt`
- `prompts/content_repurpose_blog_prompt.txt`
- `prompts/content_repurpose_social_media_prompt.txt`

## Notes

- Set `OPENAI_API_KEY` for analysis, recap, and content generation.
- Set `API_AUTH_KEY` for transcript fetching.
- The frontend currently expects the backend at the same origin or proxied via Vite.
- Node.js was not available in the current coding environment, so the Vue app was scaffolded but not built locally here.
