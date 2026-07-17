# DARE — Diagnostic Attribution for RAG Explainability

DARE explains a RAG system's answers based on how it used the context it received 
to generate the answer. 

Feed it a corpus of
`(query, answer, retrieved chunks)` and it tells you, per sentence of each
answer, how each retrieved chunk contributed to the answer generation.


This README covers the **batch report**, but DARE also has a live single-query API and a drop-in React widget for
product surfaces-- documented in **[dare-widget/README.md](dare-widget/README.md)**

---

## Why ablation-based attribution

RAG's structure is a natural fit for ablation based attribution because
the pre-chunked information is already in easily human-interpretable bite sizes. 

## Setup

```bash
git clone https://github.com/evamaiwinston/dare-vng.git
cd dare-vng

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -e .                 # installs the dare package + its runtime deps
pip install -r requirements.txt  # dev/batch extras (jupyter, gradio, etc. — optional but simplest)

cp .env.example .env
```

Edit `.env` — at minimum:

```bash
OPENAI_API_KEY=...        # your LLM endpoint's key
OPENAI_BASE_URL=...       # must be OpenAI-compatible and support prompt_logprobs
LLM_MODEL=...              # the exact model that generated the answers you're attributing —
                            # not just "a capable model". See note below.
```

**This has to be the same model that produced the answers, not a substitute.**
Attribution measures *this model's own* probability of the response under different
context — score with a different model and you're measuring its opinion of someone
else's answer, not why the original model wrote it. Nothing errors out if you get
this wrong; the numbers just won't mean what they claim to.

Smoke-test the install without touching your own data yet:

```bash
python -m dare.batch --corpus data/cached_responses.jsonl --limit 3
```

If that produces `runs/batch_<timestamp>/summary.md` with no errors, the install and
`.env` are good and the only remaining work is getting *your* data into the shape
below.

---

## The batch report

`python -m dare.batch --corpus <file>` runs attribution over a whole corpus and
produces a corpus-level report — the primary way to use DARE.

### Getting your data in — the corpus shape

Reads a `.jsonl` (one JSON object per line) or `.json` (array of objects) file. This
isn't enforced by a schema today — it's whatever `dare.schema.RAGRecord.from_obj`
reads via plain `dict.get()` calls, so it's spelled out here for anyone plugging in
data from a different system.

Two accepted per-record shapes — nested (has a `response` object) or flat
(everything top-level):

```json
{
  "qa_id": "rec-001",
  "question": "What's the meal cap for domestic travel?",
  "response": {
    "answer": "$50/day.",
    "knowledge_sources": [
      {"content": "Domestic travel meal allowance is $50/day.", "chunk_id": "c1", "document_id": "policy_2025_v3", "score": 0.91}
    ]
  }
}
```

```json
{
  "qa_id": "rec-001",
  "query": "What's the meal cap for domestic travel?",
  "answer": "$50/day.",
  "knowledge_sources": [
    {"content": "Domestic travel meal allowance is $50/day.", "chunk_id": "c1", "document_id": "policy_2025_v3", "score": 0.91}
  ]
}
```

**Fields:**

| Field | Required | Notes |
|---|---|---|
| `qa_id` | no | your record's id; auto-generated if omitted |
| `query` / `question` | yes | either key name works |
| `answer` | yes | empty/missing ⇒ record silently skipped, see below |
| `knowledge_sources` | yes | list of chunk objects, fields below |
| `error` | no | if set, record is skipped regardless of other fields |

**Each `knowledge_sources` entry:**

| Field | Required | Notes |
|---|---|---|
| `content` | yes | verbatim chunk text; empty ⇒ this chunk is ignored |
| `chunk_id` | no | unique id for this chunk |
| `document_id` | no | groups chunks from the same source document |
| `score` | no | your retrieval relevance score, any scale — shown in the report, never used in the attribution math |


**Plugging in a different system**: if your data doesn't naturally produce either
shape above, write a small standalone adapter script that converts your export into
one of them — do not modify `dare/schema.py` to special-case your system. The
adapter is the only thing that needs to know your system's shape; `dare.batch`
stays generic. Same pattern as `dare.providers.LogprobProvider` — one fixed
interface, swappable implementations on the other side of it.

### Parameters worth tuning

| Parameter | Where | Default | Adjust when |
|---|---|---|---|
| `--num-ablations` | CLI flag | 32 | Your answers cite more chunks than typical, or per-sentence scores look unstable on rerun. |
| `--max-workers` | CLI flag | 3 | Raise if your endpoint can take more concurrent requests; lower if you're hitting rate limits. |
| `--limit` | CLI flag | 3 | Always smoke-test a handful of records before a full run. |
| `--cache-path` | CLI flag | `./.cache/logprobs.sqlite` | Point at a fresh path per data source so reruns are free without colliding with anyone else's cache. |
| `--instruction` | CLI flag | off | Fold a static system prompt in as its own attributable lane, separate from retrieved chunks. Invalidates the context-only cache the first time — real API cost, not free. |
| `LASSO_ALPHA` (.env) | env var | 0.01 | Lower keeps more sources with nonzero credit (multi-source synthesis); higher sparsifies onto fewer, dominant sources. Tune empirically on your own data — don't inherit this default. |
| `--signals` + `EMBED_MODEL` (.env) | CLI flag + env var | off / `intfloat/multilingual-e5-base` | Optional query↔chunk cosine sanity check, not a competing attribution method. Swap `EMBED_MODEL` if your data isn't the same language/domain. |
| `SHELL_TOKENIZER` (.env) | env var | `gpt2` | Structural shell only. One real constraint: the internal prompt template assumes ChatML markers — a non-ChatML model needs a code change in `dare/attribution.py`, not just this env var. |

### Running it

```bash
python -m dare.batch --corpus path/to/your_corpus.jsonl --limit 20
```

Output lands in `runs/batch_<timestamp>/`:

| File | Contents |
|---|---|
| `results.json` | Full per-record, per-unit attribution — every field a renderer needs, inlined verbatim (chunk text, retrieval score, mass), nothing requires a lookup back to the original RAG system. |
| `report.json` | Corpus-level aggregate: record counts, avg sources/record, context/instruction mass distribution (mean/median/sd), instruction incidence. |
| `summary.md` | Human-readable render of the above. |
| `metadata.json` | Run provenance (model, alpha, ablations, instruction hash) — only written when invoked via the CLI. |

Once a smoke-test run looks right, drop `--limit` and run your full corpus.

---

---

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
