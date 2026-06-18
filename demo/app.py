"""Minimal Gradio demo for context attribution.

Deliberately bare: mock mode only, one button, a progress bar, and three
outputs (query, answer, raw score table). This is the skeleton we iterate on
toward the full explainability UI (ranked source cards, emphasis, backend
mode). The pipeline is a black box reached only through runner.run_attribution.

Run:  python demo/app.py     (then open the printed local URL)
"""

import gradio as gr

from runner import run_attribution


def attribute(progress=gr.Progress(track_tqdm=True)):
    """Run the mock-mode pipeline and return (query, answer, score table).

    progress=gr.Progress(track_tqdm=True) hooks the ablation loop's tqdm bar
    (context_cite.utils) so the ~34s run shows real per-ablation progress.
    """
    result = run_attribution(source="mock")
    score_table = result["attributions"].data  # DataFrame: columns Score, Source
    return result["query"], result["response"], score_table


with gr.Blocks(title="Context Attribution (minimal)") as demo:
    gr.Markdown("# Context Attribution — minimal demo")

    run_btn = gr.Button("Run attribution", variant="primary")

    query_out = gr.Textbox(label="Query", interactive=False)
    answer_out = gr.Markdown(label="Answer")
    scores_out = gr.Dataframe(
        headers=["Score", "Source"],
        label="Attribution scores (ranked)",
        wrap=True,
    )

    run_btn.click(attribute, outputs=[query_out, answer_out, scores_out])


if __name__ == "__main__":
    demo.launch()
