"""Result types produced by the attribution engine.

Raw outputs from attribute_by_sentence (attribution.py):
    SourceAttribution  — Source (partitioned context piece) Lasso score + chunk it belongs to.
    UnitAttribution    — Unit (partitioned response piece) paired with its SourceAttribution rows.

From summarize_record (summary.py):
    ChunkAttribution   — Summed SourceAttributions of one chunk.
    UnitSummary        — Response unit with attributions by origin (context or instruction), chunk granularity.
    RecordSummary      — Full response chunk attributions.
    UnitRelative       — Response unit's attributions normalized against strongest unit in the same record.
"""

from __future__ import annotations

from dataclasses import dataclass


# --- Raw engine output ------------------------------------------------------

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


# --- Descriptive / report structure (built by dare.summary) -----------------

@dataclass
class ChunkAttribution:
    chunk_id: str | None
    positive_mass: float          # Σ positive source scores for this chunk (reported magnitude)
    net_score: float              # Σ ALL source scores incl negatives (collinearity/competition signal)
    n_sources: int                # partitioned sources that rolled into this chunk
    n_negative_sources: int       # how many of them were negative
    chunk_text: str               # the WHOLE retrieved chunk, verbatim as fed into attribution — the
                                  # honest chunk, NOT truncated to its top-scoring segment. The most
                                  # influential segment, if ever needed, is derivable from the matching
                                  # source_attributions (max score for this chunk_id).
    doc_id: str | None
    retrieval_score: float | None


@dataclass
class UnitSummary:
    text: str
    span: tuple[int, int]
    source_attributions: list[SourceAttribution]       # ALL raw rows, both origins — nothing hidden
    chunk_attributions: list[ChunkAttribution]         # origin="context" only, rolled up by chunk
    instruction_attributions: list[SourceAttribution]  # origin="instruction" raw directive-sentence rows
    context_mass: float                                # Σ positive context rows
    instruction_mass: float                            # Σ positive instruction rows


@dataclass
class RecordSummary:
    record_id: str
    query: str
    response: str
    whole_source_attributions: list[SourceAttribution]       # all raw rows, both origins
    whole_chunk_attributions: list[ChunkAttribution]         # context only, rolled up
    whole_instruction_attributions: list[SourceAttribution]  # instruction rows
    whole_context_mass: float
    whole_instruction_mass: float
    units: list[UnitSummary]      # in RESPONSE ORDER (faithful); renderer sorts for a ranked view


# --- Derived relative view (built by dare.summary.relativize_record) ---------

@dataclass
class UnitRelative:
    """Unit's relative view within its record.

    Renderer maps relative_strength (in [0, 1]) to opacity and
    dominant_lane (context/instruction) to hue.
    """
    index: int
    text: str
    span: tuple[int, int]
    support: float              # Σ positive sources, both lanes
    against: float              # Σ |negative sources|, both lanes (competing)
    relative_strength: float    # support / record's max support, in [0, 1]
    dominant_lane: str          # "context" | "instruction" | "none"
    context_mass: float
    instruction_mass: float
