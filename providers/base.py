from abc import ABC, abstractmethod
from typing import Optional, Callable, List, Dict, Any


class LLMResponse:
    text: str
    model: str
    duration_ms: int

    def __init__(self, text: str, model: str = "", duration_ms: int = 0):
        self.text = text
        self.model = model
        self.duration_ms = duration_ms


class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        chunk_callback: Optional[Callable[[str], None]] = None,
        timeout: int = 120,
    ) -> LLMResponse:
        ...

    @abstractmethod
    def stream_complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int = 120,
    ):
        ...

    def complete_json(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: int = 60,
    ) -> Optional[Dict[str, Any]]:
        import json
        from utils import extract_json
        from llm_cache import cache_get, cache_set

        def _try_parse(text: str) -> Optional[Dict[str, Any]]:
            json_str = extract_json(text.strip())
            if json_str and json_str[0] in ('{', '['):
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
            return None

        cached = cache_get(prompt, self.__class__.__name__, temperature, max_tokens)
        if cached is not None:
            result = _try_parse(cached)
            if result is not None:
                return result

        response = self.complete(
            prompt=prompt, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout,
        )
        result = _try_parse(response.text)
        if result is not None:
            cache_set(prompt, response.text, self.__class__.__name__, temperature, max_tokens)
            return result

        retry_prompt = prompt + "\n\nReturn ONLY valid JSON. No markdown, no code fences, no explanation. Just the raw JSON object."
        response = self.complete(
            prompt=retry_prompt, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout,
        )
        result = _try_parse(response.text)
        if result is not None:
            cache_set(prompt, response.text, self.__class__.__name__, temperature, max_tokens)
        return result


class TranscriberProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, language: str = "en", initial_prompt: Optional[str] = None, progress_callback: Optional[Callable[[int, int], None]] = None) -> str:
        ...

    def get_segments(self, audio_path: str, language: str = "en", initial_prompt: Optional[str] = None) -> list:
        ...

    def cancel(self):
        ...

    @abstractmethod
    def cleanup(self):
        ...


class PDFParserProvider(ABC):
    @abstractmethod
    def parse(self, pdf_path: str, redact: bool = True) -> Any:
        ...

    @abstractmethod
    def extract_text(self, pdf_path: str) -> str:
        ...
