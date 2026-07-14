"""FastAPI wrapper around the attribution engine (INFO.md Step 6).

One endpoint: POST /attribute. Takes {query, answer, chunks} — the same three
things a frontend already has in hand right after rendering a RAG answer — and
returns a RecordSummary plus a per-record `relative` view as JSON. This module
owns HTTP concerns only (request shape, CORS, error mapping); the computation is
exactly the attribute_by_sentence -> summarize_record -> relativize_record chain
dare.batch runs, just driven by one live request instead of a corpus row. The
synthesis instruction is folded into the ablation set (origin="instruction"),
same as batch's --instruction, so the widget reports the instruction lane too.

Run: uvicorn dare.api:app --host 0.0.0.0 --port 8000

Endpoint functions are plain `def`, not `async def` — attribute_by_sentence is
synchronous and network-bound (serial ablation calls, tens of seconds today;
see INFO.md's deferred latency fix), so FastAPI needs to dispatch it to its
worker threadpool rather than run it on the event loop, or one slow request
blocks every other concurrent request. A plain `def` route gets that
dispatch automatically.
"""

from __future__ import annotations

import dataclasses
import logging
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dare.attribution import attribute_by_sentence
from dare.config import Settings
from dare.prompts import SYNTHESIS_SYSTEM
from dare.providers import CachingProvider, OpenAICompatProvider
from dare.schema import Chunk
from dare.summary import relativize_record, summarize_record

logger = logging.getLogger(__name__)

# Built once at process start, not per-request, so the sqlite cache connection
# is reused across requests instead of reopened on every call. CachingProvider
# is already thread-safe (dare/providers/cache.py) — built for exactly this
# kind of concurrent access, originally for dare.batch's ThreadPoolExecutor.
_SETTINGS = Settings.from_env()
_PROVIDER = CachingProvider(OpenAICompatProvider(_SETTINGS))

app = FastAPI(title="DARE Attribution API")

# CORS origins intentionally empty: whether the browser calls this endpoint
# directly (needs the frontend's real origin here) or the frontend's own
# backend proxies the call (needs no CORS at all) is still an open decision.
# Left empty so an unconfigured deployment fails loudly (blocked) rather than
# silently wide open — fill in the real origin(s) once that's settled.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


class ChunkIn(BaseModel):
    """One retrieved chunk. Field names mirror `knowledge_sources` entries
    (see dare.schema.RAGRecord.chunks) so the frontend can forward the chunk
    objects it already has from its own RAG call, unchanged."""
    content: str
    chunk_id: str | None = None
    document_id: str | None = None
    score: float | None = None


class AttributeRequest(BaseModel):
    query: str
    answer: str
    chunks: list[ChunkIn]


@app.post("/attribute")
def attribute(req: AttributeRequest) -> dict:
    if not req.chunks:
        raise HTTPException(status_code=400, detail="at least one chunk is required")

    chunks = [
        Chunk(
            content=c.content,
            chunk_id=c.chunk_id,
            doc_id=c.document_id,
            score=c.score,
        )
        for c in req.chunks
    ]

    try:
        result = attribute_by_sentence(
            req.query, req.answer, chunks,
            provider=_PROVIDER, settings=_SETTINGS, instruction=SYNTHESIS_SYSTEM,
            # Run this request's ablation calls concurrently (serving path only;
            # batch stays serial). Configurable via WIDGET_MAX_WORKERS, default 8.
            max_workers=_SETTINGS.widget_max_workers,
        )
    except Exception as e:  # noqa: BLE001 — surface as a clean HTTP error, not a stack trace
        logger.exception("attribution failed for query=%r", req.query)
        raise HTTPException(status_code=502, detail=f"attribution failed: {e}") from e

    summary = summarize_record(
        record_id=str(uuid.uuid4()),
        query=req.query,
        response=result["response"],
        whole=result["whole"],
        units=result["units"],
        chunks=chunks,
    )
    # The per-record RELATIVE view (support normalized within this response, one
    # dominant lane per unit) — the same measurement batch's renderer uses,
    # computed here so the widget paints it rather than recomputing. Carried
    # alongside the RecordSummary fields under "relative".
    return {
        **dataclasses.asdict(summary),
        "relative": [dataclasses.asdict(r) for r in relativize_record(summary)],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
