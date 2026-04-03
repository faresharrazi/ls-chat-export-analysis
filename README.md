# Livestorm Chat Export + OpenAI Analysis

Streamlit app to:
- Fetch Livestorm session chat messages (with pagination)
- Clean and export messages as CSV
- Run OpenAI analysis over the full raw JSON response

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## OpenAI Analysis

1. Paste your OpenAI API key in the sidebar.
2. Click `Fetch chat messages`.
3. Click `Run analysis`.

The analysis sends:
- `raw_api_response` (full fetched JSON)
- `derived_stats` (quick computed metrics)

and renders markdown analysis in the UI.

## Editable Prompt

You can change the analysis instructions without code edits:

- `prompts/openai_chat_analysis_prompt.txt`

## Notes

- Provide your Livestorm API key and session ID in the sidebar.
- OpenAI usage is optional; if no OpenAI key is provided, fetch/export still works.
- There is no guaranteed free OpenAI model; `gpt-4o-mini` is typically a low-cost option.
