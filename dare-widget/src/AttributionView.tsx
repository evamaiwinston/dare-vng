/**
 * AttributionView — turns a RecordSummary into the visual.
 *
 * Built in pieces:
 *   1. relative shading (lane hue + per-record opacity) — the "numbers"
 *   2. the annotated answer (shaded, clickable units)
 *   3. whole-response chunks (right panel, default state)
 *   4. the per-unit drill-in drawer (right panel, selected state)
 *   5. assembly — the two-column inspector
 *
 * This view is the single-response twin of the batch report (tools/render.py):
 * the backend runs the SAME attribute_by_sentence -> summarize_record ->
 * relativize_record chain (instruction folded in), and this file only PAINTS the
 * result — opacity from `relative_strength`, hue from `dominant_lane`. No scoring,
 * bucketing, or calibration happens here anymore; the measurement lives in
 * dare/summary.py. styles.ts only paints chrome (see its header).
 *
 * Terminology (locked): units are "attributed" to context/instruction by causal
 * dependence — NOT "grounded" (groundedness needs NLI, not wired).
 */

import { useState } from "react";
import type { CSSProperties } from "react";

import type {
  ChunkAttribution,
  RecordSummary,
  SourceAttribution,
  UnitRelative,
  UnitSummary,
} from "./types";

// ---------------------------------------------------------------------------
// Piece 1 — relative shading (lane hue + per-record opacity)
// ---------------------------------------------------------------------------

/** The two lanes' hues, matching the batch renderer (tools/render.py): green for
 *  retrieved-context grounding, amber for the folded synthesis instruction. */
const LANE_HUE: Record<string, string> = {
  context: "126, 224, 192", // green
  instruction: "242, 200, 121", // amber
};

/** Red — same hue as the drawer's "against" bar/rows, for a context-driven unit
 *  whose negative pull outweighs its own support. */
const AGAINST_HUE = "240, 138, 138";

/**
 * A unit's fill: hue by dominant lane — green for context, amber for
 * instruction — except a context-driven unit whose `against` outweighs its
 * own `support` shades red instead (net-contradicted, even though context is
 * still the strongest positive lane). All three hues use the same opacity
 * gradient — linear 0.06 → 0.91 in `relative_strength` (the same curve as
 * render.py's `0.06 + 0.85 * strength`). A "none" lane (no positive support)
 * gets no fill; the dashed `unattributed` underline stands in instead.
 */
function shadeStyle(rel: UnitRelative): CSSProperties {
  if (rel.dominant_lane === "none" || rel.relative_strength <= 0) return {};
  const hue =
    rel.dominant_lane === "instruction"
      ? LANE_HUE.instruction
      : rel.against > rel.support
        ? AGAINST_HUE
        : LANE_HUE.context;
  const alpha = 0.06 + 0.85 * rel.relative_strength;
  return { background: `rgba(${hue}, ${alpha.toFixed(3)})` };
}

/** Human label for a unit's lane, used in the tooltip. */
function laneLabel(lane: UnitRelative["dominant_lane"]): string {
  if (lane === "instruction") return "instruction-driven";
  if (lane === "context") return "context-driven";
  return "not attributed to context";
}

/** The batch report's three-band strength word, from a unit's within-record
 *  relative_strength (∈ [0, 1]). Mirrors render.py's 0.66 / 0.33 cutoffs. */
function strengthWord(relativeStrength: number): string {
  if (relativeStrength >= 0.66) return "strongly attributed";
  if (relativeStrength >= 0.33) return "moderately attributed";
  return "weakly attributed";
}

// ---------------------------------------------------------------------------
// Piece 2 — the annotated answer (shaded, clickable units)
// ---------------------------------------------------------------------------

/** One walked piece of the response: a `unit` (with its index, to shade/click)
 *  or plain text (`unitIndex: null`) — the gaps between units, e.g. the newlines
 *  between bullets, which must render but aren't attributed. */
interface Segment {
  text: string;
  unitIndex: number | null;
}

