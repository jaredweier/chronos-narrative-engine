import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import json
import os
import tempfile

from transcriber import (
    _classify_confidence_tier,
    _is_hallucinated_segment,
    TranscriptSegment,
    WordTimestamp,
    BodyCamTranscriber,
)
from config import WHISPER_USE_BATCHED, WHISPER_ENABLE_ALIGNMENT, WHISPER_ENABLE_DIARIZATION


class FakeWord:
    def __init__(self, word="test", start=0.0, end=1.0, probability=0.95):
        self.word = word
        self.start = start
        self.end = end
        self.probability = probability


class FakeSegment:
    def __init__(self, start=0.0, end=5.0, text="test text",
                 no_speech_prob=0.1, compression_ratio=1.0, avg_logprob=-0.3,
                 words=None):
        self.start = start
        self.end = end
        self.text = text
        self.no_speech_prob = no_speech_prob
        self.compression_ratio = compression_ratio
        self.avg_logprob = avg_logprob
        self.words = words or []


class TestConfidenceTier:
    def test_high_confidence(self):
        assert _classify_confidence_tier(0.95) == "high"

    def test_medium_confidence(self):
        assert _classify_confidence_tier(0.80) == "medium"

    def test_low_confidence(self):
        assert _classify_confidence_tier(0.60) == "low"

    def test_uncertain_confidence(self):
        assert _classify_confidence_tier(0.30) == "uncertain"

    def test_boundary_high(self):
        assert _classify_confidence_tier(0.9) == "high"

    def test_boundary_medium(self):
        assert _classify_confidence_tier(0.7) == "medium"

    def test_boundary_low(self):
        assert _classify_confidence_tier(0.5) == "low"


class TestWordTimestamp:
    def test_format_without_speaker(self):
        wt = WordTimestamp(word="hello", start=1.0, end=1.5, probability=0.95)
        assert wt.format() == "hello[1.00-1.50]"

    def test_format_with_speaker(self):
        wt = WordTimestamp(word="hello", start=1.0, end=1.5, probability=0.95, speaker="SPEAKER_00")
        assert wt.format() == "<SPEAKER_00> hello[1.00-1.50]"

    def test_format_zero_probability(self):
        wt = WordTimestamp(word="test", start=0.0, end=0.0)
        assert wt.format() == "test[0.00-0.00]"


class TestTranscriptSegment:
    def test_confidence_from_words(self):
        words = [
            WordTimestamp(word="a", start=0.0, end=0.5, probability=0.9),
            WordTimestamp(word="b", start=0.5, end=1.0, probability=0.7),
        ]
        seg = TranscriptSegment(start=0.0, end=1.0, text="a b", words=words)
        assert seg.confidence == pytest.approx(0.8)

    def test_confidence_empty_words(self):
        seg = TranscriptSegment(start=0.0, end=1.0, text="test", no_speech_prob=0.2)
        assert seg.confidence == pytest.approx(0.8)

    def test_confidence_all_zero_prob(self):
        words = [WordTimestamp(word="a", start=0.0, end=0.5, probability=0.0)]
        seg = TranscriptSegment(start=0.0, end=1.0, text="a", words=words, no_speech_prob=0.3)
        assert seg.confidence == pytest.approx(0.7)

    def test_is_low_confidence_true(self):
        seg = TranscriptSegment(start=0.0, end=1.0, text="test", confidence_tier="low")
        assert seg.is_low_confidence is True

    def test_is_low_confidence_uncertain(self):
        seg = TranscriptSegment(start=0.0, end=1.0, text="test", confidence_tier="uncertain")
        assert seg.is_low_confidence is True

    def test_is_low_confidence_false(self):
        seg = TranscriptSegment(start=0.0, end=1.0, text="test", confidence_tier="high")
        assert seg.is_low_confidence is False

    def test_words_default_empty_list(self):
        seg = TranscriptSegment(start=0.0, end=1.0, text="test")
        assert seg.words == []


