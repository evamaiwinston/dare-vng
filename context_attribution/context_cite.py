"""
Context attribution pipeline using ContextCite + vllm prompt_logprobs.

Ports notebook 03_local_pipeline.ipynb to an importable module.

High-level usage:
    from context_attribution.context_cite import attribute_response, fetch_backend, prepare_inputs

    data = fetch_backend("Nhân viên VNG được nghỉ phép bao nhiêu ngày mỗi năm?")
    context, response = prepare_inputs(data)
    df = attribute_response(context, query, response)
"""

import os
import json
import time
import logging
import numpy as np
import requests
import torch
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from transformers import GPT2TokenizerFast

# --- Compatibility patches (context_cite 0.0.4 + pandas 2.x + numpy 2.x) ----
from pandas.io.formats.style import Styler
if not hasattr(Styler, "applymap"):
    Styler.applymap = Styler.map

from context_cite import ContextCiter
from context_cite import utils as _cc_utils

from context_attribution.partitioner import MarkdownContextPartitioner


def _patched_color_scale(val, max_val):
    # Fixes: (1) negative val overshoots RGB >255, (2) numpy 2.x f-string formatting
    start_color = (255, 255, 255)
    end_color = (80, 180, 80)
    if val <= 0:
        return f"background-color: rgb{start_color}"
    elif val >= max_val:
        return f"background-color: rgb{end_color}"
    fraction = val / max_val
    interpolated = tuple(int(start_color[i] + (end_color[i] - start_color[i]) * fraction) for i in range(3))
    return f"background-color: rgb{interpolated}"

_cc_utils._color_scale = _patched_color_scale

# --- Config ------------------------------------------------------------------

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

API_KEY  = os.getenv("OPENAI_API_KEY")
LLM_URL  = os.getenv("OPENAI_BASE_URL", "").rstrip("/") + "/v1/chat/completions"
MODEL    = os.getenv("LLM_MODEL", "local-model-mini")

BACKEND_URL   = os.getenv("BACKEND_API_URL")
WORKSPACE_ID  = os.getenv("BACKEND_WORKSPACE_ID")
BACKEND_TOKEN = os.getenv("BACKEND_API_KEY")

# local-model-mini crashes the vllm worker when total prompt tokens exceed ~340
# (measured overhead=44, safe limit=340). Set to None when switching to local-model.
MINI_MAX_RESPONSE_CHARS = 500  # 120 if "mini" in MODEL else None  # ~40 response tokens
MINI_MAX_CONTEXT_CHARS  = 2200 #900 if "mini" in MODEL else None  # ~250 context tokens

# --- Logging -----------------------------------------------------------------

logger = logging.getLogger(__name__)

_api_call_count = 0      # monotonic counter so log lines can be correlated
_estimate_tok = None     # lazy GPT-2 tokenizer, used only for size estimates

# --- Graceful-call throttle / retry ------------------------------------------
# The mini worker can fall over under a burst of prompt_logprobs calls. Throttle
# spaces calls out; retry rides through transient 5xx / connection errors. These
# are operational only — they change no attribution value. Override from a notebook.
API_CALL_DELAY    = 0.0  # seconds to sleep BEFORE each call (set >0 to throttle)
API_MAX_RETRIES   = 1    # total attempts per call (1 = no retry)
API_RETRY_BACKOFF = 10.0  # seconds; wait = backoff * attempt_number (linear)


def _estimate_tokens(text: str) -> int:
    """Rough token count for logging only (GPT-2 BPE; over-counts non-English)."""
    global _estimate_tok
    if _estimate_tok is None:
        _estimate_tok = GPT2TokenizerFast.from_pretrained("gpt2")
    return len(_estimate_tok.encode(text, add_special_tokens=False))

# --- Tokenizer ---------------------------------------------------------------

def make_tokenizer() -> GPT2TokenizerFast:
    """GPT-2 as a structural tokenizer shell for ContextCiter.

    Provides pad/eos tokens, encode/decode, token_to_chars, and .pad().
    The chat_template matches the ChatML format the LLM endpoint expects.
    Actual log-probabilities come from the API, not GPT-2 weights.
    """
    tok = GPT2TokenizerFast.from_pretrained("gpt2")
    tok.pad_token    = tok.eos_token
    tok.padding_side = "left"
    tok.chat_template = (
        "{% for message in messages %}"
        "<|im_start|>{{ message['role'] }}\n{{ message['content'] }}<|im_end|>\n"
        "{% endfor %}"
        "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}"
    )
    return tok

# --- API helpers -------------------------------------------------------------

