# Livestorm Session Workspace

Streamlit app to:
- Fetch Livestorm session chat messages (with pagination)
- Fetch Livestorm session questions (with pagination)
- Fetch transcript JSON from the transcript API by session ID via the async job API
- Explore transcript, chat, and questions in dedicated expandable blocks
- Clean and export messages/questions as CSV
- Run OpenAI analysis on `Transcript`, `Chat + Questions`, or all three together

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## OpenAI Analysis

1. Set `OPENAI_API_KEY` in environment/secrets.
2. Set `API_AUTH_KEY` in environment/secrets for transcript fetches.
3. Fetch one or more sources:
   - `Fetch Chat & Questions`
   - `Fetch Transcript`
4. In the Analysis block, choose one of:
   - `Transcript`
   - `Chat & Questions`
   - both together
5. Click `Run analysis`.

The analysis sends:
- `chat_api_response` and `questions_api_response` together when `Chat & Questions` is selected
- `transcript_api_response` when transcript is selected
- `derived_stats` for the selected sources

and renders markdown analysis in the dedicated Analysis block.

## Project Structure

```text
assets/
  icons/
livestorm_app/
  config.py
  renderers.py
  services.py
  state.py
prompts/
app.py
README.md
requirements.txt
```

## UI Layout

- `Transcript Block`: transcript metrics, verbose charts, transcript viewer, JSON export
- `Chat & Questions Block`: engagement charts, chat table, questions table, CSV exports
- `Analysis Block`: source selection, language selection, markdown/PDF export

## Editable Prompt

You can change the analysis instructions without code edits:

- `prompts/analysis_base_prompt.txt`
- `prompts/analysis_chat_prompt.txt`
- `prompts/analysis_questions_prompt.txt`
- `prompts/analysis_transcript_prompt.txt`
- `prompts/analysis_all_sources_prompt.txt`

## Notes

- Provide your Livestorm API key and session ID in the sidebar.
- OpenAI usage is optional; if no OpenAI key is provided, fetch/export still works.
- Transcript fetches require `API_AUTH_KEY`.
- Transcript fetches use `POST /api/transcribe/jobs` plus polling every 3 seconds for up to 15 minutes.
- Questions are never analyzed by themselves; they are always bundled with chat.
- There is no guaranteed free OpenAI model; `gpt-4o-mini` is typically a low-cost option.
