"""Adapter between the demo UI and the context_attribution module.

This is the ONLY place the demo touches the pipeline. The algorithm is treated
as a black box: we import `run_pipeline` and call it, nothing more. Isolating
the call here means the LLM-endpoint policy (live now, possibly cached /
precomputed later) and the source selection can change without touching the UI.

Progress is NOT handled here. The ablation loop inside the pipeline drives a
`tqdm` bar (context_cite.utils), which the Gradio layer tracks directly via
`gr.Progress(track_tqdm=True)`. Keeping that out of the adapter leaves this a
plain, blocking pass-through.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `gradio`/`python demo/app.py` to run from any cwd: ensure the repo root
# (which contains the `context_attribution` package) is importable.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from context_attribution.context_cite import run_pipeline  # noqa: E402

# Default mock file shipped with the demo.
DEFAULT_MOCK_PATH = Path(__file__).resolve().parent / "demo_mock_data.json"


def run_attribution(
    *,
    source: str = "mock",
    query: str | None = None,
    num_ablations: int = 32,
    mock_path: str | Path | None = None,
) -> dict:
    """Run the attribution pipeline once and return its result dict unchanged.

    Thin pass-through to `run_pipeline` — no recomputation. All the expensive
    work (the LLM ablation calls + the Lasso fit) happens inside that single
    call; everything the UI renders is already in the returned dict.

    Arguments:
        source: "mock" (load `mock_path`, default the bundled demo file) or
            "backend" (send `query` to the live RAG backend).
        query: the question. Optional in mock mode (the mock's own `query`
            field is used if omitted); required in backend mode.
        num_ablations: number of ablations the pipeline runs.
        mock_path: override the mock file in mock mode.

    Returns:
        dict with keys {source, query, answer, context, response,
        num_sources, attributions}, where `attributions` is a sorted,
        color-scaled pandas Styler (its `.data` has columns "Score", "Source").
    """
    if source == "mock":
        return run_pipeline(
            query=query or None,
            source="mock",
            mock_path=str(mock_path or DEFAULT_MOCK_PATH),
            num_ablations=num_ablations,
        )
    if source == "backend":
        if not query:
            raise ValueError("backend mode requires a query")
        return run_pipeline(
            query=query,
            source="backend",
            num_ablations=num_ablations,
        )
    raise ValueError(f"unknown source {source!r} (use 'mock' or 'backend')")
