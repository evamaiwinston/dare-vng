"""Runtime configuration loaded from .env via Settings.from_env().
See .env.example
"""

from __future__ import annotations

import oss
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DOTENV = _REPO_ROOT / ".env"


@dataclass
class Settings:
    api_key: str | None = None
    llm_url: str = "/v1/chat/completions"
    model: str | None = None
    shell_tokenizer: str = "gpt2"
    lasso_alpha: float = 0.01
    embed_model: str = "intfloat/multilingual-e5-base"
    backend_url: str | None = None
    workspace_id: str | None = None
    backend_token: str | None = None
    mini_max_response_chars: int | None = None
    mini_max_context_chars: int | None = None
    api_call_delay: float = 0.5
    api_max_retries: int = 3
    api_retry_backoff: float = 10.0
    api_timeout: tuple[int, int] = (10, 90)
    widget_max_workers: int = 8

    @classmethod
    def from_env(cls, dotenv_path: str | Path | None = None) -> "Settings":
        load_dotenv(dotenv_path=dotenv_path or _DEFAULT_DOTENV)
        base = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
        _int_or_none = lambda k: int(os.getenv(k)) if os.getenv(k) else None
        return cls(
            api_key=os.getenv("OPENAI_API_KEY"),
            llm_url=base + "/v1/chat/completions",
            model=os.getenv("LLM_MODEL"),
            shell_tokenizer=os.getenv("SHELL_TOKENIZER", "gpt2"),
            lasso_alpha=float(os.getenv("LASSO_ALPHA", "0.01")),
            embed_model=os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base"),
            backend_url=os.getenv("BACKEND_API_URL"),
            workspace_id=os.getenv("BACKEND_WORKSPACE_ID"),
            backend_token=os.getenv("BACKEND_API_KEY"),
            mini_max_response_chars=_int_or_none("MINI_MAX_RESPONSE_CHARS"),
            mini_max_context_chars=_int_or_none("MINI_MAX_CONTEXT_CHARS"),
            api_call_delay=float(os.getenv("API_CALL_DELAY", "0.5")),
            api_max_retries=int(os.getenv("API_MAX_RETRIES", "3")),
            api_retry_backoff=float(os.getenv("API_RETRY_BACKOFF", "10.0")),
            api_timeout=(int(os.getenv("API_TIMEOUT_CONNECT", "10")), int(os.getenv("API_TIMEOUT_READ", "90"))),
            widget_max_workers=int(os.getenv("WIDGET_MAX_WORKERS", "8")),
        )