class TestHallucinationDetection:
    def test_high_no_speech_prob(self):
        seg = FakeSegment(no_speech_prob=0.6)
        assert _is_hallucinated_segment(seg) is True

    def test_high_compression_ratio(self):
        seg = FakeSegment(compression_ratio=2.5)
        assert _is_hallucinated_segment(seg) is True

    def test_low_avg_logprob(self):
        seg = FakeSegment(avg_logprob=-1.5)
        assert _is_hallucinated_segment(seg) is True

    def test_clean_segment(self):
        seg = FakeSegment(no_speech_prob=0.1, compression_ratio=1.0, avg_logprob=-0.3)
        assert _is_hallucinated_segment(seg) is False

    def test_missing_attributes(self):
        seg = object()
        assert _is_hallucinated_segment(seg) is False


class TestTimestampFormatting:
    def test_format_timestamp_basic(self):
        t = BodyCamTranscriber.__new__(BodyCamTranscriber)
        assert t.format_timestamp(0) == "00:00"
        assert t.format_timestamp(65) == "01:05"
        assert t.format_timestamp(3661) == "61:01"

    def test_format_timestamp_precise(self):
        t = BodyCamTranscriber.__new__(BodyCamTranscriber)
        assert t.format_timestamp_precise(0) == "00:00.00"
        assert t.format_timestamp_precise(65.5) == "01:05.50"
        assert t.format_timestamp_precise(3661.123) == "61:01.12"


class TestFormatTranscript:
    def test_basic_format(self, monkeypatch):
        monkeypatch.setattr('transcriber.WHISPER_TRANSCRIPT_CORRECTOR_ENABLED', False)
        seg = TranscriptSegment(start=0.0, end=5.0, text="hello world", confidence_tier="high")
        t = BodyCamTranscriber.__new__(BodyCamTranscriber)
        result = t.format_transcript([seg])
        assert "[00:00 -> 00:05]" in result
        assert "hello world" in result
        assert "[?]" not in result

    def test_low_confidence_marker(self, monkeypatch):
        monkeypatch.setattr('transcriber.WHISPER_TRANSCRIPT_CORRECTOR_ENABLED', False)
        seg = TranscriptSegment(start=0.0, end=5.0, text="unclear audio", confidence_tier="low")
        t = BodyCamTranscriber.__new__(BodyCamTranscriber)
        result = t.format_transcript([seg])
        assert "[?]" in result

    def test_speaker_tag(self, monkeypatch):
        monkeypatch.setattr('transcriber.WHISPER_TRANSCRIPT_CORRECTOR_ENABLED', False)
        seg = TranscriptSegment(start=0.0, end=5.0, text="hello", speaker="SPEAKER_00")
        t = BodyCamTranscriber.__new__(BodyCamTranscriber)
        result = t.format_transcript([seg])
        assert "<SPEAKER_00>" in result

    def test_metadata_line(self, monkeypatch):
        monkeypatch.setattr('transcriber.WHISPER_TRANSCRIPT_CORRECTOR_ENABLED', False)
        seg = TranscriptSegment(start=0.0, end=5.0, text="test", confidence_tier="high",
                                words=[WordTimestamp(word="test", start=0.0, end=5.0, probability=0.95)])
        t = BodyCamTranscriber.__new__(BodyCamTranscriber)
        result = t.format_transcript([seg])
        assert "[METADATA]" in result
        assert "confidence=" in result
        assert "low_confidence=0" in result

    def test_metadata_low_conf_count(self, monkeypatch):
        monkeypatch.setattr('transcriber.WHISPER_TRANSCRIPT_CORRECTOR_ENABLED', False)
        segs = [
            TranscriptSegment(start=0.0, end=2.0, text="good", confidence_tier="high",
                              words=[WordTimestamp(word="good", start=0.0, end=2.0, probability=0.95)]),
            TranscriptSegment(start=2.0, end=4.0, text="bad", confidence_tier="low",
                              words=[WordTimestamp(word="bad", start=2.0, end=4.0, probability=0.4)]),
        ]
        t = BodyCamTranscriber.__new__(BodyCamTranscriber)
        result = t.format_transcript(segs)
        assert "low_confidence=1" in result

    def test_empty_segments(self):
        t = BodyCamTranscriber.__new__(BodyCamTranscriber)
        result = t.format_transcript([])
        assert result == ""


