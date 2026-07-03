"""signals.py — secondary signals over an attribution summary.

Currently one signal: **query↔chunk cosine**. Attribution already says which
chunk a unit leaned on; this asks whether that chunk is even on-topic for the
question. Low cosine ⇒ the unit grounded in something off-topic. Pure over a
``RecordSummary`` plus an injected embedder — the embedder is the only I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dare.results import RecordSummary


@dataclass
class UnitSignal:
    grounding_chunk_id: str | None
    chunk_query_cosine: float | None   # None when the unit has no positive-mass chunk


@dataclass
class RecordSignals:
    record_id: str
    units: list[UnitSignal]            # parallel to summary.units, by index


def cosine(a, b) -> float:
    """Cosine similarity of two vectors, in [-1, 1]. 0.0 if either is zero-length."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _grounding_text(unit) -> tuple[str | None, str | None]:
    """(chunk_id, whole-chunk text) of the unit's top positive-mass chunk, else (None, None).

    Whole chunk = every partitioned source row sharing the top chunk's ``chunk_id``,
    joined — not just the single strongest row (`representative_text`). The fuller
    text is a more stable topical signal for the query↔chunk cosine; a lone table
    row or form step is too sparse to embed meaningfully. Falls back to
    ``representative_text`` if no rows are recoverable.
    """
    if not unit.chunk_attributions:
        return None, None
    top = unit.chunk_attributions[0]             # already ranked by positive_mass
    if top.positive_mass <= 0:
        return None, None
    rows = [
        a.source_text for a in unit.source_attributions
        if a.origin != "instruction" and a.chunk_id == top.chunk_id and a.source_text
    ]
    return top.chunk_id, "\n".join(rows) or top.representative_text


def compute_signals(summary: RecordSummary, *, embedder) -> RecordSignals:
    """Attach query↔chunk cosine to each unit of a ``RecordSummary``.

    Embeds the query once and each unit's grounding-chunk text (deduped) as
    passages, then computes ``cosine(query, chunk)`` per unit. Units with no
    positive-mass grounding chunk get ``None``. ``embedder`` is any object with
    ``embed_query`` / ``embed_passage`` methods.
    """
    query_vec = embedder.embed_query([summary.query])[0]

    per_unit = [_grounding_text(u) for u in summary.units]
    texts = sorted({t for _, t in per_unit if t is not None})
    vecs = dict(zip(texts, embedder.embed_passage(texts))) if texts else {}

    units = [
        UnitSignal(
            grounding_chunk_id=chunk_id,
            chunk_query_cosine=(cosine(query_vec, vecs[text]) if text is not None else None),
        )
        for chunk_id, text in per_unit
    ]
    return RecordSignals(record_id=summary.record_id, units=units)
