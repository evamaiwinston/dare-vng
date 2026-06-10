import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_API_URL")
WORKSPACE_ID = os.getenv("BACKEND_WORKSPACE_ID")
TOKEN = os.getenv("BACKEND_API_KEY")

start = time.time()

response = requests.post(
    f"{BACKEND_URL}/api/v1/workspaces/{WORKSPACE_ID}/chat",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "query": "Nhân viên VNG được nghỉ phép bao nhiêu ngày mỗi năm?",
        "mode": "agent",
        "top_k": 5
    }
)

elapsed = time.time() - start

data = response.json()
print("MODE:", data.get("mode"))
print("ANSWER:", data.get("answer"))
print("TOOLS USED:", data.get("tools_used"))
print("KNOWLEDGE SOURCES:", len(data.get("knowledge_sources", [])))
print("MEMORY SOURCES:", len(data.get("memory_sources", [])))
print("REASONING TRACE STEPS:", len(data.get("reasoning_trace", [])))
print("STATUS CODE:", response.status_code)
print(f"ELAPSED TIME: {elapsed:.2f}s")
print("RAW RESPONSE:", response.text)