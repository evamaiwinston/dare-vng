"""Context attribution pipeline using ContextCite + logprob provider.

Primary entry point (batch report or widget API):

    from dare.attribution import attribute_by_sentence
    result = attribute_by_sentence(query, response, chunks)
"""

import json
import math
import logging
from concurrent.futures import ThreadPoolExecutor
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
from context_cite.solver import LassoRegression

from dare.config import Settings
from dare.results import SourceAttribution, UnitAttribution
from dare.partitioner import MarkdownContextPartitioner, markdown_unit_spans
from dare.providers import LogprobProvider, OpenAICompatProvider
from dare.schema import Chunk


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

# Config / logging

logger = logging.getLogger(__name__)

SETTINGS = Settings.from_env()

# Tokenizer 

def make_tokenizer(shell_tokenizer: str | None = None):
    """Structural tokenizer shell for ContextCiter, loaded from SHELL_TOKENIZER.

    The chat_template matches the ChatML format the LLM endpoint expects. 
    Actual log-probabilities come from the API, not the shell tokenizer's weights.
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

# Engine

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
    """Align API's per-token logprobs onto the shell tokenizer's token boundaries."""
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

# APIModel — shim for ContextCiter model interface:
#
#   model.device                                torch.device("cpu")
#   model.generate(input_ids, ...)              LongTensor [1, full_seq_len]
#   model(input_ids, attention_mask, labels)    obj with .logits [bs, seq, V]
#
# generate(): response is already known, append its encoded tokens.
#
# __call__(): ContextCite uses logit-probabilities log(p/(1-p))
#   aggregate_logit_probs applies logsigmoid, inverting back to log p.
#   Convert the API logprob (alp = log p) to logit_prob = alp - log(1-p) before
#   encoding it. Raw log p would make logsigmoid mangle it (~10x signal compression).
#   Lasso needs properly scaled probs

class APIModel:

    device = torch.device("cpu")

    def __init__(
        self,
        response: str,
        provider: LogprobProvider | None = None,
        tokenizer=None,
        max_workers: int = 1,
    ):
        self._response  = response
        self._provider  = provider or OpenAICompatProvider()
        self._tokenizer = tokenizer or make_tokenizer()
        # >1 fires the per-batch ablation rows concurrently (each row is an
        # independent score_response call). Default 1 = serial, unchanged. Scoring
        # is deterministic (temperature 0), so concurrency changes only wall-clock,
        # not the logit-probs — provided every row keeps writing its OWN logits[b]
        # slot (index-addressed below), never appending in completion order.
        self._max_workers = max_workers

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

        def score_row(b: int) -> None:
            """Score ablation row b and write ITS slot logits[b]. Index-addressed,
            so it's safe to run rows concurrently."""
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

        if self._max_workers > 1 and bs > 1:
            with ThreadPoolExecutor(max_workers=self._max_workers) as ex:
                # list() forces every future so exceptions propagate here, not silently.
                list(ex.map(score_row, range(bs)))
        else:
            for b in range(bs):
                score_row(b)

        return SimpleNamespace(logits=logits)

# Data helpers

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
    """Return the query string, preferring explicit query over data["query"]. Raises if neither is set."""
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

