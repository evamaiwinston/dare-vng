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
class Source:
    """One retrieved unit, with its identity and rank preserved.

    `position` is the order the RAG returned it — which is the order the model saw
    it, so it's fidelity-critical and we never reorder by score. `origin` marks a
    retrieved-context source vs an instruction unit (used later for instruction
    ablation). Attribution weights map back onto these.
    """
    content: str
    position: int
    chunk_id: str | None = None
    doc_id: str | None = None
    score: float | None = None       # retrieval relevance score, if any
    origin: str = "context"          # "context" | "instruction"


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
    def sources(self) -> list[Source]:
        """Typed, ordered context sources. The single adapter point that knows the
        VNG field names (knowledge_sources / content / chunk_id / document_id / score);
        order is preserved exactly as returned."""
        return [
            Source(
                content=k.get("content", ""),
                position=i,
                chunk_id=k.get("chunk_id"),
                doc_id=k.get("document_id"),
                score=k.get("score"),
            )
            for i, k in enumerate(self.knowledge_sources)
        ]

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


def sources_to_context(sources: list[Source], sep: str = "\n\n") -> str:
    """Join source contents in order into the context string the engine attributes.

    Order is preserved (never sorted) so the assembled context matches what the
    model actually saw — re-ordering would attribute against a prompt that never
    existed.
    """
    return sep.join(s.content for s in sources)
