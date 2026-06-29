"""Batch attribution over a corpus of RAGRecords.

The mode-agnostic engine driver: `run_batch` attributes each record and returns
per-record results; `aggregate` summarizes them; `write_report` dumps json + a
readable markdown summary under `runs/`. Concurrency is a single dial
(`max_workers` records at once — start small). The provider is injected: pass a
`CachingProvider` so the first run populates the cache and every rerun is free.

This same `run_batch` is what a future async/live worker calls — only the feeder
(file now, a stream later) changes.

    python -m dare.batch --limit 3            # smoke-test the whole flow on 3 records
    python -m dare.batch --limit 3 --no-cache # bypass the cache
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dare.attribution import attribute_response, prepare_inputs, resolve_query
from dare.config import Settings
from dare.schema import RAGRecord, load_corpus


def attribute_record(rec: RAGRecord, *, provider, num_ablations=32, settings: Settings | None = None) -> dict:
    """Attribute one record (whole response) and return a result dict with a few
    rollup signals useful for surfacing weakly-grounded answers."""
    query = resolve_query(rec.query, rec.payload)
    context, response = prepare_inputs(rec.payload, settings=settings)
    styler = attribute_response(
        context, query, response,
        num_ablations=num_ablations, provider=provider, settings=settings, verbose=False,
    )
    df = styler.data  # columns: Score, Source
    rows = [{"score": float(s), "source": src} for s, src in zip(df["Score"], df["Source"])]
    rows.sort(key=lambda r: -r["score"])

    top_score = rows[0]["score"] if rows else 0.0
    total_pos = sum(r["score"] for r in rows if r["score"] > 0)
    return {
        "id": rec.id,
        "query": query,
        "answer": rec.answer,
        "num_sources": len(rows),
        "top_score": top_score,
        "top_source": rows[0]["source"] if rows else "",
        # how much one source dominates the positive signal (1.0 = a single source)
        "concentration": (top_score / total_pos) if total_pos > 0 else 0.0,
        "attributions": rows,
    }


def run_batch(records, *, provider, limit=None, max_workers=3, num_ablations=32, settings=None) -> list[dict]:
    """Attribute `records` (filtered to the attributable ones, capped at `limit`),
    running up to `max_workers` concurrently. Per-record failures are captured,
    not raised, so one bad record never sinks the batch."""
    recs = [r for r in records if r.attributable]
    if limit:
        recs = recs[:limit]
    print(f"Batch: {len(recs)} attributable record(s) | max_workers={max_workers} | ablations={num_ablations}")

    def work(i, rec):
        try:
            return i, attribute_record(rec, provider=provider, num_ablations=num_ablations, settings=settings)
        except Exception as e:  # noqa: BLE001 — capture per-record, keep the batch alive
            return i, {"id": rec.id, "error": repr(e)}

    results: list = [None] * len(recs)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(work, i, r) for i, r in enumerate(recs)]
        for fut in as_completed(futures):
            i, res = fut.result()
            results[i] = res
            tag = "ERR" if "error" in res else f"top={res['top_score']:.2f}"
            print(f"  [{i+1}/{len(recs)}] {res['id']}  {tag}")
    return results


def aggregate(results: list[dict]) -> dict:
    """Roll up a batch: counts + the least-grounded records surfaced first
    (lowest top attribution score = no source strongly drove the answer)."""
    ok = [r for r in results if "error" not in r]
    errs = [r for r in results if "error" in r]
    least_grounded = sorted(ok, key=lambda r: r["top_score"])
    return {
        "records": len(results),
        "ok": len(ok),
        "errors": len(errs),
        "avg_num_sources": round(sum(r["num_sources"] for r in ok) / max(len(ok), 1), 2),
        "least_grounded": [
            {
                "id": r["id"],
                "top_score": round(r["top_score"], 3),
                "concentration": round(r["concentration"], 3),
                "query": r["query"][:70],
                "top_source": r["top_source"][:70],
            }
            for r in least_grounded
        ],
        "error_ids": [r["id"] for r in errs],
    }


def write_report(results: list[dict], report: dict, out_dir: str | Path = "runs") -> Path:
    """Write results.json + report.json + summary.md to runs/batch_<timestamp>/."""
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    run_dir = Path(out_dir) / f"batch_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    (run_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))

    lines = [
        f"# Batch report — {stamp}",
        "",
        f"- records: **{report['records']}**  (ok: {report['ok']}, errors: {report['errors']})",
        f"- avg sources/record: {report['avg_num_sources']}",
        "",
        "## Least-grounded records (lowest top attribution score first)",
        "",
        "| id | top_score | concentration | query | top source |",
        "|----|----------:|--------------:|-------|------------|",
    ]
    for r in report["least_grounded"]:
        q = r["query"].replace("|", "\\|")
        s = r["top_source"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {r['id']} | {r['top_score']} | {r['concentration']} | {q} | {s} |")
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
    args = ap.parse_args()

    records = load_corpus(args.corpus)
    base = OpenAICompatProvider()
    provider = base if args.no_cache else CachingProvider(base)

    results = run_batch(
        records, provider=provider,
        limit=args.limit, max_workers=args.max_workers, num_ablations=args.num_ablations,
    )
    report = aggregate(results)
    run_dir = write_report(results, report)

    print("\n" + json.dumps({k: v for k, v in report.items() if k != "least_grounded"}, indent=2, ensure_ascii=False))
    if hasattr(provider, "hits"):
        print(f"cache: {provider.hits} hits, {provider.misses} misses")
    print("report ->", run_dir)


if __name__ == "__main__":
    main()
