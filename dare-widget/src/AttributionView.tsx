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

/**
 * A unit's fill: hue by dominant lane, opacity by its per-record relative
 * strength — linear 0.06 → 0.91 in `relative_strength` (the same curve as
 * render.py's `0.06 + 0.85 * strength`). A "none" lane (no positive support)
 * gets no fill; the dashed `unattributed` underline stands in instead.
 */
function shadeStyle(rel: UnitRelative): CSSProperties {
  const hue = LANE_HUE[rel.dominant_lane];
  if (!hue || rel.relative_strength <= 0) return {};
  const alpha = 0.06 + 0.85 * rel.relative_strength;
  return { background: `rgba(${hue}, ${alpha.toFixed(3)})` };
}

/** Human label for a unit's lane, used in the tooltip and drawer. */
function laneLabel(lane: UnitRelative["dominant_lane"]): string {
  if (lane === "instruction") return "instruction-driven";
  if (lane === "context") return "context-driven";
  return "not attributed to context";
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
  const positive = chunks.filter((c) => c.positive_mass > 0);
  const total = positive.reduce((sum, c) => sum + c.positive_mass, 0);

  return (
    <div className="chunks">
      <h4>Chunks that influenced this answer</h4>
      {total === 0 ? (
        <p className="drawer-empty">No retrieved chunk positively influenced this answer.</p>
      ) : (
        positive.map((c, i) => {
          const pct = Math.round((100 * c.positive_mass) / total);
          return (
            <div className="chunk" key={c.chunk_id ?? i}>
              <div className="chunk-head">
                <span className="chunk-doc">
                  {docLabel(c.doc_id)}
                  {c.chunk_id ? <span className="chunk-id"> · #{c.chunk_id.slice(0, 6)}</span> : null}
                </span>
                <span className="chunk-share">{pct}%</span>
              </div>
              {/* part-to-whole: fill width = this chunk's share of total positive mass */}
              <div className="chunk-track">
                <span style={{ width: `${((100 * c.positive_mass) / total).toFixed(1)}%` }} />
              </div>
              <div className="chunk-text">{c.chunk_text}</div>
              <div className="chunk-meta">
                {pct}% of grounding · positive_mass {c.positive_mass.toFixed(1)}
              </div>
            </div>
          );
        })
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
function UnitDrawer({ unit, rel, onClose }: UnitDrawerProps) {
  const [showNegatives, setShowNegatives] = useState(false);
  const [openChunks, setOpenChunks] = useState<Set<number>>(() => new Set());

  // context lane (retrieved chunks) vs instruction lane (folded system prompt)
  const sources = unit.source_attributions.filter((s) => s.origin !== "instruction");
  const positives = sources.filter((s) => s.score > 0).sort((a, b) => b.score - a.score);
  const negatives = sources.filter((s) => s.score < 0).sort((a, b) => a.score - b.score);
  const topScore = positives.length ? positives[0].score : 1;

  const instrRows = unit.instruction_attributions
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score);

  // chunk_id -> full chunk_text, for the on-demand "see full chunk".
  const chunkText = new Map<string | null, string>();
  for (const c of unit.chunk_attributions) chunkText.set(c.chunk_id, c.chunk_text);

  const toggleChunk = (i: number) =>
    setOpenChunks((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  const provenance = (s: SourceAttribution) => (
    <span className="src-doc">
      {docLabel(s.doc_id)}
      {s.chunk_id ? <span className="chunk-id"> · #{s.chunk_id.slice(0, 6)}</span> : null}
    </span>
  );

  return (
    <div className="drawer">
      <div className="drawer-top">
        <div className="drawer-quote">"{unit.text.trim()}"</div>
        <button className="drawer-close" onClick={onClose} title="Back to overall" aria-label="Back to overall">
          ✕
        </button>
      </div>
      <div className="drawer-strength">
        <b>{laneLabel(rel.dominant_lane)}</b> · support {rel.support.toFixed(1)}
        {rel.against > 0 ? ` · against ${rel.against.toFixed(1)}` : ""}
      </div>

      {/* instruction lane — the folded synthesis prompt's causal effect on this unit */}
      {rel.instruction_mass > 0 && (
        <div className="instr-lane">
          <h5>Synthesis instruction</h5>
          <div className="src">
            <div className="src-head">
              <span className="src-doc">instruction prompt</span>
              <span className="src-score" style={{ color: "#8a6d2b" }}>
                {rel.instruction_mass.toFixed(1)}
              </span>
            </div>
            <div className="src-text">
              {instrRows.length ? instrRows[0].source_text : "(synthesis prompt directive)"}
            </div>
          </div>
        </div>
      )}

      {positives.length === 0 ? (
        <p className="drawer-empty">No sources attributed to context for this sentence.</p>
      ) : (
        <>
          <h5>Sources that drove this sentence</h5>
          {positives.map((s, i) => (
            <div className="src" key={i}>
              <div className="src-head">
                {provenance(s)}
                <span className="src-score">{s.score.toFixed(1)}</span>
              </div>
              {/* bar relative to the strongest source in THIS unit (within-unit is fine here) */}
              <div className="chunk-track">
                <span style={{ width: `${((100 * s.score) / topScore).toFixed(1)}%` }} />
              </div>
              <div className="src-text">{s.source_text}</div>
              <button className="src-more" onClick={() => toggleChunk(i)}>
                {openChunks.has(i) ? "hide full chunk" : "see full chunk"}
              </button>
              {openChunks.has(i) && <div className="chunk-text">{chunkText.get(s.chunk_id) ?? s.source_text}</div>}
            </div>
          ))}
          <p className="src-count">
            {positives.length} of {sources.length} fragments drove this sentence
          </p>
        </>
      )}

      {negatives.length > 0 && (
        <div className="competing">
          <button className="competing-toggle" onClick={() => setShowNegatives((v) => !v)}>
            {showNegatives ? "▾" : "▸"} {negatives.length} competing source{negatives.length === 1 ? "" : "s"} (−)
          </button>
          {showNegatives && (
            <>
              <p className="competing-note">
                Negative scores are competing or near-duplicate (collinear) fragments — not drivers of this
                sentence.
              </p>
              {negatives.map((s, i) => (
                <div className="src competing-src" key={i}>
                  <div className="src-head">
                    {provenance(s)}
                    <span className="src-score neg">{s.score.toFixed(1)}</span>
                  </div>
                  <div className="src-text">{s.source_text}</div>
                </div>
              ))}
            </>
          )}
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
          <UnitDrawer unit={selectedUnit} rel={relative[selected]} onClose={() => setSelected(null)} />
        ) : (
          <WholeChunks chunks={whole_chunk_attributions} />
        )}
      </div>
    </div>
  );
}
