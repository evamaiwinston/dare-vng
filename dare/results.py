"""Result types — every dataclass the attribution engine hands back.

The output data contract, in one place (the input contract lives in ``schema.py`` —
"schema in, results out"). Named ``results`` not ``models`` on purpose: in an LLM
tool "model" means the LLM (same reasoning ``schema.py`` gives for its name).

Two families, in dependency order:

  Raw engine output (from ``attribute_by_sentence``):
    SourceAttribution  — one source's Lasso row (score + provenance); the shared atom,
                         used at BOTH the whole-response and per-unit levels.
    UnitAttribution    — a response unit's text/span wrapping its SourceAttribution rows.

  Descriptive / report structure (from ``summarize_record`` in ``summary.py``):
    ChunkAttribution   — SourceAttributions rolled up to one retrieved chunk, by positive mass.
    UnitSummary        — one unit, split by origin (context chunks vs instruction), nothing hidden.
    RecordSummary      — one record's full distribution, report-ready. Descriptive only.

This module imports nothing but stdlib — it's a leaf everything else depends on.
"""

from __future__ import annotations

from dataclasses import dataclass


# --- Raw engine output ------------------------------------------------------

@dataclass
class SourceAttribution:
    """One source's Lasso attribution row. The atomic result, shared across levels."""
    score: float
    source_text: str
    chunk_id: str | None
    doc_id: str | None
    retrieval_score: float | None
    origin: str


@dataclass
class UnitAttribution:
    """One response unit's text/span wrapping its raw SourceAttribution rows."""
    text: str
    span: tuple[int, int]
    attributions: list[SourceAttribution]


# --- Descriptive / report structure (built by dare.summary) -----------------

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
