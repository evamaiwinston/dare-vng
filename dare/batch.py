"""Batch attribution over a corpus of RAGRecords.

The mode-agnostic engine driver: `run_batch` attributes each record into a
descriptive `RecordSummary`; `aggregate` rolls the batch up into corpus-level
distribution stats (no verdicts, no ranking); `write_report` dumps json + a
readable markdown report under `runs/`. Concurrency is a single dial
(`max_workers` records at once — start small). The provider is injected: pass a
`CachingProvider` so the first run populates the cache and every rerun is free.

This same `run_batch` is what a future async/live worker calls — only the feeder
(file now, a stream later) changes.

    python -m dare.batch --limit 3            # smoke-test the whole flow on 3 records
    python -m dare.batch --limit 3 --no-cache # bypass the cache
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dare.attribution import attribute_by_sentence, resolve_query
from dare.config import Settings
from dare.schema import RAGRecord, load_corpus
from dare.summary import summarize_record
from dare.signals import compute_signals


def attribute_record(
    rec: RAGRecord,
    *,
    provider,
    num_ablations: int = 32,
    settings: Settings | None = None,
    instruction: str | None = None,
    embedder=None,
) -> dict:
    """Attribute one record into a descriptive `RecordSummary`.

    Runs one ablation pass, then rolls the per-source Lasso rows up into a
    ``RecordSummary`` — context attributions rolled to chunk granularity,
    instruction mass split into its own lane, units kept in response order. When
    ``instruction`` is given, the static generation prompt is folded into the
    ablation set (``origin='instruction'``) so its causal effect is measured in
    the same pass at no extra API cost.

    Returns a dict carrying the summary plus flat record-level scalars for cheap
    console / rollup access. Descriptive only — no labels, no thresholds.
    """
    query = resolve_query(rec.query, rec.payload)
    res = attribute_by_sentence(
        query, rec.answer, rec.chunks,
        num_ablations=num_ablations, provider=provider, settings=settings, instruction=instruction,
    )
    summary = summarize_record(rec.id, query, rec.answer, res["whole"], res["units"], rec.chunks)
    out = {
        "id": rec.id,
        "query": query,
        "answer": rec.answer,
        "num_sources": len(summary.whole_source_attributions),
        "context_mass": summary.whole_context_mass,
        "instruction_mass": summary.whole_instruction_mass,
        "summary": summary,
    }
    if embedder is not None:
        out["signals"] = compute_signals(summary, embedder=embedder)
    return out


def run_batch(
    records,
    *,
    provider,
    limit: int | None = None,
    max_workers: int = 3,
    num_ablations: int = 32,
    settings: Settings | None = None,
    instruction: str | None = None,
    embedder=None,
) -> list[dict]:
    """Attribute `records` (filtered to the attributable ones, capped at `limit`),
    running up to `max_workers` concurrently. Per-record failures are captured,
    not raised, so one bad record never sinks the batch."""
    recs = [r for r in records if r.attributable]
    if limit:
        recs = recs[:limit]
    print(f"Batch: {len(recs)} attributable record(s) | max_workers={max_workers} | ablations={num_ablations} | instruction={'on' if instruction else 'off'}")

    def work(i, rec):
        try:
            return i, attribute_record(rec, provider=provider, num_ablations=num_ablations, settings=settings, instruction=instruction, embedder=embedder)
        except Exception as e:  # noqa: BLE001 — capture per-record, keep the batch alive
            return i, {"id": rec.id, "error": repr(e)}

    results: list = [None] * len(recs)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(work, i, r) for i, r in enumerate(recs)]
        for fut in as_completed(futures):
            i, res = fut.result()
            results[i] = res
            tag = "ERR" if "error" in res else f"ctx={res['context_mass']:.1f} instr={res['instruction_mass']:.1f}"
            print(f"  [{i+1}/{len(recs)}] {res['id']}  {tag}")
    return results


def aggregate(results: list[dict]) -> dict:
    """Roll a batch up into corpus-level facts: counts + the per-unit attribution
    distribution (mean/median/spread of context mass, instruction-lane incidence).

    Descriptive only — no ranking, no verdicts. Records stay in input order; any
    ordered view is the renderer's convenience, never a judgment encoded here.
    """
    ok = [r for r in results if "error" not in r]
    errs = [r for r in results if "error" in r]

    unit_context_masses = [u.context_mass for r in ok for u in r["summary"].units]
    units_with_instruction = sum(
        1 for r in ok for u in r["summary"].units if u.instruction_mass > 0
    )

    return {
        "records": len(results),
        "ok": len(ok),
        "errors": len(errs),
        "error_ids": [r["id"] for r in errs],
        "avg_num_sources": round(sum(r["num_sources"] for r in ok) / max(len(ok), 1), 2),
        "distribution": {
            "n_units": len(unit_context_masses),
            "context_mass_mean": round(statistics.fmean(unit_context_masses), 3) if unit_context_masses else 0.0,
            "context_mass_median": round(statistics.median(unit_context_masses), 3) if unit_context_masses else 0.0,
            "context_mass_sd": round(statistics.pstdev(unit_context_masses), 3) if len(unit_context_masses) > 1 else 0.0,
            "units_with_instruction": units_with_instruction,
        },
        "records_overview": [
            {
                "id": r["id"],
                "query": r["query"],
                "context_mass": round(r["context_mass"], 3),
                "instruction_mass": round(r["instruction_mass"], 3),
                "n_units": len(r["summary"].units),
            }
            for r in ok
        ],
    }


def write_report(results: list[dict], report: dict, out_dir: str | Path = "runs",
                 meta: dict | None = None) -> Path:
    """Write results.json + report.json + summary.md to runs/batch_<timestamp>/.

    The markdown centerpiece is the per-unit attribution in RESPONSE ORDER: each
    answer unit with its context / instruction mass and the chunk it grounded in
    (id + retrieval score + text), so mis-grounding surfaces as data. Magnitude is
    reported, never ranked into a verdict.

    ``meta`` (optional) is the run's provenance — the config that produced this
    run (model, instruction folded, ablations, ...). Written as ``metadata.json``
    with the run timestamp injected, so the dir name and the recorded timestamp
    always agree and no renderer has to guess how the numbers were made.
    """
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    run_dir = Path(out_dir) / f"batch_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    class _DataclassEncoder(json.JSONEncoder):
        def default(self, obj):
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return dataclasses.asdict(obj)
            return super().default(obj)

    (run_dir / "results.json").write_text(json.dumps(results, cls=_DataclassEncoder, indent=2, ensure_ascii=False))
    (run_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    if meta is not None:
        (run_dir / "metadata.json").write_text(
            json.dumps({"timestamp": stamp, **meta}, indent=2, ensure_ascii=False))

    def cell(text, n=90):
        """One-line, length-capped cell for tables/quotes."""
        t = " ".join((text or "").split())
        return (t[: n - 1] + "…") if len(t) > n else t

    def short(cid):
        return cid[:8] if cid else "—"

    dist = report["distribution"]
    lines = [
        f"# Batch report — {stamp}",
        "",
        f"- records: **{report['records']}**  (ok: {report['ok']}, errors: {report['errors']})",
        f"- avg sources/record: {report['avg_num_sources']}",
        "",
        "_mass = summed positive Lasso attribution (higher ⇒ the answer relied on that "
        "source more). Context and instruction are separate lanes. Masses are not "
        "comparable across records. Full detail in results.json._",
        "",
        "## Per-unit attribution distribution (corpus-wide)",
        "",
        f"- answer units: **{dist['n_units']}**",
        f"- context mass — mean {dist['context_mass_mean']}, median {dist['context_mass_median']}, sd {dist['context_mass_sd']}",
        f"- units with instruction-lane mass: **{dist['units_with_instruction']}** / {dist['n_units']}",
        "",
        "## Per-unit attribution by record (response order)",
        "",
    ]

    for r in results:
        if "error" in r:
            lines += [f"### {r['id']} — ERROR: {r['error']}", ""]
            continue
        s = r["summary"]
        sig = r.get("signals")
        lines += [f"### {s.record_id}", f"**Q:** {cell(s.query, 240)}", ""]
        for idx, u in enumerate(s.units):
            lines.append(f"**Answer unit:** \"{cell(u.text, 240)}\"")
            lines.append(f"  - context mass **{u.context_mass:.2f}** · instruction mass **{u.instruction_mass:.2f}**")
            top_chunk = u.chunk_attributions[0] if u.chunk_attributions else None
            if top_chunk and top_chunk.positive_mass > 0:
                lines.append(
                    f"  - grounded in chunk `{short(top_chunk.chunk_id)}` "
                    f"(retr {top_chunk.retrieval_score}, mass {top_chunk.positive_mass:.2f}): "
                    f"\"{cell(top_chunk.chunk_text, 240)}\""
                )
                if sig and idx < len(sig.units) and sig.units[idx].chunk_query_cosine is not None:
                    lines.append(f"    · chunk↔query cosine {sig.units[idx].chunk_query_cosine:.2f}")
            else:
                lines.append("  - _(no positive context attribution — retrieved context did not raise this unit's likelihood)_")
            for a in [x for x in u.instruction_attributions if x.score > 0][:2]:
                lines.append(f"  - instruction **{a.score:.2f}**: \"{cell(a.source_text, 200)}\"")
            lines.append("")

    (run_dir / "summary.md").write_text("\n".join(lines) + "\n")
    return run_dir


def main():
    from dare.providers import OpenAICompatProvider
    from dare.providers.cache import CachingProvider

    ap = argparse.ArgumentParser(prog="python -m dare.batch", description="Batch context attribution over a corpus.")
    ap.add_argument("--corpus", default="data/raw_responses.jsonl", help="jsonl/json corpus file.")
    ap.add_argument("--limit", type=int, default=3, help="Max records (default 3 — start small).")
    ap.add_argument("--max-workers", type=int, default=3, help="Records attributed concurrently.")
    ap.add_argument("--num-ablations", type=int, default=32)
    ap.add_argument("--no-cache", action="store_true", help="Bypass the on-disk logprob cache.")
    ap.add_argument("--cache-path", default="./.cache/logprobs.sqlite",
                    help="SQLite logprob cache file. Point at a fresh path (e.g. .cache/fullrun.sqlite) "
                         "for a clean, single-epoch, archivable run instead of the shared default.")
    ap.add_argument("--instruction", action="store_true",
                    help="Fold the static SYNTHESIS_SYSTEM prompt into the ablation set (origin=instruction). "
                         "Changes the prompt -> invalidates the context-only cache, makes real API calls.")
    ap.add_argument("--signals", action="store_true",
                    help="Compute query↔chunk cosine per unit (runs a local embedding model).")
    args = ap.parse_args()

    instruction = None
    if args.instruction:
        from dare.prompts import SYNTHESIS_SYSTEM
        instruction = SYNTHESIS_SYSTEM

    settings = Settings.from_env()
    records = load_corpus(args.corpus)
    base = OpenAICompatProvider()
    provider = base if args.no_cache else CachingProvider(base, path=args.cache_path)

    embedder = None
    if args.signals:
        from dare.providers import LocalEmbeddingProvider
        embedder = LocalEmbeddingProvider()

    results = run_batch(
        records, provider=provider,
        limit=args.limit, max_workers=args.max_workers, num_ablations=args.num_ablations,
        instruction=instruction, embedder=embedder,
    )
    report = aggregate(results)
    # Run provenance — the config that produced this run, so results.json is
    # self-describing (which prompt was folded, which model, how many ablations).
    # instruction_folded + instruction_sha are the load-bearing fields for the
    # attribution's defense: they prove *which* system prompt was in the ablation set.
    meta = {
        "corpus": args.corpus,
        "limit": args.limit,
        "num_ablations": args.num_ablations,
        "instruction_folded": bool(args.instruction),
        "instruction_sha": hashlib.sha256(instruction.encode()).hexdigest()[:12] if instruction else None,
        "signals": bool(args.signals),
        "no_cache": args.no_cache,
        "cache_path": None if args.no_cache else args.cache_path,
        "max_workers": args.max_workers,
        "model": settings.model,
        "lasso_alpha": settings.lasso_alpha,
        "embed_model": settings.embed_model if args.signals else None,
        "records_ok": report["ok"],
        "records_error": report["errors"],
    }
    run_dir = write_report(results, report, meta=meta)

    print("\n" + json.dumps(report, indent=2, ensure_ascii=False))
    if hasattr(provider, "hits"):
        print(f"cache: {provider.hits} hits, {provider.misses} misses")
    print("report ->", run_dir)


if __name__ == "__main__":
    main()