/**
 * Walk the response left-to-right using each unit's [start, end] span, emitting
 * the units in order and the plain-text gaps between them. Rebuilds the response
 * exactly (units + gaps = the whole string), so what renders is the verbatim
 * answer, just sliced so each unit can be shaded and clicked. Mirrors
 * tools/render.py's segments().
 */
export function segments(response: string, units: UnitSummary[]): Segment[] {
  const segs: Segment[] = [];
  let cursor = 0;
  units.forEach((u, i) => {
    const [start, end] = u.span;
    if (start > cursor) segs.push({ text: response.slice(cursor, start), unitIndex: null });
    segs.push({ text: response.slice(start, end), unitIndex: i });
    cursor = end;
  });
  if (cursor < response.length) segs.push({ text: response.slice(cursor), unitIndex: null });
  return segs;
}

interface AnnotatedAnswerProps {
  response: string;
  units: UnitSummary[];
  relative: UnitRelative[];
  selected: number | null;
  onSelect: (unitIndex: number) => void;
}

/**
 * The response, rendered as shaded clickable units. Each unit's fill comes from
 * its `UnitRelative` (opacity = per-record relative strength, hue = dominant
 * lane); unattributed units get no fill and the dashed underline (via the
 * `unattributed` class). Clicking a unit only reports the selection up via
 * `onSelect` — this component holds no state; the parent decides what the click
 * reveals (the drawer).
 */
