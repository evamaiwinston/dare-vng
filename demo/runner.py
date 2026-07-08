"""Adapter between the demo UI and the dare package.

This is the ONLY place the demo touches the pipeline. `run_pipeline` (defined
here) orchestrates dare's public building blocks — fetch/load, prepare_inputs,
attribute_response — into one blocking call. Isolating that here means the
LLM-endpoint policy (live now, possibly cached / precomputed later) and the
source selection can change without touching the UI.

Progress is NOT handled here. The ablation loop inside the pipeline drives a
`tqdm` bar (context_cite.utils), which the Gradio layer tracks directly via
`gr.Progress(track_tqdm=True)`. Keeping that out of the adapter leaves this a
plain, blocking pass-through.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `gradio`/`python demo/app.py` to run from any cwd: ensure the repo root
# (which contains the `dare` package) is importable.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dare.attribution import (  # noqa: E402
    load_mock,
    fetch_backend,
    prepare_inputs,
    attribute_response,
    resolve_query,
    MarkdownContextPartitioner,
    SETTINGS,
    Settings,
    LogprobProvider,
    _patched_color_scale,
)
# Re-export mock discovery so the UI can import everything from `runner` (which
# already put the repo root on sys.path) rather than re-resolving the path.
from tools.mocks import (  # noqa: E402,F401
    MOCK_DIR,
    list_mocks,
    resolve_mock,
)

# Default mock used when the UI/caller names none.
DEFAULT_MOCK_PATH = MOCK_DIR / "demo_mock_data.json"


# --- Full pipeline (fetch + attribute in one call) ---------------------------

def run_pipeline(
    query: str | None = None,
    *,
    source: str = "backend",
    mock_path: str | Path | None = None,
    num_ablations: int = 32,
    ablation_keep_prob: float = 0.5,
    batch_size: int = 1,
    as_dataframe: bool = True,
    verbose: bool = True,
    start_idx: int | None = None,
    end_idx: int | None = None,
    provider: LogprobProvider | None = None,
    settings: Settings | None = None,
) -> dict:
    """Run the full attribution pipeline; the single entry point the demo UI calls.

    Two modes, selected explicitly via ``source`` (not by backend availability):

    * ``source="backend"`` -- send ``query`` to the live RAG backend, then
      attribute the answer. ``query`` is required.
    * ``source="mock"`` -- skip the backend and load ``mock_path`` instead, for
      demo consistency. ``query`` may be omitted only if the mock file carries
      its own ``query`` field; with neither, the run is refused (see
      ``resolve_query``). The ablation logprobs still come from the live LLM
      endpoint either way.

    ``start_idx`` / ``end_idx`` cite a sub-span of the response, as character
    offsets into ``response``. Both None (the default) attributes the whole
    response. ``provider`` / ``settings`` override the endpoint and backend.

    Returns a dict with everything the UI needs to render:
    ``{source, query, answer, context, response, num_sources, attributions}``.
    """
    settings = settings or SETTINGS
    if source == "mock":
        if mock_path is None:
            raise ValueError("source='mock' requires mock_path")
        data = load_mock(mock_path)
        query = resolve_query(query, data)          # explicit > mock's own field
    elif source == "backend":
        query = resolve_query(query)                # backend: explicit query only
        data = fetch_backend(query, settings=settings)
    else:
        raise ValueError(f"unknown source {source!r} (use 'backend' or 'mock')")

    context, response = prepare_inputs(data, settings=settings)
    attributions = attribute_response(
        context,
        query,
        response,
        num_ablations=num_ablations,
        ablation_keep_prob=ablation_keep_prob,
        batch_size=batch_size,
        as_dataframe=as_dataframe,
        verbose=verbose,
        start_idx=start_idx,
        end_idx=end_idx,
        provider=provider,
        settings=settings,
    )
    return {
        "source": source,
        "query": query,
        "answer": data["answer"],
        "context": context,
        "response": response,
        "num_sources": MarkdownContextPartitioner(context).num_sources,
        "attributions": attributions,
    }


def style_scores(df, green_max: float):
    """Re-shade the Score column with a FIXED green scale.

    The pipeline's own Styler normalizes green to each run's max score
    (relative). This reuses the module's exact color function but with a fixed
    reference (`green_max`), so a given score always renders the same intensity:
    <= 0 white, >= green_max full green, linear in between. Takes the raw
    Score/Source DataFrame (e.g. `attribute(...).data`) and returns a Styler
    ready for gr.Dataframe(interactive=False).
    """
    return df.style.map(
        lambda v: _patched_color_scale(v, green_max), subset=["Score"]
    ).format(precision=3)


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


# --- Two-stage split (for the UI: show the answer, then run attribution) ------
#
# run_pipeline does fetch + attribute in one blocking call and only returns at
# the end. The UI wants the answer on screen *before* the ~34s attribution, so
# we expose the same two steps run_pipeline performs internally, in the same
# order, as separate functions. The algorithm is untouched — these just call
# its public building blocks.


def fetch_inputs(
    *,
    source: str = "mock",
    query: str | None = None,
    mock_path: str | Path | None = None,
) -> dict:
    """Stage 1 (fast): load the RAG response and prepare attribution inputs.

    No ablation / LLM scoring happens here. Returns everything needed to show
    the answer immediately and to drive stage 2:
        {source, query, answer, context, response, raw}
    where `answer` is the full endpoint answer, `raw` is the whole response
    dict (for the "full output" expander), and `context`/`response` feed
    `attribute()`.
    """
    if source == "mock":
        data = load_mock(str(mock_path or DEFAULT_MOCK_PATH))
        query = resolve_query(query, data)          # explicit > mock's own field
    elif source == "backend":
        query = resolve_query(query)                # backend: explicit query only
        data = fetch_backend(query)
    else:
        raise ValueError(f"unknown source {source!r} (use 'mock' or 'backend')")

    context, response = prepare_inputs(data)
    return {
        "source": source,
        "query": query,
        "answer": data["answer"],
        "context": context,
        "response": response,
        "raw": data,
    }


def attribute(
    inputs: dict,
    *,
    num_ablations: int = 32,
    start_idx: int | None = None,
    end_idx: int | None = None,
):
    """Stage 2 (slow): run attribution on stage-1 inputs.

    This is the ~34s ablation loop (its tqdm drives the UI progress bar).
    `start_idx`/`end_idx` cite a sub-span of the response (char offsets into
    `inputs["response"]`); both None attributes the whole response.
    Returns the sorted, color-scaled pandas Styler (Styler.data has columns
    "Score", "Source").
    """
    return attribute_response(
        inputs["context"],
        inputs["query"],
        inputs["response"],
        num_ablations=num_ablations,
        start_idx=start_idx,
        end_idx=end_idx,
    )
