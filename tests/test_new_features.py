import os
import sys
import json
import tempfile
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from llm_cache import cache_get, cache_set, cache_clear, cache_size
from ncic_codes import lookup_ncic_code, lookup_ncic_make, search_ncic
from providers.base import LLMProvider, LLMResponse
from wi_statutes import find_statutes_in_text, statutes_for_nibrs, nibrs_for_statute, get_statute
from nibrs_checker import suggest_statutes_from_narrative
from nibrs_export import build_nibrs_xml
from phrase_book import export_phrases_to_json, import_phrases_from_json
from providers.registry import get_llm, clear_provider_cache, register_llm
from redactor import sanitize_location, sanitize_pii_content
from spell_check import check_text_spelling, auto_correct
from config import WHISPER_LANGUAGE, validate_config
from database import save_snapshot_db, get_snapshots
from fine_tune_pipeline import export_quality_report


class _JsonTestProvider(LLMProvider):
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0
    def complete(self, prompt="", temperature=0.7, max_tokens=2048, stream=False, chunk_callback=None, timeout=120):
        resp_text = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return LLMResponse(text=resp_text, model="test_model", duration_ms=0)
    def stream_complete(self, *args, **kwargs):
        yield "ok"

class TestLLMCache:
    def test_cache_set_get(self, monkeypatch):
        monkeypatch.setattr("llm_cache.LLM_CACHE_ENABLED", True)
        cache_clear()
        cache_set("prompt1", "result1")
        assert cache_get("prompt1") == "result1"

    def test_cache_miss(self, monkeypatch):
        monkeypatch.setattr("llm_cache.LLM_CACHE_ENABLED", True)
        cache_clear()
        assert cache_get("nonexistent") is None

    def test_cache_ttl_expiry(self, monkeypatch):
        monkeypatch.setattr("llm_cache.LLM_CACHE_TTL_SECONDS", 0)
        monkeypatch.setattr("llm_cache.LLM_CACHE_ENABLED", True)
        cache_clear()
        cache_set("prompt_expire", "will_expire")
        assert cache_get("prompt_expire") is None

    def test_cache_clear(self, monkeypatch):
        monkeypatch.setattr("llm_cache.LLM_CACHE_ENABLED", True)
        cache_clear()
        cache_set("a", "1")
        cache_set("b", "2")
        assert cache_clear() == 2
        assert cache_size() == 0

    def test_cache_size(self, monkeypatch):
        monkeypatch.setattr("llm_cache.LLM_CACHE_ENABLED", True)
        cache_clear()
        cache_set("x", "10")
        cache_set("y", "20")
        assert cache_size() == 2

    def test_cache_disabled(self, monkeypatch):
        monkeypatch.setattr("llm_cache.LLM_CACHE_ENABLED", False)
        cache_clear()
        cache_set("key_disabled", "val")
        assert cache_get("key_disabled") is None
        assert cache_size() == 0


class TestNCICCodes:
    def test_lookup_ncic_code_found(self):
        assert lookup_ncic_code("0101") == "Arson"

    def test_lookup_ncic_code_not_found(self):
        assert lookup_ncic_code("XXXX") == ""

    def test_lookup_ncic_make(self):
        assert lookup_ncic_make("FD") == "Ford"

    def test_search_ncic_by_code(self):
        results = search_ncic("0201")
        assert any(r["code"] == "0201" for r in results)

    def test_search_ncic_by_desc(self):
        results = search_ncic("arson")
        assert any("Arson" in r["description"] for r in results)


class TestLLMJsonRetry:
    def test_complete_json_first_attempt_succeeds(self, monkeypatch):
        monkeypatch.setattr("llm_cache.LLM_CACHE_ENABLED", False)
        provider = _JsonTestProvider([json.dumps({"key": "value"})])
        result = provider.complete_json(prompt="test prompt")
        assert result == {"key": "value"}

    def test_complete_json_retry_succeeds(self, monkeypatch):
        monkeypatch.setattr("llm_cache.LLM_CACHE_ENABLED", False)
        provider = _JsonTestProvider(["not json at all", json.dumps({"success": True})])
        result = provider.complete_json(prompt="test retry")
        assert result == {"success": True}

    def test_complete_json_both_fail(self, monkeypatch):
        monkeypatch.setattr("llm_cache.LLM_CACHE_ENABLED", False)
        provider = _JsonTestProvider(["bad data", "still bad"])
        result = provider.complete_json(prompt="test fail")
        assert result is None


class TestStatuteAutoLink:
    def test_find_statutes_in_text_with_section(self):
        text = "The suspect violated § 940.01 by committing homicide."
        results = find_statutes_in_text(text)
        codes = [r["code"] for r in results]
        assert "940.01" in codes

    def test_find_statutes_in_text_without_section(self):
        text = "The officer cited 940.60(1) for the battery."
        results = find_statutes_in_text(text)
        codes = [r["code"] for r in results]
        assert "940.60(1)" in codes

    def test_find_statutes_in_text_no_match(self):
        text = "The suspect fled the scene on foot."
        results = find_statutes_in_text(text)
        assert results == []

    def test_find_statutes_in_text_multiple(self):
        text = "Violations include § 940.01 and § 946.41 and 943.20(1)."
        results = find_statutes_in_text(text)
        assert len(results) == 3


