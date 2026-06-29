"""
Context attribution pipeline using ContextCite + a logprob provider.

The LLM calls now go through a `LogprobProvider` (default: the OpenAI-compatible
`prompt_logprobs` endpoint); runtime config lives in a `Settings` object instead
of module globals. Both default to a process-wide `SETTINGS`, so the simple
usage is unchanged:

    from dare.attribution import attribute_response, fetch_backend, prepare_inputs

    data = fetch_backend("Nhân viên VNG được nghỉ phép bao nhiêu ngày mỗi năm?")
    context, response = prepare_inputs(data)
    df = attribute_response(context, query, response)

Pass `settings=` / `provider=` to override the endpoint, throttle, or backend.
"""

import json
import math
import logging
import numpy as np
import requests
import torch
from pathlib import Path
from types import SimpleNamespace

from transformers import AutoTokenizer

# Compatibility patches
from pandas.io.formats.style import Styler
if not hasattr(Styler, "applymap"):
    Styler.applymap = Styler.map

from context_cite import ContextCiter
from context_cite import utils as _cc_utils

from dare.config import Settings
from dare.partitioner import MarkdownContextPartitioner, markdown_unit_spans
from dare.providers import LogprobProvider, OpenAICompatProvider
from dare.schema import Source, sources_to_context


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

# --- Config / logging --------------------------------------------------------
# Process-wide default Settings (reads .env once at import, exactly as the old
# module-level globals did). High-level functions fall back to it; pass an
# explicit `settings=` to override per call.

logger = logging.getLogger(__name__)

SETTINGS = Settings.from_env()

# --- Tokenizer ---------------------------------------------------------------

def make_tokenizer(shell_tokenizer: str | None = None):
    """Structural tokenizer shell for ContextCiter, loaded from SHELL_TOKENIZER.

    Any HF fast tokenizer works: it must provide encode/decode, token_to_chars,
    pad/eos, and .pad(). Default "gpt2"; set SHELL_TOKENIZER (via Settings) to
    the model's own tokenizer repo (e.g. the Qwen HF id) so local tokenization
    matches the API's — making response-token alignment ~1:1 and avoiding GPT-2
    byte-splitting of non-English text. The chat_template matches the ChatML
    format the LLM endpoint expects. Actual log-probabilities come from the API,
    not the shell tokenizer's weights.
    """
    tok = AutoTokenizer.from_pretrained(shell_tokenizer or SETTINGS.shell_tokenizer)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    tok.chat_template = (
        "{% for message in messages %}"
        "<|im_start|>{{ message['role'] }}\n{{ message['content'] }}<|im_end|>\n"
        "{% endfor %}"
        "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}"
    )
    return tok

# --- Engine glue -------------------------------------------------------------

def _extract_user_content(prompt_text: str) -> str:
    start = prompt_text.find("<|im_start|>user\n")
    if start == -1:
        raise ValueError(f"No user turn found in prompt: {prompt_text[:80]!r}")
    start += len("<|im_start|>user\n")
    end = prompt_text.find("<|im_end|>", start)
    return prompt_text[start:] if end == -1 else prompt_text[start:end]


def _align_to_shell_tokens(
    api_tokens: list[tuple[str, float]],
    response_text: str,
    shell_response_ids: list[int],
    tokenizer,
) -> list[float]:
    """Align the API's per-token logprobs onto the shell tokenizer's token
    boundaries (the shell tokenizer is SHELL_TOKENIZER — e.g. Qwen — not GPT-2)."""
    n = len(shell_response_ids)
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
#   3. Ask the provider to score the response (prompt_logprobs=1).
#   4. Align API token logprobs onto the shell tokenizer's token boundaries.
#   5. Build fake logits so _compute_logit_probs returns the aligned values:
#
#      logits[b, j, label_id] = logit_prob + log(V-1),  all others = 0
#      → softmax-based loss recovers logit_prob exactly.
#
#      ContextCite speaks in LOGIT-probabilities log(p/(1-p)), not log-probs:
#      aggregate_logit_probs applies logsigmoid, which inverts the logit
#      transform back to log p. So we convert the API logprob (alp = log p) to
#      logit_prob = alp - log(1-p) here before encoding it. Feeding raw log p
#      would make logsigmoid mangle it (≈10x signal compression), which lets the
#      Lasso shrink the true source away.
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

    def __init__(
        self,
        response: str,
        provider: LogprobProvider | None = None,
        tokenizer=None,
    ):
        self._response  = response
        self._provider  = provider or OpenAICompatProvider()
        self._tokenizer = tokenizer or make_tokenizer()

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

            api_tokens = self._provider.score_response(user_content, response_text)
            aligned    = _align_to_shell_tokens(api_tokens, response_text, response_ids, self._tokenizer)

            # Row j of the tail corresponds to old global position resp_start-1+j,
            # which is exactly what output.logits[:, -(R+1):-1] reads back.
            for j, (rid, alp) in enumerate(zip(response_ids, aligned)):
                # alp = log p (API logprob) -> logit_prob = log(p/(1-p)) so the
                # downstream logsigmoid recovers log p correctly. expm1 keeps
                # log(1-p) stable for tiny p; clamp near p=1 to avoid -inf.
                log1m = math.log(-math.expm1(alp)) if alp < -1e-7 else math.log(1e-7)
                logits[b, j, rid] = (alp - log1m) + log_V1

        return SimpleNamespace(logits=logits)