def _actual_tokens(raw_logprobs: list) -> list[tuple[str, float | None]]:
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


def _extract_user_content(prompt_text: str) -> str:
    start = prompt_text.find("<|im_start|>user\n")
    if start == -1:
        raise ValueError(f"No user turn found in prompt: {prompt_text[:80]!r}")
    start += len("<|im_start|>user\n")
    end = prompt_text.find("<|im_end|>", start)
    return prompt_text[start:] if end == -1 else prompt_text[start:end]


def _api_response_token_logprobs(user_content: str, response_text: str) -> list[tuple[str, float]]:
    global _api_call_count
    _api_call_count += 1
    call_n = _api_call_count

    est_tokens = _estimate_tokens(user_content) + _estimate_tokens(response_text)
    logger.info(
        "API call #%d -> %s | user_content=%d chars, response=%d chars, ~%d est tokens (GPT-2)",
        call_n, MODEL, len(user_content), len(response_text), est_tokens,
    )

    body = {
        "model": MODEL,
        "messages": [
            {"role": "user",      "content": user_content},
            {"role": "assistant", "content": response_text},
        ],
        "temperature": 0,
        "max_tokens": 1,
        "prompt_logprobs": 1,
    }

    payload = None
    for attempt in range(1, max(API_MAX_RETRIES, 1) + 1):
        if API_CALL_DELAY:
            time.sleep(API_CALL_DELAY)          # throttle: space calls out
        try:
            r = requests.post(
                LLM_URL,
                headers={"Authorization": f"Bearer {API_KEY}"},
                json=body,
                timeout=600,
            )
        except requests.RequestException as e:
            logger.warning("API call #%d attempt %d/%d transport error: %s",
                           call_n, attempt, API_MAX_RETRIES, e)
            if attempt >= API_MAX_RETRIES:
                raise
            time.sleep(API_RETRY_BACKOFF * attempt)
            continue

        if r.ok:
            payload = r.json()
            break

        logger.error(
            "API call #%d attempt %d/%d FAILED: HTTP %d | user_content=%d chars, "
            "response=%d chars, ~%d est tokens (GPT-2) | body: %s",
            call_n, attempt, API_MAX_RETRIES, r.status_code, len(user_content),
            len(response_text), est_tokens, r.text[:300],
        )
        if attempt >= API_MAX_RETRIES:
            r.raise_for_status()                # exhausted retries -> propagate
        time.sleep(API_RETRY_BACKOFF * attempt)
    prompt_logprobs = payload["prompt_logprobs"]
    usage = payload.get("usage") or {}
    logger.info(
        "API call #%d OK: %d prompt tokens (server-side), usage=%s",
        call_n, len(prompt_logprobs), usage or "n/a",
    )

    tokens   = _actual_tokens(prompt_logprobs)
    full_txt = "".join(t for t, _ in tokens)

    start = full_txt.rfind(response_text)
    if start == -1:
        start = full_txt.rfind(response_text.strip())
    if start == -1:
        raise ValueError(f"response_text not found in decoded sequence.\nTail: {full_txt[-300:]!r}")
    end = start + len(response_text)

    out, pos = [], 0
    for decoded, lp in tokens:
        tok_end = pos + len(decoded)
        if lp is not None and pos >= start and tok_end <= end:
            out.append((decoded, lp))
        pos = tok_end
        if pos >= end:
            break
    return out


def _align_to_gpt2_tokens(
    api_tokens: list[tuple[str, float]],
    response_text: str,
    gpt2_response_ids: list[int],
    tokenizer: GPT2TokenizerFast,
) -> list[float]:
    n = len(gpt2_response_ids)
    if not api_tokens:
        return [-5.0] * n

    api_spans, pos = [], 0
    for decoded, lp in api_tokens:
        api_spans.append((pos, pos + len(decoded), lp))
        pos += len(decoded)

    enc = tokenizer(response_text, add_special_tokens=False)

    result = []
    for j in range(n):
        cs = enc.token_to_chars(j)
        our_s, our_e = cs.start, cs.end
        overlapping = [
            (lp, min(our_e, a_e) - max(our_s, a_s))
            for a_s, a_e, lp in api_spans
            if min(our_e, a_e) > max(our_s, a_s)
        ]
        if overlapping:
            total = sum(o for _, o in overlapping)
            result.append(sum(lp * o / total for lp, o in overlapping))
        else:
            mid = (our_s + our_e) / 2
            result.append(min(api_spans, key=lambda x: abs((x[0] + x[1]) / 2 - mid))[2])
    return result

