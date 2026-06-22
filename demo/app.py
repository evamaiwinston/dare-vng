"""Gradio demo for context attribution.

Two-column layout:
  Left  — an upload widget, a bundled-mock dropdown, the query (auto-filled from
          the chosen file, editable), a Run button, the answer, and an expander
          with the full endpoint output.
  Right — a progress bar during the attribution, then the color-scaled
          Score/Source table.

The test file can come from either input: upload any JSON at runtime, or pick
one of the bundled mocks (the dropdown is built from the shared mock_data/
folder via context_attribution.mocks.list_mocks — drop a JSON in there and it
shows up). An uploaded file takes precedence over the dropdown. Choosing either
fills the query box from that file's `query`. A run requires a query: if the
box is empty and the file carries none, the run is refused.

Run (from inside demo/):  python app.py
"""

import json

import gradio as gr

from config import NUM_ABLATIONS, GREEN_MAX
from runner import fetch_inputs, attribute, style_scores, list_mocks, resolve_mock

# Mock files discovered from mock_data/, labelled by their bare stem.
_MOCKS = list_mocks()
_MOCK_LABELS = [p.stem for p in _MOCKS]


def _query_from(ref):
    """Read a test file's own `query` (fast, no LLM) to populate the box.

    ``ref`` is either a dropdown label (a bundled mock's stem) or an uploaded
    file's path; ``resolve_mock`` accepts both.
    """
    if not ref:
        return ""
    data = json.loads(resolve_mock(ref).read_text())
    return data.get("query", "")


def run(label, upload, query, progress=gr.Progress(track_tqdm=True)):
    """Stage 1: show the answer. Stage 2: run attribution, show the table.

    The test file comes from the upload widget if a file is given, otherwise
    from the dropdown (the bundled mocks). The (editable) query box supplies the
    question. A query is required — empty box with no `query` in the file is a
    refusal, surfaced as a UI error rather than a silent run.
    progress=gr.Progress(track_tqdm=True) hooks the ablation loop's tqdm so the
    right column shows real per-ablation progress.
    """
    ref = upload or label
    if not ref:
        raise gr.Error("Upload a test file or pick a mock to run.")
    if not (query or "").strip():
        raise gr.Error("Enter a query to run (this file has none of its own).")

    inputs = fetch_inputs(
        source="mock",
        query=query,
        mock_path=resolve_mock(ref),
    )

    # Stage 1 — answer is available instantly; clear any prior table.
    yield inputs["answer"], inputs["raw"], None

    # Stage 2 — the slow ablation loop; progress bar advances on the right.
    styler = attribute(inputs, num_ablations=NUM_ABLATIONS)
    # Re-shade with a FIXED green scale instead of the pipeline's per-run-max one.
    scores = style_scores(styler.data, GREEN_MAX)
    yield inputs["answer"], inputs["raw"], scores


with gr.Blocks(title="Context Attribution") as demo:
    gr.Markdown("# Context Attribution")

    with gr.Row(equal_height=False):
        # --- Left: file + query + answer ------------------------------------
        with gr.Column(scale=1):
            upload_in = gr.File(
                label="Upload test file (.json)",
                file_types=[".json"],
                file_count="single",
            )
            mock_dd = gr.Dropdown(
                choices=_MOCK_LABELS,
                value=_MOCK_LABELS[0] if _MOCK_LABELS else None,
                label="…or pick a bundled mock",
            )
            query_in = gr.Textbox(
                label="Query",
                value=_query_from(_MOCK_LABELS[0]) if _MOCK_LABELS else "",
                lines=2,
            )
            run_btn = gr.Button("Run", variant="primary")

            answer_md = gr.Markdown(label="Answer")

            with gr.Accordion("Full endpoint output", open=False):
                raw_out = gr.JSON(label="Raw response")

        # --- Right: attribution ---------------------------------------------
        with gr.Column(scale=1):
            scores_out = gr.Dataframe(
                label="Context attribution",
                interactive=False,  # required for the Styler colors to render
                wrap=True,
            )

    # Selecting a mock or uploading a file fills the query box from that file.
    mock_dd.change(_query_from, inputs=mock_dd, outputs=query_in)
    upload_in.change(_query_from, inputs=upload_in, outputs=query_in)

    run_btn.click(
        run,
        inputs=[mock_dd, upload_in, query_in],
        outputs=[answer_md, raw_out, scores_out],
    )


if __name__ == "__main__":
    demo.launch()