# --- Data helpers ------------------------------------------------------------

def fetch_backend(query: str, settings: Settings | None = None) -> dict:
    """Call the backend RAG API and return the raw response dict."""
    s = settings or SETTINGS
    resp = requests.post(
        f"{s.backend_url}/api/v1/workspaces/{s.workspace_id}/chat",
        headers={"Authorization": f"Bearer {s.backend_token}"},
        json={"query": query, "mode": "agent", "top_k": 5},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def load_mock(mock_path: str | Path) -> dict:
    """Load a demo mock RAG response (same shape as fetch_backend output)."""
    with open(mock_path) as f:
        return json.load(f)


def resolve_query(query: str | None, data: dict | None = None) -> str:
    """Return the query to attribute, or raise if there is none.

    Resolution order: an explicit ``query`` (from the CLI or the UI box) wins;
    otherwise the mock/RAG ``data``'s own ``query`` field is used. There is no
    placeholder fallback — a run with no query is an error: it is logged and
    refused, never silently run against a stand-in question.
    """
    candidate = (query or (data or {}).get("query") or "").strip()
    if not candidate:
        logger.error(
            "No query provided — refusing to run. Pass a query on the CLI/UI or "
            "include a 'query' field in the mock file."
        )
        raise ValueError("a query is required (none given and none in the mock data)")
    return candidate


def prepare_inputs(data: dict, settings: Settings | None = None) -> tuple[str, str]:
    """Apply model capacity limits and return (context, response).

    Truncates to ``settings.mini_max_response_chars`` /
    ``settings.mini_max_context_chars`` when running against local-model-mini
    (which crashes the vllm worker above ~340 tokens). Both limits are None for
    local-model (no truncation).
    """
    s = settings or SETTINGS
    max_response_chars = s.mini_max_response_chars
    max_context_chars  = s.mini_max_context_chars

    raw_response = data["answer"]
    if max_response_chars and len(raw_response) > max_response_chars:
        trunc = raw_response[:max_response_chars]
        last_sent = max(trunc.rfind(". "), trunc.rfind(".\n"), trunc.rfind("! "), trunc.rfind("? "))
        response = trunc[:last_sent + 1] if last_sent > len(trunc) // 3 else trunc
    else:
        response = raw_response

    chunks = data["knowledge_sources"]
    context_parts, ctx_chars = [], 0
    for chunk in chunks:
        content = chunk["content"]
        needed = len(content) + (2 if context_parts else 0)
        if max_context_chars is None or ctx_chars + needed <= max_context_chars:
            context_parts.append(content)
            ctx_chars += needed
        else:
            break
    context = "\n\n".join(context_parts)

    print(f"Chunks: {len(context_parts)}/{len(chunks)} | Context: {ctx_chars} chars | Response: {len(response)} chars")
    return context, response

# --- High-level entry point --------------------------------------------------

def _build_citer(
    context: str,
    query: str,
    response: str,
    *,
    num_ablations: int = 32,
    ablation_keep_prob: float = 0.5,
    batch_size: int = 1,
    provider: LogprobProvider | None = None,
    settings: Settings | None = None,
) -> ContextCiter:
    """Construct a ContextCiter wired to a logprob provider. Shared by the
    whole-response and per-unit attribution paths so setup never diverges. The
    ablation pass is lazy — it runs on the first attribution query and is cached,
    so further queries against the returned object cost no LLM calls."""
    settings = settings or SETTINGS
    provider = provider or OpenAICompatProvider(settings)
    tokenizer = make_tokenizer(settings.shell_tokenizer)
    model = APIModel(response=response, provider=provider, tokenizer=tokenizer)
    return ContextCiter(
        model=model,
        tokenizer=tokenizer,
        context=context,
        query=query,
        num_ablations=num_ablations,
        ablation_keep_prob=ablation_keep_prob,
        batch_size=batch_size,
        partitioner=MarkdownContextPartitioner(context),
    )


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
    provider: LogprobProvider | None = None,
    settings: Settings | None = None,
):
    """Run context attribution and return source weights.

    Uses MarkdownContextPartitioner to split context into markdown-aware sources
    (headers dropped, one source per list item, tables atomic, plain text by
    sentence), masks random subsets across num_ablations calls to the logprob
    provider, then fits a Lasso to identify which sources drove the response.

    start_idx / end_idx select a sub-span of the response to attribute, as
    character offsets into ``response``. Both None (the default) attributes the
    whole response. Pass ``provider`` / ``settings`` to override the endpoint.
    """
    cc = _build_citer(
        context, query, response,
        num_ablations=num_ablations, ablation_keep_prob=ablation_keep_prob,
        batch_size=batch_size, provider=provider, settings=settings,
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
    start_idx: int | None = None,
    end_idx: int | None = None,
    provider: LogprobProvider | None = None,
    settings: Settings | None = None,
) -> dict:
    """Run the full attribution pipeline; the single entry point a UI calls.

    Two modes, selected explicitly via ``source`` (not by backend availability):

    * ``source="backend"`` -- send ``query`` to the live RAG backend, then
      attribute the answer. ``query`` is required.
    * ``source="mock"`` -- skip the backend and load ``mock_path`` instead, for
      demo consistency. ``query`` may be omitted only if the mock file carries
      its own ``query`` field; with neither, the run is refused (see
      ``resolve_query``). The ablation logprobs still come from the live LLM
      endpoint either way.

    ``start_idx`` / ``end_idx`` cite a sub-span of the response, as character
    offsets into ``response``. Both None (the default) attributes the whole
    response. ``provider`` / ``settings`` override the endpoint and backend.

    Returns a dict with everything the UI needs to render:
    ``{source, query, answer, context, response, num_sources, attributions}``.
    """
    settings = settings or SETTINGS
    if source == "mock":
        if mock_path is None:
            raise ValueError("source='mock' requires mock_path")
        data = load_mock(mock_path)
        query = resolve_query(query, data)          # explicit > mock's own field
    elif source == "backend":
        query = resolve_query(query)                # backend: explicit query only
        data = fetch_backend(query, settings=settings)
    else:
        raise ValueError(f"unknown source {source!r} (use 'backend' or 'mock')")

    context, response = prepare_inputs(data, settings=settings)
    attributions = attribute_response(
        context,
        query,
        response,
        num_ablations=num_ablations,
        ablation_keep_prob=ablation_keep_prob,
        batch_size=batch_size,
        as_dataframe=as_dataframe,
        verbose=verbose,
        start_idx=start_idx,
        end_idx=end_idx,
        provider=provider,
        settings=settings,
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


# --- Per-unit (per-sentence) attribution -------------------------------------

def _map_unit_to_source(unit_text: str, sources: list[Source]) -> Source | None:
    """Map an attribution unit (a partitioned context segment) back to the Source
    chunk it came from, by content containment. Sources don't overlap in the
    joined context, so containment is unambiguous in practice."""
    t = unit_text.strip()
    if not t:
        return None
    for src in sources:
        if t in src.content:
            return src
    norm = " ".join(t.split())                        # whitespace-normalized retry
    for src in sources:
        if norm in " ".join(src.content.split()):
            return src
    return None


def _attribution_rows(df, sources: list[Source]) -> list[dict]:
    """Turn a get_attributions dataframe (Score, Source) into rows that carry the
    originating chunk's identity + retrieval score, sorted by attribution score."""
    rows = []
    for score, text in zip(df["Score"], df["Source"]):
        src = _map_unit_to_source(text, sources)
        rows.append({
            "score": float(score),
            "source_text": text,
            "chunk_id": src.chunk_id if src else None,
            "doc_id": src.doc_id if src else None,
            "retrieval_score": src.score if src else None,
            "origin": src.origin if src else None,
        })
    rows.sort(key=lambda r: -r["score"])
    return rows


def attribute_by_sentence(
    query: str,
    response: str,
    sources: list[Source],
    *,
    num_ablations: int = 32,
    ablation_keep_prob: float = 0.5,
    batch_size: int = 1,
    provider: LogprobProvider | None = None,
    settings: Settings | None = None,
) -> dict:
    """Attribute each response *unit* (sentence / bullet / list item / table) from
    a single ablation pass, mapping every attribution back to its Source chunk.

    The ablation pass runs once; each unit is a free re-slice of the cached
    logit-probs (no extra LLM calls). Response units are split markdown-aware
    (the same splitter as the context), so tables/bullets in the answer stay
    intact rather than being chopped by naive sentence tokenization.

    Returns ``{response, whole, units}`` where ``whole`` and each
    ``units[i]["attributions"]`` is a list of rows
    ``{score, source_text, chunk_id, doc_id, retrieval_score, origin}``. No
    grounded/ungrounded verdict is made here — that's the diagnosis layer's job.
    """
    context = sources_to_context(sources)
    cc = _build_citer(
        context, query, response,
        num_ablations=num_ablations, ablation_keep_prob=ablation_keep_prob,
        batch_size=batch_size, provider=provider, settings=settings,
    )
    _ = cc._logit_probs                               # trigger the ablation pass once (cached)
    resp = cc.response                                # exactly what ContextCite scored

    whole = _attribution_rows(
        cc.get_attributions(as_dataframe=True, verbose=False).data, sources
    )

    units = []
    for s, e in markdown_unit_spans(resp):
        try:
            df = cc.get_attributions(start_idx=s, end_idx=e, as_dataframe=True, verbose=False).data
            attribs = _attribution_rows(df, sources)
        except Exception as ex:                       # noqa: BLE001 — never sink the record
            logger.warning("per-unit attribution failed for span (%d,%d): %s", s, e, ex)
            attribs = []
        units.append({"text": resp[s:e], "span": [s, e], "attributions": attribs})

    return {"response": resp, "whole": whole, "units": units}
