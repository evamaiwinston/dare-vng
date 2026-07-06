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
 * "context" = a retrieved chunk, "instruction" = the folded system prompt.
 * The current endpoint never folds the instruction, so in practice every row is
 * "context" — but we type both to stay faithful to the contract.
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
 * range into `RecordSummary.response`. `context_mass` is this unit's total
 * positive grounding from retrieved chunks — the number the widget shades by.
 */
export interface UnitSummary {
  text: string;
  span: [number, number];
  source_attributions: SourceAttribution[]; // all raw rows, both origins
  chunk_attributions: ChunkAttribution[]; // context only, rolled up by chunk
  instruction_attributions: SourceAttribution[]; // always empty today
  context_mass: number;
  instruction_mass: number; // always 0 today
}

/**
 * One record's full attribution distribution — the top-level object returned by
 * `POST /attribute` (mirrors `RecordSummary`). `response` is the exact answer
 * string the engine scored; `units` are in response order.
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
}
