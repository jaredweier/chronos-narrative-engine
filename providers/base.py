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

    def complete_json(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: int = 60,
    ) -> Optional[Dict[str, Any]]:
        import json
        from utils import extract_json
        response = self.complete(
            prompt=prompt, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout,
        )
        text = response.text.strip()
        json_str = extract_json(text)
        if json_str and json_str[0] in ('{', '['):
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        return None


class TranscriberProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, language: str = "en", initial_prompt: Optional[str] = None) -> str:
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
