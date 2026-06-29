"""Typed data schema — the records the batch / diagnose layers operate on.

Named `schema` (not `models`) on purpose: in an LLM tool "model" means the LLM,
so the data-contract lives here instead. A `RAGRecord` pairs a query with the
RAG response payload (answer + knowledge sources) in the shape `prepare_inputs()`
consumes. `load_corpus` normalizes the on-disk shapes we have:

* wrapped log line — ``{qa_id, question, response:{answer, knowledge_sources,...}}``
  (e.g. ``data/raw_responses.jsonl``)
* bare payload — ``{answer, knowledge_sources, query?}`` (e.g. the mock files)

Deliberately small for now; `Source` / `Attribution` / `Explanation` join it later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RAGRecord:
    id: str
    query: str
    payload: dict                 # {answer, knowledge_sources, ...} for prepare_inputs
    error: str | None = None

    @property
    def answer(self) -> str:
        return self.payload.get("answer") or ""

    @property
    def knowledge_sources(self) -> list:
        return self.payload.get("knowledge_sources") or []

    @property
    def attributable(self) -> bool:
        """True if there's an answer and at least one source with content to attribute."""
        return (
            not self.error
            and bool(self.answer)
            and any(k.get("content") for k in self.knowledge_sources)
        )

    @classmethod
    def from_obj(cls, obj: dict, idx: int = 0) -> "RAGRecord":
        # Wrapped log line: the RAG payload is nested under `response`.
        if isinstance(obj.get("response"), dict):
            payload = obj["response"] or {}
            query = obj.get("question") or payload.get("query") or ""
            rid = obj.get("qa_id") or f"rec{idx}"
            return cls(id=str(rid), query=query, payload=payload, error=obj.get("error"))
        # Bare payload.
        query = obj.get("query") or obj.get("question") or ""
        rid = obj.get("qa_id") or obj.get("session_id") or f"rec{idx}"
        return cls(id=str(rid), query=query, payload=obj, error=obj.get("error"))


def load_corpus(path: str | Path, limit: int | None = None) -> list[RAGRecord]:
    """Load records from a `.jsonl` (one object per line) or `.json` (array/object) file."""
    path = Path(path)
    if path.suffix == ".jsonl":
        objs = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    else:
        data = json.loads(path.read_text())
        objs = data if isinstance(data, list) else [data]
    records = [RAGRecord.from_obj(o, i) for i, o in enumerate(objs)]
    return records[:limit] if limit else records