class TestNibrsWiCrossReference:
    def test_statutes_for_nibrs_found(self):
        results = statutes_for_nibrs("09A")
        codes = [r["code"] for r in results]
        assert "940.01" in codes

    def test_statutes_for_nibrs_not_found(self):
        results = statutes_for_nibrs("ZZZZ")
        assert results == []

    def test_nibrs_for_statute_found(self):
        results = nibrs_for_statute("940.01")
        assert "09A" in results
        assert "23A" in results

    def test_nibrs_for_statute_not_found(self):
        results = nibrs_for_statute("000.00")
        assert results == []


class TestStatuteSuggestion:
    def test_suggest_statutes_from_narrative_finds_keywords(self):
        narrative = "The suspect committed murder and homicide. He intentionally killed the victim with a deadly weapon."
        results = suggest_statutes_from_narrative(narrative)
        assert len(results) > 0
        assert all(r["score"] > 0 for r in results)

    def test_suggest_statutes_from_narrative_empty(self):
        results = suggest_statutes_from_narrative("")
        assert results == []


class TestNIBRSEnhancedXML:
    def test_build_nibrs_xml_with_optional_segments(self):
        xml_str = build_nibrs_xml(
            incident_id="INC001",
            nibrs_offense_code="09A",
            arrestee={"name": "John Doe", "age": 30, "sex": "M", "race": "W", "ethnicity": "NH", "resident_status": "R", "arrest_type": "O"},
            offender={"name": "Jane Doe", "age": 25, "sex": "F", "race": "B"},
            property={"property_description": "Wallet", "loss_type": "S", "value": 500, "ucr_code": "123"},
            victim={"name": "Jim Doe", "age": 40, "sex": "M", "race": "W", "ethnicity": "NH", "victim_type": "I", "injury_type": "N"},
        )
        assert "<Arrestee>" in xml_str
        assert "<Name>John Doe</Name>" in xml_str
        assert "<Offender>" in xml_str
        assert "<Name>Jane Doe</Name>" in xml_str
        assert "<Property>" in xml_str
        assert "<PropertyDescription>Wallet</PropertyDescription>" in xml_str
        assert "<Victim>" in xml_str
        assert "<Name>Jim Doe</Name>" in xml_str

    def test_build_nibrs_xml_without_optional_segments(self):
        xml_str = build_nibrs_xml(
            incident_id="INC002",
            nibrs_offense_code="09A",
        )
        assert "<Arrestee>" not in xml_str
        assert "<Offender>" not in xml_str
        assert "<Property>" not in xml_str
        assert "<Victim>" not in xml_str


class TestPhraseBookImportExport:
    def test_export_phrases_to_json(self, monkeypatch, tmpdir):
        sample_phrases = [
            {"label": "Greeting", "phrase_text": "Good morning", "category": "General"},
            {"label": "Farewell", "phrase_text": "Stay safe", "category": "General"},
        ]
        monkeypatch.setattr("phrase_book.get_phrases", lambda officer, category=None: sample_phrases)
        filepath = os.path.join(str(tmpdir), "export.json")
        count = export_phrases_to_json("TestOfficer", filepath)
        assert count == 2
        assert os.path.exists(filepath)
        with open(filepath, "r") as f:
            data = json.load(f)
        assert data["count"] == 2
        assert data["officer"] == "TestOfficer"
        assert len(data["phrases"]) == 2

    def test_import_phrases_from_json(self, monkeypatch, tmpdir):
        data = {"officer": "TestOfficer", "phrases": [{"label": "Custom", "phrase_text": "Custom phrase", "category": "Custom"}], "count": 1}
        filepath = os.path.join(str(tmpdir), "import.json")
        with open(filepath, "w") as f:
            json.dump(data, f)
        mock_add = MagicMock()
        monkeypatch.setattr("phrase_book.add_phrase", mock_add)
        count = import_phrases_from_json("TestOfficer", filepath)
        assert count == 1
        mock_add.assert_called_once_with("TestOfficer", "Custom", "Custom phrase", "Custom")


