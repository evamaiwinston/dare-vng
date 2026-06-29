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

from dare.attribution import attribute_by_sentence, resolve_query
from dare.config import Settings
from dare.schema import RAGRecord, load_corpus


def _unit_top_score(u: dict) -> float:
    return u["attributions"][0]["score"] if u["attributions"] else 0.0


def attribute_record(rec: RAGRecord, *, provider, num_ablations=32, settings: Settings | None = None) -> dict:
    """Attribute one record per-unit (sentence / bullet / table) from a single
    ablation pass, with whole-response rollup signals. Each attribution is mapped
    back to its Source chunk (chunk_id + retrieval score)."""
    query = resolve_query(rec.query, rec.payload)
    res = attribute_by_sentence(
        query, rec.answer, rec.sources,
        num_ablations=num_ablations, provider=provider, settings=settings,
    )
    whole = res["whole"]          # rows {score, source_text, chunk_id, doc_id, retrieval_score, origin}
    units = res["units"]

    top_score = whole[0]["score"] if whole else 0.0
    total_pos = sum(r["score"] for r in whole if r["score"] > 0)
    weakest = min(units, key=_unit_top_score) if units else None

    return {
        "id": rec.id,
        "query": query,
        "answer": rec.answer,
        "num_sources": len(whole),
        "top_score": top_score,
        "top_source": whole[0]["source_text"] if whole else "",
        "top_chunk_id": whole[0]["chunk_id"] if whole else None,
        # how much one source dominates the positive signal (1.0 = a single source)
        "concentration": (top_score / total_pos) if total_pos > 0 else 0.0,
        # the answer unit least supported by any chunk — the prime failure candidate
        "weakest_unit": ({
            "text": weakest["text"],
            "top_score": _unit_top_score(weakest),
            "top_chunk_id": weakest["attributions"][0]["chunk_id"] if weakest["attributions"] else None,
        } if weakest else None),
        "whole": whole,
        "units": units,
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
    with_weakest = sorted(
        (r for r in ok if r.get("weakest_unit")),
        key=lambda r: r["weakest_unit"]["top_score"],
    )
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
                "query": r["query"],
                "top_source": r["top_source"],
            }
            for r in least_grounded
        ],
        # the single weakest answer unit per record, weakest first — prime failure
        # candidates (raw scores; the grounded/ungrounded verdict is the diagnoser's job)
        "weakest_units": [
            {
                "id": r["id"],
                "top_score": round(r["weakest_unit"]["top_score"], 3),
                "unit": r["weakest_unit"]["text"],
                "top_chunk_id": r["weakest_unit"]["top_chunk_id"],
            }
            for r in with_weakest
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

    def cell(text, n=90):
        """One-line, length-capped cell for tables."""
        t = " ".join((text or "").split())
        return (t[: n - 1] + "…") if len(t) > n else t

    def short(cid):
        return cid[:8] if cid else "—"

    lines = [
        f"# Batch report — {stamp}",
        "",
        f"- records: **{report['records']}**  (ok: {report['ok']}, errors: {report['errors']})",
        f"- avg sources/record: {report['avg_num_sources']}",
        "",
        "_attr = attribution weight (higher ⇒ the answer relied on that source more); "
        "retr = retrieval score. Scores are not comparable across records. Full text in results.json._",
        "",
        "## Least-grounded records (lowest top attribution first)",
        "",
        "| id | top_score | concentration | top source |",
        "|----|----------:|--------------:|------------|",
    ]
    for r in report["least_grounded"]:
        lines.append(f"| {r['id']} | {r['top_score']} | {r['concentration']} | {cell(r['top_source'])} |")

    lines += [
        "",
        "## Weakest answer unit per record (lowest top-attribution first)",
        "",
        "| id | unit top_score | top chunk | answer unit |",
        "|----|---------------:|-----------|-------------|",
    ]
    for r in report.get("weakest_units", []):
        lines.append(f"| {r['id']} | {r['top_score']} | `{short(r['top_chunk_id'])}` | {cell(r['unit'])} |")

    # The readable centerpiece: each answer unit + the source TEXT it attributed
    # to (full query, full unit, top-3 positive attributions).
    lines += ["", "## Per-unit attribution by record", ""]
    for r in results:
        if "error" in r:
            lines += [f"### {r['id']} — ERROR: {r['error']}", ""]
            continue
        lines += [f"### {r['id']}", f"**Q:** {' '.join(r['query'].split())}", ""]
        for u in r.get("units", []):
            lines.append(f"**Answer unit:** \"{' '.join(u['text'].split())}\"")
            tops = [a for a in u["attributions"] if a["score"] > 0][:3]
            if not tops:
                lines.append("  - _(no positive attribution — nothing in context raised this unit's likelihood)_")
            for a in tops:
                lines.append(
                    f"  - attr **{a['score']:.2f}** · chunk `{short(a['chunk_id'])}` · "
                    f"retr {a['retrieval_score']} · \"{cell(a['source_text'], 240)}\""
                )
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
