"""Descriptive attribution summary — turns raw scores into a report-ready structure.

A pure function over ``attribute_by_sentence``'s output. It does NOT classify:
no DEPENDENT/INDEPENDENT verdict, no thresholds, no boilerplate filtering. A report
states what happened; any thresholding is a separate, data-driven step later.

It does three things:
  (a) splits attributions by ``origin`` — context (retrieved chunks) vs instruction
      (the folded-in system prompt) — and reports each its own way, because they
      answer different questions and must never be merged (instruction is not a chunk);
  (b) rolls context-origin rows up to CHUNK granularity by positive mass, so the
      "which retrieved document grounded this" magnitude is reported correctly;
  (c) keeps the raw source rows alongside, so nothing is hidden.

Granularity vocabulary (locked — mirrors LOG terminology, never conflate):
  source = one partitioned piece of a chunk — what ContextCite ablates and fits. Raw Lasso rows.
  chunk  = one retrieved document excerpt (chunk_id) — its sources rolled back up.
  origin = "context" (from a retrieved chunk) | "instruction" (from the system prompt).
Field names always carry the granularity (`source_attributions` / `chunk_attributions`),
and the two have distinct types (`SourceAttribution` / `ChunkAttribution`).

Why roll up to chunk for the report: ContextCite splits each chunk into however many
sources the partitioner cuts, so a chunk's contribution is spread across its pieces.
Comparing a fragmented chunk's top piece against an unfragmented chunk's single score is
not like-for-like and can name the wrong document as the primary source. Summing positive
mass per chunk puts them on equal footing. ``net_score`` / ``n_negative_sources`` are
reported too, so collinearity and genuine competing sources surface as numbers.

Why split on origin and not chunk_id: instruction rows have chunk_id=None — but so do
context sources that failed to map. Splitting on origin keeps those apart; splitting on
chunk_id would lump instruction mass in with unmapped context as phantom chunks.
"""

from __future__ import annotations

from dataclasses import dataclass

from dare.models import SourceAttribution, UnitAttribution


@dataclass
class ChunkAttribution:
    """One retrieved chunk's attribution, with its sources rolled up. By CHUNK."""
    chunk_id: str | None
    positive_mass: float          # Σ positive source scores for this chunk (reported magnitude)
    net_score: float              # Σ ALL source scores incl negatives (collinearity/competition signal)
    n_sources: int                # partitioned sources that rolled into this chunk
    n_negative_sources: int       # how many of them were negative
    representative_text: str      # text of this chunk's strongest single source row
    doc_id: str | None
    retrieval_score: float | None


@dataclass
class UnitSummary:
    """One response unit's attribution, split by origin. Nothing filtered."""
    text: str
    span: tuple[int, int]
    source_attributions: list[SourceAttribution]       # ALL raw rows, both origins — nothing hidden
    chunk_attributions: list[ChunkAttribution]         # origin="context" only, rolled up by chunk
    instruction_attributions: list[SourceAttribution]  # origin="instruction" raw directive-sentence rows
    context_mass: float                                # Σ positive context rows
    instruction_mass: float                            # Σ positive instruction rows


@dataclass
class RecordSummary:
    """One record's full attribution distribution, report-ready. Descriptive only."""
    record_id: str
    query: str
    response: str
    whole_source_attributions: list[SourceAttribution]       # all raw rows, both origins
    whole_chunk_attributions: list[ChunkAttribution]         # context only, rolled up
    whole_instruction_attributions: list[SourceAttribution]  # instruction rows
    whole_context_mass: float
    whole_instruction_mass: float
    units: list[UnitSummary]      # in RESPONSE ORDER (faithful); renderer sorts for a ranked view


def _positive_mass(rows: list[SourceAttribution]) -> float:
    return sum(a.score for a in rows if a.score > 0)


def _split_by_origin(rows: list[SourceAttribution]) -> tuple[list[SourceAttribution], list[SourceAttribution]]:
    """(context_rows, instruction_rows). Split on origin, never chunk_id — both
    instruction and unmapped-context are chunk_id=None."""
    ctx   = [r for r in rows if r.origin != "instruction"]
    instr = [r for r in rows if r.origin == "instruction"]
    return ctx, instr


def aggregate_by_chunk(context_rows: list[SourceAttribution]) -> list[ChunkAttribution]:
    """Roll context-origin source rows up to chunk granularity, ranked by positive_mass desc.

    Expects CONTEXT rows only (caller splits off instruction first). Groups by
    ``chunk_id`` and reports, per chunk: positive_mass (Σ positive), net_score (Σ all),
    source counts, and the strongest single row's text as the representative. ALL chunks
    are kept — including net-zero/negative ones (competing sources). Context rows are
    always chunk-mapped in practice (verified 0/522 unmapped on the cached corpus); a
    stray unmapped row (chunk_id=None) would collapse into a single None-keyed entry —
    still surfaced, never dropped.
    """
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
            representative_text=rep.source_text,
            doc_id=rep.doc_id,
            retrieval_score=rep.retrieval_score,
        ))

    chunks.sort(key=lambda c: -c.positive_mass)
    return chunks


def summarize_record(
    record_id: str,
    query: str,
    response: str,
    whole: list[SourceAttribution],
    units: list[UnitAttribution],
) -> RecordSummary:
    """Build a descriptive RecordSummary from one record's attribution output.

    ``whole`` and ``units`` are exactly ``attribute_by_sentence``'s ``whole`` and
    ``units`` (source-level). Attributions are split by origin: context → chunk rollup,
    instruction → kept as raw directive rows. Units stay in response order. When no
    instruction was folded in, the instruction lanes are simply empty/zero, so the same
    function reads both context-only and instruction runs.
    """
    whole_ctx, whole_instr = _split_by_origin(whole)

    unit_summaries = []
    for u in units:
        ctx, instr = _split_by_origin(u.attributions)
        unit_summaries.append(UnitSummary(
            text=u.text,
            span=u.span,
            source_attributions=u.attributions,
            chunk_attributions=aggregate_by_chunk(ctx),
            instruction_attributions=sorted(instr, key=lambda r: -r.score),
            context_mass=_positive_mass(ctx),
            instruction_mass=_positive_mass(instr),
        ))

    return RecordSummary(
        record_id=record_id,
        query=query,
        response=response,
        whole_source_attributions=whole,
        whole_chunk_attributions=aggregate_by_chunk(whole_ctx),
        whole_instruction_attributions=sorted(whole_instr, key=lambda r: -r.score),
        whole_context_mass=_positive_mass(whole_ctx),
        whole_instruction_mass=_positive_mass(whole_instr),
        units=unit_summaries,
    )
