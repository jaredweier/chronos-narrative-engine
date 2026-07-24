import re
import time
from typing import Optional, Callable
from providers.base import LLMProvider, LLMResponse
from config import DEPARTMENT_NAME
from logger import get_logger

logger = get_logger(__name__)

_CASE_NUMBER_RE = re.compile(r'Case\s*#?\s*:?\s*(\S+)', re.IGNORECASE)
_REPORT_TYPE_RE = re.compile(r'Report\s+Type\s*:?\s*(.+?)$', re.IGNORECASE | re.MULTILINE)
_LOCATION_RE = re.compile(r'(?:Location|Address)\s*:?\s*(.+?)$', re.IGNORECASE | re.MULTILINE)
_OFFICER_RE = re.compile(r'(?:Officer|Responding)\s*:?\s*(.+?)$', re.IGNORECASE | re.MULTILINE)


def _extract_field(pattern: re.Pattern, text: str) -> str:
    m = pattern.search(text)
    return m.group(1).strip() if m else "[INSERT DETAIL]"


def _generate_template_narrative(prompt: str) -> str:
    report_type = _extract_field(_REPORT_TYPE_RE, prompt)
    case_number = _extract_field(_CASE_NUMBER_RE, prompt)
    location = _extract_field(_LOCATION_RE, prompt)
    officer = _extract_field(_OFFICER_RE, prompt)

    lines = [
        f"INCIDENT NARRATIVE — {report_type}",
        f"{'=' * 60}",
        "",
        f"On [INSERT DATE] at approximately [INSERT TIME], I, {officer}, was dispatched to {location} in reference to {report_type.lower()}.",
        "",
        "Upon arrival, I made contact with [INSERT NAME(S)] who stated [INSERT DETAIL].",
        "",
        "[INSERT DETAIL]",
        "",
        "I observed [INSERT DETAIL] and documented the scene accordingly. Photographs were taken and evidence was collected.",
        "",
        "All persons involved were identified and their statements were documented.",
        "",
        "Disposition: [INSERT DISPOSITION].",
        "",
        f"Respectfully submitted,",
        f"{officer}",
        f"{DEPARTMENT_NAME}",
        "",
        f"Case #{case_number}",
        "",
        f"[NOTE: This is a template-based narrative generated because the AI provider was unavailable. "
        f"Please verify all details and replace bracketed placeholders.]",
    ]
    return "\n".join(lines)


class FallbackLLMProvider(LLMProvider):
    def __init__(self, inner: LLMProvider):
        self._inner = inner

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
        try:
            response = self._inner.complete(
                prompt=prompt, temperature=temperature,
                max_tokens=max_tokens, stream=stream,
                chunk_callback=chunk_callback, timeout=timeout,
            )
            if response.text.startswith("[ERROR]"):
                logger.info("Inner LLM returned error; falling back to template generation")
                fallback_text = _generate_template_narrative(prompt)
                duration = int((time.time() - start) * 1000)
                return LLMResponse(
                    text=fallback_text,
                    model=f"{response.model}_fallback",
                    duration_ms=duration,
                )
            return response
        except Exception as e:
            logger.warning("Inner LLM raised %s; using template fallback", e)
            fallback_text = _generate_template_narrative(prompt)
            duration = int((time.time() - start) * 1000)
            return LLMResponse(
                text=fallback_text,
                model="fallback_template",
                duration_ms=duration,
            )

    def stream_complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int = 120,
    ):
        try:
            stream = self._inner.stream_complete(
                prompt=prompt, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout,
            )
            has_yielded = False
            for token in stream:
                if not has_yielded and token.startswith("[ERROR]"):
                    logger.info("Inner LLM stream returned error; falling back to template generation")
                    fallback_text = _generate_template_narrative(prompt)
                    yield fallback_text
                    return
                has_yielded = True
                yield token
        except Exception as e:
            logger.warning("Inner LLM stream raised %s; using template fallback", e)
            fallback_text = _generate_template_narrative(prompt)
            yield fallback_text
