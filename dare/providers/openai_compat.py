"""OpenAI-compatible prompt_logprobs provider.

Scores a fixed response with one chat-completions call using
``prompt_logprobs=1`` (the vLLM / NVIDIA NIM extension), then slices out the
response tokens. This is the default `LogprobProvider`; it owns the throttle /
retry policy and the ChatML response-span parsing. The numbers it returns are
the actual attribution signal — the throttle/retry around the call are
operational only and change none of them.
"""

from __future__ import annotations

import logging
import time

import requests
from transformers import GPT2TokenizerFast

from dare.config import Settings

logger = logging.getLogger(__name__)

_ASSISTANT_HEADER = "<|im_start|>assistant\n"


def actual_tokens(raw_logprobs: list) -> list[tuple[str, float | None]]:
    """Decode prompt_logprobs entries into ``[(token, logprob|None), ...]``.

    Each entry is either None (a position with no logprob, e.g. the leading
    special token) or a dict of candidates; with >1 candidate the actual prompt
    token is the one of highest rank.
    """
    result = []
    for entry in raw_logprobs:
        if entry is None:
            result.append(("<|im_start|>", None))
            continue
        if len(entry) == 1:
            v = list(entry.values())[0]
        else:
            v = max(entry.values(), key=lambda x: x["rank"])
        result.append((v["decoded_token"], v["logprob"]))
    return result


def response_span(full_txt: str, response_text: str) -> tuple[int, int]:
    """(start, end) char offsets of the response within the decoded prompt.

    The endpoint templates the messages as ChatML, so the response is the
    content of the assistant turn:

        ...<|im_start|>assistant\\n{RESPONSE}<|im_end|>...<|im_start|>assistant\\n

    (a trailing generation-prompt header with no content may follow). When those
    markers are present we bound the response by the first *closed* assistant
    turn rather than matching ``response_text`` directly — the server normalizes
    whitespace in the content (markdown-table / bullet newlines collapse to
    spaces), which breaks an exact substring match.

    Falls back to the original text search when the stream carries no ChatML
    markers, so a different model/endpoint keeps the prior behavior. Raises
    ValueError if neither locates the response.
    """
    search = 0
    while True:
        h = full_txt.find(_ASSISTANT_HEADER, search)
        if h == -1:
            break
        s = h + len(_ASSISTANT_HEADER)
        e = full_txt.find("<|im_end|>", s)
        if e > s:                       # a closed assistant turn with content
            return s, e
        search = s                      # empty/generation-prompt turn — keep looking

    start = full_txt.rfind(response_text)
    if start == -1:
        start = full_txt.rfind(response_text.strip())
    if start == -1:
        raise ValueError(
            f"response not found in decoded sequence (no assistant turn, no text "
            f"match).\nTail: {full_txt[-300:]!r}"
        )
    return start, start + len(response_text)


class OpenAICompatProvider:
    """Default LogprobProvider over an OpenAI-compatible prompt_logprobs endpoint."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self._call_count = 0           # monotonic, so log lines correlate
        self._estimate_tok = None      # lazy GPT-2 tokenizer, size estimates only

    def _estimate_tokens(self, text: str) -> int:
        """Rough token count for logging only (GPT-2 BPE; over-counts non-English)."""
        if self._estimate_tok is None:
            self._estimate_tok = GPT2TokenizerFast.from_pretrained("gpt2")
        return len(self._estimate_tok.encode(text, add_special_tokens=False))

    def score_response(
        self, user_content: str, response_text: str
    ) -> list[tuple[str, float]]:
        s = self.settings
        self._call_count += 1
        call_n = self._call_count

        est_tokens = self._estimate_tokens(user_content) + self._estimate_tokens(response_text)
        logger.info(
            "API call #%d -> %s | user_content=%d chars, response=%d chars, ~%d est tokens (GPT-2)",
            call_n, s.model, len(user_content), len(response_text), est_tokens,
        )

        body = {
            "model": s.model,
            "messages": [
                {"role": "user",      "content": user_content},
                {"role": "assistant", "content": response_text},
            ],
            "temperature": 0,
            "max_tokens": 1,
            "prompt_logprobs": 1,
        }

        payload = None
        for attempt in range(1, max(s.api_max_retries, 1) + 1):
            if s.api_call_delay:
                time.sleep(s.api_call_delay)        # throttle: space calls out
            try:
                r = requests.post(
                    s.llm_url,
                    headers={"Authorization": f"Bearer {s.api_key}"},
                    json=body,
                    timeout=s.api_timeout,
                )
            except requests.RequestException as e:
                logger.warning("API call #%d attempt %d/%d transport error: %s",
                               call_n, attempt, s.api_max_retries, e)
                if attempt >= s.api_max_retries:
                    raise
                time.sleep(s.api_retry_backoff * attempt)
                continue

            if r.ok:
                payload = r.json()
                break

            logger.error(
                "API call #%d attempt %d/%d FAILED: HTTP %d | user_content=%d chars, "
                "response=%d chars, ~%d est tokens (GPT-2) | body: %s",
                call_n, attempt, s.api_max_retries, r.status_code, len(user_content),
                len(response_text), est_tokens, r.text[:300],
            )
            if attempt >= s.api_max_retries:
                r.raise_for_status()                # exhausted retries -> propagate
            time.sleep(s.api_retry_backoff * attempt)

        prompt_logprobs = payload["prompt_logprobs"]
        usage = payload.get("usage") or {}
        logger.info(
            "API call #%d OK: %d prompt tokens (server-side), usage=%s",
            call_n, len(prompt_logprobs), usage or "n/a",
        )

        tokens   = actual_tokens(prompt_logprobs)
        full_txt = "".join(t for t, _ in tokens)

        start, end = response_span(full_txt, response_text)

        out, pos = [], 0
        for decoded, lp in tokens:
            tok_end = pos + len(decoded)
            if lp is not None and pos >= start and tok_end <= end:
                out.append((decoded, lp))
            pos = tok_end
            if pos >= end:
                break
        return out
