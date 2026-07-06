/**
 * AttributionView — turns a RecordSummary into the visual.
 *
 * Built in pieces:
 *   1. calibration + bucketing logic  (this piece — the "numbers")
 *   2. the annotated answer            (shaded, clickable units)
 *   3. the overall descriptive count
 *   4. the drill-in drawer
 *
 * Everything score-related is decided here, then handed to the JSX as inline
 * styles / class names (styles.ts only paints chrome — see its header).
 *
 * Terminology (locked): units are "attributed" to context by causal dependence
 * — NOT "grounded" (groundedness needs NLI, not wired). So the buckets are
 * unattributed / weakly / moderately / strongly attributed.
 */

import { useState } from "react";
import type { CSSProperties } from "react";

import type { ChunkAttribution, RecordSummary, SourceAttribution, UnitSummary } from "./types";

// ---------------------------------------------------------------------------
// Piece 1 — calibration + bucketing (the "numbers")
// ---------------------------------------------------------------------------

/**
 * The tunable thresholds, in ONE place so a recalibration is a one-object edit
 * (or a `calibration` prop at integration time — no package rebuild).
 *
 * Category edges are corpus PERCENTILES of per-unit `context_mass` (not
 * arbitrary thirds): "moderate" means "attributed more strongly than the median
 * unit, up to the 75th percentile" — an absolute, cross-answer statement,
 * unlike a within-answer max which would always crown some unit "strong".
 */
export interface Calibration {
  /** ≤ this = "weakly attributed". Corpus median of per-unit context_mass. */
  weakMax: number;
  /** ≤ this = "moderately"; above = "strongly". Corpus p75. */
  moderateMax: number;
  /** context_mass that renders full-intensity green. Opacity = min(mass/shadeCap, 1). */
  shadeCap: number;
}

/**
 * PROVISIONAL — do not trust as final. Derived from per-unit context_mass over
 * runs/batch_<timestamp>/results.json, but that sample is only ~33 distinct
 * records (re-run ~7×) and ~94% instruction-folded, whereas this widget runs
 * context-only. Retune recipe (full corpus, context-only, dedup) is in LOG.md
 * (2026-07-06). Rounded to signal the imprecision.
 */
export const DEFAULT_CALIBRATION: Calibration = {
  weakMax: 10, // ~median  (provisional)
  moderateMax: 35, // ~p75     (provisional)
  shadeCap: 50, // demo GREEN_MAX, for tool-wide consistency
};

export type Bucket = "unattributed" | "weak" | "moderate" | "strong";

/**
 * Which bucket a unit falls in, from its context_mass. The only principled edge
 * is 0 — the L1 zero-floor, where the fit itself says "no retrieved source moved
 * this unit". NOTE this is NOT a fabrication flag: the widget is context-only,
 * so mass≈0 is ambiguous — instruction-driven boilerplate/framing OR the model's
 * priors (telling them apart needs instruction ablation, which the live button
 * skips). Presented neutrally as "not attributed to context". The
 * weak/moderate/strong edges above 0 are the corpus percentiles from Calibration.
 */
export function bucketOf(mass: number, cal: Calibration): Bucket {
  if (mass <= 0) return "unattributed";
  if (mass <= cal.weakMax) return "weak";
  if (mass <= cal.moderateMax) return "moderate";
  return "strong";
}

/**
 * Green opacity for a unit's shading: linear in context_mass up to a fixed
 * absolute cap (shadeCap), then saturated. Fixed — NOT the per-answer max — so a
 * weakly-attributed answer renders pale and a strongly-attributed one solid,
 * comparably across answers. Unattributed (mass ≤ 0) gets 0: no green, the
 * dashed underline instead.
 */
export function shadeAlpha(mass: number, cal: Calibration): number {
  if (mass <= 0) return 0;
  return Math.min(mass / cal.shadeCap, 1);
}

export interface BucketTally {
  strong: number;
  moderate: number;
  weak: number;
  unattributed: number;
  total: number;
}

/** Count how many units land in each bucket — the raw material for the overall
 *  descriptive count. */
export function tallyBuckets(units: UnitSummary[], cal: Calibration): BucketTally {
  const t: BucketTally = { strong: 0, moderate: 0, weak: 0, unattributed: 0, total: units.length };
  for (const u of units) t[bucketOf(u.context_mass, cal)] += 1;
  return t;
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
  calibration: Calibration;
  selected: number | null;
  onSelect: (unitIndex: number) => void;
}

