"""Cosine-similarity baseline for context attribution + top-k log-prob eval.

Runs the dare attribution pipeline on a mock QA example at several ablation
budgets (default 32 / 64 / 128) and, alongside it, scores every source with a
plain embedding cosine-similarity baseline. Both methods score the SAME set of
sources (the markdown-partitioned spans of the context), so the per-source
numbers line up and can be compared directly.

It then runs the standard ContextCite faithfulness eval on each method: rank the
sources, drop the top-k, and measure how far the response's log-probability
falls. A method that found the sources the answer truly depends on produces a
large drop. We report the drop for k = 1, 3, 5.

    logprob_drop(method, k) = logprob(response | full context)
                            - logprob(response | context minus the method's top-k)

Nothing in the dare attribution module is touched: this only imports its
entry points (`load_mock`, `prepare_inputs`, `attribute_response`) plus an
`OpenAICompatProvider` to score a masked context — the same public provider the
attribution engine uses.

Output: a JSON file under `demo/eval/results/` holding, per source, its
context-cite score at each ablation budget and its cosine similarity to both the
query and the response, plus an `eval` block with the top-k log-prob drops per
method. The companion notebook (plot_logprob_drop.ipynb) reads this and renders
the grouped bar chart; the expensive LLM work stays here so re-plotting is free.

Usage:
    python demo/eval/cosine_baseline.py
    python demo/eval/cosine_baseline.py --mock test_qa_en.json --ablations 32,64,128
    python demo/eval/cosine_baseline.py --ks 1,3,5 --embed-model nvidia/nv-embedqa-e5-v5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# Make the `dare` package importable from any cwd (mirrors the
# bootstrap in demo/runner.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
from openai import OpenAI  # noqa: E402

from dare.attribution import (  # noqa: E402
    attribute_response,
    load_mock,
    prepare_inputs,
    resolve_query,
)
from dare.providers import OpenAICompatProvider  # noqa: E402
from dare.mocks import resolve_mock  # noqa: E402
from dare.partitioner import MarkdownContextPartitioner  # noqa: E402
from context_cite.context_citer import DEFAULT_PROMPT_TEMPLATE  # noqa: E402

load_dotenv(dotenv_path=REPO_ROOT / ".env")

# The embeddings endpoint is the same OpenAI-compatible backend the pipeline
# already talks to (NVIDIA NIM by default). nv-embedqa is an asymmetric QA model:
# it expects an input_type of "query" or "passage". Override with --embed-model.
DEFAULT_EMBED_MODEL = os.getenv("EMBED_MODEL", "nvidia/nv-embedqa-e5-v5")
DEFAULT_ABLATIONS = [64, 128, 256]
DEFAULT_KS = [1, 3, 5]
DEFAULT_MOCK = "test_qa_en.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _embed_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "").rstrip("/") + "/v1",
    )


def embed(client: OpenAI, model: str, texts: list[str], input_type: str) -> np.ndarray:
    """Return an (len(texts), dim) array of embeddings.

    `input_type` is "query" or "passage" — nv-embedqa-style models embed the two
    asymmetrically. Sources are passages; the query/response we match them
    against are treated as queries. Batched to stay under request limits.
    """
    out: list[list[float]] = []
    for start in range(0, len(texts), 50):
        batch = texts[start:start + 50]
        resp = client.embeddings.create(
            model=model,
            input=batch,
            extra_body={"input_type": input_type, "truncate": "END"},
        )
        out.extend(d.embedding for d in resp.data)
    return np.array(out, dtype=np.float64)


def cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity of each row of `a` against the single vector `b`."""
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-12)
    b_norm = b / (np.linalg.norm(b) + 1e-12)
    return a_norm @ b_norm


# --- Top-k log-prob drop eval ------------------------------------------------
#
# The faithfulness metric: rank sources by a method's scores, drop the top-k,
# and see how much the response's total log-probability falls. We score a masked
# context exactly as the pipeline does — the same "Context: {context}\n\nQuery:
# {query}" prompt, scored with prompt_logprobs — so the baseline (full context)
# and ablated numbers are directly comparable.


def response_logprob(partitioner, mask: np.ndarray, query: str, response: str, provider) -> float:
    """Total log-prob of `response` given the context kept by `mask`.

    `mask` is a boolean array over sources (True = keep). The kept sources are
    re-joined by the partitioner, dropped into the pipeline's prompt template,
    and scored by summing the per-token response log-probs the `provider`
    returns (the same LogprobProvider the attribution engine uses).
    """
    context = partitioner.get_context(mask)
    user_content = DEFAULT_PROMPT_TEMPLATE.format(context=context, query=query)
    token_logprobs = provider.score_response(user_content, response)
    return float(sum(lp for _, lp in token_logprobs))


