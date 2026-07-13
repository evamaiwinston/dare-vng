#!/usr/bin/env python3
"""THROWAWAY — translate a run's Vietnamese strings to English for the prototype report.

Collects every human-readable VN string in runs/<run>/results.json (query, unit text,
chunk representative text, source rows, instruction drivers), batches them to the Gemini
free-tier REST API, and caches the result in translations.json (a VN->EN dict). Cached:
re-runs only translate strings not already in the sidecar, so it's cheap and idempotent.

Nothing in dare/ imports this. It exists only so the annotated-answer prototype is
readable enough to judge the FORM. The attribution itself stays on the real VN data.

    export GEMINI_API_KEY=...          # free-tier key from aistudio.google.com
    python tools/translate.py                # defaults to the 0702 run
    python tools/translate.py runs/batch_20260702_094705
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()  # pick up GEMINI_API_KEY from repo .env (same file as OPENAI_API_KEY etc.)

DEFAULT_RUN = "runs/batch_20260702_094705"
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
SIDECAR = Path("translations.json")
BATCH = 40


def collect_strings(results: list[dict]) -> list[str]:
    """Every VN string the renderer shows, deduped, order-stable."""
    seen: dict[str, None] = {}

    def add(s):
        if s and s.strip():
            seen.setdefault(s, None)

    for r in results:
        if "error" in r:
            continue
        s = r["summary"]
        add(s["query"])
        for u in s["units"]:
            add(u["text"])
            for c in (u.get("chunk_attributions") or []):
                add(c["chunk_text"])
            for a in (u.get("source_attributions") or []):
                add(a["source_text"])
            for a in (u.get("instruction_attributions") or []):
                add(a["source_text"])
    return list(seen)


def gemini_translate(strings: list[str], api_key: str) -> list[str]:
    """One batch -> list of English translations, same order/length (Gemini structured JSON)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={api_key}"
    prompt = (
        "Translate each Vietnamese string in this JSON array to natural English. "
        "These are HR-policy Q&A snippets. Return a JSON array of the SAME length in the "
        "SAME order — translation text only, no numbering, no commentary.\n\n"
        + json.dumps(strings, ensure_ascii=False)
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": {"type": "ARRAY", "items": {"type": "STRING"}},
        },
    }
    r = requests.post(url, json=body, timeout=(10, 120))
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    out = json.loads(text)
    if len(out) != len(strings):
        raise ValueError(f"batch length mismatch: sent {len(strings)}, got {len(out)}")
    return out


def main():
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_RUN)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("set GEMINI_API_KEY (free tier: https://aistudio.google.com/apikey)")

    results = json.loads((run / "results.json").read_text())
    strings = collect_strings(results)

    cache: dict[str, str] = json.loads(SIDECAR.read_text()) if SIDECAR.exists() else {}
    todo = [s for s in strings if s not in cache]
    print(f"strings: {len(strings)} total | {len(cache)} cached | {len(todo)} to translate")

    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        try:
            for src, en in zip(chunk, gemini_translate(chunk, api_key)):
                cache[src] = en
            SIDECAR.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
            print(f"  [{min(i+BATCH, len(todo))}/{len(todo)}] ok")
        except Exception as e:  # noqa: BLE001 — keep partial progress, report and stop
            print(f"  batch at {i} FAILED: {repr(e)[:200]}")
            break
        time.sleep(4.5)  # free tier ~15 RPM — space calls out

    print(f"-> {SIDECAR.resolve()} ({len(cache)} entries)")


if __name__ == "__main__":
    main()
