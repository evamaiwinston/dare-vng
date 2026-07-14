# DARE — Diagnostic Attribution for RAG Explainability

Use cases:
- Batch report - inspect aggregated RAG behavior, debug incorrect answers + build trust in correct answers
- Chat-bot widget - show attribution to users on demand

## What it does

Feed it a `(query, answer, chunks)` triple. It returns, per sentence of the answer:
- which retrieved chunk(s) it actually came from
- how strongly it relied on that chunk, vs. the system's own instructions, vs. neither (i.e.
  possibly made up)

## Quick start

```bash
git clone https://github.com/evamaiwinston/dare-vng.git
cd dare-vng
python -m venv venv && source venv/bin/activate
pip install -e .
pip install -r requirements.txt

cp .env.example .env
# fill in OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
```

## Ways to run

| Mode | Command | Use case |
|---|---|---|
| **Batch report** | `python -m dare.batch --corpus data/cached_responses.jsonl --limit 20` | Run over a saved corpus, get a report in `runs/` |
| **Live API** | `uvicorn dare.api:app --reload` | `POST /attribute` with one query/answer/chunks, get JSON back |
| **Widget** | `cd dare-widget && npm install && npm run play` | Drop-in React component (`<DareWidget />`) for a live product surface |
| **Interactive demo** | `cd demo && python app.py` | Gradio UI — explore attribution on one example at a time |


## Project structure

```
dare/                     core engine + FastAPI app
  attribution.py            attribution engine — attribute_by_sentence(query, answer, chunks)
  batch.py                  runs attribution over a whole corpus (python -m dare.batch)
  summary.py                turns raw scores into the readable report/API shape
  api.py                    FastAPI app — POST /attribute (what the widget calls)
  schema.py                 data types in/out (Chunk, RAGRecord)
  providers/                 LLM endpoint/cache providers
  tests/                     pytest suite

dare-widget/              drop-in React widget (npm package)
  src/DareWidget.tsx        the component a host app imports
  src/AttributionView.tsx   renders one attribution result
  src/api.ts                calls api
  playground/                Vite sandbox to preview the widget without a host app

demo/                     Gradio demo app
tools/                    standalone CLI scripts
data/                     sample corpora
runs/                     batch output (git-ignored)
```

