"""Settings — the runtime config that used to live as module globals.

`Settings.from_env()` reads the same environment variables the attribution
module read at import time (loading `.env` first), so behavior is unchanged:
the values are just gathered into one object that can be passed around — and
overridden per call — instead of mutated as globals. `dare.attribution` holds a
process-wide default (`SETTINGS`) that the high-level functions fall back to.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DOTENV = _REPO_ROOT / ".env"


@dataclass
class Settings:
    # --- LLM endpoint (the logprob provider) --------------------------------
    api_key: str | None = None
    llm_url: str = "/v1/chat/completions"
    model: str | None = None
    # Structural tokenizer shell for ContextCiter (NOT the model's weights —
    # log-probs come from the API). "gpt2" default; set to the model's own
    # tokenizer repo (e.g. the Qwen HF id) so local tokenization matches the
    # API's, making response-token alignment ~1:1.
    shell_tokenizer: str = "gpt2"

    # --- RAG backend --------------------------------------------------------
    backend_url: str | None = None
    workspace_id: str | None = None
    backend_token: str | None = None

    # --- Capacity limits (None = no truncation) -----------------------------
    # local-model-mini crashes the vllm worker when total prompt tokens exceed
    # ~340. Both None for local-model (no truncation). Used by prepare_inputs.
    mini_max_response_chars: int | None = None
    mini_max_context_chars: int | None = None

    # --- Graceful-call throttle / retry -------------------------------------
    # Operational only — these change no attribution value. The NVIDIA-hosted
    # endpoint queues server-side under load and can briefly 429 a burst of
    # prompt_logprobs calls; the throttle spaces calls out and retry rides
    # through transient timeouts / 429 / 5xx / connection errors.
    api_call_delay: float = 0.5            # sleep BEFORE each call (0 disables)
    api_max_retries: int = 3               # total attempts per call (1 = none)
    api_retry_backoff: float = 10.0        # linear: wait = backoff * attempt
    api_timeout: tuple[int, int] = (10, 90)  # (connect, read) seconds

    @classmethod
    def from_env(cls, dotenv_path: str | Path | None = None) -> "Settings":
        """Build Settings from environment variables, loading `.env` first.

        Mirrors exactly what `dare.attribution` read as globals at import.
        Pass `dotenv_path` to load a different env file (default: repo-root
        `.env`).
        """
        load_dotenv(dotenv_path=dotenv_path or _DEFAULT_DOTENV)
        base = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
        return cls(
            api_key=os.getenv("OPENAI_API_KEY"),
            llm_url=base + "/v1/chat/completions",
            model=os.getenv("LLM_MODEL"),
            shell_tokenizer=os.getenv("SHELL_TOKENIZER", "gpt2"),
            backend_url=os.getenv("BACKEND_API_URL"),
            workspace_id=os.getenv("BACKEND_WORKSPACE_ID"),
            backend_token=os.getenv("BACKEND_API_KEY"),
        )
