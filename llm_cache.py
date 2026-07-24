import json
import time
import hashlib
from typing import Optional, Dict, Any
from config import LLM_CACHE_ENABLED, LLM_CACHE_TTL_SECONDS

_cache: Dict[str, Dict] = {}

def _make_key(prompt: str, model: str, temperature: float, max_tokens: int) -> str:
    raw = f"{prompt}|{model}|{temperature}|{max_tokens}"
    return hashlib.sha256(raw.encode()).hexdigest()

def cache_get(prompt: str, model: str = "", temperature: float = 0.7, max_tokens: int = 2048) -> Optional[str]:
    if not LLM_CACHE_ENABLED:
        return None
    key = _make_key(prompt, model, temperature, max_tokens)
    entry = _cache.get(key)
    if entry is None:
        return None
    if time.time() - entry["ts"] > LLM_CACHE_TTL_SECONDS:
        del _cache[key]
        return None
    return entry["text"]

def cache_set(prompt: str, text: str, model: str = "", temperature: float = 0.7, max_tokens: int = 2048) -> None:
    if not LLM_CACHE_ENABLED:
        return
    key = _make_key(prompt, model, temperature, max_tokens)
    _cache[key] = {"text": text, "ts": time.time()}

def cache_clear() -> int:
    global _cache
    n = len(_cache)
    _cache.clear()
    return n

def cache_size() -> int:
    return len(_cache)