/**
 * The response, rendered as shaded clickable units. Each unit's green opacity is
 * its `shadeAlpha` (fixed-cap, so it reads honestly across answers); unattributed
 * units get no fill and the dashed underline (via the `unattributed` class).
 * Clicking a unit only reports the selection up via `onSelect` — this component
 * holds no state; the parent decides what the click reveals (the drawer).
 */
function AnnotatedAnswer({ response, units, calibration, selected, onSelect }: AnnotatedAnswerProps) {
  return (
    <div className="answer">
      {segments(response, units).map((seg, i) => {
        // Plain-text gap between units — render as-is, not interactive.
        if (seg.unitIndex === null) return <span key={i}>{seg.text}</span>;

        const idx = seg.unitIndex;
        const unit = units[idx];
        const bucket = bucketOf(unit.context_mass, calibration);
        const alpha = shadeAlpha(unit.context_mass, calibration);

        const className =
          "unit" +
          (bucket === "unattributed" ? " unattributed" : "") +
          (idx === selected ? " selected" : "");

        // Score-driven green is applied INLINE here (styles.ts only knows the hue).
        const style: CSSProperties = alpha > 0 ? { background: `rgba(34, 160, 94, ${alpha.toFixed(3)})` } : {};

        return (
          <span
            key={i}
            className={className}
            style={style}
            onClick={() => onSelect(idx)}
            title={`${bucket} · context_mass ${unit.context_mass.toFixed(1)}`}
          >
            {seg.text}
          </span>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Piece 3 — the overall descriptive count
// ---------------------------------------------------------------------------

/** The buckets in display order (strongest → none), with their proportion-bar
 *  class and human label. Drives both the bar segments and the legend. */
const COUNT_SEGMENTS: { bucket: Exclude<Bucket, never>; cls: string; label: string }[] = [
  { bucket: "strong", cls: "seg-strong", label: "strongly attributed" },
  { bucket: "moderate", cls: "seg-moderate", label: "moderately attributed" },
  { bucket: "weak", cls: "seg-weak", label: "weakly attributed" },
  { bucket: "unattributed", cls: "seg-unattributed", label: "not attributed to context" },
];

/** The honest one-line summary, e.g.
 *  "4 of 6 sentences strongly attributed · 1 moderately · 1 not attributed to context".
 *  Descriptive count only — no verdict, no absolute score. */
function phraseCount(t: BucketTally): string {
  const s = t.total === 1 ? "sentence" : "sentences";
  const parts = [`${t.strong} of ${t.total} ${s} strongly attributed`];
  if (t.moderate) parts.push(`${t.moderate} moderately`);
  if (t.weak) parts.push(`${t.weak} weakly`);
  if (t.unattributed) parts.push(`${t.unattributed} not attributed to context`);
  return parts.join(" · ");
}

interface OverallCountProps {
  units: UnitSummary[];
  calibration: Calibration;
}

/**
 * The top summary strip: a descriptive count of how the answer's sentences fall
 * across the attribution buckets. This is the ONE aggregate view — the annotated
 * answer below already shows the continuous, in-place picture, so this earns its
 * space by summarizing, not repeating. "Unattributed" is shown neutrally (no
 * warning): context-only can't distinguish boilerplate/framing from priors.
 */
function OverallCount({ units, calibration }: OverallCountProps) {
  const t = tallyBuckets(units, calibration);
  if (t.total === 0) return null;

  return (
    <div className="overall">
      <h4>Overall attribution</h4>

      <p className="count-lead">
        <b>{t.strong}</b> of {t.total} {t.total === 1 ? "sentence" : "sentences"} strongly attributed
        {t.unattributed > 0 ? ` · ${t.unattributed} not attributed to context` : ""}
      </p>

      {/* proportion bar: one segment per non-empty bucket, WIDTH = share of total */}
      <div className="count-bar" title={phraseCount(t)}>
        {COUNT_SEGMENTS.filter((s) => t[s.bucket] > 0).map((s) => (
          <span key={s.bucket} className={s.cls} style={{ width: `${(100 * t[s.bucket]) / t.total}%` }} />
        ))}
      </div>

      {/* legend: swatch + label + count, only for buckets present */}
      <div className="count-legend">
        {COUNT_SEGMENTS.filter((s) => t[s.bucket] > 0).map((s) => (
          <span key={s.bucket}>
            <span className={`sw ${s.cls}`} />
            {s.label} <b>{t[s.bucket]}</b>
          </span>
        ))}
      </div>

      {t.unattributed > 0 && (
        <p className="count-note">
          "Not attributed to context" sentences may be boilerplate/framing or the model's own wording —
          the live view doesn't run instruction analysis, so read them in context.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Piece 4 — whole-response chunks, part-to-whole (right panel, default state)
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
                {c.retrieval_score != null ? ` · retrieval ${c.retrieval_score.toFixed(2)}` : ""}
                {c.n_negative_sources > 0
                  ? ` · ${c.n_negative_sources} competing source${c.n_negative_sources === 1 ? "" : "s"}`
                  : ""}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Piece 5 — the per-unit source drawer (right panel, selected state)
// ---------------------------------------------------------------------------

interface UnitDrawerProps {
  unit: UnitSummary;
  calibration: Calibration;
  onClose: () => void;
}

/**
 * The inspector's SELECTED state: the source fragments that drove ONE clicked
 * sentence — source-forward (raw per-fragment scores), because at the unit level
 * a sentence is usually driven by one specific fragment and a chunk rollup would
 * dilute it. Three-way split of the unit's sources:
 *   positive → shown, ranked, bar relative to the top source in THIS unit;
 *   negative → collapsed ("competing sources" — collinear/competing, on demand);
 *   neutral (≈0) → omitted (the null case), only counted.
 * Each source carries its provenance (which document/chunk), and its full parent
 * chunk_text is available on demand for context.
 */
function UnitDrawer({ unit, calibration, onClose }: UnitDrawerProps) {
  const [showNegatives, setShowNegatives] = useState(false);
  const [openChunks, setOpenChunks] = useState<Set<number>>(() => new Set());

  // context sources only (instruction lane is empty today, but be explicit)
  const sources = unit.source_attributions.filter((s) => s.origin !== "instruction");
  const positives = sources.filter((s) => s.score > 0).sort((a, b) => b.score - a.score);
  const negatives = sources.filter((s) => s.score < 0).sort((a, b) => a.score - b.score);
  const topScore = positives.length ? positives[0].score : 1;

  // chunk_id -> full chunk_text, for the on-demand "see full chunk".
  const chunkText = new Map<string | null, string>();
  for (const c of unit.chunk_attributions) chunkText.set(c.chunk_id, c.chunk_text);

  const bucket = bucketOf(unit.context_mass, calibration);
  const strengthLabel = bucket === "unattributed" ? "not attributed to context" : `${bucket}ly attributed`;

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
        <b>{strengthLabel}</b> · context_mass {unit.context_mass.toFixed(1)}
      </div>

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
// Piece 6 — assembly: the two-column inspector
// ---------------------------------------------------------------------------

export interface AttributionViewProps {
  summary: RecordSummary;
  /** Override the provisional bucket/shade thresholds (see DEFAULT_CALIBRATION). */
  calibration?: Calibration;
}

/**
 * The top-level view: left = highlighted response, right = inspector panel. The
 * panel is contextual — with no sentence selected it shows the overview
 * (OverallCount + WholeChunks, both aggregate/chunk-level); click a sentence and
 * it swaps to that unit's source-level drawer (✕ returns to overview). Owns the
 * `selected` state that ties the two columns together; every child is otherwise
 * a pure function of props.
 */
export function AttributionView({ summary, calibration = DEFAULT_CALIBRATION }: AttributionViewProps) {
  const [selected, setSelected] = useState<number | null>(null);
  const { response, units, whole_chunk_attributions } = summary;

  // Guard a stale index (defensive — units is stable per summary in practice).
  const selectedUnit = selected != null && selected < units.length ? units[selected] : null;

  return (
    <div className="view">
      <div className="view-left">
        <AnnotatedAnswer
          response={response}
          units={units}
          calibration={calibration}
          selected={selectedUnit ? selected : null}
          onSelect={setSelected}
        />
      </div>
      <div className="view-right">
        {selectedUnit ? (
          <UnitDrawer unit={selectedUnit} calibration={calibration} onClose={() => setSelected(null)} />
        ) : (
          <>
            <OverallCount units={units} calibration={calibration} />
            <WholeChunks chunks={whole_chunk_attributions} />
          </>
        )}
      </div>
    </div>
  );
}
