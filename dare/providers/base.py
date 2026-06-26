"""LogprobProvider — the one thing the attribution engine needs from an LLM.

Attribution fundamentally needs per-token log-probabilities of a *fixed*
response under a given user prompt: masking context and re-scoring the same
response is what reveals which sources the response depended on. Any backend
that can return those token logprobs satisfies this protocol, and the engine
never calls an LLM any other way — so swapping endpoints is swapping a provider.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LogprobProvider(Protocol):
    def score_response(
        self, user_content: str, response_text: str
    ) -> list[tuple[str, float]]:
        """Return ``[(token, logprob), ...]`` for the tokens of ``response_text``
        scored as the assistant reply to ``user_content``.

        Tokens are the provider's own tokenization; the caller aligns them onto
        its tokenizer boundaries. Only the response tokens are returned (prompt
        tokens are dropped).
        """
        ...
