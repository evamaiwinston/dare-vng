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
    r = requests.post(
        LLM_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "user",      "content": user_content},
                {"role": "assistant", "content": response_text},
            ],
            "temperature": 0,
            "max_tokens": 1,
            "prompt_logprobs": 1,
        },
    )
    if not r.ok:
        print(f"  API error {r.status_code}: {r.text[:200]}")
    r.raise_for_status()

    tokens   = _actual_tokens(r.json()["prompt_logprobs"])
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
#      logits[b, pos, label_id] = api_logprob + log(V-1),  all others = 0
#      → softmax-based loss recovers api_logprob exactly.

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
        bs, seq_len = input_ids.shape
        V      = self._tokenizer.vocab_size
        logits = torch.zeros(bs, seq_len, V)
        log_V1 = float(np.log(V - 1))

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

            for j, (rid, alp) in enumerate(zip(response_ids, aligned)):
                pos = resp_start - 1 + j
                logits[b, pos, rid] = alp + log_V1

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
):
    """Run context attribution and return source weights.

    ContextCite partitions context into sentences, masks random subsets across
    num_ablations calls to the LLM endpoint (prompt_logprobs=1), then fits a
    Lasso to identify which sentences drove the response.
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
    )
    return cc.get_attributions(as_dataframe=as_dataframe, verbose=verbose)
