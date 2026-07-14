"""Schema of a RAGRecord triple (query, response, chunks) — expected by attribute_by_sentence()."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    """One retrieved chunk:

    `content` - chunk content verbatim
    `origin`  - retrieved-context chunk vs system instruction
    """
    content: str
    chunk_id: str | None = None
    doc_id: str | None = None
    score: float | None = None       # retrieval relevance score, if any
    origin: str = "context"          # "context" | "instruction"


@dataclass
class RAGRecord:
    id: str
    query: str
    payload: dict                 # {answer, knowledge_sources, ...} for prepare_inputs (demo only)
    error: str | None = None

    @property
    def answer(self) -> str:
        return self.payload.get("answer") or ""

    @property
    def knowledge_sources(self) -> list:
        return self.payload.get("knowledge_sources") or []

    @property
    def chunks(self) -> list[Chunk]:
        """Adapter point for VNG field names (knowledge_sources / content / chunk_id / document_id / score)."""
        return [
            Chunk(
                content=k.get("content", ""),
                chunk_id=k.get("chunk_id"),
                doc_id=k.get("document_id"),
                score=k.get("score"),
            )
            for k in self.knowledge_sources
        ]

    @property
    def attributable(self) -> bool:
        return (
            not self.error
            and bool(self.answer)
            and any(k.get("content") for k in self.knowledge_sources)
        )

    @classmethod
    def from_obj(cls, obj: dict, idx: int = 0) -> "RAGRecord":
        if isinstance(obj.get("response"), dict):
            payload = obj["response"] or {}
            query = obj.get("question") or payload.get("query") or ""
            rid = obj.get("qa_id") or f"rec{idx}"
            return cls(id=str(rid), query=query, payload=payload, error=obj.get("error"))
        query = obj.get("query") or obj.get("question") or ""
        rid = obj.get("qa_id") or obj.get("session_id") or f"rec{idx}"
        return cls(id=str(rid), query=query, payload=obj, error=obj.get("error"))


def load_corpus(path: str | Path, limit: int | None = None) -> list[RAGRecord]:
    path = Path(path)
    if path.suffix == ".jsonl":
        objs = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    else:
        data = json.loads(path.read_text())
        objs = data if isinstance(data, list) else [data]
    records = [RAGRecord.from_obj(o, i) for i, o in enumerate(objs)]
    return records[:limit] if limit else records
