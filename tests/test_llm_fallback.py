import os
import sys
import re

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from providers.base import LLMProvider, LLMResponse
from providers.llm_fallback import FallbackLLMProvider, _generate_template_narrative


class _OkProvider(LLMProvider):
    def complete(self, prompt="", temperature=0.7, max_tokens=2048, stream=False, chunk_callback=None, timeout=120):
        return LLMResponse(text="This is a valid AI-generated narrative.", model="test_model", duration_ms=50)
    def stream_complete(self, *args, **kwargs):
        yield "ok"


class _ErrorProvider(LLMProvider):
    def complete(self, prompt="", temperature=0.7, max_tokens=2048, stream=False, chunk_callback=None, timeout=120):
        return LLMResponse(text="[ERROR] Cannot connect to Ollama.", model="test_model", duration_ms=50)
    def stream_complete(self, *args, **kwargs):
        yield "ok"


class _RaisingProvider(LLMProvider):
    def complete(self, prompt="", temperature=0.7, max_tokens=2048, stream=False, chunk_callback=None, timeout=120):
        raise ConnectionError("Connection refused")
    def stream_complete(self, *args, **kwargs):
        yield "ok"


class TestFallbackPassthrough:
    def test_passes_through_successful_response(self):
        inner = _OkProvider()
        fallback = FallbackLLMProvider(inner)
        resp = fallback.complete(prompt="Generate a report")
        assert resp.text == "This is a valid AI-generated narrative."
        assert resp.model == "test_model"

    def test_passes_through_model_name(self):
        inner = _OkProvider()
        fallback = FallbackLLMProvider(inner)
        resp = fallback.complete(prompt="Test")
        assert resp.model == "test_model"


class TestFallbackOnError:
    def test_fallback_on_error_response(self):
        inner = _ErrorProvider()
        fallback = FallbackLLMProvider(inner)
        resp = fallback.complete(prompt="Generate a narrative for a theft report")
        assert not resp.text.startswith("[ERROR]")
        assert "INCIDENT NARRATIVE" in resp.text
        assert "_fallback" in resp.model

    def test_fallback_includes_narrative_structure(self):
        inner = _ErrorProvider()
        fallback = FallbackLLMProvider(inner)
        resp = fallback.complete(prompt="Generate a report")
        assert "Respectfully submitted" in resp.text
        assert "[INSERT" in resp.text

    def test_fallback_on_exception(self):
        inner = _RaisingProvider()
        fallback = FallbackLLMProvider(inner)
        resp = fallback.complete(prompt="Generate a report")
        assert "INCIDENT NARRATIVE" in resp.text
        assert resp.model == "fallback_template"


class TestTemplateNarrative:
    def test_extracts_report_type_from_prompt(self):
        prompt = "Report Type: Theft Report\nSome text"
        result = _generate_template_narrative(prompt)
        assert "Theft Report" in result

    def test_uses_department_name(self):
        prompt = "Generate a report"
        result = _generate_template_narrative(prompt)
        from config import DEPARTMENT_NAME
        assert DEPARTMENT_NAME in result

    def test_uses_default_placeholders_when_no_details(self):
        prompt = "Make a narrative"
        result = _generate_template_narrative(prompt)
        placeholders = re.findall(r'\[INSERT[^\]]*\]', result)
        assert len(placeholders) >= 3

    def test_extracts_case_number(self):
        prompt = "Case #: 25-1234\nGenerate a narrative"
        result = _generate_template_narrative(prompt)
        assert "25-1234" in result

    def test_has_correct_sections(self):
        prompt = "Generate a narrative"
        result = _generate_template_narrative(prompt)
        assert result.startswith("INCIDENT NARRATIVE")
        assert "Respectfully submitted" in result
        assert "[NOTE:" in result
