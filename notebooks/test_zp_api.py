import os, requests
from dotenv import load_dotenv
load_dotenv()

base = os.getenv("OPENAI_BASE_URL").rstrip("/")
key = os.getenv("OPENAI_API_KEY")

r = requests.post(
    f"{base}/v1/chat/completions",
    headers={"Authorization": f"Bearer {key}"},
    json={
        "model": "local-model-mini",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 1,
        "temperature": 0,
    }
)
print("STATUS:", r.status_code)
print("RESPONSE:", r.text[:300])