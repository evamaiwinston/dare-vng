"""Diagnostic: inspect the NVIDIA prompt_logprobs response + tokenizer alignment.

Not part of the pipeline. Makes ONE real LLM call with a representative
context/query/response, then dumps the intermediate structures the attribution
pipeline relies on, so a model swap (e.g. mini -> NVIDIA Qwen) can be checked
against the assumptions in `actual_tokens` / `_align_to_shell_tokens`.

Run:  python -m dare.inspect_logprobs
"""

import sys
from collections import Counter

import requests

from dare.config import Settings
from dare.providers.openai_compat import actual_tokens
from dare.attribution import (
    _align_to_shell_tokens, make_tokenizer,
    load_mock, prepare_inputs,
)

SETTINGS = Settings.from_env()

# Default probe text (Vietnamese). Override by passing a mock JSON path:
#   python -m dare.inspect_logprobs mock_data/cc_example.json
CONTEXT = (
    "Chính sách này áp dụng cho Nhân viên thuộc Công ty Cổ phần Tập đoàn VNG. "
    "Nhân viên bậc 2-5 được nghỉ 16 ngày phép năm, bậc 1 được nghỉ 14 ngày."
)
QUERY = "Nhân viên VNG được nghỉ phép bao nhiêu ngày mỗi năm?"
RESPONSE = "Nhân viên bậc 2-5 được nghỉ 16 ngày phép năm, bậc 1 được nghỉ 14 ngày."

if len(sys.argv) > 1:
    _data = load_mock(sys.argv[1])
    if isinstance(_data, list):                      # a corpus array -> pick one record
        _idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        print(f"(corpus array: inspecting record [{_idx}] of {len(_data)})")
        _data = _data[_idx]
    QUERY = _data.get("query", QUERY)
    CONTEXT, RESPONSE = prepare_inputs(_data)  # same truncation the pipeline applies


def _rule(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main():
    user_content = f"Context:\n{CONTEXT}\n\nQuestion: {QUERY}"

    _rule(f"1. Raw request -> {SETTINGS.model}")
    r = requests.post(
        SETTINGS.llm_url,
        headers={"Authorization": f"Bearer {SETTINGS.api_key}"},
        json={
            "model": SETTINGS.model,
            "messages": [
                {"role": "user",      "content": user_content},
                {"role": "assistant", "content": RESPONSE},
            ],
            "temperature": 0,
            "max_tokens": 1,
            "prompt_logprobs": 1,
        },
        timeout=SETTINGS.api_timeout,
    )
    print(f"HTTP {r.status_code}")
    r.raise_for_status()
    raw = r.json()["prompt_logprobs"]

    _rule("2. prompt_logprobs shape")
    none_count = sum(1 for e in raw if e is None)
    cand_counts = Counter(len(e) for e in raw if e is not None)
    print(f"total entries        : {len(raw)}")
    print(f"None entries         : {none_count}")
    print(f"candidates per entry : {dict(sorted(cand_counts.items()))}  "
          f"(1 => only top-1 returned; >1 => actual token also present)")

    # Keys present on a candidate value — does 'rank' exist? is it 'decoded_token'?
    sample = next((e for e in raw if e is not None), None)
    if sample:
        any_val = next(iter(sample.values()))
        print(f"candidate value keys : {sorted(any_val.keys())}")
        has_rank = "rank" in any_val
        print(f"'rank' present       : {has_rank}  "
              f"{'' if has_rank else '<-- actual_tokens multi-candidate path will KeyError'}")

    # Show a multi-candidate entry in full, if any (this is where the actual
    # prompt token vs top-1 distinction lives).
    multi = next((e for e in raw if e is not None and len(e) > 1), None)
    if multi:
        print("\nexample multi-candidate entry:")
        for tok, info in multi.items():
            print(f"  {tok!r:>20} -> {info}")
    else:
        print("\n** every entry has exactly 1 candidate — cannot distinguish the\n"
              "   actual prompt token from the model's top-1. If NVIDIA never\n"
              "   returns the real token when it isn't top-1, logprobs are wrong. **")

    _rule("3. actual_tokens() reconstruction")
    tokens = actual_tokens(raw)
    full_txt = "".join(t for t, _ in tokens)
    print(f"decoded {len(tokens)} tokens")
    start = full_txt.rfind(RESPONSE)
    if start == -1:
        start = full_txt.rfind(RESPONSE.strip())
    print(f"response_text found via rfind : {start != -1}  (index={start})")
    if start == -1:
        print("** RESPONSE not found in decoded token stream — alignment would raise. **")
        print(f"decoded tail: {full_txt[-200:]!r}")

    _rule("4. Response-token logprobs (API side)")
    if start != -1:
        end = start + len(RESPONSE)
        pos, api_tokens = 0, []
        for decoded, lp in tokens:
            tok_end = pos + len(decoded)
            if lp is not None and pos >= start and tok_end <= end:
                api_tokens.append((decoded, lp))
            pos = tok_end
            if pos >= end:
                break
        for decoded, lp in api_tokens:
            print(f"  {decoded!r:>20} : {lp:.4f}")

        _rule("5. Tokenizer alignment (API tokens -> shell-tokenizer boundaries)")
        tok = make_tokenizer()
        shell_ids = tok.encode(RESPONSE, add_special_tokens=False)
        aligned = _align_to_shell_tokens(api_tokens, RESPONSE, shell_ids, tok)
        print(f"shell tokenizer ({tok.name_or_path}) response tokens : {len(shell_ids)}   API response tokens : {len(api_tokens)}")
        print("shell_token -> aligned_logprob")
        for tid, alp in zip(gpt2_ids, aligned):
            print(f"  {tok.decode([tid])!r:>20} : {alp:.4f}")


if __name__ == "__main__":
    main()
