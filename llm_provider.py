from providers.registry import get_llm as _get_llm
from providers.base import LLMProvider, LLMResponse
from providers.llm_fallback import FallbackLLMProvider
from config import LLM_FALLBACK_ENABLED


def get_llm_provider() -> LLMProvider:
    inner = _get_llm()
    if LLM_FALLBACK_ENABLED:
        return FallbackLLMProvider(inner)
    return inner
