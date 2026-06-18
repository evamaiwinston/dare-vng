"""Gradio demo for context attribution.

Two-column layout:
  Left  — query box (decorative for now; always runs the mock), a Run button,
          the answer, and an expander with the full endpoint output.
  Right — a progress bar during the ~34s attribution, then the color-scaled
          Score/Source table.

One button, staged like the CLI: a generator yields the answer immediately,
then runs attribution and yields the highlighted table. The pipeline is a
black box reached only through runner.fetch_inputs / runner.attribute.

Run (from inside demo/):  python app.py
"""

import gradio as gr

from runner import fetch_inputs, attribute


def run(query, progress=gr.Progress(track_tqdm=True)):
    """Stage 1: show the answer. Stage 2: run attribution, show the table.

    `query` is accepted but ignored for now — the demo always runs the mock.
    progress=gr.Progress(track_tqdm=True) hooks the ablation loop's tqdm so the
    right column shows real per-ablation progress.
    """
    inputs = fetch_inputs(source="mock")

    # Stage 1 — answer is available instantly; clear any prior table.
    yield inputs["answer"], inputs["raw"], None

    # Stage 2 — the slow ablation loop; progress bar advances on the right.
    styler = attribute(inputs)
    yield inputs["answer"], inputs["raw"], styler


with gr.Blocks(title="Context Attribution") as demo:
    gr.Markdown("# Context Attribution")

    with gr.Row(equal_height=False):
        # --- Left: query + answer -------------------------------------------
        with gr.Column(scale=1):
            query_in = gr.Textbox(
                label="Query",
                placeholder="Type a question… (demo runs the mock either way)",
                lines=2,
            )
            run_btn = gr.Button("Run", variant="primary")
            answer_out = gr.Markdown(label="Answer")
            with gr.Accordion("Full endpoint output", open=False):
                raw_out = gr.JSON(label="Raw response")

        # --- Right: attribution ---------------------------------------------
        with gr.Column(scale=1):
            scores_out = gr.Dataframe(
                label="Context attribution",
                interactive=False,  # required for the Styler colors to render
                wrap=True,
            )

    run_btn.click(run, inputs=[query_in], outputs=[answer_out, raw_out, scores_out])


if __name__ == "__main__":
    demo.launch()
