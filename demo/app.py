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

from config import NUM_ABLATIONS, MOCK_DATA_PATH, CITE_START, CITE_END
from runner import fetch_inputs, attribute

# Highlight the cited span only when BOTH offsets are set. Config is static per
# app start, so this is decided once and picks the left answer component below.
CITE_ACTIVE = CITE_START is not None and CITE_END is not None
_CITED_LABEL = "cited"


def _answer_payload(inputs):
    """Build the value for the left answer component.

    When citing is active, return HighlightedText segments with the cited span
    labeled; otherwise return the plain answer string (rendered as markdown).
    Offsets index `response`, which is a prefix of `answer` (== answer when the
    answer fits the char limit), so they map straight onto `answer`.
    """
    answer = inputs["answer"]
    if not CITE_ACTIVE:
        return answer
    s = max(0, CITE_START)
    e = min(CITE_END, len(inputs["response"]))
    if e <= s:  # nothing to highlight — show plain
        return [(answer, None)]
    return [
        (answer[:s], None),
        (answer[s:e], _CITED_LABEL),
        (answer[e:], None),
    ]


def run(query, progress=gr.Progress(track_tqdm=True)):
    """Stage 1: show the answer. Stage 2: run attribution, show the table.

    `query` is accepted but ignored for now — the demo always runs the mock.
    The mock file and ablation count come from config.py.
    progress=gr.Progress(track_tqdm=True) hooks the ablation loop's tqdm so the
    right column shows real per-ablation progress.
    """
    inputs = fetch_inputs(source="mock", mock_path=MOCK_DATA_PATH)
    answer = _answer_payload(inputs)

    # Stage 1 — answer is available instantly; clear any prior table.
    yield answer, inputs["raw"], None

    # Stage 2 — the slow ablation loop; progress bar advances on the right.
    styler = attribute(
        inputs,
        num_ablations=NUM_ABLATIONS,
        start_idx=CITE_START,
        end_idx=CITE_END,
    )
    yield answer, inputs["raw"], styler


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
            if CITE_ACTIVE:
                # Cited span shaded; renders plain text (no markdown) but never
                # breaks on arbitrary offsets.
                answer_out = gr.HighlightedText(
                    label=f"Answer (citing chars {CITE_START}–{CITE_END})",
                    color_map={_CITED_LABEL: "#fde68a"},
                    show_legend=False,
                    combine_adjacent=True,
                )
            else:
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