class TestSegmentsFromRaw:
    def test_normal_segment(self):
        raw = [FakeSegment(start=0.0, end=5.0, text=" hello world ",
                           words=[FakeWord(word="hello", probability=0.9)])]
        t = BodyCamTranscriber.__new__(BodyCamTranscriber)
        segs, hallucinated, total_words = t._segments_from_raw(raw)
        assert len(segs) == 1
        assert segs[0].text == "hello world"
        assert hallucinated == 0
        assert total_words == 1

    def test_hallucinated_segment_filtered(self):
        raw = [
            FakeSegment(start=0.0, end=5.0, text="real", no_speech_prob=0.0, compression_ratio=1.0, avg_logprob=-0.3),
            FakeSegment(start=5.0, end=10.0, text="hallucination", no_speech_prob=0.9, compression_ratio=3.0, avg_logprob=-2.0),
        ]
        t = BodyCamTranscriber.__new__(BodyCamTranscriber)
        segs, hallucinated, total_words = t._segments_from_raw(raw)
        assert len(segs) == 1
        assert segs[0].text == "real"
        assert hallucinated == 1

    def test_confidence_tier_assigned(self):
        raw = [FakeSegment(start=0.0, end=5.0, text="test",
                           words=[FakeWord(word="test", probability=0.95)])]
        t = BodyCamTranscriber.__new__(BodyCamTranscriber)
        segs, _, _ = t._segments_from_raw(raw)
        t._assign_confidence_tiers(segs)
        assert segs[0].confidence_tier == "high"


class TestProviderGetSegments:
    def test_get_segments_returns_list(self):
        from providers.transcribe_whisper import WhisperTranscriberProvider
        provider = WhisperTranscriberProvider()
        assert hasattr(provider, 'get_segments')

    def test_get_segments_calls_transcribe_file(self):
        from providers.transcribe_whisper import WhisperTranscriberProvider
        provider = WhisperTranscriberProvider()
        with patch.object(provider, '_get') as mock_get:
            mock_t = MagicMock()
            mock_t.transcribe_file.return_value = [TranscriptSegment(start=0.0, end=1.0, text="test")]
            mock_get.return_value = mock_t
            result = provider.get_segments("fake.wav")
            mock_t.transcribe_file.assert_called_once_with("fake.wav", "en", initial_prompt=None)
            assert len(result) == 1
            assert result[0].text == "test"


class TestFineTunePipeline:
    def test_export_training_pairs_empty_db(self):
        from fine_tune_pipeline import export_training_pairs
        with patch('fine_tune_pipeline.get_db_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.return_value.cursor.return_value = mock_cursor
            with tempfile.TemporaryDirectory() as tmpdir:
                pairs = export_training_pairs(min_pairs=1, output_dir=tmpdir)
                assert pairs == []
                manifest_path = os.path.join(tmpdir, "training_manifest.json")
                assert os.path.exists(manifest_path)
                with open(manifest_path) as f:
                    data = json.load(f)
                    assert data["total_pairs"] == 0

    def test_prepare_fine_tune_dataset(self):
        from fine_tune_pipeline import prepare_fine_tune_dataset
        pairs = [
            {"incident_id": "1", "officer_name": "Test", "document_type": "DUI",
             "ai_draft": "draft text", "corrected": "corrected text"}
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = prepare_fine_tune_dataset(pairs, tmpdir)
            assert path is not None
            assert os.path.exists(path)
            with open(path) as f:
                lines = f.read().strip().split("\n")
                assert len(lines) == 1
                record = json.loads(lines[0])
                assert record["text"] == "corrected text"
                assert record["ai_text"] == "draft text"
                assert record["document_type"] == "DUI"


class TestConfigValues:
    def test_batched_default_enabled(self):
        assert WHISPER_USE_BATCHED is True

    def test_alignment_default_enabled(self):
        assert WHISPER_ENABLE_ALIGNMENT is True

    def test_diarization_default_disabled(self):
        assert WHISPER_ENABLE_DIARIZATION is False

    def test_cancel_method(self):
        t = BodyCamTranscriber()
        t._cancel_event = MagicMock()
        t.cancel()
        t._cancel_event.set.assert_called_once()

    def test_reset_cancel(self):
        t = BodyCamTranscriber()
        t._cancel_event = MagicMock()
        t.reset_cancel()
        t._cancel_event.clear.assert_called_once()
