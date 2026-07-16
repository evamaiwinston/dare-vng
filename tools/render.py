#!/usr/bin/env python3
"""THROWAWAY PROTOTYPE — annotated-answer report renderer.

Reads an existing runs/batch_*/results.json (zero API calls, pure read of cached
output) and writes one self-contained HTML file.

Design (v3 — strength-first):
  - Each answer sentence is shaded by OPACITY = its TOTAL attribution strength
    (context + instruction), normalised within the answer. Pale = weakly attributed
    (the model wrote it from priors); solid = strongly attributed.
  - Click a unit -> the drawer leads with that strength, then shows WHAT IT'S MADE OF:
    one bar per grounding chunk + the instruction lane as its own bar, summing to the
    strength. So a weak sentence drills into empty bars; a strong one into a lit bar
    (context = green, instruction = amber). The click always tracks the shade.

Nothing in dare/ imports this; nothing here imports dare/. If the form is wrong, delete it.

    python tools/render.py                              # defaults to the 0702 run
    python tools/render.py runs/batch_20260702_094705   # any run dir
    open dare_report.html
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

DEFAULT_RUN = "runs/batch_20260702_094705"
SIDECAR = Path("translations.json")

# VN->EN map (populated in main from translations.json if present). English is shown
# as the readable text; the original VN rides along in a title tooltip. Empty => VN only.
TR: dict[str, str] = {}


def esc(s: str) -> str:
    return html.escape(s or "").replace("\n", "<br>")


def en(s: str) -> str:
    """English gloss if we have one, else the original."""
    return TR.get(s, s)


def doc_label(doc_id: str | None) -> str:
    """A short, readable label for a document id/path (basename, truncated).
    Mirrors AttributionView.tsx's docLabel()."""
    if not doc_id:
        return "unknown source"
    base = doc_id.rsplit("/", 1)[-1]
    return base[:44] + "…" if len(base) > 44 else base


def chunk_title(text: str) -> str | None:
    """The chunk's section title = its first markdown heading line, else its
    first non-empty line. Mirrors AttributionView.tsx's chunkTitle()."""
    first = next((l.strip() for l in (text or "").split("\n") if l.strip()), None)
    if not first:
        return None
    m = re.match(r"^#{1,6}\s+(.*)$", first)
    return (m.group(1) if m else first).strip()


def segments(response: str, units: list[dict]):
    """Walk the response, emitting (text, unit_index_or_None). Gaps between unit
    spans (the newlines between bullets) come back as plain, un-highlighted text."""
    segs, cursor = [], 0
    for i, u in enumerate(units):
        s, e = u["span"]
        if s > cursor:
            segs.append((response[cursor:s], None))
        segs.append((response[s:e], i))
        cursor = e
    if cursor < len(response):
        segs.append((response[cursor:], None))
    return segs


def render_record(r: dict) -> tuple[str, dict]:
    """Return (html_section, {unit_idx: detail_dict}) for one record."""
    s = r["summary"]
    rid = s["record_id"]
    units = s["units"]

    # opacity is normalised WITHIN the record: the strongest-attributed unit (either
    # lane) = full ink, so the weak-in-both sentences come out palest.
    max_total = max(((u["context_mass"] + u["instruction_mass"]) for u in units), default=1.0) or 1.0

    spans_html = []
    details: dict[int, dict] = {}
    for text, idx in segments(s["response"], units):
        if idx is None:
            spans_html.append(esc(text))
            continue
        u = units[idx]
        total = u["context_mass"] + u["instruction_mass"]          # = support (Σ positive)
        against = sum(-a["score"] for a in (u.get("source_attributions") or []) if a["score"] < 0)

        # hue = which lane drove the sentence (green context / amber instruction),
        # except a context-dominant unit that's net-contradicted (against > total)
        # shades red instead. Opacity = strength, same gradient for all three hues.
        # instruction-main when the instruction lane outweighs the strongest single chunk.
        max_chunk = max((c["positive_mass"] for c in (u.get("chunk_attributions") or [])), default=0.0)
        instr_main = u["instruction_mass"] > 0 and u["instruction_mass"] >= max_chunk

        if total > 0:
            if instr_main:
                hue = "242,200,121"
            elif against > total:
                hue = "240,138,138"
            else:
                hue = "126,224,192"
            alpha = 0.06 + 0.85 * (total / max_total)
            css = f"background:rgba({hue},{alpha:.2f})"
            style = "unit"
        else:
            css = ""
            style = "unit nocontext"

        vn_title = html.escape(" ".join(u["text"].split()))
        spans_html.append(
            f'<span class="{style}" style="{css}" title="{vn_title}" data-rid="{rid}" data-idx="{idx}">{esc(en(u["text"]))}</span>'
        )

        # source rows: every fragment (context + folded instruction, positive AND
        # negative), ranked by |score| — matches the widget's UnitDrawer `sources`.
        chunk_text_by_id = {c["chunk_id"]: c["chunk_text"] for c in (u.get("chunk_attributions") or [])}

        def src_tag(a: dict) -> str:
            if a.get("origin") == "instruction":
                return "system instruction"
            text = chunk_text_by_id.get(a["chunk_id"])
            title = text and chunk_title(text)
            if title:
                return title
            label = doc_label(a["doc_id"])
            return label + (" · #" + a["chunk_id"][:6] if a.get("chunk_id") else "")

        details[idx] = {
            "text": en(u["text"]),
            "support": round(total, 2),
            "against": round(against, 2),
            "instr_main": instr_main,
            "sources": [
                {"score": round(a["score"], 2), "text": en(a["source_text"]),
                 "instr": a.get("origin") == "instruction", "tag": src_tag(a)}
                for a in sorted(
                    (a for a in (u.get("source_attributions") or []) if a["score"] != 0),
                    key=lambda a: -abs(a["score"]),
                )[:8]
            ],
            # every source chunk this sentence used, full verbatim text, for the
            # collapsible "Source chunks" section — matches the widget 1:1.
            "chunks": [
                {"title": chunk_title(c["chunk_text"]) or doc_label(c["doc_id"]), "text": en(c["chunk_text"])}
                for c in (u.get("chunk_attributions") or [])
            ],
        }

    section = (
        f'<section class="rec" id="{rid}">'
        f'<h2>{esc(rid)}</h2>'
        f'<p class="q" title="{html.escape(" ".join(s["query"].split()))}"><b>Q:</b> {esc(en(s["query"]))}</p>'
        f'<div class="answer">{"".join(spans_html)}</div>'
        f"</section>"
    )
    return section, details


