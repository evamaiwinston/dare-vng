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

from dare.results import (
    ChunkAttribution,
    RecordSummary,
    SourceAttribution,
    UnitAttribution,
    UnitSummary,
)
from dare.schema import Chunk


def _positive_mass(rows: list[SourceAttribution]) -> float:
    return sum(a.score for a in rows if a.score > 0)


def _split_by_origin(rows: list[SourceAttribution]) -> tuple[list[SourceAttribution], list[SourceAttribution]]:
    """(context_rows, instruction_rows). Split on origin, never chunk_id — both
    instruction and unmapped-context are chunk_id=None."""
    ctx   = [r for r in rows if r.origin != "instruction"]
    instr = [r for r in rows if r.origin == "instruction"]
    return ctx, instr


def aggregate_by_chunk(
    context_rows: list[SourceAttribution],
    chunk_texts: dict[str | None, str] | None = None,
) -> list[ChunkAttribution]:
    """Roll context-origin source rows up to chunk granularity, ranked by positive_mass desc.

    Expects CONTEXT rows only (caller splits off instruction first). Groups by
    ``chunk_id`` and reports, per chunk: positive_mass (Σ positive), net_score (Σ all),
    source counts, and — from the ``chunk_texts`` (``chunk_id -> full content``) map
    built off the original sources — the whole chunk that was fed into attribution.
    ALL chunks are kept — including net-zero/negative ones (competing sources). Context
    rows are always chunk-mapped in practice (verified 0/522 unmapped on the cached
    corpus); a stray unmapped row (chunk_id=None) would collapse into a single
    None-keyed entry — still surfaced, never dropped.
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
    """Build a descriptive RecordSummary from one record's attribution output.

    ``whole`` and ``units`` are exactly ``attribute_by_sentence``'s ``whole`` and
    ``units`` (source-level). ``chunks`` is the original ``Chunk`` list that was fed
    into attribution — passed so each chunk can carry its verbatim full text
    (``ChunkAttribution.chunk_text``) instead of a truncated top-row excerpt. Omitting
    it degrades chunk_text to the strongest segment (back-compat for callers without
    the sources on hand). Attributions are split by origin: context → chunk rollup,
    instruction → kept as raw directive rows. Units stay in response order. When no
    instruction was folded in, the instruction lanes are simply empty/zero, so the same
    function reads both context-only and instruction runs.
    """
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
