import json
import time
import requests
from typing import Optional, Callable
from config import OLLAMA_API_ENDPOINT, OLLAMA_MODEL
from logger import get_logger
from providers.base import LLMProvider, LLMResponse

logger = get_logger(__name__)


class OllamaLLMProvider(LLMProvider):
    def __init__(self, base_url: str = OLLAMA_API_ENDPOINT, model: str = OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model

    def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        chunk_callback: Optional[Callable[[str], None]] = None,
        timeout: int = 120,
    ) -> LLMResponse:
        start = time.time()
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": 0.9,
            },
        }
        kwargs = {"timeout": timeout}
        if stream:
            kwargs["stream"] = True

        try:
            response = requests.post(self.base_url, json=body, **kwargs)
            response.raise_for_status()

            if stream:
                accumulated = ""
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        token = data.get("response", "")
                        accumulated += token
                        if chunk_callback:
                            chunk_callback(token)
                text = accumulated.strip()
            else:
                text = response.json().get("response", "").strip()

            duration = int((time.time() - start) * 1000)
            return LLMResponse(text=text, model=self.model, duration_ms=duration)

        except requests.ConnectionError:
            return LLMResponse(
                text="[ERROR] Cannot connect to Ollama. Please ensure Ollama is running (ollama serve).",
                model=self.model,
            )
        except requests.Timeout:
            return LLMResponse(
                text="[ERROR] Generation timed out. The model may be overloaded.",
                model=self.model,
            )
        except Exception as e:
            logger.error("Ollama request failed: %s", e)
            return LLMResponse(
                text=f"[ERROR] Generation failed: {e}",
                model=self.model,
            )

    def stream_complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int = 120,
    ):
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": 0.9,
            },
        }
        try:
            response = requests.post(self.base_url, json=body, stream=True, timeout=timeout)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        yield token

        except requests.ConnectionError:
            yield "[ERROR] Cannot connect to Ollama. Please ensure Ollama is running (ollama serve)."
        except requests.Timeout:
            yield "[ERROR] Generation timed out. The model may be overloaded."
        except Exception as e:
            logger.error("Ollama stream failed: %s", e)
            yield f"[ERROR] Generation failed: {e}"
