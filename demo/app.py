"""Gradio demo for context attribution.

Two-column layout, two explicit steps:
  Left  — an upload widget, the query (auto-filled from the uploaded file,
          editable), a Run button, the answer, and an expander with the full
          endpoint output. Run does step 1 only: it shows the response. It does
          NOT start attribution.
  Right — a "Run attribution" button that starts step 2 (the slow module), a
          progress bar during it, then the color-scaled Score/Source table.

The two steps are separate clicks. Run loads the RAG response (stage 1) and
stashes the prepared attribution inputs in a gr.State; Run attribution reads
that state and runs the ablation module (stage 2). Run also clears any prior
table, and Run attribution refuses if no response has been Run yet.

Span selection. By default the answer is shown as rendered markdown and
attribution covers the whole response. Tick "Select a span to attribute" and
the answer flips to a raw plain-text view (the exact `response` string the
module scores): highlight a portion there and Run attribution attributes only
that span. The highlight is captured by a small JS listener (Gradio has no
native text-selection event) that writes the selection's character offsets —
which, in the raw <pre>, map 1:1 to `response` indices — into a hidden field
read back as start_idx/end_idx.

Drop any JSON test file (in the shape load_mock/prepare_inputs expect) on the
upload widget. Uploading it fills the query box from that file's `query`. A run
requires a query: if the box is empty and the file carries none, it is refused.

Run (from inside demo/):  python app.py
"""

import html
import json

import gradio as gr
import pandas as pd

from config import NUM_ABLATIONS, GREEN_MAX
from runner import fetch_inputs, attribute, style_scores, resolve_mock

# Hide the offset-relay textbox while keeping it in the DOM, so the selection JS
# can write to it. (visible=False can drop a component from the DOM entirely.)
_CSS = "#cc-span { display: none !important; }"

# Document-level mouseup listener: when the selection sits inside the raw
# response <pre>, compute its character offsets relative to that element's text
# (a 1:1 map to the `response` string) and push "start,end" into the hidden
# #cc-span textbox so Gradio syncs it server-side. Installed once on page load;
# it resolves #cc-response dynamically, so it survives the <pre> re-rendering.
_SELECT_JS = """
() => {
  document.addEventListener('mouseup', () => {
    const root = document.getElementById('cc-response');
    if (!root) return;
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0);
    if (!root.contains(range.startContainer) || !root.contains(range.endContainer)) return;
    const pre = document.createRange();
    pre.selectNodeContents(root);
    pre.setEnd(range.startContainer, range.startOffset);
    const start = pre.toString().length;
    const end = start + sel.toString().length;
    const ta = document.querySelector('#cc-span textarea');
    if (ta) {
      ta.value = (end > start) ? (start + ',' + end) : '';
      ta.dispatchEvent(new Event('input', { bubbles: true }));
    }
  });
}
"""


def _query_from(upload):
    """Read an uploaded test file's own `query` (fast, no LLM) for the box."""
    if not upload:
        return ""
    data = json.loads(resolve_mock(upload).read_text())
    return data.get("query", "")


def _response_pre(response: str) -> str:
    """Render `response` as a selectable raw-text <pre>.

    Whitespace is preserved and HTML-escaped, so the element's text content is
    exactly `response`; selection offsets within it index `response` directly.
    """
    body = html.escape(response or "")
    return (
        '<pre id="cc-response" style="white-space:pre-wrap;word-break:break-word;'
        'margin:0;font-family:inherit">' + body + "</pre>"
    )


def _parse_span(span: str):
    """Parse the hidden "start,end" relay into (start, end) ints, or (None, None).

    Returns (None, None) for an empty/blank/malformed value or an empty range,
    which the caller treats as "no span selected".
    """
    if not span or "," not in span:
        return None, None
    a, _, b = span.partition(",")
    try:
        start, end = int(a), int(b)
    except ValueError:
        return None, None
    return (start, end) if end > start >= 0 else (None, None)


def _span_preview(use_span, inputs, span):
    """Confirmation banner: show exactly what the offsets select, server-side.

    Slices the stashed `response` with the captured (start, end) so a highlight
    that doesn't match what's shown here reveals an offset misalignment. Hidden
    unless the span box is ticked.
    """
    if not use_span:
        return gr.update(value="", visible=False)
    start, end = _parse_span(span)
    if start is None:
        return gr.update(
            value="**Attributing:** whole response — highlight a portion to narrow it.",
            visible=True,
        )
    response = (inputs or {}).get("response", "")
    excerpt = response[start:end]
    return gr.update(
        value=f"**Attributing chars [{start}, {end}):**\n\n```\n{excerpt}\n```",
        visible=True,
    )


