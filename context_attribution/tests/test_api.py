import pytest
import requests

QUERY = "Nhân viên VNG được nghỉ phép bao nhiêu ngày mỗi năm?"


@pytest.fixture(scope="module")
def chat_response(backend_url, workspace_id, backend_token):
    resp = requests.post(
        f"{backend_url}/api/v1/workspaces/{workspace_id}/chat",
        headers={"Authorization": f"Bearer {backend_token}"},
        json={"query": QUERY, "mode": "agent", "top_k": 5},
        timeout=200,
    )
    return resp


def test_status_ok(chat_response):
    assert chat_response.status_code == 200


def test_has_answer(chat_response):
    data = chat_response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0


def test_has_knowledge_sources(chat_response):
    data = chat_response.json()
    assert "knowledge_sources" in data
    assert len(data["knowledge_sources"]) > 0


def test_mode_is_agent(chat_response):
    assert chat_response.json().get("mode") == "agent"


def test_elapsed_time(chat_response):
    # Basic smoke check — backend responded at all
    assert chat_response.elapsed.total_seconds() < 300
