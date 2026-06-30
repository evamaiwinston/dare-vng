from __future__ import annotations
from dataclasses import dataclass


@dataclass
class SourceAttribution:
    score: float
    source_text: str
    chunk_id: str | None
    doc_id: str | None
    retrieval_score: float | None
    origin: str


@dataclass
class UnitAttribution:
    text: str
    span: tuple[int, int]
    attributions: list[SourceAttribution]
