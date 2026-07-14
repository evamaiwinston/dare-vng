"""Turns raw output from attribution into structure for report.
 
Splits attributions by origin, context vs instruction
Rolls context-origin rows up to chunk granularity by positive mass, keeps raw rows alongside.

Granularity clarification:
  chunk  = one retrieved document excerpt 
  source = one partitioned piece of a chunk
"""

from __future__ import annotations

from dare.results import (
    ChunkAttribution,
    RecordSummary,
    SourceAttribution,
    UnitAttribution,
    UnitRelative,
    UnitSummary,
)
from dare.schema import Chunk


def _positive_mass(rows: list[SourceAttribution]) -> float:
    return sum(a.score for a in rows if a.score > 0)


def _split_by_origin(rows: list[SourceAttribution]) -> tuple[list[SourceAttribution], list[SourceAttribution]]:
    """(context_rows, instruction_rows)"""
    ctx   = [r for r in rows if r.origin != "instruction"]
    instr = [r for r in rows if r.origin == "instruction"]
    return ctx, instr


def aggregate_by_chunk(
    context_rows: list[SourceAttribution],
    chunk_texts: dict[str | None, str] | None = None,
) -> list[ChunkAttribution]:
    """Group context source rows by chunk_id, sum their positive scores.
    Returns ChunkAttributions ranked by positive mass, descending.
    """
    chunk_texts = chunk_texts or {}
    grouped: dict[str | None, list[SourceAttribution]] = {}
    for a in context_rows:
        grouped.setdefault(a.chunk_id, []).append(a)

    chunks: list[ChunkAttribution] = []
    for rows in grouped.values():
        rep = max(rows, key=lambda r: r.score)
        chunks.append(ChunkAttribution(
            chunk_id=rep.chunk_id,
            positive_mass=_positive_mass(rows),
            net_score=sum(r.score for r in rows),
            n_sources=len(rows),
            n_negative_sources=sum(1 for r in rows if r.score < 0),
            doc_id=rep.doc_id,
            retrieval_score=rep.retrieval_score,
            # the honest whole chunk fed into attribution; fall back to the top
            # segment's text only when the original content wasn't passed in
            # (e.g. an unmapped None-keyed group).
            chunk_text=chunk_texts.get(rep.chunk_id) or rep.source_text,
        ))

    chunks.sort(key=lambda c: -c.positive_mass)
    return chunks


def summarize_record(
    record_id: str,
    query: str,
    response: str,
    whole: list[SourceAttribution],
    units: list[UnitAttribution],
    chunks: list[Chunk] | None = None,
) -> RecordSummary:
    """Descriptive RecordSummary from one record's attribution output."""
    # chunk_id -> verbatim retrieved content, so every rollup shows the whole chunk.
    chunk_texts = {c.chunk_id: c.content for c in (chunks or []) if c.chunk_id}

    whole_ctx, whole_instr = _split_by_origin(whole)

    unit_summaries = []
    for u in units:
        ctx, instr = _split_by_origin(u.attributions)
        unit_summaries.append(UnitSummary(
            text=u.text,
            span=u.span,
            source_attributions=u.attributions,
            chunk_attributions=aggregate_by_chunk(ctx, chunk_texts),
            instruction_attributions=sorted(instr, key=lambda r: -r.score),
            context_mass=_positive_mass(ctx),
            instruction_mass=_positive_mass(instr),
        ))

    return RecordSummary(
        record_id=record_id,
        query=query,
        response=response,
        whole_source_attributions=whole,
        whole_chunk_attributions=aggregate_by_chunk(whole_ctx, chunk_texts),
        whole_instruction_attributions=sorted(whole_instr, key=lambda r: -r.score),
        whole_context_mass=_positive_mass(whole_ctx),
        whole_instruction_mass=_positive_mass(whole_instr),
        units=unit_summaries,
    )


def relativize_record(summary: RecordSummary) -> list[UnitRelative]:
    """Each unit's support against strongest unit in the same record. Relative measurement lands in [0,1].
    One ``UnitRelative`` per unit in response order.

    support = summed positive mass, both origin lanes 
    
    Normalization is within record only — strengths are NOT
    comparable across records. ``dominant_lane`` names what drove the unit, instruction or context
    """
    supports = [u.context_mass + u.instruction_mass for u in summary.units]
    max_support = max(supports, default=0.0) or 1.0   # floor so an all-zero record can't /0

    out: list[UnitRelative] = []
    for i, u in enumerate(summary.units):
        support = supports[i]
        against = sum(-a.score for a in u.source_attributions if a.score < 0)
        max_chunk = max((c.positive_mass for c in u.chunk_attributions), default=0.0)
        if support <= 0:
            lane = "none"
        elif u.instruction_mass > 0 and u.instruction_mass >= max_chunk:
            lane = "instruction"
        else:
            lane = "context"
        out.append(UnitRelative(
            index=i,
            text=u.text,
            span=u.span,
            support=support,
            against=against,
            relative_strength=support / max_support,
            dominant_lane=lane,
            context_mass=u.context_mass,
            instruction_mass=u.instruction_mass,
        ))
    return out
