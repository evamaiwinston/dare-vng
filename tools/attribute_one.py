"""Sandbox drop-in for `dare.attribution.attribute_by_sentence`.

`attribute_one()` has the SAME signature and SAME return
(``{response, whole, units}``) as the real engine, and today just delegates to
it — so results are identical. It exists as the ONE place to prototype ablation
concurrency later (copy the engine's ablation loop in here and thread it)
WITHOUT editing `dare/attribution.py`. The notebook calls `attribute_one(...)`
instead of `attribute_by_sentence(...)`; when the sandbox changes, the notebook
line doesn't.

Like the engine, it runs a SINGLE ablation pass and produces both the whole-
response attribution and the per-sentence/unit attributions from that one pass.

Notebook use (record already loaded):
    from tools.attribute_one import attribute_one
    res = attribute_one(rec.query, rec.answer, rec.chunks, num_ablations=32,
                        provider=provider, settings=settings)          # no instruction
    res_i = attribute_one(rec.query, rec.answer, rec.chunks, num_ablations=32,
                          provider=provider, settings=settings,
                          instruction=SYNTHESIS_SYSTEM)                 # instruction lane

`run_one()` + the CLI below are thin conveniences on top (load a record, time it,
summarize) for quick command-line checks — the notebook doesn't need them.
"""

import argparse
import os
import sys
import time

# Allow `python tools/attribute_one.py ...`: put the repo root on sys.path so the
# `tools` / `dare` packages import even when the script's own dir is sys.path[0].
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dare.attribution import attribute_by_sentence, resolve_query
from dare.config import Settings
from dare.prompts import SYNTHESIS_SYSTEM
from dare.providers import CachingProvider, OpenAICompatProvider
from dare.schema import load_corpus
from dare.summary import summarize_record


def attribute_one(
    query: str,
    response: str,
    chunks: list,
    *,
    num_ablations: int = 32,
    ablation_keep_prob: float = 0.5,
    batch_size: int = 1,
    provider=None,
    settings: Settings | None = None,
    instruction: str | None = None,
) -> dict:
    """Drop-in for `dare.attribution.attribute_by_sentence` — same args, same
    ``{response, whole, units}`` return, one ablation pass giving both the whole
    response and every unit.

    Today this delegates verbatim, so it IS the engine. It's the seam for later:
    to prototype ablation concurrency, replace the body below with a copy of the
    engine's `_build_citer` / `_ForwardShim` path that threads the ablation calls
    (add a ``max_workers`` param here) — the notebook keeps calling this unchanged.

    ``provider`` left None => the engine builds a bare `OpenAICompatProvider`
    (cache OFF), which is what you want for honest timings.
    """
    return attribute_by_sentence(
        query, response, chunks,
        num_ablations=num_ablations,
        ablation_keep_prob=ablation_keep_prob,
        batch_size=batch_size,
        provider=provider,
        settings=settings,
        instruction=instruction,
    )


# --- command-line conveniences (not used by the notebook) --------------------

def build_provider(*, use_cache: bool = False, settings: Settings | None = None):
    """A logprob provider. Default cache-OFF (bare `OpenAICompatProvider`) so every
    ablation call hits the model live. ``use_cache=True`` wraps it in
    `CachingProvider` (identical results, replays ``./.cache/logprobs.sqlite``)."""
    settings = settings or Settings.from_env()
    base = OpenAICompatProvider(settings)
    return CachingProvider(base) if use_cache else base


def load_record(corpus, qa_id: str | None = None, index: int = 0):
    """Load ONE `RAGRecord` from a corpus (`.jsonl` or `.json`, incl. mock_data/).
    Pick by ``qa_id`` else ``index``. Raises if not found / not attributable."""
    records = load_corpus(corpus)
    if qa_id is not None:
        rec = next((r for r in records if r.id == qa_id), None)
        if rec is None:
            raise KeyError(f"no record with id {qa_id!r} in {corpus} ({len(records)} records)")
    else:
        rec = records[index]
    if not rec.attributable:
        raise ValueError(f"record {rec.id!r} has no answer/sources to attribute")
    return rec