def main():
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_RUN)
    results = json.loads((run / "results.json").read_text())
    ok = [r for r in results if "error" not in r]

    global TR
    if SIDECAR.exists():
        TR = json.loads(SIDECAR.read_text())

    nav = "".join(f'<a href="#{r["summary"]["record_id"]}">{r["summary"]["record_id"]}</a>' for r in ok)
    sections, all_details = [], {}
    for r in ok:
        sec, det = render_record(r)
        sections.append(sec)
        all_details[r["summary"]["record_id"]] = det

    data_json = json.dumps(all_details, ensure_ascii=False)

    doc = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DARE — attribution strength ({run.name})</title>
<style>
  :root{{--bg:#0f1220;--panel:#171a2b;--ink:#e7e9f3;--muted:#9aa0bd;--line:#2a2f4a;--accent:#6ea8fe;
    --pos:126,224,192;--ins:242,200,121;--neg:240,138,138}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);
    font:15.5px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}}
  code{{font-family:Menlo,Consolas,monospace;font-size:.82em;color:var(--muted)}}
  .wrap{{display:grid;grid-template-columns:170px 1fr 390px;max-width:1460px;margin:0 auto}}
  nav{{position:sticky;top:0;height:100vh;overflow:auto;padding:20px 12px;border-right:1px solid var(--line);background:#0c0e1a}}
  nav b{{font-size:13px;letter-spacing:.5px}}
  nav a{{display:block;color:var(--muted);padding:4px 8px;border-radius:6px;font-size:13px;text-decoration:none}}
  nav a:hover{{background:var(--panel);color:var(--ink)}}
  main{{padding:24px 30px 120px;min-width:0}}
  header.hero{{border:1px solid var(--line);background:var(--panel);border-radius:14px;padding:18px 22px;margin-bottom:20px}}
  header.hero h1{{margin:0 0 6px;font-size:22px}}
  header.hero p{{margin:.3em 0;color:var(--muted);font-size:13.5px;max-width:84ch}}
  .ramp{{display:inline-block;width:150px;height:12px;border-radius:3px;vertical-align:middle;
    background:linear-gradient(90deg,rgba(var(--pos),.06),rgba(var(--pos),.9))}}
  section.rec{{border:1px solid var(--line);background:var(--panel);border-radius:14px;padding:18px 22px;margin:16px 0;scroll-margin-top:14px}}
  section.rec h2{{margin:0 0 4px;font-size:16px;color:var(--accent);font-family:Menlo,monospace}}
  .q{{color:var(--muted);font-size:13.5px;margin:0 0 14px}}
  .answer{{font-size:16.5px;line-height:2.15;color:#f4f6ff}}
  .unit{{border-radius:4px;padding:1px 3px;cursor:pointer}}
  .unit:hover{{outline:2px solid var(--accent)}}
  .unit.sel{{outline:2px solid var(--accent)}}
  .unit.nocontext{{border-bottom:2px dashed var(--muted)}}
  aside{{position:sticky;top:0;height:100vh;overflow:auto;padding:20px 16px;border-left:1px solid var(--line);background:#0c0e1a}}
  aside .ph{{color:var(--muted);font-size:13.5px;line-height:1.5}}
  aside h3{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin:18px 0 6px}}
  .uq{{font-size:14.5px;margin-bottom:12px}}
  .strength{{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:12px 14px}}
  .sval{{font-size:24px;font-weight:800;font-variant-numeric:tabular-nums}}
  .sval .sw{{font-size:13px;font-weight:700;margin-left:6px}}
  .sbar{{height:8px;background:#0a0c16;border-radius:5px;overflow:hidden;margin:8px 0 0}}
  .sbar span{{display:block;height:100%;background:rgba(var(--pos),.85)}}
  .dv{{display:flex;height:14px;background:#0a0c16;border-radius:5px;overflow:hidden;margin:10px 0 0}}
  .dv-l{{flex:1;display:flex;justify-content:flex-end}}
  .dv-r{{flex:1;display:flex;justify-content:flex-start;border-left:1px solid var(--line)}}
  .dv-l span{{height:100%;background:rgba(var(--neg),.8)}}
  .dv-r span{{height:100%;background:rgba(var(--pos),.85)}}
  .dv-lab{{display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);margin-top:3px}}
  .sval-instr{{display:inline-block;margin-left:8px;font-size:11px;font-weight:700;color:rgb(var(--ins));border:1px solid rgba(var(--ins),.5);border-radius:999px;padding:1px 8px;vertical-align:middle}}
  .num{{font-variant-numeric:tabular-nums;font-weight:700}}
  .neg{{color:rgb(var(--neg))}}
  .pos{{color:rgb(var(--pos))}}
  .badge{{display:inline-block;background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:2px 10px;font-size:12px;color:var(--muted)}}
  /* per-sentence source rows + collapsible full chunks — mirrors the widget's
     UnitDrawer (dare-widget/src/styles.ts) so both surfaces read identically. */
  .src-row{{border-radius:8px;padding:7px 9px;margin:7px 0;border:1px solid var(--line)}}
  .src-row-head{{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font-size:12px}}
  .src-tag{{color:var(--ink);font-weight:600;word-break:break-word}}
  .src-num{{font-variant-numeric:tabular-nums;font-weight:800;white-space:nowrap}}
  .src-row-text{{margin-top:5px;font-size:12.5px;color:var(--ink);white-space:pre-wrap;word-break:break-word}}
  .fullchunks{{margin-top:14px;border-top:1px dashed var(--line);padding-top:10px}}
  .fc{{margin:6px 0}}
  .fc-toggle{{font:inherit;font-size:12.5px;color:var(--ink);background:none;border:none;padding:0;cursor:pointer;text-align:left}}
  .fc-toggle:hover{{color:#fff}}
  .fc-text{{margin-top:6px;font-size:12.5px;color:var(--ink);background:#0a0c16;border:1px solid var(--line);border-radius:6px;padding:6px 8px;max-height:140px;overflow:auto;white-space:pre-wrap;word-break:break-word}}
  .drawer-empty{{font-size:13px;color:var(--muted)}}
</style></head>
<body><div class="wrap">
<nav><b>RECORDS</b>{nav}</nav>
<main>
  <header class="hero">
    <h1>Attribution strength <span class="badge">{run.name}</span></h1>
    <p>Each sentence is shaded by <b>how strongly the provided material drove it</b> (opacity = strength,
       within each answer: pale <span class="ramp"></span> strong). The <b>hue is the lane</b>:
       <span style="background:rgba(var(--pos),.5);padding:0 5px;border-radius:3px">green = context-driven</span>,
       <span style="background:rgba(var(--ins),.5);padding:0 5px;border-radius:3px">amber = instruction-driven</span>.
       Pale = weakly attributed (mostly the model's own priors).</p>
    <p><b>Click a sentence</b> → the drawer shows its strength as <b>support vs. against</b>
       (<span style="color:rgb(var(--pos))">green support</span> ▶ / ◀ <span class="neg">red against</span>):
       long bars both sides = strong but cancelling (competing/collinear chunks), short both = genuinely weak.
       Then the <b>sources</b>, ranked by attribution strength — context rows are a ± heatmap
       (<span style="background:rgba(var(--pos),.5);padding:0 5px;border-radius:3px">green +</span> /
       <span style="background:rgba(var(--neg),.5);padding:0 5px;border-radius:3px">red −</span>);
       <b>instruction</b> rows are
       <span style="background:rgba(var(--ins),.5);padding:0 5px;border-radius:3px">amber boxes</span>
       with the sign in the number. The <b>source chunks</b> below that expand to their full verbatim text.</p>
    <p style="color:#f2c879">Prototype · descriptive only. Strength is relative <i>within</i> an answer (raw magnitudes
       aren't comparable across answers).
       {"Text in English (Gemini gloss) — hover a sentence for the Vietnamese." if TR else "Text is Vietnamese — run translate.py for an English gloss."}</p>
  </header>
  {"".join(sections)}
</main>
<aside id="drawer"><p class="ph">Click a sentence to see its attribution strength and sources.</p></aside>
</div>
<script>
const DATA = {data_json};
function esc(s){{return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/\\n/g,"<br>");}}
function num(x){{return x==null?"—":(typeof x==="number"?x.toFixed(2):x);}}
// Per-unit drawer — matches AttributionView.tsx's UnitDrawer 1:1: strength +
// diverging bar, then sources ranked by |score|, then collapsible full chunks.
function draw(rid, idx){{
  const rec = DATA[rid]||{{}};
  const d = rec[idx]; if(!d) return;
  const maxSup = Math.max(1e-9, ...Object.values(rec).map(u=>u.support));
  const rel = d.support/maxSup;
  const word = rel>=0.66 ? "strongly attributed" : rel>=0.33 ? "moderately attributed" : "weakly attributed";
  // diverging support/against scaled to the record's largest of either
  const scale = Math.max(1e-9, ...Object.values(rec).flatMap(u=>[u.support, u.against]));
  const supW = (100*Math.min(d.support/scale,1)).toFixed(1);
  const agW = (100*Math.min(d.against/scale,1)).toFixed(1);
  const instrNote = d.instr_main ? '<span class="sval-instr">driven by instruction</span>' : '';

  const maxAbs = Math.max(1e-9, ...d.sources.map(a=>Math.abs(a.score)));
  const srcRows = d.sources.length ? '<h3>Sources, ranked by attribution strength</h3>' + d.sources.map(s=>{{
      const rgb = s.instr ? 'var(--ins)' : (s.score<0 ? 'var(--neg)' : 'var(--pos)');
      const a = (0.10+0.72*Math.min(Math.abs(s.score)/maxAbs,1)).toFixed(2);
      return `<div class="src-row" style="background:rgba(${{rgb}},${{a}})">
          <div class="src-row-head">
            <span class="src-tag">${{esc(s.tag)}}</span>
            <span class="src-num" style="color:rgb(${{rgb}})">${{s.score>=0?'+':''}}${{num(s.score)}}</span>
          </div>
          <div class="src-row-text">${{esc(s.text)}}</div>
        </div>`;}}).join("")
    : '<p class="drawer-empty">Nothing moved this sentence — it came from the model\\'s own priors.</p>';

  const fullChunks = d.chunks.length ? `<div class="fullchunks"><h3>Source chunks — full text</h3>${{
      d.chunks.map((c,i)=>`<div class="fc">
          <button class="fc-toggle" data-i="${{i}}">▸ ${{esc(c.title)}}</button>
          <div class="fc-text" data-chunk="${{i}}" style="display:none">${{esc(c.text)}}</div>
        </div>`).join("")}}</div>` : '';

  document.getElementById("drawer").innerHTML = `
    <div class="uq">“${{esc(d.text)}}”</div>
    <div class="strength">
      <div class="sval">${{num(d.support)}} <span class="sw">${{word}}</span>${{instrNote}}</div>
      <div class="dv"><div class="dv-l"><span style="width:${{agW}}%"></span></div><div class="dv-r"><span style="width:${{supW}}%"></span></div></div>
      <div class="dv-lab"><span>◀ against ${{num(d.against)}}</span><span>support ${{num(d.support)}} ▶</span></div>
    </div>
    ${{srcRows}}
    ${{fullChunks}}`;
}}
document.addEventListener("click", e=>{{
  const t = e.target.closest(".fc-toggle");
  if(t){{
    const box = t.nextElementSibling;
    const open = box.style.display !== "none";
    box.style.display = open ? "none" : "block";
    t.textContent = (open ? "▸ " : "▾ ") + t.textContent.slice(2);
    return;
  }}
  const u = e.target.closest(".unit"); if(!u) return;
  document.querySelectorAll(".unit.sel").forEach(x=>x.classList.remove("sel"));
  u.classList.add("sel");
  draw(u.dataset.rid, u.dataset.idx);
}});
</script>
</body></html>"""

    out = Path("dare_report.html")
    out.write_text(doc)
    lang = f"English gloss ({len(TR)} strings)" if TR else "Vietnamese only"
    print(f"records: {len(ok)} | {lang} | -> {out.resolve()}")


if __name__ == "__main__":
    main()
