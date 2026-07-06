/**
 * The widget's stylesheet, as a string injected once into the Shadow DOM.
 *
 * Because it lives inside a shadow root, these rules are fully isolated: the
 * host app's CSS can't reach in and ours can't leak out. That's why the
 * selectors are plain, un-prefixed class names — there's no global namespace to
 * collide with. `:host` targets the widget's own host element in the host page.
 *
 */

export const STYLES = `
:host {
  /* Design tokens. --grn is the single accent hue; its alpha is applied inline
     (score-driven) by AttributionView, or via the fixed chrome rules below. */
  --grn: 34, 160, 94;
  --ink: #1f2328;
  --muted: #656d76;
  --line: #d0d7de;
  --bg: #ffffff;
  --panel: #f6f8fa;
  --radius: 10px;

  all: initial;                 /* hard reset: don't inherit host page fonts/colours */
  display: block;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  color: var(--ink);
}

* { box-sizing: border-box; }

.card {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--bg);
  padding: 14px 16px;
  max-width: 100%;
}

/* --- Two-column inspector layout ----------------------------------------- */
/* Left = highlighted response, right = inspector panel. Stacks to one column
   when the host container is narrow (container query, falls back gracefully). */
.view {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}
@media (min-width: 680px) {
  .view { grid-template-columns: minmax(0, 1fr) minmax(0, 380px); }
}
.view-left { min-width: 0; }
.view-right {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel);
  padding: 12px 14px;
  align-self: start;
}

/* --- The on-demand trigger + its transient states ------------------------- */

.trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  color: var(--ink);
  font: inherit;
  font-weight: 600;
  padding: 8px 14px;
  cursor: pointer;
}
.trigger:hover { background: #eef1f4; }
.trigger:disabled { opacity: 0.6; cursor: default; }

.status {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  font-size: 13px;
}
.spinner {
  width: 14px; height: 14px;
  border: 2px solid var(--line);
  border-top-color: rgb(var(--grn));
  border-radius: 50%;
  animation: dare-spin 0.8s linear infinite;
}
@keyframes dare-spin { to { transform: rotate(360deg); } }

.error {
  border: 1px solid #ffc1c0;
  background: #fff5f5;
  color: #b3261e;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
}
.error button {
  margin-top: 8px;
  font: inherit;
  font-size: 12px;
  border: 1px solid #ffc1c0;
  background: #fff;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
}

/* --- Overall descriptive count ------------------------------------------- */

.overall { margin-bottom: 12px; }
.overall h4, .chunks h4 {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--muted);
}

/* --- Whole-response chunks (part-to-whole shares) ------------------------ */
.chunks { margin-top: 14px; border-top: 1px solid var(--line); padding-top: 12px; }
.chunk-doc { color: var(--ink); font-size: 12.5px; word-break: break-word; }
.chunk-share { font-variant-numeric: tabular-nums; font-weight: 700; white-space: nowrap; }
/* stacked proportion bar: one segment per bucket. WIDTHS are set inline from
   the bucket tallies (data); the segment COLOURS below are fixed bucket keys. */
.count-bar {
  display: flex;
  height: 8px;
  border-radius: 5px;
  overflow: hidden;
  background: var(--panel);
}
.count-bar span { display: block; height: 100%; }
.seg-strong    { background: rgba(var(--grn), 0.9); }
.seg-moderate  { background: rgba(var(--grn), 0.55); }
.seg-weak      { background: rgba(var(--grn), 0.25); }
.seg-unattributed{ background: repeating-linear-gradient(45deg, #e7ebef, #e7ebef 3px, #fff 3px, #fff 6px); }

.count-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: 8px;
  font-size: 12.5px;
  color: var(--muted);
}
.count-legend b { color: var(--ink); font-variant-numeric: tabular-nums; }
.count-legend .sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: middle; }
/* hero line of the descriptive count */
.count-lead { font-size: 13.5px; color: var(--ink); margin-bottom: 8px; }
.count-lead b { font-weight: 700; }

/* --- Annotated answer ---------------------------------------------------- */

.answer {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 15px;
  line-height: 2;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}
/* .unit = base chrome; the score-driven background opacity is set INLINE by
   AttributionView (min(context_mass / shadeCap, 1)). Unattributed units (mass<=0)
   get no inline background and the dashed underline below instead. */
.unit {
  border-radius: 4px;
  padding: 1px 2px;
  cursor: pointer;
  transition: outline-color 0.1s;
}
.unit:hover  { outline: 2px solid rgba(var(--grn), 0.9); }
.unit.selected { outline: 2px solid rgba(var(--grn), 0.9); }
.unit.unattributed { border-bottom: 2px dashed var(--muted); }

.hint { margin-top: 8px; font-size: 12px; color: var(--muted); }

/* --- Drill-in drawer (opens inline below the answer) --------------------- */

/* the drawer has no box of its own — it lives inside .view-right, which is the panel */
.drawer { min-width: 0; }
.drawer-quote {
  font-size: 14px;
  font-style: italic;
  color: var(--ink);
  margin-bottom: 6px;
}
.drawer-strength { font-size: 12.5px; color: var(--muted); margin-bottom: 12px; }
.drawer-strength b { color: var(--ink); }
.drawer h5 {
  margin: 0 0 8px;
  font-size: 11.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--muted);
}

/* one grounding chunk: label + strength number, a bar whose WIDTH is set inline
   from positive_mass, then the full verbatim chunk_text and its metadata. */
.chunk { margin: 10px 0; }
.chunk-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  font-size: 12.5px;
  margin-bottom: 4px;
}
.chunk-id { font-family: ui-monospace, Menlo, Consolas, monospace; color: var(--muted); }
.chunk-mass { font-variant-numeric: tabular-nums; font-weight: 700; }
.chunk-track { height: 8px; background: #fff; border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }
.chunk-track span { display: block; height: 100%; background: rgba(var(--grn), 0.85); }
.chunk-text {
  margin-top: 6px;
  font-size: 12.5px;
  color: var(--ink);
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 8px;
  max-height: 140px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
.chunk-meta { margin-top: 4px; font-size: 11.5px; color: var(--muted); }

.drawer-empty { font-size: 13px; color: var(--muted); }

/* drawer header row: quote + ✕ back-to-overall */
.drawer-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.drawer-close { border: none; background: transparent; color: var(--muted); font-size: 16px; line-height: 1; cursor: pointer; padding: 2px 4px; border-radius: 4px; }
.drawer-close:hover { background: var(--panel); color: var(--ink); }

/* one source fragment row (the per-unit drill-down) */
.src { margin: 10px 0; }
.src-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; font-size: 12.5px; margin-bottom: 4px; }
.src-doc { color: var(--ink); word-break: break-word; }
.src-score { font-variant-numeric: tabular-nums; font-weight: 700; white-space: nowrap; }
.src-score.neg { color: #b3261e; }
.src-text { margin-top: 6px; font-size: 12.5px; color: var(--ink); background: #fff; border: 1px solid var(--line); border-radius: 6px; padding: 6px 8px; white-space: pre-wrap; word-break: break-word; }
.src-more { margin-top: 4px; font: inherit; font-size: 11.5px; color: rgb(var(--grn)); background: none; border: none; padding: 0; cursor: pointer; text-decoration: underline; }
.src-count { margin-top: 10px; font-size: 11.5px; color: var(--muted); }

/* collapsed "competing sources" (negatives) */
.competing { margin-top: 12px; border-top: 1px dashed var(--line); padding-top: 8px; }
.competing-toggle { font: inherit; font-size: 12px; color: var(--muted); background: none; border: none; padding: 0; cursor: pointer; }
.competing-toggle:hover { color: var(--ink); }
.competing-note { font-size: 11.5px; color: var(--muted); margin: 6px 0; }
.competing-src { opacity: 0.85; }

/* header shown once loaded: title + ✕ to collapse back to the trigger */
.wm-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.wm-title { font-weight: 700; font-size: 14px; }

.footer { margin-top: 12px; font-size: 11px; color: var(--muted); }
`;