function AnnotatedAnswer({ response, units, relative, selected, onSelect }: AnnotatedAnswerProps) {
  return (
    <div className="answer">
      {segments(response, units).map((seg, i) => {
        // Plain-text gap between units — render as-is, not interactive.
        if (seg.unitIndex === null) return <span key={i}>{seg.text}</span>;

        const idx = seg.unitIndex;
        const rel = relative[idx];

        const className =
          "unit" +
          (rel.dominant_lane === "none" ? " unattributed" : "") +
          (idx === selected ? " selected" : "");

        return (
          <span
            key={i}
            className={className}
            style={shadeStyle(rel)}
            onClick={() => onSelect(idx)}
            title={`${laneLabel(rel.dominant_lane)} · support ${rel.support.toFixed(1)}`}
          >
            {seg.text}
          </span>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Piece 3 — whole-response chunks, part-to-whole (right panel, default state)
// ---------------------------------------------------------------------------

/** A short, readable label for a document id/path (basename, truncated). */
function docLabel(docId: string | null): string {
  if (!docId) return "unknown source";
  const base = docId.includes("/") ? docId.slice(docId.lastIndexOf("/") + 1) : docId;
  return base.length > 44 ? base.slice(0, 44) + "…" : base;
}

/** The chunk's section title = the first markdown heading line of its text
 *  (e.g. "### Điều 17. Tạm ứng lương" → "Điều 17. Tạm ứng lương"), else the first
 *  non-empty line. Returns null for empty text so callers can fall back to the id.
 *  Every corpus chunk starts with a heading, so this is the primary chunk label. */
function chunkTitle(text: string): string | null {
  const first = text.split("\n").map((l) => l.trim()).find((l) => l.length > 0);
  if (!first) return null;
  const heading = first.match(/^#{1,6}\s+(.*)$/);
  return (heading ? heading[1] : first).trim();
}

interface WholeChunksProps {
  chunks: ChunkAttribution[];
}

/**
 * "Which retrieved documents influenced this answer", as PART-TO-WHOLE shares of
 * the total positive attribution mass. Shares (not independent/max bars) because
 * chunk positive_mass is additive within the fit, so the denominator is
 * meaningful and no chunk is falsely "100%". Raw positive_mass is secondary (its
 * absolute value is noisy — surrogate faithfulness is only moderate). Full
 * chunk_text is shown (the chunk-level "whole excerpt, not a fragment" decision).
 */
function WholeChunks({ chunks }: WholeChunksProps) {
  // Influential chunks (positive attribution), ranked by influence — tag + full
  // text only, no bars or numbers (the raw magnitudes are noisy and not the point
  // in the overview; the click-through drawer carries the per-sentence detail).
  const influential = chunks
    .filter((c) => c.positive_mass > 0)
    .sort((a, b) => b.positive_mass - a.positive_mass);

  return (
    <div className="chunks">
      <h4>Chunks that influenced this answer</h4>
      {influential.length === 0 ? (
        <p className="drawer-empty">No retrieved chunk positively influenced this answer.</p>
      ) : (
        influential.map((c, i) => (
          <div className="chunk" key={c.chunk_id ?? i}>
            <div className="chunk-head">
              <span className="chunk-doc">{chunkTitle(c.chunk_text) ?? docLabel(c.doc_id)}</span>
            </div>
            <div className="chunk-text">{c.chunk_text}</div>
          </div>
        ))
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Piece 4 — the per-unit source drawer (right panel, selected state)
// ---------------------------------------------------------------------------

interface UnitDrawerProps {
  unit: UnitSummary;
  rel: UnitRelative;
  /** Largest support-or-against across the whole record, so the diverging bar is
   *  scaled the same for every unit (matches tools/render.py). */
  scale: number;
  onClose: () => void;
}

/**
 * The inspector's SELECTED state: what drove ONE clicked sentence. Header shows
 * the unit's lane + support/against from its `UnitRelative`. Then the two lanes:
 *   instruction → the folded synthesis-prompt directive, shown when it carried mass;
 *   context     → the source fragments, source-forward (raw per-fragment scores),
 *                 because at the unit level a sentence is usually driven by one
 *                 specific fragment and a chunk rollup would dilute it.
 * Context sources split three ways: positive (shown, ranked), negative (collapsed
 * "competing sources"), neutral (≈0, omitted). Each source carries its provenance
 * and its full parent chunk_text on demand.
 */
function UnitDrawer({ unit, rel, scale, onClose }: UnitDrawerProps) {
  const [openChunks, setOpenChunks] = useState<Set<number>>(() => new Set());

  // Diverging support/against bar widths, scaled to the largest of either across
  // ALL units in this record (`scale`) — same as render.py's drawer.
  const supW = (100 * Math.min(rel.support / scale, 1)).toFixed(1);
  const agW = (100 * Math.min(rel.against / scale, 1)).toFixed(1);

  // Every source fragment (context + folded instruction, positive AND negative),
  // ranked by attribution strength (|score|) — the batch report's ± heatmap rows.
  const sources = [...unit.source_attributions]
    .filter((s) => s.score !== 0)
    .sort((a, b) => Math.abs(b.score) - Math.abs(a.score))
    .slice(0, 8);
  const maxAbs = sources.length ? Math.abs(sources[0].score) : 1;

  // Hue by kind: green = context support, red = against, amber = instruction.
  const srcHue = (s: SourceAttribution) =>
    s.origin === "instruction" ? "var(--ins)" : s.score < 0 ? "var(--neg)" : "var(--grn)";
  // chunk_id -> full chunk_text, so a source row can be tagged with its section
  // heading (the markdown "### ..." title) instead of an opaque id.
  const chunkTextById = new Map(unit.chunk_attributions.map((c) => [c.chunk_id, c.chunk_text]));
  const srcTag = (s: SourceAttribution) => {
    if (s.origin === "instruction") return "system instruction";
    const text = chunkTextById.get(s.chunk_id);
    return (text && chunkTitle(text)) || docLabel(s.doc_id) + (s.chunk_id ? " · #" + s.chunk_id.slice(0, 6) : "");
  };

  // The chunks this sentence used, for the collapsible full-text section (no bars).
  const usedChunks = unit.chunk_attributions;
  const toggleChunk = (i: number) =>
    setOpenChunks((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  return (
    <div className="drawer">
      <div className="drawer-top">
        <button className="drawer-close" onClick={onClose} title="Back to overall" aria-label="Back to overall">
          ✕
        </button>
      </div>
      {/* strength block: value + band word, then the support (green) / against
          (red) diverging bar — mirrors the batch report (tools/render.py). The
          selected sentence is already highlighted on the left, so it isn't
          reprinted here. */}
      <div className="strength">
        <div className="sval">
          {rel.support.toFixed(2)}
          <span className="sw">{strengthWord(rel.relative_strength)}</span>
          {rel.dominant_lane === "instruction" && (
            <span className="sval-instr">driven by instruction</span>
          )}
        </div>
        <div className="dv">
          <div className="dv-l">
            <span style={{ width: `${agW}%` }} />
          </div>
          <div className="dv-r">
            <span style={{ width: `${supW}%` }} />
          </div>
        </div>
        <div className="dv-lab">
          <span>◀ against {rel.against.toFixed(2)}</span>
          <span>support {rel.support.toFixed(2)} ▶</span>
        </div>
      </div>

      {sources.length === 0 ? (
        <p className="drawer-empty">Nothing moved this sentence — it came from the model's own priors.</p>
      ) : (
        <>
          <h5>Sources, ranked by attribution strength</h5>
          {sources.map((s, i) => {
            const hue = srcHue(s);
            const alpha = 0.1 + 0.72 * Math.min(Math.abs(s.score) / maxAbs, 1);
            return (
              <div className="src-row" key={i} style={{ background: `rgba(${hue}, ${alpha.toFixed(2)})` }}>
                <div className="src-row-head">
                  <span className="src-tag">{srcTag(s)}</span>
                  <span className="src-num" style={{ color: `rgb(${hue})` }}>
                    {s.score >= 0 ? "+" : ""}
                    {s.score.toFixed(1)}
                  </span>
                </div>
                <div className="src-row-text">{s.source_text}</div>
              </div>
            );
          })}
        </>
      )}

      {usedChunks.length > 0 && (
        <div className="fullchunks">
          <h5>Source chunks — full text</h5>
          {usedChunks.map((c, i) => (
            <div className="fc" key={c.chunk_id ?? i}>
              <button className="fc-toggle" onClick={() => toggleChunk(i)}>
                {openChunks.has(i) ? "▾" : "▸"} {chunkTitle(c.chunk_text) ?? docLabel(c.doc_id)}
              </button>
              {openChunks.has(i) && <div className="chunk-text">{c.chunk_text}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Piece 5 — assembly: the two-column inspector
// ---------------------------------------------------------------------------

export interface AttributionViewProps {
  summary: RecordSummary;
}

/**
 * The top-level view: left = highlighted response, right = inspector panel. The
 * panel is contextual — with no sentence selected it shows the whole-response
 * chunk shares; click a sentence and it swaps to that unit's source-level drawer
 * (✕ returns to the overview). Owns the `selected` state that ties the two
 * columns together; every child is otherwise a pure function of props.
 */
export function AttributionView({ summary }: AttributionViewProps) {
  const [selected, setSelected] = useState<number | null>(null);
  const { response, units, relative, whole_chunk_attributions } = summary;

  // Largest support-or-against across the record, so the drawer's diverging bar is
  // scaled consistently for every unit (matches tools/render.py).
  const scale = Math.max(1e-9, ...relative.flatMap((u) => [u.support, u.against]));

  // Guard a stale index (defensive — units is stable per summary in practice).
  const selectedUnit = selected != null && selected < units.length ? units[selected] : null;

  return (
    <div className="view">
      <div className="view-left">
        <AnnotatedAnswer
          response={response}
          units={units}
          relative={relative}
          selected={selectedUnit ? selected : null}
          onSelect={setSelected}
        />
      </div>
      <div className="view-right">
        {selectedUnit && selected != null ? (
          <UnitDrawer unit={selectedUnit} rel={relative[selected]} scale={scale} onClose={() => setSelected(null)} />
        ) : (
          <WholeChunks chunks={whole_chunk_attributions} />
        )}
      </div>
    </div>
  );
}
