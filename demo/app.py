"""Gradio demo for context attribution.

Two-column layout:
  Left  — a mock-file dropdown, the query (auto-filled from the mock, editable),
          a Run button, the answer, and an expander with the full endpoint output.
  Right — a progress bar during the attribution, then the color-scaled
          Score/Source table.

The dropdown is built from the shared mock_data/ folder (context_attribution.
mocks.list_mocks) — drop a JSON file in there and it shows up here. Selecting a
mock fills the query box from that file's `query`. A run requires a query: if
the box is empty and the mock carries none, the run is refused.

Run (from inside demo/):  python app.py
"""

import json

import gradio as gr

from config import NUM_ABLATIONS, GREEN_MAX
from runner import fetch_inputs, attribute, style_scores, list_mocks, resolve_mock

# Mock files discovered from mock_data/, labelled by their bare stem.
_MOCKS = list_mocks()
_MOCK_LABELS = [p.stem for p in _MOCKS]


def _mock_query(label):
    """Read a mock file's own `query` (fast, no LLM) to populate the box."""
    if not label:
        return ""
    data = json.loads(resolve_mock(label).read_text())
    return data.get("query", "")


def run(label, query, progress=gr.Progress(track_tqdm=True)):
    """Stage 1: show the answer. Stage 2: run attribution, show the table.

    The dropdown picks the mock file; the (editable) query box supplies the
    question. A query is required — empty box with no `query` in the mock is a
    refusal, surfaced as a UI error rather than a silent run.
    progress=gr.Progress(track_tqdm=True) hooks the ablation loop's tqdm so the
    right column shows real per-ablation progress.
    """
    if not (query or "").strip():
        raise gr.Error("Enter a query to run (this mock has none of its own).")

    inputs = fetch_inputs(
        source="mock",
        query=query,
        mock_path=resolve_mock(label),
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
        # --- Left: mock + query + answer ------------------------------------
        with gr.Column(scale=1):
            mock_dd = gr.Dropdown(
                choices=_MOCK_LABELS,
                value=_MOCK_LABELS[0] if _MOCK_LABELS else None,
                label="Mock file",
            )
            query_in = gr.Textbox(
                label="Query",
                value=_mock_query(_MOCK_LABELS[0]) if _MOCK_LABELS else "",
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

    # Selecting a mock fills the query box from that file.
    mock_dd.change(_mock_query, inputs=mock_dd, outputs=query_in)

    run_btn.click(
        run,
        inputs=[mock_dd, query_in],
        outputs=[answer_md, raw_out, scores_out],
    )


if __name__ == "__main__":
    demo.launch()
