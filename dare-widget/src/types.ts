/**
 * TypeScript mirror of the DARE attribution API's data contract.
 *
 * This file is the single source of truth for the shapes crossing the wire, and
 * it deliberately tracks the Python side field-for-field:
 *
 *   - Request types mirror `dare/api.py`   (ChunkIn / AttributeRequest)
 *   - Result types  mirror `dare/results.py` (the `RecordSummary` tree that
 *     `POST /attribute` returns via `dataclasses.asdict`)
 *
 * No logic lives here — just types. If the Python dataclasses change, this file
 * is the one place that must change with them.
 */

// ---------------------------------------------------------------------------
// Request side — what we POST to /attribute (mirrors dare/api.py)
// ---------------------------------------------------------------------------

/**
 * One retrieved chunk, exactly as `ChunkIn` in api.py expects it. The field
 * names mirror a `knowledge_sources` entry from the RAG chat response, so the
 * host can forward those objects unchanged — only `content` is required.
 */
export interface DareChunk {
  content: string;
  chunk_id?: string | null;
  document_id?: string | null;
  score?: number | null;
}

/** The full request body for `POST /attribute` (mirrors `AttributeRequest`). */
export interface AttributeRequest {
  query: string;
  answer: string;
  chunks: DareChunk[];
}

// ---------------------------------------------------------------------------
// Result side — what /attribute returns (mirrors dare/results.py)
// ---------------------------------------------------------------------------

/**
 * Where an attribution row came from. Locked vocabulary (see dare/summary.py):
 * "context" = a retrieved chunk, "instruction" = the folded system prompt. The
 * endpoint folds the synthesis instruction (api.py), so both origins appear.
 */
export type AttributionOrigin = "context" | "instruction";

/**
 * One source's Lasso attribution row — the atomic result (mirrors
 * `SourceAttribution`). A "source" is one partitioned *piece* of a chunk (a
 * bullet, a table row, a sentence), which is what the engine actually scores.
 */
export interface SourceAttribution {
  score: number;
  source_text: string;
  chunk_id: string | null;
  doc_id: string | null;
  retrieval_score: number | null;
  origin: AttributionOrigin;
}

/**
 * One retrieved chunk's attribution, with its source pieces rolled back up
 * (mirrors `ChunkAttribution`). `chunk_text` is the WHOLE verbatim chunk the
 * model saw — not the top-scoring fragment — so a trust-facing view can show
 * the real document excerpt. `positive_mass` is this chunk's grounding strength.
 */
export interface ChunkAttribution {
  chunk_id: string | null;
  positive_mass: number; // Σ positive source scores — the reported strength
  net_score: number; // Σ all scores incl. negatives (collinearity signal)
  n_sources: number; // partitioned pieces that rolled into this chunk
  n_negative_sources: number;
  chunk_text: string; // the whole retrieved chunk, verbatim
  doc_id: string | null;
  retrieval_score: number | null;
}

/**
 * One response unit (sentence / bullet / list item / table) and its attribution,
 * split by origin (mirrors `UnitSummary`). `span` is a [start, end] character
 * range into `RecordSummary.response`. The widget shades by the per-record
 * relative view (see `UnitRelative`), not by these raw masses directly.
 */
export interface UnitSummary {
  text: string;
  span: [number, number];
  source_attributions: SourceAttribution[]; // all raw rows, both origins
  chunk_attributions: ChunkAttribution[]; // context only, rolled up by chunk
  instruction_attributions: SourceAttribution[]; // folded synthesis-instruction rows
  context_mass: number; // Σ positive context rows
  instruction_mass: number; // Σ positive instruction rows
}

/**
 * One unit's per-record RELATIVE view (mirrors `UnitRelative` in dare/results.py,
 * built by `relativize_record` and returned under `RecordSummary.relative`).
 * `support` is the positive mass across both lanes; `relative_strength` is that
 * support normalized against the strongest unit in THIS response (∈ [0, 1], so it
 * is comparable only within one answer); `dominant_lane` names the driving lane.
 * The widget shades opacity by `relative_strength` and hue by `dominant_lane`.
 */
export interface UnitRelative {
  index: number;
  text: string;
  span: [number, number];
  support: number;
  against: number;
  relative_strength: number; // ∈ [0, 1], normalized within this response
  dominant_lane: "context" | "instruction" | "none";
  context_mass: number;
  instruction_mass: number;
}

/**
 * One record's full attribution distribution — the top-level object returned by
 * `POST /attribute`. Mirrors `RecordSummary`, PLUS a `relative` array that the
 * endpoint attaches alongside the dataclass fields (api.py, via relativize_record).
 * `response` is the exact answer string the engine scored; `units`/`relative` are
 * both in response order and index-aligned.
 */
export interface RecordSummary {
  record_id: string;
  query: string;
  response: string;
  whole_source_attributions: SourceAttribution[];
  whole_chunk_attributions: ChunkAttribution[];
  whole_instruction_attributions: SourceAttribution[];
  whole_context_mass: number;
  whole_instruction_mass: number;
  units: UnitSummary[];
  relative: UnitRelative[]; // per-unit relative view, index-aligned with `units`
}
