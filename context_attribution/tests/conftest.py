import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")


@pytest.fixture(scope="session")
def backend_url():
    url = os.getenv("BACKEND_API_URL")
    if not url:
        pytest.skip("BACKEND_API_URL not set")
    return url


@pytest.fixture(scope="session")
def workspace_id():
    wid = os.getenv("BACKEND_WORKSPACE_ID")
    if not wid:
        pytest.skip("BACKEND_WORKSPACE_ID not set")
    return wid


@pytest.fixture(scope="session")
def backend_token():
    token = os.getenv("BACKEND_API_KEY")
    if not token:
        pytest.skip("BACKEND_API_KEY not set")
    return token


@pytest.fixture(scope="session")
def llm_url():
    base = os.getenv("OPENAI_BASE_URL")
    if not base:
        pytest.skip("OPENAI_BASE_URL not set")
    return base.rstrip("/") + "/v1/chat/completions"


@pytest.fixture(scope="session")
def llm_key():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def llm_model():
    return os.getenv("LLM_MODEL", "local-model-mini")
