"""CachingProvider — wrap a LogprobProvider, persist its calls, replay them.

ContextCite's ablation masks are deterministic, so the same record produces the
exact same ``(user_content, response_text)`` calls every run. Caching them means
you pay the LLM cost once, then rerun attribution / diagnosis / reports for free
and instantly. Keyed on a hash of ``(model, user_content, response_text)``;
backed by sqlite so it's safe under the batch runner's thread pool.

    from dare.providers import OpenAICompatProvider
    from dare.providers.cache import CachingProvider
    provider = CachingProvider(OpenAICompatProvider())   # populate on first run, replay after
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path

from dare.providers.base import LogprobProvider


class CachingProvider:
    """A LogprobProvider that memoizes `inner.score_response` to a sqlite file."""

    def __init__(
        self,
        inner: LogprobProvider,
        path: str | Path = "./.cache/logprobs.sqlite",
        model_tag: str | None = None,
    ):
        self.inner = inner
        # Namespacing the key by model keeps caches from different endpoints apart.
        self.model_tag = model_tag or getattr(getattr(inner, "settings", None), "model", "") or ""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS lp (k TEXT PRIMARY KEY, v TEXT)")
        self._db.commit()
        self.hits = 0
        self.misses = 0

    def _key(self, user_content: str, response_text: str) -> str:
        h = hashlib.sha256()
        for part in (self.model_tag, user_content, response_text):
            h.update(part.encode("utf-8"))
            h.update(b"\x00")
        return h.hexdigest()

    def score_response(self, user_content: str, response_text: str) -> list[tuple[str, float]]:
        key = self._key(user_content, response_text)
        with self._lock:
            row = self._db.execute("SELECT v FROM lp WHERE k=?", (key,)).fetchone()
        if row is not None:
            self.hits += 1
            return [tuple(x) for x in json.loads(row[0])]

        # Miss: call the real provider OUTSIDE the lock so concurrent network
        # calls aren't serialized. A rare double-miss on the same key just scores
        # twice — harmless, since the result is deterministic.
        self.misses += 1
        out = self.inner.score_response(user_content, response_text)
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO lp VALUES (?, ?)", (key, json.dumps(out))
            )
            self._db.commit()
        return out

    def close(self) -> None:
        with self._lock:
            self._db.close()
