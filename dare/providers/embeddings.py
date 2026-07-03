"""LocalEmbeddingProvider — text → vector via a local sentence-embedding model.

Runs an open multilingual embedder (default ``intfloat/multilingual-e5-base``)
locally through ``transformers`` — no API, no key, nothing leaves the machine.
Chosen because the hosted ``nv-embedqa`` embedder was non-discriminative on
Vietnamese (0010's wrong-chunk grounding scored the same as correct answers); a
Vietnamese-capable local model separates on-topic from off-topic grounding cleanly.

e5 is asymmetric — it expects a ``"query:"`` / ``"passage:"`` prefix — so the two
methods name that intent and contain the prefix detail. That's the whole surface
``signals.py`` depends on, so swapping to a hosted/company embedder later is just
another class with the same ``embed_query`` / ``embed_passage`` methods.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

from dare.config import Settings


class LocalEmbeddingProvider:
    """Embeds text with a local HF sentence-embedding model. Model loads lazily."""

    _BATCH = 16   # keep peak memory modest on CPU

    def __init__(self, settings: Settings | None = None, model: str | None = None):
        self.model_name = model or (settings or Settings.from_env()).embed_model
        self._tok = None
        self._model = None

    def _load(self) -> None:
        if self._model is None:
            self._tok = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(self.model_name)
            self._model.eval()

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        """Embed texts as *queries* (the question side)."""
        return self._embed(texts, "query")

    def embed_passage(self, texts: list[str]) -> list[list[float]]:
        """Embed texts as *passages* (the chunk side)."""
        return self._embed(texts, "passage")

    def _embed(self, texts: list[str], prefix: str) -> list[list[float]]:
        self._load()
        out: list[list[float]] = []
        for i in range(0, len(texts), self._BATCH):
            batch = [f"{prefix}: {t}" for t in texts[i:i + self._BATCH]]
            inp = self._tok(batch, padding=True, truncation=True, max_length=512,
                            return_tensors="pt")
            with torch.no_grad():
                hidden = self._model(**inp).last_hidden_state
            mask = inp["attention_mask"].unsqueeze(-1).float()
            emb = (hidden * mask).sum(1) / mask.sum(1)      # mean pool over tokens
            emb = F.normalize(emb, p=2, dim=1)              # unit vectors -> cosine = dot
            out.extend(emb.tolist())
        return out