def run(upload, query, use_span):
    """Stage 1 (fast): load the RAG response and show the answer.

    The test file comes from the upload widget; the (editable) query box
    supplies the question. A query is required — empty box with no `query` in
    the file is a refusal, surfaced as a UI error rather than a silent run.

    Returns the rendered answer, the raw plain-text response (for span
    selection), the raw endpoint dict, the stage-1 `inputs` (stashed in a
    gr.State so the separate "Run attribution" step can use them), a cleared
    attribution table, a cleared span relay, and a reset confirmation banner —
    so neither a stale table nor a stale selection lingers next to a fresh
    answer.
    """
    if not upload:
        raise gr.Error("Upload a test file to run.")
    if not (query or "").strip():
        raise gr.Error("Enter a query to run (this file has none of its own).")

    inputs = fetch_inputs(
        source="mock",
        query=query,
        mock_path=resolve_mock(upload),
    )
    return (
        inputs["answer"],
        _response_pre(inputs["response"]),
        inputs["raw"],
        inputs,
        pd.DataFrame(columns=["Score", "Source"]),
        "",
        _span_preview(use_span, inputs, ""),
    )


def toggle_span(use_span, inputs, span):
    """Flip the answer between rendered markdown and the raw selectable view,
    and refresh the confirmation banner."""
    return (
        gr.update(visible=not use_span),
        gr.update(visible=use_span),
        _span_preview(use_span, inputs, span),
    )


def run_attribution(inputs, use_span, span, progress=gr.Progress(track_tqdm=True)):
    """Stage 2 (slow): run attribution on the stashed stage-1 inputs.

    Driven by the "Run attribution" button, which is only meaningful after a
    Run has produced `inputs`. When `use_span` is set, attribution is restricted
    to the highlighted character span (`span` is the hidden "start,end" relay);
    otherwise the whole response is attributed.
    progress=gr.Progress(track_tqdm=True) hooks the ablation loop's tqdm so the
    right column shows real per-ablation progress.
    """
    if not inputs:
        raise gr.Error("Press Run first to load a response, then attribute it.")

    start_idx = end_idx = None
    if use_span:
        start_idx, end_idx = _parse_span(span)
        if start_idx is None:
            raise gr.Error(
                "Highlight a portion of the response (in the plain-text view) "
                "before running, or untick the box to attribute the whole response."
            )

    # The slow ablation loop; progress bar advances on the right.
    styler = attribute(
        inputs, num_ablations=NUM_ABLATIONS, start_idx=start_idx, end_idx=end_idx
    )
    # Re-shade with a FIXED green scale instead of the pipeline's per-run-max one.
    return style_scores(styler.data, GREEN_MAX)


with gr.Blocks(title="Context Attribution", theme=gr.themes.Soft()) as demo:
    gr.Markdown("## Context Attribution")

    with gr.Row(equal_height=False):
        # --- Left: file + query + answer ------------------------------------
        with gr.Column(scale=1):
            upload_in = gr.File(
                label="Upload test file (.json)",
                file_types=[".json"],
                file_count="single",
            )
            query_in = gr.Textbox(
                label="Query",
                lines=2,
            )
            run_btn = gr.Button("Run", variant="primary")

            # Stage-1 inputs, stashed so "Run attribution" can pick them up.
            inputs_state = gr.State()

            # Confirmation banner: what the captured offsets actually select.
            span_preview = gr.Markdown(visible=False)
            # Rendered answer (default) and the raw selectable view (when ticked).
            answer_md = gr.Markdown(label="Answer", visible=True)
            answer_raw = gr.HTML(visible=False)
            span_toggle = gr.Checkbox(
                label="Select a span to attribute",
                value=False,
            )
            # Hidden relay: JS writes "start,end" character offsets here.
            span_box = gr.Textbox(elem_id="cc-span", value="")

            with gr.Accordion("Full endpoint output", open=False):
                raw_out = gr.JSON(label="Raw response")

        # --- Right: attribution ---------------------------------------------
        with gr.Column(scale=1):
            attribute_btn = gr.Button("Run attribution", variant="primary")
            scores_out = gr.Dataframe(
                value=pd.DataFrame(columns=["Score", "Source"]),
                label="Context attribution",
                interactive=False,  # required for the Styler colors to render
                wrap=True,
            )

    # Uploading a file fills the query box from that file.
    upload_in.change(_query_from, inputs=upload_in, outputs=query_in)

    # The checkbox flips the answer between rendered and raw-selectable views
    # and refreshes the confirmation banner.
    span_toggle.change(
        toggle_span,
        inputs=[span_toggle, inputs_state, span_box],
        outputs=[answer_md, answer_raw, span_preview],
    )

    # A new highlight (JS writes the relay) refreshes the confirmation banner.
    span_box.change(
        _span_preview,
        inputs=[span_toggle, inputs_state, span_box],
        outputs=span_preview,
    )

    # Step 1: Run loads the response and shows the answer.
    run_btn.click(
        run,
        inputs=[upload_in, query_in, span_toggle],
        outputs=[answer_md, answer_raw, raw_out, inputs_state, scores_out, span_box, span_preview],
    )

    # Step 2: Run attribution starts the (slow) attribution module.
    attribute_btn.click(
        run_attribution,
        inputs=[inputs_state, span_toggle, span_box],
        outputs=scores_out,
    )

    # Install the selection listener once the page is up.
    demo.load(None, None, None, js=_SELECT_JS)


if __name__ == "__main__":
    demo.launch(css=_CSS)
