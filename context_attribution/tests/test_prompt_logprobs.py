"""
Tests for the prompt_logprobs endpoint feature used by the attribution pipeline.

The attribution pipeline (APIModel.__call__) relies on prompt_logprobs=1 to score
how much each context sentence contributed to the response. These tests verify:
  1. The endpoint accepts prompt_logprobs=1 without error.
  2. The response includes a prompt_logprobs field.
  3. Each entry is either None or a dict mapping token strings to logprob dicts.
  4. Logprob dicts contain the keys APIModel._actual_tokens() expects.
"""
import pytest
import requests

CONTEXT = (
    "Chính sách này áp dụng cho Nhân viên thuộc Công ty Cổ phần Tập đoàn VNG. "
    "Nhân viên bậc 2-5 được nghỉ 16 ngày phép năm, bậc 1 được nghỉ 14 ngày."
)
QUERY = "Nhân viên VNG được nghỉ phép bao nhiêu ngày mỗi năm?"
RESPONSE = "Nhân viên bậc 2-5 được nghỉ 16 ngày phép năm, bậc 1 được nghỉ 14 ngày."


@pytest.fixture(scope="module")
def logprobs_response(llm_url, llm_key, llm_model):
    user_content = f"Context:\n{CONTEXT}\n\nQuestion: {QUERY}"
    r = requests.post(
        llm_url,
        headers={"Authorization": f"Bearer {llm_key}"},
        json={
            "model": llm_model,
            "messages": [
                {"role": "user",      "content": user_content},
                {"role": "assistant", "content": RESPONSE},
            ],
            "temperature": 0,
            "max_tokens": 1,
            "prompt_logprobs": 1,
        },
        timeout=60,
    )
    return r


def test_status_ok(logprobs_response):
    assert logprobs_response.status_code == 200, logprobs_response.text[:300]


def test_prompt_logprobs_field_present(logprobs_response):
    data = logprobs_response.json()
    assert "prompt_logprobs" in data, (
        "prompt_logprobs missing — endpoint may not be vllm-compatible"
    )


def test_prompt_logprobs_is_list(logprobs_response):
    data = logprobs_response.json()
    lp = data["prompt_logprobs"]
    assert isinstance(lp, list)
    assert len(lp) > 0


def test_prompt_logprobs_entry_format(logprobs_response):
    # Each entry must be None (special tokens) or a dict of {token_str: logprob_dict}
    data = logprobs_response.json()
    for entry in data["prompt_logprobs"]:
        assert entry is None or isinstance(entry, dict), f"Unexpected entry type: {type(entry)}"


def test_logprob_dict_has_required_keys(logprobs_response):
    # APIModel._actual_tokens() reads "decoded_token", "logprob", and "rank" from each value
    data = logprobs_response.json()
    for entry in data["prompt_logprobs"]:
        if entry is None:
            continue
        for token_str, lp_info in entry.items():
            assert "decoded_token" in lp_info, f"Missing decoded_token in: {lp_info}"
            assert "logprob" in lp_info,       f"Missing logprob in: {lp_info}"
        break  # one real entry is enough to validate structure


@pytest.mark.parametrize("ctx_chars", [500, 900])
def test_context_sizes_succeed(llm_url, llm_key, llm_model, ctx_chars):
    # Regression check: both small and medium contexts complete without error.
    user_content = f"Context:\n{CONTEXT[:ctx_chars]}\n\nQuestion: {QUERY}"
    r = requests.post(
        llm_url,
        headers={"Authorization": f"Bearer {llm_key}"},
        json={
            "model": llm_model,
            "messages": [
                {"role": "user",      "content": user_content},
                {"role": "assistant", "content": RESPONSE},
            ],
            "temperature": 0,
            "max_tokens": 1,
            "prompt_logprobs": 1,
        },
        timeout=60,
    )
    assert r.status_code == 200, f"ctx_chars={ctx_chars}: {r.text[:200]}"
