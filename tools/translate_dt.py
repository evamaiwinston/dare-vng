#!/usr/bin/env python3
"""THROWAWAY — translate a run's Vietnamese strings to English via deep-translator
(free, unofficial Google Translate HTTP endpoint — no API key, no LLM tokens, no
Gemini quota). Same sidecar contract as translate.py: caches into translations.json
(a VN->EN dict), re-runs only translate strings not already cached, so it's cheap
and idempotent, and both scripts can share the same cache file.

Collects only what dare_report.html actually renders (query, unit text, whole-chunk
text, instruction lines, and each unit's top-8-by-|score| source rows — the same cap
render.py applies) rather than every attributed row, so there's nothing wasted on
strings that never reach the screen.

Nothing in dare/ imports this. It exists only so the annotated-answer prototype is
readable enough to judge the FORM. The attribution itself stays on the real VN data.

    python tools/translate_dt.py                         # defaults to the 0702 run
    python tools/translate_dt.py runs/batch_20260713_101216
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from deep_translator import GoogleTranslator

DEFAULT_RUN = "runs/batch_20260702_094705"
SIDECAR = Path("translations.json")
BATCH = 50
MAX_CHARS = 3000  # deep-translator's underlying endpoint hard-caps at 5000 chars/request


def collect_strings(results: list[dict]) -> list[str]:
    """Every VN string the renderer actually displays, deduped, order-stable.

    Mirrors render.py exactly: whole_chunk_attributions (record-level dedup'd chunk
    text), whole_instruction_attributions, and per-unit source rows capped to the
    top 8 by |score| (render.py's own display cap) rather than the full source list.
    """
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
            for a in sorted(u.get("source_attributions") or [], key=lambda a: -abs(a["score"]))[:8]:
                add(a.get("source_text"))
        for c in s["whole_chunk_attributions"]:
            add(c["chunk_text"])
        for a in s["whole_instruction_attributions"]:
            add(a.get("source_text"))
    return list(seen)


def chunk_text(text: str, max_len: int = MAX_CHARS) -> list[str]:
    """Split into pieces each <= max_len, preferring paragraph/line boundaries.

    Some chunk_text values are full insurance-benefit tables up to ~14.6K chars,
    and not all of them contain blank-line breaks (one 10.5K-char table was a
    single unbroken block) — so this falls through blank-line -> line -> hard
    character split rather than assuming any one separator exists.
    """
    if len(text) <= max_len:
        return [text]
    for sep in ("\n\n", "\n"):
        if sep in text:
            pieces, current = [], ""
            for part in text.split(sep):
                candidate = f"{current}{sep}{part}" if current else part
                if len(candidate) <= max_len:
                    current = candidate
                    continue
                if current:
                    pieces.append(current)
                current = part if len(part) <= max_len else ""
                if not current and part:
                    pieces.extend(chunk_text(part, max_len))
            if current:
                pieces.append(current)
            return pieces
    # No separators at all (e.g. one giant table row) — hard character split.
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]


def translate_piece(piece: str, translator: GoogleTranslator, retries: int = 3) -> str:
    """One piece, a few retries with backoff — the unofficial endpoint is flaky
    (TranslationNotFound / RequestError / TooManyRequests happen transiently,
    not just on bad input), so a single blip shouldn't nuke the whole run."""
    for attempt in range(retries):
        try:
            return translator.translate(piece)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def translate_one(text: str, translator: GoogleTranslator) -> str:
    pieces = chunk_text(text)
    if len(pieces) == 1:
        return translate_piece(pieces[0], translator)
    return "\n\n".join(translate_piece(p, translator) if p.strip() else p for p in pieces)


def main():
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_RUN)

    results = json.loads((run / "results.json").read_text())
    strings = collect_strings(results)

    cache: dict[str, str] = json.loads(SIDECAR.read_text()) if SIDECAR.exists() else {}
    todo = [s for s in strings if s not in cache]
    print(f"strings: {len(strings)} total | {len(cache)} cached | {len(todo)} to translate")

    translator = GoogleTranslator(source="vi", target="en")

    failed: list[str] = []
    for i, src in enumerate(todo, 1):
        try:
            cache[src] = translate_one(src, translator)
        except Exception as e:  # noqa: BLE001 — skip this one string, keep going
            failed.append(src)
            print(f"  [{i}/{len(todo)}] SKIPPED ({repr(e)[:120]}): {src[:60]!r}")
        if i % BATCH == 0 or i == len(todo):
            SIDECAR.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
            print(f"  [{i}/{len(todo)}] ok — saved")

    print(f"-> {SIDECAR.resolve()} ({len(cache)} entries, {len(failed)} skipped)")
    if failed:
        print("   skipped strings will be retried automatically next run (not cached)")


if __name__ == "__main__":
    main()
