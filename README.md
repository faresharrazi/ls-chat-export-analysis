# Livestorm Chat Export + OpenAI Analysis

Streamlit app to:
- Fetch Livestorm session chat messages (with pagination)
- Clean and export messages as CSV
- Run OpenAI analysis over the full raw JSON response
- Ask Q&A questions scoped only to fetched chat messages

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
3. Click `Run OpenAI analysis`.

The app sends:
- `raw_api_response` (full fetched JSON)
- `derived_stats` (quick computed metrics)

and renders markdown analysis in the UI.

## Chat Q&A

After fetching messages, use the Q&A input to ask things like:
- "How many people said Bonjour?"
- "Who said 'Hello'?"

Answers are instructed to use only fetched chat messages.

## Editable Prompt

You can change the analysis instructions without code edits:

- `prompts/openai_chat_analysis_prompt.txt`
- `prompts/openai_chat_qa_prompt.txt`

## Notes

- Provide your Livestorm API key and session ID in the sidebar.
- OpenAI usage is optional; if no OpenAI key is provided, fetch/export still works.
- There is no guaranteed free OpenAI model; `gpt-4o-mini` is typically a low-cost option.
