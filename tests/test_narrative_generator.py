import pytest
from narrative_generator import _build_narrative_prompt, count_insert_placeholders, has_unfilled_placeholders


class TestPromptTruncation:
    def test_truncation_applies_when_over_limit(self, monkeypatch):
        monkeypatch.setattr('narrative_generator.MAX_TOTAL_PROMPT_CHARS', 200)
        long_text = "X" * 500
        result = _build_narrative_prompt("System prompt", cad_text=long_text)
        assert len(result) < 500
        assert "[TRUNCATED" in result

    def test_truncation_does_not_apply_when_under_limit(self, monkeypatch):
        monkeypatch.setattr('narrative_generator.MAX_TOTAL_PROMPT_CHARS', 99999)
        result = _build_narrative_prompt("System prompt", cad_text="Short CAD data")
        assert "[TRUNCATED" not in result


class TestPlaceholderDetection:
    def test_count_insert_placeholders(self):
        assert count_insert_placeholders("Report [INSERT DETAIL] here") == 1

    def test_count_multiple_placeholders(self):
        assert count_insert_placeholders("[INSERT Name] [INSERT Date]") == 2

    def test_no_placeholders(self):
        assert count_insert_placeholders("Complete narrative") == 0

    def test_has_unfilled_true(self):
        assert has_unfilled_placeholders("Found [INSERT Detail] here")

    def test_has_unfilled_false(self):
        assert not has_unfilled_placeholders("Complete narrative with no placeholders")
