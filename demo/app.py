"""Gradio demo for context attribution.

Two-column layout:
  Left  — a test-case dropdown, the query (auto-filled from the case, editable),
          a Run button, the answer, and an expander with the full endpoint output.
  Right — a progress bar during the attribution, then the color-scaled
          Score/Source table.

Selecting a case fills the query box from that case's `query`. Run is staged
like the CLI: a generator yields the answer immediately, then runs attribution
and yields the table. The pipeline is a black box reached only through
runner.fetch_inputs / runner.attribute.

Each case may cite a response sub-span (config.CASES start/end). Span cases get
a shaded HighlightedText answer; full-answer cases render markdown (so tables
show). The component is toggled per run.

Run (from inside demo/):  python app.py
"""

import json

import gradio as gr

from config import NUM_ABLATIONS, GREEN_MAX, CASES, case_by_label, case_path
from runner import fetch_inputs, attribute, style_scores

_CITED_LABEL = "cited"
_CASE_LABELS = [c["label"] for c in CASES]


def _case_query(label):
    """Read a case file's own `query` (fast, no LLM) to populate the box."""
    data = json.loads(case_path(case_by_label(label)).read_text())
    return data.get("query", "")


def _answer_components(inputs, start, end):
    """Build (markdown_update, highlighted_update) for the answer panel.

    Full-answer cases (no span) → markdown shown, highlighted hidden.
    Span cases → highlighted shown with the cited span shaded, markdown hidden.
    Offsets index `response` (a prefix of `answer`), so they map onto `answer`.
    """
    answer = inputs["answer"]
    has_span = start is not None or end is not None
    if not has_span:
        return gr.update(value=answer, visible=True), gr.update(visible=False)

    s = max(0, start or 0)
    e = min(end if end is not None else len(inputs["response"]), len(inputs["response"]))
    if e <= s:  # degenerate span — fall back to plain markdown
        return gr.update(value=answer, visible=True), gr.update(visible=False)

    segments = [
        (answer[:s], None),
        (answer[s:e], _CITED_LABEL),
        (answer[e:], None),
    ]
    return gr.update(visible=False), gr.update(value=segments, visible=True)


def run(label, query, progress=gr.Progress(track_tqdm=True)):
    """Stage 1: show the answer. Stage 2: run attribution, show the table.

    The selected case picks the mock file and the cited span; the (editable)
    query box overrides the case's own query when non-empty.
    progress=gr.Progress(track_tqdm=True) hooks the ablation loop's tqdm so the
    right column shows real per-ablation progress.
    """
    case = case_by_label(label)
    start, end = case["start"], case["end"]
    inputs = fetch_inputs(
        source="mock",
        query=query or None,
        mock_path=case_path(case),
    )
    md_update, hl_update = _answer_components(inputs, start, end)

    # Stage 1 — answer is available instantly; clear any prior table.
    yield md_update, hl_update, inputs["raw"], None

    # Stage 2 — the slow ablation loop; progress bar advances on the right.
    styler = attribute(inputs, num_ablations=NUM_ABLATIONS, start_idx=start, end_idx=end)
    # Re-shade with a FIXED green scale instead of the pipeline's per-run-max one.
    scores = style_scores(styler.data, GREEN_MAX)
    yield md_update, hl_update, inputs["raw"], scores


with gr.Blocks(title="Context Attribution") as demo:
    gr.Markdown("# Context Attribution")

    with gr.Row(equal_height=False):
        # --- Left: case + query + answer ------------------------------------
        with gr.Column(scale=1):
            case_dd = gr.Dropdown(
                choices=_CASE_LABELS,
                value=_CASE_LABELS[0],
                label="Test case",
            )
            query_in = gr.Textbox(
                label="Query",
                value=_case_query(_CASE_LABELS[0]),
                lines=2,
            )
            run_btn = gr.Button("Run", variant="primary")

            # Two answer components, toggled per run (see _answer_components).
            answer_md = gr.Markdown(label="Answer", visible=True)
            answer_hl = gr.HighlightedText(
                label="Answer (cited span shaded)",
                color_map={_CITED_LABEL: "#fde68a"},
                show_legend=False,
                combine_adjacent=True,
                visible=False,
            )

            with gr.Accordion("Full endpoint output", open=False):
                raw_out = gr.JSON(label="Raw response")

        # --- Right: attribution ---------------------------------------------
        with gr.Column(scale=1):
            scores_out = gr.Dataframe(
                label="Context attribution",
                interactive=False,  # required for the Styler colors to render
                wrap=True,
            )

    # Selecting a case fills the query box from that case.
    case_dd.change(_case_query, inputs=case_dd, outputs=query_in)

    run_btn.click(
        run,
        inputs=[case_dd, query_in],
        outputs=[answer_md, answer_hl, raw_out, scores_out],
    )


if __name__ == "__main__":
    demo.launch()