def run_one(
    record,
    *,
    num_ablations: int = 32,
    instruction: bool | str | None = None,
    use_cache: bool = False,
    provider=None,
    settings: Settings | None = None,
):
    """Convenience: attribute one already-loaded record via `attribute_one`, timed,
    then roll up into a `RecordSummary`. ``instruction=True`` folds in the real
    `SYNTHESIS_SYSTEM` prompt; a str folds in that verbatim text."""
    settings = settings or Settings.from_env()
    provider = provider or build_provider(use_cache=use_cache, settings=settings)
    query = resolve_query(record.query, record.payload)
    instr_text = SYNTHESIS_SYSTEM if instruction is True else (instruction or None)

    t0 = time.perf_counter()
    res = attribute_one(
        query, record.answer, record.chunks,
        num_ablations=num_ablations, provider=provider, settings=settings,
        instruction=instr_text,
    )
    elapsed = time.perf_counter() - t0

    summary = summarize_record(record.id, query, record.answer, res["whole"], res["units"], record.chunks)
    return {
        "id": record.id,
        "query": query,
        "answer": record.answer,
        "elapsed": elapsed,
        "num_ablations": num_ablations,
        "instruction": bool(instr_text),
        "summary": summary,
        "raw": res,
        "provider": provider,
    }


def _print_result(out: dict) -> None:
    s = out["summary"]
    cache_on = isinstance(out["provider"], CachingProvider)
    print(f"\nid            : {out['id']}")
    print(f"query         : {out['query']}")
    print(f"elapsed       : {out['elapsed']:.2f}s  ({out['num_ablations']} ablations, "
          f"instruction={'on' if out['instruction'] else 'off'}, cache={'on' if cache_on else 'off'})")
    print(f"context mass  : {s.whole_context_mass:.3f}")
    print(f"instr. mass   : {s.whole_instruction_mass:.3f}")
    print(f"units         : {len(s.units)}")
    if cache_on:
        p = out["provider"]
        print(f"cache         : {p.hits} hits, {p.misses} misses")
    for u in s.units:
        print(f"  - ctx {u.context_mass:.2f} · instr {u.instruction_mass:.2f} :: {u.text[:80]}")


def main():
    parser = argparse.ArgumentParser(
        prog="attribute_one",
        description="Attribute ONE record via attribute_one (a drop-in for the real "
                    "attribute_by_sentence engine).",
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--corpus", metavar="PATH", default=None,
                     help="Corpus file (.jsonl or .json) to load the record from.")
    src.add_argument("--mock", metavar="NAME_OR_PATH", default=None,
                     help="A mock from mock_data/ (name or path). See --list-mocks.")
    parser.add_argument("--list-mocks", action="store_true",
                        help="List mock files in mock_data/ and exit.")
    parser.add_argument("--qa-id", default=None,
                        help="Record id to attribute (default: use --index).")
    parser.add_argument("--index", type=int, default=0,
                        help="Record index to attribute when --qa-id is omitted (default: 0).")
    parser.add_argument("--num-ablations", type=int, default=32,
                        help="Number of ablations (default: 32).")
    parser.add_argument("--instruction", action="store_true",
                        help="Fold the SYNTHESIS_SYSTEM generation prompt into the ablation set.")
    parser.add_argument("--cache", action="store_true",
                        help="Use the sqlite logprob cache (default: OFF, so timings are live).")
    args = parser.parse_args()

    # Imported lazily so the notebook path (which never lists mocks) doesn't pull it in.
    from tools.mocks import list_mocks, mock_names, resolve_mock

    if args.list_mocks:
        mocks = list_mocks()
        if not mocks:
            print("No mock files found in mock_data/.")
        else:
            print(f"Available mocks in mock_data/ ({len(mocks)}):")
            for name in mock_names():
                print(f"  {name}")
        return

    corpus = args.corpus
    if args.mock:
        try:
            corpus = str(resolve_mock(args.mock))
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)
    if not corpus:
        print("Error: provide --corpus PATH or --mock NAME (see --list-mocks).", file=sys.stderr)
        sys.exit(2)

    try:
        rec = load_record(corpus, qa_id=args.qa_id, index=args.index)
    except (KeyError, ValueError, IndexError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    out = run_one(
        rec,
        num_ablations=args.num_ablations,
        instruction=args.instruction,
        use_cache=args.cache,
    )
    _print_result(out)


if __name__ == "__main__":
    main()