class TestProviderCaching:
    def test_get_llm_returns_cached_instance(self, monkeypatch):
        monkeypatch.setattr("llm_cache.LLM_CACHE_ENABLED", False)
        class _MockProvider(LLMProvider):
            def complete(self, *args, **kwargs):
                return LLMResponse(text="ok", duration_ms=0)
            def stream_complete(self, *args, **kwargs):
                yield "ok"
        register_llm("test_cache_provider", _MockProvider)
        monkeypatch.setattr("providers.registry.LLM_PROVIDER", "test_cache_provider")
        clear_provider_cache()
        first = get_llm()
        second = get_llm()
        assert first is second

    def test_clear_provider_cache_resets(self, monkeypatch):
        monkeypatch.setattr("llm_cache.LLM_CACHE_ENABLED", False)
        class _MockProvider2(LLMProvider):
            def complete(self, *args, **kwargs):
                return LLMResponse(text="ok", duration_ms=0)
            def stream_complete(self, *args, **kwargs):
                yield "ok"
        register_llm("test_cache_provider2", _MockProvider2)
        monkeypatch.setattr("providers.registry.LLM_PROVIDER", "test_cache_provider2")
        clear_provider_cache()
        first = get_llm()
        clear_provider_cache()
        second = get_llm()
        assert first is not second


class TestLocationRedaction:
    def test_sanitize_location_gps(self):
        text = "The incident occurred at 43° 02' 14\" N, 88° 00' 57\" W near the park."
        result = sanitize_location(text)
        assert "[GPS COORDINATES]" in result
        assert "43°" not in result

    def test_sanitize_location_intersection(self):
        text = "The crash occurred at the Intersection of Main Street and Oak Avenue."
        result = sanitize_location(text)
        assert "[INTERSECTION]" in result

    def test_sanitize_location_landmark(self):
        text = "The suspect was seen near the County Hospital on the east side."
        result = sanitize_location(text)
        assert "[LANDMARK]" in result

    def test_sanitize_pii_content_calls_location(self):
        text = "GPS: 43° 02' 14\" N, 88° 00' 57\" W. SSN: 123-45-6789. Email: test@example.com."
        result = sanitize_pii_content(text)
        assert "[GPS COORDINATES]" in result
        assert "[REDACTED_SSN]" in result
        assert "[REDACTED_EMAIL]" in result
        assert "123-45-6789" not in result
        assert "test@example.com" not in result


class TestSpellCheckCustomDict:
    def test_get_combined_dict_includes_custom(self, monkeypatch):
        monkeypatch.setattr("spell_check.get_custom_dict", lambda: {"custommispeling": "customspelling"})
        monkeypatch.setattr("spell_check.SPELL_CHECK_ENABLED", True)
        text = "This is a custommispeling in the report."
        issues = check_text_spelling(text)
        assert any(orig == "custommispeling" for orig, corr, pos in issues)
        assert any(corr == "customspelling" for orig, corr, pos in issues)

    def test_auto_correct_uses_custom_dict(self, monkeypatch):
        monkeypatch.setattr("spell_check.get_custom_dict", lambda: {"custommispeling": "customspelling"})
        monkeypatch.setattr("spell_check.SPELL_CHECK_ENABLED", True)
        text = "custommispeling is present"
        result = auto_correct(text)
        assert "customspelling" in result
        assert "custommispeling" not in result


class TestMultiLanguage:
    def test_whisper_language_default(self):
        assert WHISPER_LANGUAGE == "en"


class TestDatabaseSnapshots:
    def test_save_and_get_snapshots(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        mock_cursor.lastrowid = 42

        mock_fetchall_result = [
            {"id": 1, "incident_id": "INC001", "snapshot_text": "test snapshot v1", "label": "AI Draft", "officer_name": "Officer", "created_at": "2026-01-01T00:00:00", "previous_snapshot_id": None}
        ]
        mock_conn2 = MagicMock()
        mock_conn2.execute.return_value.fetchall.return_value = mock_fetchall_result

        call_count = 0
        calls = [mock_conn, mock_conn2]

        @contextmanager
        def mock_get_conn():
            nonlocal call_count
            idx = call_count
            call_count += 1
            yield calls[idx]

        monkeypatch.setattr("database.get_db_connection", mock_get_conn)
        monkeypatch.setattr("spell_check.SPELL_CHECK_ENABLED", False)

        result_id = save_snapshot_db("INC001", "test snapshot v1", "AI Draft", "Officer")
        assert result_id == 42

        snapshots = get_snapshots("INC001")
        assert len(snapshots) == 1
        assert snapshots[0]["snapshot_text"] == "test snapshot v1"


class TestConfigValidation:
    def test_validate_config_returns_list(self):
        result = validate_config()
        assert isinstance(result, list)


class TestFineTuneQualityMetrics:
    def test_export_quality_report(self, monkeypatch, tmpdir, mock_pairs_fixture):
        monkeypatch.setattr("fine_tune_pipeline.export_training_pairs", lambda min_pairs=1, output_dir=None: mock_pairs_fixture)
        monkeypatch.setattr("database.get_db_connection", lambda: MagicMock())

        result = export_quality_report(output_dir=str(tmpdir))
        assert result.endswith("quality_report.json")
        assert os.path.exists(result)
        with open(result, "r") as f:
            report = json.load(f)
        assert report["total_pairs"] == 1
        assert "average_edit_distance" in report
        assert "by_document_type" in report