def topk_logprob_drops(
    partitioner,
    query: str,
    response: str,
    method_scores: dict[str, np.ndarray],
    ks: list[int],
    provider,
) -> dict:
    """Drop in response log-prob after removing each method's top-k sources.

    `method_scores` maps a method name to a per-source score array (higher =
    more important). Returns a dict with the full-context baseline log-prob and,
    per method, the drop at each k. Identical removal sets (different methods can
    pick the same top-k) are scored once and cached.
    """
    n = partitioner.num_sources
    full_mask = np.ones(n, dtype=bool)
    baseline = response_logprob(partitioner, full_mask, query, response, provider)
    print(f"Baseline log-prob (full context): {baseline:.3f}")

    cache: dict[frozenset, float] = {}

    def drop_for(removed: list[int]) -> float:
        key = frozenset(removed)
        if key not in cache:
            mask = full_mask.copy()
            mask[list(removed)] = False
            cache[key] = baseline - response_logprob(partitioner, mask, query, response, provider)
        return cache[key]

    methods_out: dict[str, dict] = {}
    for name, scores in method_scores.items():
        # Most important first; ties broken by index for determinism.
        ranking = sorted(range(n), key=lambda i: (-scores[i], i))
        drops, removed_idx = {}, {}
        for k in ks:
            removed = ranking[:k]
            drops[str(k)] = drop_for(removed)
            removed_idx[str(k)] = removed
            print(f"  {name:>12}  k={k}  drop={drops[str(k)]:.3f}")
        methods_out[name] = {"drops": drops, "removed_indices": removed_idx}

    return {
        "metric": "logprob_drop_topk",
        "baseline_logprob": baseline,
        "k_values": ks,
        "methods": methods_out,
    }


def run(
    mock_ref: str,
    ablations: list[int],
    ks: list[int],
    embed_model: str,
    out_path: Path,
) -> dict:
    # --- Load the mock and prepare the exact inputs the pipeline attributes ----
    mock_path = resolve_mock(mock_ref)
    data = load_mock(str(mock_path))
    query = resolve_query(None, data)
    context, response = prepare_inputs(data)

    # Canonical, ordered source list — identical to the attributions "Source"
    # column, and what the cosine baseline scores too. Keep the partitioner: the
    # eval rebuilds masked contexts from it.
    partitioner = MarkdownContextPartitioner(context)
    sources = partitioner.parts
    print(f"Sources: {len(sources)} | Ablation budgets: {ablations}\n")

    # --- Context-cite scores at each ablation budget --------------------------
    # Score map per budget, keyed by source text (the "Source" column). Aligned
    # back to `sources` order below so every method shares one index space.
    cc_scores: dict[int, dict[str, float]] = {}
    for n in ablations:
        print(f"--- ContextCite with {n} ablations ---")
        styler = attribute_response(context, query, response, num_ablations=n)
        df = styler.data  # columns: Score, Source
        cc_scores[n] = dict(zip(df["Source"], df["Score"].astype(float)))

    # --- Cosine-similarity baseline -------------------------------------------
    print("\n--- Cosine baseline (embeddings) ---")
    client = _embed_client()
    src_emb = embed(client, embed_model, sources, "passage")
    query_emb = embed(client, embed_model, [query], "query")[0]
    response_emb = embed(client, embed_model, [response], "query")[0]
    cos_query = cosine(src_emb, query_emb)
    cos_response = cosine(src_emb, response_emb)

    # --- Assemble aligned per-source records ----------------------------------
    records = []
    for i, src in enumerate(sources):
        records.append({
            "index": i,
            "source": src,
            "context_cite": {str(n): cc_scores[n].get(src) for n in ablations},
            "cosine_query": float(cos_query[i]),
            "cosine_response": float(cos_response[i]),
        })

    # --- Top-k log-prob drop eval ---------------------------------------------
    # One score array per plotted method, all in the shared source-index space.
    # The similarity baseline ranks by response-similarity (apter than query-
    # similarity for a response-log-prob metric); cosine_query is still stored
    # per source above if you want to re-rank by it.
    print("\n--- Top-k log-prob drop eval ---")
    method_scores = {f"cc_{n}": np.array([cc_scores[n][s] for s in sources]) for n in ablations}
    method_scores["similarity"] = cos_response
    provider = OpenAICompatProvider()
    eval_block = topk_logprob_drops(partitioner, query, response, method_scores, ks, provider)
    eval_block["similarity_basis"] = "cosine_response"

    result = {
        "meta": {
            "mock": mock_path.name,
            "query": query,
            "num_sources": len(sources),
            "ablation_counts": ablations,
            "k_values": ks,
            "embedding_model": embed_model,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "sources": records,
        "eval": eval_block,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nWrote {len(records)} source records -> {out_path}")
    return result


def main():
    parser = argparse.ArgumentParser(
        prog="python demo/eval/cosine_baseline.py",
        description="Context-cite vs cosine-similarity baseline over ablation budgets.",
    )
    parser.add_argument(
        "--mock",
        default=DEFAULT_MOCK,
        help=f"Mock file name or path (default: {DEFAULT_MOCK}).",
    )
    parser.add_argument(
        "--ablations",
        default=",".join(str(n) for n in DEFAULT_ABLATIONS),
        help="Comma-separated ablation budgets (default: 32,64,128).",
    )
    parser.add_argument(
        "--ks",
        default=",".join(str(k) for k in DEFAULT_KS),
        help="Comma-separated top-k values for the log-prob drop eval (default: 1,3,5).",
    )
    parser.add_argument(
        "--embed-model",
        default=DEFAULT_EMBED_MODEL,
        help=f"Embedding model id (default: {DEFAULT_EMBED_MODEL}).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON path (default: demo/eval/results/<mock>_baseline.json).",
    )
    args = parser.parse_args()

    ablations = [int(x) for x in args.ablations.split(",") if x.strip()]
    ks = [int(x) for x in args.ks.split(",") if x.strip()]
    mock_stem = Path(args.mock).stem
    out_path = Path(args.out) if args.out else RESULTS_DIR / f"{mock_stem}_baseline.json"

    run(args.mock, ablations, ks, args.embed_model, out_path)


if __name__ == "__main__":
    main()