# --- APIModel ----------------------------------------------------------------
#
# Satisfies the interface ContextCiter uses:
#
#   model.device                               → torch.device("cpu")
#   model.generate(input_ids, ...)             → LongTensor [1, full_seq_len]
#   model(input_ids, attention_mask, labels)   → obj with .logits [bs, seq, V]
#
# generate():
#   We already have RESPONSE from the backend, so no live generation call.
#   We append encoded RESPONSE tokens to the prompt.
#
# __call__():
#   For each ablated batch item:
#   1. Decode prompt / response from input_ids / labels via GPT-2.
#   2. Parse the ChatML prompt to extract user_content (masked context + query).
#   3. Call the LLM endpoint with prompt_logprobs=1 to score the response.
#   4. Align API token logprobs onto GPT-2 token boundaries.
#   5. Build fake logits so _compute_logit_probs returns the aligned logprobs:
#
#      logits[b, j, label_id] = api_logprob + log(V-1),  all others = 0
#      → softmax-based loss recovers api_logprob exactly.
#
#   Only the response tail of the logits is ever read downstream
#   (_get_response_logit_probs slices output.logits[:, -(R+1):-1]), so we
#   allocate just [bs, R+1, V] rather than the full [bs, seq_len, V]. The prompt
#   rows were only ever zero-filled and discarded; skipping them makes the
#   allocation independent of context length (the old full-width tensor grew
#   with MAX_CONTEXT_CHARS and was ~95% wasted). R is the response token count,
#   constant across ablations and batch items since the response is fixed.

class APIModel:

    device = torch.device("cpu")

    def __init__(self, response: str):
        self._response  = response
        self._tokenizer = make_tokenizer()

    def generate(self, input_ids: torch.Tensor, **kwargs) -> torch.Tensor:
        resp_ids = self._tokenizer.encode(self._response, add_special_tokens=False)
        full_ids = input_ids[0].tolist() + resp_ids
        return torch.tensor([full_ids], dtype=torch.long)

    def __call__(self, input_ids, attention_mask=None, labels=None, **kwargs):
        bs     = input_ids.shape[0]
        V      = self._tokenizer.vocab_size
        log_V1 = float(np.log(V - 1))

        # R = number of response tokens (non -100 labels). Constant across rows
        # because the response is fixed; only the context mask varies. Allocate
        # just the response tail [bs, R+1, V] — independent of context length.
        R      = sum(1 for l in labels[0].tolist() if l != -100)
        logits = torch.zeros(bs, R + 1, V)

        for b in range(bs):
            ids = input_ids[b].tolist()
            lbs = labels[b].tolist()

            resp_start   = next(i for i, l in enumerate(lbs) if l != -100)
            prompt_ids   = ids[:resp_start]
            response_ids = lbs[resp_start:]

            prompt_text   = self._tokenizer.decode(prompt_ids)
            response_text = self._tokenizer.decode(response_ids)
            user_content  = _extract_user_content(prompt_text)

            api_tokens = _api_response_token_logprobs(user_content, response_text)
            aligned    = _align_to_gpt2_tokens(api_tokens, response_text, response_ids, self._tokenizer)

            # Row j of the tail corresponds to old global position resp_start-1+j,
            # which is exactly what output.logits[:, -(R+1):-1] reads back.
            for j, (rid, alp) in enumerate(zip(response_ids, aligned)):
                logits[b, j, rid] = alp + log_V1

        return SimpleNamespace(logits=logits)

# --- Data helpers ------------------------------------------------------------

