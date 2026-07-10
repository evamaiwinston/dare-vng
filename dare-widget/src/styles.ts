/**
 * The widget's stylesheet, as a string injected once into the Shadow DOM.
 *
 * Because it lives inside a shadow root, these rules are fully isolated: the
 * host app's CSS can't reach in and ours can't leak out. That's why the
 * selectors are plain, un-prefixed class names — there's no global namespace to
 * collide with. `:host` targets the widget's own host element in the host page.
 *
 * The palette mirrors the batch report (tools/render.py) so the widget and the
 * report read as the same dark surface.
 */

export const STYLES = `
:host {
  /* Design tokens — the batch report's dark palette (tools/render.py :root).
     --grn/--ins/--neg are rgb TRIPLES; their alpha is applied inline
     (score-driven) by AttributionView, or via the fixed chrome rules below. */
  --grn: 126, 224, 192;   /* green = context lane / support */
  --ins: 242, 200, 121;   /* amber = instruction lane */
  --neg: 240, 138, 138;   /* red   = against */
  --ink: #e7e9f3;
  --muted: #9aa0bd;
  --line: #2a2f4a;
  --accent: #6ea8fe;
  --bg: #0f1220;
  --panel: #171a2b;
  --track: #0a0c16;       /* inset groove behind bars */
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
.trigger:hover { background: #20263f; }
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
  border: 1px solid rgba(var(--neg), 0.5);
  background: rgba(var(--neg), 0.12);
  color: rgb(var(--neg));
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
}
.error button {
  margin-top: 8px;
  font: inherit;
  font-size: 12px;
  border: 1px solid rgba(var(--neg), 0.5);
  background: transparent;
  color: rgb(var(--neg));
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
}

/* --- Whole-response chunks (part-to-whole shares) ------------------------ */
.chunks h4 {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--muted);
}
.chunk-doc { color: var(--ink); font-size: 12.5px; word-break: break-word; }

/* --- Annotated answer ---------------------------------------------------- */

.answer {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 15px;
  line-height: 2;
  color: #f4f6ff;
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
.unit:hover  { outline: 2px solid var(--accent); }
.unit.selected { outline: 2px solid var(--accent); }
.unit.unattributed { border-bottom: 2px dashed var(--muted); }

/* --- Drill-in drawer (opens inline below the answer) --------------------- */

/* the drawer has no box of its own — it lives inside .view-right, which is the panel */
.drawer { min-width: 0; }
.drawer h5 {
  margin: 0 0 8px;
  font-size: 11.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--muted);
}

/* --- Strength block (matches the batch report's drawer) ------------------ */
.strength {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 11px;
  padding: 12px 14px;
  margin-bottom: 14px;
}
.sval { font-size: 24px; font-weight: 800; font-variant-numeric: tabular-nums; color: var(--ink); line-height: 1.2; }
.sval .sw { font-size: 13px; font-weight: 700; margin-left: 6px; color: var(--muted); }
.sval-instr { display: inline-block; margin-left: 8px; font-size: 11px; font-weight: 700; color: rgb(var(--ins)); border: 1px solid rgba(var(--ins), 0.5); border-radius: 999px; padding: 1px 8px; vertical-align: middle; }
.dv { display: flex; height: 14px; background: var(--track); border-radius: 5px; overflow: hidden; margin-top: 10px; }
.dv-l { flex: 1; display: flex; justify-content: flex-end; }
.dv-r { flex: 1; display: flex; justify-content: flex-start; border-left: 1px solid var(--line); }
.dv-l span { height: 100%; background: rgba(var(--neg), 0.8); }
.dv-r span { height: 100%; background: rgba(var(--grn), 0.85); }
.dv-lab { display: flex; justify-content: space-between; font-size: 11.5px; color: var(--muted); margin-top: 4px; }

/* per-sentence source rows — color-coded ± heat boxes (green support / red
   against / amber instruction), opacity by |score|; matches the batch report. */
.src-row { border-radius: 8px; padding: 7px 9px; margin: 7px 0; border: 1px solid var(--line); }
.src-row-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; font-size: 12px; }
.src-tag { color: var(--ink); font-weight: 600; word-break: break-word; }
.src-num { font-variant-numeric: tabular-nums; font-weight: 800; white-space: nowrap; }
.src-row-text { margin-top: 5px; font-size: 12.5px; color: var(--ink); white-space: pre-wrap; word-break: break-word; }

/* collapsible full source chunks at the drawer bottom — no bars, just readable text */
.fullchunks { margin-top: 14px; border-top: 1px dashed var(--line); padding-top: 10px; }
.fc { margin: 6px 0; }
.fc-toggle { font: inherit; font-size: 12.5px; color: var(--ink); background: none; border: none; padding: 0; cursor: pointer; text-align: left; }
.fc-toggle:hover { color: #fff; }

/* one influential chunk in the overview / a source chunk's full text: just its
   tag (doc + id) and the full verbatim chunk_text — no bars or numbers. */
.chunk { margin: 10px 0; }
.chunk-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  font-size: 12.5px;
  margin-bottom: 4px;
}
.chunk-text {
  margin-top: 6px;
  font-size: 12.5px;
  color: var(--ink);
  background: var(--track);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 8px;
  max-height: 140px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
.drawer-empty { font-size: 13px; color: var(--muted); }

/* drawer header row: just the ✕ back-to-overall (the sentence is already
   highlighted on the left, so it isn't reprinted here). */
.drawer-top { display: flex; justify-content: flex-end; align-items: flex-start; gap: 8px; margin-bottom: 6px; }
.drawer-close { border: none; background: transparent; color: var(--muted); font-size: 16px; line-height: 1; cursor: pointer; padding: 2px 4px; border-radius: 4px; }
.drawer-close:hover { background: var(--panel); color: var(--ink); }

/* header shown once loaded: title + ✕ to collapse back to the trigger */
.wm-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.wm-title { font-weight: 700; font-size: 14px; }

.footer { margin-top: 12px; font-size: 11px; color: var(--muted); }
`;
