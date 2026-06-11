import pytest
import requests


@pytest.fixture(scope="module")
def zp_response(llm_url, llm_key, llm_model):
    r = requests.post(
        llm_url,
        headers={"Authorization": f"Bearer {llm_key}"},
        json={
            "model": llm_model,
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 1,
            "temperature": 0,
        },
        timeout=30,
    )
    return r


def test_status_ok(zp_response):
    assert zp_response.status_code == 200


def test_returns_json(zp_response):
    data = zp_response.json()
    assert isinstance(data, dict)


def test_has_choices(zp_response):
    data = zp_response.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
