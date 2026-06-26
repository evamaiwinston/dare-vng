"""LLM logprob providers for the attribution engine."""

from dare.providers.base import LogprobProvider
from dare.providers.openai_compat import OpenAICompatProvider

__all__ = ["LogprobProvider", "OpenAICompatProvider"]