# High level entry point

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
    max_workers: int = 1,
) -> ContextCiter:
    """Construct a ContextCiter wired to the logprob provider. The ablation pass is lazy — cached on first query, so re-slicing units costs no extra LLM calls."""
    settings = settings or SETTINGS
    provider = provider or OpenAICompatProvider(settings)
    tokenizer = make_tokenizer(settings.shell_tokenizer)
    model = APIModel(response=response, provider=provider, tokenizer=tokenizer, max_workers=max_workers)
    return ContextCiter(
        model=model,
        tokenizer=tokenizer,
        context=context,
        query=query,
        num_ablations=num_ablations,
        ablation_keep_prob=ablation_keep_prob,
        batch_size=batch_size,
        partitioner=MarkdownContextPartitioner(context),
        solver=LassoRegression(lasso_alpha=settings.lasso_alpha),
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


#  Per-unit (per-sentence) attribution

# The separator that assembles chunk contents (and the folded instruction) into
# one context string. MUST match the join below in _assemble_context so the
# per-segment character ranges line up with the string the partitioner splits.
# A sentinel marks the instruction lane (a folded system prompt, not a chunk).
_CONTEXT_SEP = "\n\n"
_INSTRUCTION = object()


def _assemble_context(chunks: list[Chunk], instruction: str | None) -> tuple[str, list[tuple[int, int, object]]]:
    """Build the ablation context string and each segment's (start, end, owner) range in one pass, so provenance is attached by position — not by text matching."""
    segments: list[tuple[object, str]] = []
    if instruction:                                   # folded instruction leads the context
        segments.append((_INSTRUCTION, instruction))
    segments.extend((c, c.content) for c in chunks)

    context = _CONTEXT_SEP.join(content for _, content in segments)

    ranges: list[tuple[int, int, object]] = []
    pos = 0
    for owner, content in segments:
        ranges.append((pos, pos + len(content), owner))
        pos += len(content) + len(_CONTEXT_SEP)
    return context, ranges


def _owner_at(pos: int, ranges: list[tuple[int, int, object]]) -> object | None:
    """Return the Chunk or _INSTRUCTION sentinel whose char range contains pos, or None if unmapped."""
    return next((owner for start, end, owner in ranges if start <= pos < end), None)


def _attribution_rows(scores, spans: list[tuple[int, int]], context: str,
                      ranges: list[tuple[int, int, object]]) -> list[SourceAttribution]:
    """Convert a per-source score array into SourceAttribution rows, resolving each source's owning chunk by character position. Sorted by score desc."""
    rows = []
    for score, (start, end) in zip(scores, spans):
        owner = _owner_at(start, ranges)
        if isinstance(owner, Chunk):                  # a retrieved chunk
            rows.append(SourceAttribution(
                score=float(score), source_text=context[start:end],
                chunk_id=owner.chunk_id, doc_id=owner.doc_id,
                retrieval_score=owner.score, origin=owner.origin,
            ))
        else:                                         # _INSTRUCTION sentinel or unmapped
            rows.append(SourceAttribution(
                score=float(score), source_text=context[start:end], chunk_id=None,
                doc_id=None, retrieval_score=None,
                origin="instruction" if owner is _INSTRUCTION else "context",
            ))
    rows.sort(key=lambda r: -r.score)
    return rows


def attribute_by_sentence(
    query: str,
    response: str,
    chunks: list[Chunk],
    *,
    num_ablations: int = 32,
    ablation_keep_prob: float = 0.5,
    batch_size: int = 1,
    provider: LogprobProvider | None = None,
    settings: Settings | None = None,
    instruction: str | None = None,
    max_workers: int = 1,
) -> dict:
    """Attribute each response unit (sentence / bullet / table) against its source chunks.

    Runs one ablation pass via ContextCite and maps every Lasso score back to its
    originating Chunk by character position.

    Args:
        query: The user question being answered.
        response: The LLM response to attribute.
        chunks: Retrieved context chunks fed into generation.
        num_ablations: Number of random context masks to run.
        ablation_keep_prob: Fraction of sources kept per mask.
        batch_size: Ablation masks per API call (raised to max_workers if left at 1).
        provider: LogprobProvider to use; defaults to OpenAICompatProvider from env.
        settings: Settings override; defaults to env.
        instruction: System prompt to fold into the ablation set. Adds an
            instruction lane to results (origin="instruction") at no extra API cost,
            but invalidates the context-only logprob cache.
        max_workers: Concurrent ablation calls (default 1 = serial, same results).

    Returns:
        dict with keys:
            response: The response string as scored by ContextCite.
            whole: list[SourceAttribution] for the full response.
            units: list[UnitAttribution], one per markdown unit, in response order.
    """
    # Concurrency needs >1 mask per batch to overlap; lift the default-1 batch to
    # match the worker count so the ThreadPoolExecutor in APIModel has rows to fan out.
    if max_workers > 1 and batch_size == 1:
        batch_size = max_workers

    # Assemble the context and each segment's owning chunk in one pass, so a
    # part's provenance is attached by construction (see _assemble_context).
    context, ranges = _assemble_context(chunks, instruction)
    cc = _build_citer(
        context, query, response,
        num_ablations=num_ablations, ablation_keep_prob=ablation_keep_prob,
        batch_size=batch_size, provider=provider, settings=settings,
        max_workers=max_workers,
    )
    _ = cc._logit_probs                               # trigger the ablation pass once (cached)
    resp = cc.response                                # exactly what ContextCite scored

    # context parts, in the SAME order as the per-source score array from
    # get_attributions(as_dataframe=False) — the partitioner splits on these spans.
    ctx_spans = markdown_unit_spans(context)

    whole = _attribution_rows(
        cc.get_attributions(as_dataframe=False, verbose=False), ctx_spans, context, ranges,
    )

    units = []
    for s, e in markdown_unit_spans(resp):
        try:
            scores = cc.get_attributions(start_idx=s, end_idx=e, as_dataframe=False, verbose=False)
            attribs = _attribution_rows(scores, ctx_spans, context, ranges)
        except Exception as ex:                       # noqa: BLE001 — never sink the record
            logger.warning("per-unit attribution failed for span (%d,%d): %s", s, e, ex)
            attribs = []
        units.append(UnitAttribution(text=resp[s:e], span=(s, e), attributions=attribs))

    return {"response": resp, "whole": whole, "units": units}
