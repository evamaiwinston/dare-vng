"""LogprobProvider — attribution needs per-token log-probabilities of a response
for a given user prompt. Any backend that can return token logprobs satisfies this
protocol (api endpoint, caching).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LogprobProvider(Protocol):
    def score_response(
        self, user_content: str, response_text: str
    ) -> list[tuple[str, float]]:
        """Return shape `[(token, logprob), ...]` for the tokens of
        response_text, scored in the context of user_content.

        Tokenization is by provider, 
        _align_to_shell_tokens() in attribution.py aligns them to original char position. 
        Only the response tokens are returned, prompt tokens are dropped.
        """
        ...
