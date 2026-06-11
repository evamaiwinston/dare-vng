import os, json, requests, time
from dotenv import load_dotenv
load_dotenv(dotenv_path="../.env")

API_KEY = os.getenv("OPENAI_API_KEY")
LLM_URL = os.getenv("OPENAI_BASE_URL").rstrip("/") + "/v1/chat/completions"
MODEL   = os.getenv("LLM_MODEL", "local-model-mini")

print(f"Finding max context on {MODEL} (short response)\n")

with open("chat_output.txt") as f:
    data = json.load(f)
context  = "\n\n".join(c["content"] for c in data["knowledge_sources"])
query    = "Nhân viên VNG được nghỉ phép bao nhiêu ngày mỗi năm?"
# Short but meaningful response — enough for attribution to work
short_resp = (
    "Theo chính sách VNG, nhân viên bậc 2-5 được nghỉ 16 ngày phép năm, "
    "bậc 1 được nghỉ 14 ngày. Nhân viên trên 3 năm được cộng thêm 1 ngày mỗi 3 năm thâm niên."
)
print(f"Short response: {len(short_resp)} chars")
print(f"Full context:   {len(context)} chars / {len(data['knowledge_sources'])} chunks\n")

def call(ctx_chars, sleep_on_fail=2.0):
    user_content = f"Context:\n{context[:ctx_chars]}\n\nQuestion: {query}"
    r = requests.post(LLM_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": MODEL,
              "messages": [{"role": "user",      "content": user_content},
                           {"role": "assistant", "content": short_resp}],
              "temperature": 0, "max_tokens": 1, "prompt_logprobs": 1},
        timeout=60)
    if r.ok:
        t = r.json().get("usage", {})
        return True, t.get("prompt_tokens")
    else:
        time.sleep(sleep_on_fail)  # give worker time to restart after crash
        return False, r.status_code

# Start from known-good (1000 chars) and bisect upward
lo, hi = 1000, len(context)
last_ok_chars, last_ok_tokens = None, None

while lo <= hi:
    mid = (lo + hi) // 2
    ok, info = call(mid)
    status = f"OK  (prompt_tokens={info})" if ok else f"FAIL {info}"
    print(f"  {mid:5d} ctx chars → {status}")
    if ok:
        last_ok_chars = mid
        last_ok_tokens = info
        lo = mid + 1
    else:
        hi = mid - 1

print(f"\nMax safe context: ~{last_ok_chars} chars → {last_ok_tokens} total prompt tokens")

# How many complete chunks fit?
chunks = data["knowledge_sources"]
running = 0
max_n = 0
for i, c in enumerate(chunks):
    seg = c["content"] + ("\n\n" if i > 0 else "")
    if running + len(seg) <= last_ok_chars:
        running += len(seg)
        max_n = i + 1
    else:
        break

print(f"Complete chunks fitting: {max_n} / {len(chunks)}")
print(f"Suggested MAX_CONTEXT_CHARS = {last_ok_chars}")