def fetch_backend(query: str) -> dict:
    """Call the backend RAG API and return the raw response dict."""
    resp = requests.post(
        f"{BACKEND_URL}/api/v1/workspaces/{WORKSPACE_ID}/chat",
        headers={"Authorization": f"Bearer {BACKEND_TOKEN}"},
        json={"query": query, "mode": "agent", "top_k": 5},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_backend_or_file(query: str, fallback_path: str | Path) -> dict:
    """Try backend API first; fall back to a local JSON file if unreachable."""
    try:
        data = fetch_backend(query)
        print("Loaded from live backend API")
        return data
    except Exception as e:
        print(f"Backend unreachable ({e.__class__.__name__}), loading from {fallback_path}")
        with open(fallback_path) as f:
            return json.load(f)


def load_mock(mock_path: str | Path) -> dict:
    """Load a demo mock RAG response (same shape as fetch_backend output)."""
    with open(mock_path) as f:
        return json.load(f)


def prepare_inputs(data: dict) -> tuple[str, str]:
    """Apply model capacity limits and return (context, response).

    Truncates to MINI_MAX_RESPONSE_CHARS / MINI_MAX_CONTEXT_CHARS when running
    against local-model-mini (which crashes the vllm worker above ~340 tokens).
    Both limits are None for local-model (no truncation).
    """
    raw_response = data["answer"]
    if MINI_MAX_RESPONSE_CHARS and len(raw_response) > MINI_MAX_RESPONSE_CHARS:
        trunc = raw_response[:MINI_MAX_RESPONSE_CHARS]
        last_sent = max(trunc.rfind(". "), trunc.rfind(".\n"), trunc.rfind("! "), trunc.rfind("? "))
        response = trunc[:last_sent + 1] if last_sent > len(trunc) // 3 else trunc
    else:
        response = raw_response

    chunks = data["knowledge_sources"]
    context_parts, ctx_chars = [], 0
    for chunk in chunks:
        content = chunk["content"]
        needed = len(content) + (2 if context_parts else 0)
        if MINI_MAX_CONTEXT_CHARS is None or ctx_chars + needed <= MINI_MAX_CONTEXT_CHARS:
            context_parts.append(content)
            ctx_chars += needed
        else:
            break
    context = "\n\n".join(context_parts)

    print(f"Chunks: {len(context_parts)}/{len(chunks)} | Context: {ctx_chars} chars | Response: {len(response)} chars")
    return context, response

# --- High-level entry point --------------------------------------------------

def attribute_response(
    context: str,
    query: str,
    response: str,
    num_ablations: int = 32,
    ablation_keep_prob: float = 0.5,
    batch_size: int = 1,
    as_dataframe: bool = True,
    verbose: bool = True,
    start_idx: int | None = None,
    end_idx: int | None = None,
):
    """Run context attribution and return source weights.

    Uses MarkdownContextPartitioner to split context into markdown-aware sources
    (headers dropped, one source per list item, tables atomic, plain text by
    sentence), masks random subsets across num_ablations calls to the LLM
    endpoint (prompt_logprobs=1), then fits a Lasso to identify which sources
    drove the response.

    start_idx / end_idx select a sub-span of the response to attribute, as
    character offsets into ``response``. Both None (the default) attributes the
    whole response.
    """
    tokenizer = make_tokenizer()
    model = APIModel(response=response)
    cc = ContextCiter(
        model=model,
        tokenizer=tokenizer,
        context=context,
        query=query,
        num_ablations=num_ablations,
        ablation_keep_prob=ablation_keep_prob,
        batch_size=batch_size,
        partitioner=MarkdownContextPartitioner(context),
    )
    return cc.get_attributions(
        start_idx=start_idx,
        end_idx=end_idx,
        as_dataframe=as_dataframe,
        verbose=verbose,
    )


# --- UI entry point ----------------------------------------------------------

def run_pipeline(
    query: str | None = None,
    *,
    source: str = "backend",
    mock_path: str | Path | None = None,
    num_ablations: int = 32,
    ablation_keep_prob: float = 0.5,
    batch_size: int = 1,
    as_dataframe: bool = True,
    verbose: bool = True,
) -> dict:
    """Run the full attribution pipeline; the single entry point a UI calls.

    Two modes, selected explicitly via ``source`` (not by backend availability):

    * ``source="backend"`` -- send ``query`` to the live RAG backend, then
      attribute the answer. ``query`` is required.
    * ``source="mock"`` -- skip the backend and load ``mock_path`` instead, for
      demo consistency. ``query`` is optional: if omitted, the mock's own
      ``query`` field is used, falling back to a demo placeholder. The ablation
      logprobs still come from the live ZP/LLM endpoint either way.

    Returns a dict with everything the UI needs to render:
    ``{source, query, answer, context, response, num_sources, attributions}``.
    """
    if source == "mock":
        if mock_path is None:
            raise ValueError("source='mock' requires mock_path")
        data = load_mock(mock_path)
        query = query or data.get("query") or "[demo] context attribution"
    elif source == "backend":
        if not query:
            raise ValueError("source='backend' requires a query")
        data = fetch_backend(query)
    else:
        raise ValueError(f"unknown source {source!r} (use 'backend' or 'mock')")

    context, response = prepare_inputs(data)
    attributions = attribute_response(
        context,
        query,
        response,
        num_ablations=num_ablations,
        ablation_keep_prob=ablation_keep_prob,
        batch_size=batch_size,
        as_dataframe=as_dataframe,
        verbose=verbose,
    )
    return {
        "source": source,
        "query": query,
        "answer": data["answer"],
        "context": context,
        "response": response,
        "num_sources": MarkdownContextPartitioner(context).num_sources,
        "attributions": attributions,
    }
