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
    sig_units = (r.get("signals") or {}).get("units") or []

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
        cos = sig_units[idx].get("chunk_query_cosine") if idx < len(sig_units) else None
        total = u["context_mass"] + u["instruction_mass"]          # = support (Σ positive)
        against = sum(-a["score"] for a in (u.get("source_attributions") or []) if a["score"] < 0)

        # hue = which lane drove the sentence (green context / amber instruction); opacity = strength.
        # instruction-main when the instruction lane outweighs the strongest single chunk.
        max_chunk = max((c["positive_mass"] for c in (u.get("chunk_attributions") or [])), default=0.0)
        instr_main = u["instruction_mass"] > 0 and u["instruction_mass"] >= max_chunk
        hue = "242,200,121" if instr_main else "126,224,192"

        if total > 0:
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

        # the breakdown that SUMS to the strength: each grounding chunk + the
        # instruction lane, each as its own contributor bar
        breakdown = [
            {"label": "chunk " + (c["chunk_id"] or "—")[:8], "mass": round(c["positive_mass"], 2),
             "kind": "ctx", "retr": c["retrieval_score"], "text": en(c["representative_text"])}
            for c in (u.get("chunk_attributions") or []) if c["positive_mass"] > 0
        ]
        if u["instruction_mass"] > 0:
            top_instr = sorted((a for a in (u.get("instruction_attributions") or []) if a["score"] > 0),
                               key=lambda a: -a["score"])
            breakdown.append({"label": "instruction", "mass": round(u["instruction_mass"], 2),
                              "kind": "instr", "retr": None,
                              "text": en(top_instr[0]["source_text"]) if top_instr else "(synthesis prompt directive)"})
        breakdown.sort(key=lambda b: -b["mass"])

        details[idx] = {
            "text": en(u["text"]),
            "total": round(total, 2),
            "against": round(against, 2),
            "instr_main": instr_main,
            "context_mass": round(u["context_mass"], 2),
            "instruction_mass": round(u["instruction_mass"], 2),
            "cosine": cos,
            "breakdown": breakdown,
            "sources": [
                {"score": round(a["score"], 2), "text": en(a["source_text"]),
                 "instr": a.get("origin") == "instruction"}
                for a in sorted(u.get("source_attributions") or [], key=lambda a: -abs(a["score"]))[:8]
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
  .mut{{color:var(--muted)}}
  .brow{{margin:8px 0}}
  .btop{{display:flex;justify-content:space-between;font-size:12.5px;margin-bottom:3px}}
  .btrack{{height:11px;background:#0a0c16;border-radius:4px;overflow:hidden}}
  .btrack span{{display:block;height:100%}}
  .btext{{color:var(--muted);font-size:11.5px;margin-top:4px}}
  .num{{font-variant-numeric:tabular-nums;font-weight:700}}
  .row{{border:1px solid var(--line);border-radius:9px;padding:6px 9px;margin:5px 0;font-size:12.5px}}
  .neg{{color:rgb(var(--neg))}}
  .pos{{color:rgb(var(--pos))}}
  .badge{{display:inline-block;background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:2px 10px;font-size:12px;color:var(--muted)}}
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
       Then <b>what it's made of</b>, and the source rows — context rows are a ± heatmap
       (<span style="background:rgba(var(--pos),.5);padding:0 5px;border-radius:3px">green +</span> /
       <span style="background:rgba(var(--neg),.5);padding:0 5px;border-radius:3px">red −</span>);
       <b>instruction</b> rows are
       <span style="background:rgba(var(--ins),.5);padding:0 5px;border-radius:3px">amber boxes</span>
       with the sign in the number.</p>
    <p style="color:#f2c879">Prototype · descriptive only. Strength is relative <i>within</i> an answer (raw magnitudes
       aren't comparable across answers). Cosine is a within-corpus on-topic proxy.
       {"Text in English (Gemini gloss) — hover a sentence for the Vietnamese." if TR else "Text is Vietnamese — run translate.py for an English gloss."}</p>
  </header>
  {"".join(sections)}
</main>
<aside id="drawer"><p class="ph">Click a sentence to see its attribution strength and what it's made of.</p></aside>
</div>
<script>
const DATA = {data_json};
function esc(s){{return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/\\n/g,"<br>");}}
function num(x){{return x==null?"—":(typeof x==="number"?x.toFixed(2):x);}}
function clip(s,n){{s=s||"";return esc(s.length>n?s.slice(0,n).trimEnd()+"…":s);}}
function heat(instr, score, max){{
  // instruction rows = amber box; context rows keep the ± heatmap (green +, red −). opacity = magnitude.
  const a = max>0 ? 0.10+0.72*Math.min(Math.abs(score)/max,1) : 0.10;
  const rgb = instr ? 'var(--ins)' : (score<0 ? 'var(--neg)' : 'var(--pos)');
  return `background:rgba(${{rgb}},${{a.toFixed(2)}})`;
}}
function draw(rid, idx){{
  const rec = DATA[rid]||{{}};
  const d = rec[idx]; if(!d) return;
  const maxSup = Math.max(1e-9, ...Object.values(rec).map(u=>u.total));
  const rel = d.total/maxSup;
  const word = rel>=0.66 ? "strongly attributed" : rel>=0.33 ? "moderately attributed" : "weakly attributed";
  // diverging support/against scaled to the record's largest of either
  const scale = Math.max(1e-9, ...Object.values(rec).flatMap(u=>[u.total, u.against]));
  const supW = (100*Math.min(d.total/scale,1)).toFixed(1);
  const agW = (100*Math.min(d.against/scale,1)).toFixed(1);
  const instrNote = d.instr_main ? ` <span style="color:rgb(var(--ins))">· mainly from the instruction</span>` : "";
  const maxBd = Math.max(1e-9, ...d.breakdown.map(b=>b.mass));
  const bars = d.breakdown.length ? d.breakdown.map(b=>{{
      const rgb = b.kind=="instr" ? "var(--ins)" : "var(--pos)";
      return `<div class="brow"><div class="btop">
          <span>${{b.label}}${{b.retr!=null?` <span class="mut">retr ${{num(b.retr)}}</span>`:''}}</span>
          <span class="num">${{num(b.mass)}}</span></div>
        <div class="btrack"><span style="width:${{(100*b.mass/maxBd).toFixed(1)}}%;background:rgba(${{rgb}},.85)"></span></div>
        <div class="btext">${{clip(b.text,500)}}</div></div>`;}}).join("")
    : '<p class="ph">Nothing — neither the retrieved context nor the instruction moved this sentence. It came from the model\\'s own priors.</p>';
  const maxAbs = Math.max(1e-9, ...d.sources.map(a=>Math.abs(a.score)));
  const srcs = d.sources.map(a=>`<div class="row" style="${{heat(a.instr, a.score, maxAbs)}}">
      <span class="num ${{a.score<0?'neg':(a.instr?'pos':'')}}">${{a.score>=0?'+':''}}${{num(a.score)}}</span>&nbsp;${{clip(a.text,700)}}</div>`).join("");
  document.getElementById("drawer").innerHTML = `
    <div class="uq">“${{esc(d.text)}}”</div>
    <div class="strength">
      <div class="sval">${{num(d.total)}} <span class="sw">${{word}}</span>${{instrNote}}</div>
      <div class="dv"><div class="dv-l"><span style="width:${{agW}}%"></span></div><div class="dv-r"><span style="width:${{supW}}%"></span></div></div>
      <div class="dv-lab"><span>◀ against ${{num(d.against)}}</span><span>support ${{num(d.total)}} ▶</span></div>
      <div class="mut" style="font-size:11.5px;margin-top:7px">chunk↔query cos ${{num(d.cosine)}}
        · support &amp; against shown vs this answer's max<br>
        <span>long bars both sides = strong but cancelling · short both = genuinely weak</span></div>
    </div>
    <h3>What the strength is made of</h3>${{bars}}
    <h3>Source rows (incl. negatives)</h3>${{srcs}}`;
}}
document.addEventListener("click", e=>{{
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
