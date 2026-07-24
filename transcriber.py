import os
import gc
import subprocess
import threading
import numpy as np
import torch
from faster_whisper import WhisperModel
from typing import List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from config import (
    WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE,
    WHISPER_CPU_THREADS, WHISPER_BATCH_SIZE, WHISPER_BEAM_SIZE,
    WHISPER_VAD_MIN_SILENCE_MS, WHISPER_VAD_SPEECH_PAD_MS,
    WHISPER_VAD_THRESHOLD, WHISPER_VAD_MIN_SPEECH_MS,
    WHISPER_AUDIO_PREPROCESS, WHISPER_INITIAL_PROMPT,
    WHISPER_NOISE_REDUCE_STRENGTH, WHISPER_NOISE_REDUCE_METHOD,
    WHISPER_DEEPFILTER_ATTEN_LIM_DB,
    WHISPER_WORD_TIMESTAMPS, WHISPER_TRANSCRIPT_CORRECTOR_ENABLED,
    WHISPER_TWO_PASS_ENABLED, WHISPER_TWO_PASS_QUICK_MODEL,
    WHISPER_LANGUAGE,
    TEMP_DIR,
)
from logger import get_logger

logger = get_logger(__name__)

os.environ["OMP_NUM_THREADS"] = str(WHISPER_CPU_THREADS)

AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.ogg', '.flac', '.webm'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv'}


def _check_ffmpeg() -> bool:
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.warning("ffmpeg not found in PATH — video audio extraction will fail")
        return False


_HAS_FFMPEG = _check_ffmpeg()


def extract_audio_from_video(video_path: str) -> Optional[str]:
    if not _HAS_FFMPEG:
        logger.error("Cannot extract audio: ffmpeg not available")
        return None
    base, _ = os.path.splitext(os.path.basename(video_path))
    out_path = os.path.join(TEMP_DIR, f"{base}_audio.wav")
    try:
        subprocess.run(
            ['ffmpeg', '-y', '-i', video_path, '-vn',
             '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
             out_path],
            capture_output=True, check=True, timeout=3600,
        )
        logger.info("Extracted audio from %s -> %s", video_path, out_path)
        return out_path
    except subprocess.TimeoutExpired:
        logger.error("Audio extraction timed out for %s", video_path)
        return None
    except subprocess.CalledProcessError as e:
        logger.error("Audio extraction failed for %s: %s", video_path, e.stderr.decode())
        return None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    probability: float = 0.0
    speaker: Optional[str] = None

    def format(self) -> str:
        speaker_tag = f"<{self.speaker}> " if self.speaker else ""
        return f"{speaker_tag}{self.word}[{self.start:.2f}-{self.end:.2f}]"


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    no_speech_prob: float = 0.0
    compression_ratio: float = 0.0
    avg_logprob: float = 0.0
    words: List[WordTimestamp] = None
    speaker: Optional[str] = None
    confidence_tier: str = "high"

    def __post_init__(self):
        if self.words is None:
            self.words = []

    @property
    def confidence(self) -> float:
        probs = [w.probability for w in self.words if w.probability > 0]
        if probs:
            return sum(probs) / len(probs)
        return max(0.0, 1.0 - self.no_speech_prob)

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence_tier in ("low", "uncertain")


# ---------------------------------------------------------------------------
# Audio preprocessing
# ---------------------------------------------------------------------------

class AudioPreprocessor:
    @staticmethod
    def trim_silence(y: np.ndarray, sr: int, top_db: int = 30) -> np.ndarray:
        import librosa
        y_trimmed, _ = librosa.effects.trim(y, top_db=top_db)
        return y_trimmed

    @staticmethod
    def reduce_noise(y: np.ndarray, sr: int, strength: float = 0.75) -> np.ndarray:
        if WHISPER_NOISE_REDUCE_METHOD == "deepfilter":
            y_df = AudioPreprocessor.reduce_noise_deepfilter(y, sr)
            if y_df is not None:
                return y_df
            logger.info("Falling back to noisereduce")
            
        try:
            import noisereduce as nr
            y_denoised = nr.reduce_noise(
                y=y, sr=sr, stationary=True, prop_decrease=strength,
            )
            return y_denoised
        except ImportError:
            logger.warning("noisereduce not available, skipping noise reduction")
            return y

    _deepfilter_model = None

    @staticmethod
    def _get_deepfilter_model():
        if AudioPreprocessor._deepfilter_model is None:
            try:
                from deepfilter_stream import DeepFilterModel
                AudioPreprocessor._deepfilter_model = DeepFilterModel()
                logger.info("Loaded DeepFilterNet3 model for noise suppression")
            except ImportError:
                logger.warning("deepfilter-stream not installed")
                return None
            except Exception as e:
                logger.warning("Failed to load DeepFilterNet3 model: %s", e)
                return None
        return AudioPreprocessor._deepfilter_model

    @staticmethod
    def reduce_noise_deepfilter(y: np.ndarray, sr: int) -> np.ndarray:
        model = AudioPreprocessor._get_deepfilter_model()
        if model is None:
            return None
        try:
            atten_lim = None
            if WHISPER_DEEPFILTER_ATTEN_LIM_DB >= 0:
                atten_lim = float(WHISPER_DEEPFILTER_ATTEN_LIM_DB)
            stream = model.new_stream(atten_lim_db=atten_lim)
            enhanced = stream.process(y.astype(np.float32), sr=sr)
            tail = stream.flush()
            if tail is not None and len(tail) > 0:
                enhanced = np.concatenate([enhanced, tail])
            stream.reset()
            return enhanced
        except Exception as e:
            logger.warning("DeepFilterNet3 processing failed: %s", e)
            return None

    @staticmethod
    def apply_highpass_filter(y: np.ndarray, sr: int, cutoff_freq: float = 80.0) -> np.ndarray:
        # Filter out low-frequency rumble (wind noise)
        try:
            from scipy.signal import butter, filtfilt
            nyq = 0.5 * sr
            normal_cutoff = cutoff_freq / nyq
            b, a = butter(4, normal_cutoff, btype='high', analog=False)
            y_filtered = filtfilt(b, a, y)
            return y_filtered
        except ImportError:
            return y

    @staticmethod
    def normalize_loudness(y: np.ndarray, sr: int, target_dbfs: float = -16.0) -> np.ndarray:
        rms = np.sqrt(np.mean(y ** 2))
        if rms > 1e-8:
            target_rms = 10 ** (target_dbfs / 20)
            y = y * (target_rms / rms)
            y = np.clip(y, -1.0, 1.0)
        return y

    @staticmethod
    def needs_noise_reduction(y: np.ndarray, sr: int, silence_threshold_pct: float = 10.0) -> bool:
        import librosa
        rms = librosa.feature.rms(y=y)[0]
        silence_frames = np.sum(rms < np.percentile(rms, 20))
        silence_pct = silence_frames / len(rms) * 100
        return silence_pct > silence_threshold_pct

    def preprocess(self, audio_path: str) -> str:
        if not WHISPER_AUDIO_PREPROCESS:
            return audio_path
        import librosa
        import soundfile as sf
        base, ext = os.path.splitext(audio_path)
        out_path = f"{base}_enhanced.wav"
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        y = self.trim_silence(y, sr)
        y = self.normalize_loudness(y, sr)
        y = self.apply_highpass_filter(y, sr)
        should_reduce = (
            WHISPER_NOISE_REDUCE_METHOD == "deepfilter"
            or self.needs_noise_reduction(y, sr)
        )
        if should_reduce:
            logger.info("Applying noise reduction method=%s strength=%.2f",
                        WHISPER_NOISE_REDUCE_METHOD, WHISPER_NOISE_REDUCE_STRENGTH)
            y = self.reduce_noise(y, sr, strength=WHISPER_NOISE_REDUCE_STRENGTH)
        sf.write(out_path, y, sr)
        return out_path


# ---------------------------------------------------------------------------
# Hallucination detection
# ---------------------------------------------------------------------------

_HALLUCINATION_COMPRESSION_RATIO_MAX = 2.0
_HALLUCINATION_NO_SPEECH_PROB_MAX = 0.5
_HALLUCINATION_AVG_LOGPROB_MIN = -1.0


def _is_hallucinated_segment(seg) -> bool:
    if hasattr(seg, 'no_speech_prob') and seg.no_speech_prob > _HALLUCINATION_NO_SPEECH_PROB_MAX:
        return True
    if hasattr(seg, 'compression_ratio') and seg.compression_ratio > _HALLUCINATION_COMPRESSION_RATIO_MAX:
        return True
    if hasattr(seg, 'avg_logprob') and seg.avg_logprob < _HALLUCINATION_AVG_LOGPROB_MIN:
        return True
    return False


# ---------------------------------------------------------------------------
# Confidence tier classifier
# ---------------------------------------------------------------------------

_CONFIDENCE_TIER_THRESHOLDS = [
    (0.9, "high"),
    (0.7, "medium"),
    (0.5, "low"),
]


def _classify_confidence_tier(confidence: float) -> str:
    for threshold, tier in _CONFIDENCE_TIER_THRESHOLDS:
        if confidence >= threshold:
            return tier
    return "uncertain"


# ---------------------------------------------------------------------------
# Forced alignment (optional — requires transformers)
# ---------------------------------------------------------------------------

def _has_transformers() -> bool:
    try:
        import transformers
        return True
    except ImportError:
        return False


_alignment_pipeline = None
_alignment_lock = threading.Lock()


def _get_alignment_pipeline():
    global _alignment_pipeline
    if _alignment_pipeline is None:
        with _alignment_lock:
            if _alignment_pipeline is None:
                try:
                    from transformers import pipeline, Pipeline
                    _alignment_pipeline = pipeline(
                        "automatic-speech-recognition",
                        "facebook/wav2vec2-large-960h-lv60-self",
                    )
                    logger.info("Loaded wav2vec2 alignment model")
                except Exception as e:
                    logger.warning("Failed to load alignment model: %s", e)
                    _alignment_pipeline = False
    return _alignment_pipeline if _alignment_pipeline is not False else None


def _align_words_with_wav2vec2(audio: np.ndarray, segments: List[TranscriptSegment], sr: int = 16000) -> List[TranscriptSegment]:
    aligner = _get_alignment_pipeline()
    if aligner is None:
        return segments

    try:
        full_text = " ".join(s.text for s in segments)
        result = aligner(audio, return_timestamps="word", chunk_length_s=30)
        word_chunks = result.get("chunks", [])

        word_index = 0
        for seg in segments:
            aligned_words = []
            for chunk in word_chunks:
                w_start, w_end = chunk.get("timestamp", (None, None))
                if w_start is None or w_end is None:
                    continue
                w_text = chunk.get("text", "").strip()
                if not w_text:
                    continue
                aligned_words.append(WordTimestamp(
                    word=w_text, start=w_start, end=w_end,
                    probability=seg.words[word_index].probability if word_index < len(seg.words) else 0.0,
                ))
                word_index += 1
            seg.words = aligned_words

        logger.info("Forced alignment applied to %d segments", len(segments))
    except Exception as e:
        logger.warning("Forced alignment failed: %s", e)

    return segments


# ---------------------------------------------------------------------------
# Speaker diarization (optional — requires pyannote.audio)
# ---------------------------------------------------------------------------

def _has_pyannote() -> bool:
    try:
        import pyannote.audio
        return True
    except ImportError:
        return False


_diarization_pipeline = None
_diarization_lock = threading.Lock()


def _get_diarization_pipeline():
    global _diarization_pipeline
    if _diarization_pipeline is None:
        with _diarization_lock:
            if _diarization_pipeline is None:
                try:
                    from pyannote.audio import Pipeline
                    _diarization_pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        use_auth_token=None,
                    )
                    logger.info("Loaded pyannote speaker diarization pipeline")
                except Exception as e:
                    logger.warning("Failed to load diarization pipeline: %s", e)
                    _diarization_pipeline = False
    return _diarization_pipeline if _diarization_pipeline is not False else None


def _apply_diarization(audio_path: str, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
    pipeline = _get_diarization_pipeline()
    if pipeline is None:
        return segments

    try:
        diarization = pipeline(audio_path)
        speaker_map = {}
        for seg in segments:
            mid = (seg.start + seg.end) / 2
            speaker = diarization.crop(mid)
            if speaker:
                label = list(speaker.labels())[0]
                seg.speaker = label
                for w in seg.words:
                    w.speaker = label
        logger.info("Speaker diarization applied to %d segments", len(segments))
    except Exception as e:
        logger.warning("Speaker diarization failed: %s", e)

    return segments


# ---------------------------------------------------------------------------
# Main transcriber
# ---------------------------------------------------------------------------

class BodyCamTranscriber:
    def __init__(
        self,
        model_size: str = WHISPER_MODEL_SIZE,
        device: str = WHISPER_DEVICE,
        compute_type: str = WHISPER_COMPUTE_TYPE,
        cpu_threads: int = WHISPER_CPU_THREADS,
        batch_size: int = WHISPER_BATCH_SIZE,
        beam_size: int = WHISPER_BEAM_SIZE,
        use_batched: bool = True,
        enable_alignment: bool = True,
        enable_diarization: bool = True,
        language: str = WHISPER_LANGUAGE,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.batch_size = batch_size
        self.beam_size = beam_size
        self.use_batched = use_batched
        self.enable_alignment = enable_alignment
        self.enable_diarization = enable_diarization
        self.language = language
        self.model = None
        self._batched_pipeline = None
        self._model_lock = threading.Lock()
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def _check_cancelled(self):
        if self._cancel_event.is_set():
            raise InterruptedError("Transcription cancelled")

    def reset_cancel(self):
        self._cancel_event.clear()

    def load_model(self):
        if self.model is None:
            with self._model_lock:
                if self.model is None:
                    try:
                        self.model = WhisperModel(
                            self.model_size,
                            device=self.device,
                            compute_type=self.compute_type,
                            cpu_threads=self.cpu_threads,
                        )
                        logger.info(
                            "Loaded Whisper model: %s (device=%s, compute=%s, batch=%d, beam=%d)",
                            self.model_size, self.device, self.compute_type,
                            self.batch_size, self.beam_size,
                        )
                        if self.use_batched:
                            try:
                                from faster_whisper import BatchedInferencePipeline
                                self._batched_pipeline = BatchedInferencePipeline(
                                    model=self.model, use_vad_model=True,
                                )
                                logger.info("BatchedInferencePipeline enabled for 4x throughput")
                            except Exception as e:
                                logger.warning("Failed to init BatchedInferencePipeline: %s", e)
                                self._batched_pipeline = None
                    except Exception as e:
                        logger.error("Failed to load Whisper model %s on %s: %s",
                                     self.model_size, self.device, e)
                        raise
        return self.model

    def clear_vram(self):
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _build_initial_prompt(self, file_path: str, base_prompt: Optional[str]) -> str:
        prompt = base_prompt or WHISPER_INITIAL_PROMPT

        if WHISPER_TWO_PASS_ENABLED:
            try:
                quick_model = WhisperModel(
                    WHISPER_TWO_PASS_QUICK_MODEL,
                    device=self.device,
                    compute_type="int8",
                    cpu_threads=self.cpu_threads,
                )
                quick_segments, _ = quick_model.transcribe(
                    file_path, language="en", vad_filter=True,
                    beam_size=1, batch_size=1,
                )
                rough_text = " ".join(seg.text.strip() for seg in quick_segments)

                from transcript_corrector import extract_domain_terms
                terms = extract_domain_terms(rough_text)
                if terms:
                    enriched = f"{prompt}. Key terms from audio: {terms}."
                    logger.info("Two-pass: enriched prompt with %d chars of domain terms", len(terms))
                    prompt = enriched

                del quick_model
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            except Exception as e:
                logger.warning("Two-pass term extraction failed: %s", e)

        return prompt

    @staticmethod
    def _segments_from_raw(raw_segments) -> Tuple[List[TranscriptSegment], int, int]:
        segments = []
        hallucinated_count = 0
        total_words = 0
        for segment in raw_segments:
            if _is_hallucinated_segment(segment):
                hallucinated_count += 1
                continue
            word_list = []
            word_timestamps_raw = getattr(segment, 'words', None)
            if word_timestamps_raw:
                for w in word_timestamps_raw:
                    word_list.append(WordTimestamp(
                        word=w.word, start=w.start, end=w.end,
                        probability=getattr(w, 'probability', 0.0),
                    ))
                    total_words += 1
            segments.append(TranscriptSegment(
                start=segment.start, end=segment.end, text=segment.text.strip(),
                no_speech_prob=getattr(segment, 'no_speech_prob', 0.0),
                compression_ratio=getattr(segment, 'compression_ratio', 0.0),
                avg_logprob=getattr(segment, 'avg_logprob', 0.0),
                words=word_list,
            ))
        return segments, hallucinated_count, total_words

    def _transcribe_sequential(
        self,
        audio_input,
        language: str,
        vad_filter: bool,
        vad_params: dict,
        enriched_prompt: str,
        progress_callback: Optional[Callable[[int, int], None]],
        chunk_index: int = 0,
        total_chunks: int = 1,
    ):
        model = self.load_model()
        self._check_cancelled()

        segments_raw, info = model.transcribe(
            audio_input,
            language=language,
            vad_filter=vad_filter,
            vad_parameters=vad_params,
            beam_size=self.beam_size,
            batch_size=self.batch_size,
            initial_prompt=enriched_prompt,
            condition_on_previous_text=True,
            word_timestamps=WHISPER_WORD_TIMESTAMPS,
            no_speech_threshold=_HALLUCINATION_NO_SPEECH_PROB_MAX,
            compression_ratio_threshold=_HALLUCINATION_COMPRESSION_RATIO_MAX,
            logprob_threshold=_HALLUCINATION_AVG_LOGPROB_MIN,
        )

        segments, hallucinated_count, total_words = self._segments_from_raw(segments_raw)
        self._assign_confidence_tiers(segments)

        if hallucinated_count > 0:
            logger.info("Chunk %d: filtered %d hallucinated segments", chunk_index, hallucinated_count)
        if progress_callback and total_chunks > 1:
            progress_callback(chunk_index + 1, total_chunks)
        return segments, info

    def _transcribe_batched(
        self,
        audio: np.ndarray,
        language: str,
        enriched_prompt: str,
        progress_callback: Optional[Callable[[int, int], None]],
    ):
        model = self.load_model()
        self._check_cancelled()

        if self._batched_pipeline is None:
            raise RuntimeError("BatchedInferencePipeline not initialized")

        segments_raw, info = self._batched_pipeline.transcribe(
            audio,
            batch_size=self.batch_size,
            beam_size=self.beam_size,
            language=language,
            initial_prompt=enriched_prompt,
            word_timestamps=WHISPER_WORD_TIMESTAMPS,
            no_speech_threshold=_HALLUCINATION_NO_SPEECH_PROB_MAX,
            compression_ratio_threshold=_HALLUCINATION_COMPRESSION_RATIO_MAX,
            logprob_threshold=_HALLUCINATION_AVG_LOGPROB_MIN,
        )

        segments, hallucinated_count, total_words = self._segments_from_raw(segments_raw)
        self._assign_confidence_tiers(segments)

        if hallucinated_count > 0:
            logger.info("Filtered %d hallucinated segments", hallucinated_count)
        logger.info("Batched transcription: %d segments (%d words)", len(segments), total_words)

        if progress_callback:
            progress_callback(1, 1)

        return segments, info

    @staticmethod
    def _assign_confidence_tiers(segments: List[TranscriptSegment]):
        for seg in segments:
            seg.confidence_tier = _classify_confidence_tier(seg.confidence)

    def transcribe_file(
        self,
        file_path: str,
        language: str = WHISPER_LANGUAGE,
        vad_filter: bool = True,
        initial_prompt: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[TranscriptSegment]:
        self.reset_cancel()
        self.load_model()

        if any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS):
            extracted = extract_audio_from_video(file_path)
            if extracted is None:
                raise RuntimeError(
                    "Could not extract audio from video file. "
                    "Ensure ffmpeg is installed and available in PATH."
                )
            file_path = extracted
            cleanup_video_audio = True
        else:
            cleanup_video_audio = False

        preprocessor = AudioPreprocessor()
        processed_path = preprocessor.preprocess(file_path)
        enriched_prompt = self._build_initial_prompt(file_path, initial_prompt)

        try:
            use_batched = (
                self.use_batched
                and self._batched_pipeline is not None
            )

            audio_y = None
            if use_batched:
                import librosa
                import soundfile as sf
                audio_y, audio_sr = librosa.load(processed_path, sr=16000, mono=True)
                segments, info = self._transcribe_batched(
                    audio_y, language, enriched_prompt, progress_callback,
                )
            else:
                vad_params = dict(
                    threshold=WHISPER_VAD_THRESHOLD,
                    min_speech_duration_ms=WHISPER_VAD_MIN_SPEECH_MS,
                    min_silence_duration_ms=WHISPER_VAD_MIN_SILENCE_MS,
                    speech_pad_ms=WHISPER_VAD_SPEECH_PAD_MS,
                )
                segments, info = self._transcribe_sequential(
                    processed_path, language, vad_filter, vad_params,
                    enriched_prompt, progress_callback, 0, 1,
                )

            if self.enable_alignment and _has_transformers():
                try:
                    if audio_y is None:
                        import librosa
                        audio_y, audio_sr = librosa.load(processed_path, sr=16000, mono=True)
                    segments = _align_words_with_wav2vec2(audio_y, segments)
                except Exception as e:
                    logger.warning("Alignment skipped: %s", e)

            if self.enable_diarization and _has_pyannote():
                try:
                    segments = _apply_diarization(processed_path, segments)
                except Exception as e:
                    logger.warning("Diarization skipped: %s", e)

            if progress_callback:
                progress_callback(1, 1)

            total_words = sum(len(s.words) for s in segments)
            avg_confidence = 0.0
            low_conf_count = 0
            if segments:
                avg_confidence = sum(s.confidence for s in segments) / len(segments)
                low_conf_count = sum(1 for s in segments if s.is_low_confidence)

            logger.info(
                "Transcribed %s: %d segments (%d words), confidence=%.2f, low-conf=%d",
                os.path.basename(file_path), len(segments), total_words,
                avg_confidence, low_conf_count,
            )
            return segments

        finally:
            if processed_path and processed_path != file_path and os.path.exists(processed_path):
                try:
                    os.remove(processed_path)
                except Exception:
                    pass
            if cleanup_video_audio and file_path != processed_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

    def format_timestamp(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def format_timestamp_precise(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:05.2f}"

    def format_transcript(self, segments: List[TranscriptSegment]) -> str:
        lines = []
        total_confidence = 0.0
        low_conf_count = 0
        for seg in segments:
            start_ts = self.format_timestamp(seg.start)
            end_ts = self.format_timestamp(seg.end)
            total_confidence += seg.confidence
            speaker_tag = f"<{seg.speaker}> " if seg.speaker else ""
            conf_marker = " [?]" if seg.is_low_confidence else ""
            if seg.is_low_confidence:
                low_conf_count += 1

            if WHISPER_WORD_TIMESTAMPS and seg.words:
                word_detail = " ".join(w.format() for w in seg.words)
                lines.append(f"[{start_ts} -> {end_ts}] {speaker_tag}{seg.text}{conf_marker}")
                lines.append(f"  \u23f1 {word_detail}")
            else:
                lines.append(f"[{start_ts} -> {end_ts}] {speaker_tag}{seg.text}{conf_marker}")

        if segments:
            avg_conf = total_confidence / len(segments)
            total_secs = segments[-1].end - segments[0].start if segments else 0
            lines.append("")
            lines.append(
                f"[METADATA] segments={len(segments)} "
                f"duration={total_secs:.0f}s "
                f"confidence={avg_conf:.2f} "
                f"low_confidence={low_conf_count}"
            )

        result = "\n".join(lines)

        if WHISPER_TRANSCRIPT_CORRECTOR_ENABLED:
            try:
                from transcript_corrector import correct_transcript
                corrected = correct_transcript(result)
                if corrected and corrected != result:
                    result = corrected + "\n\n[NOTE: Corrected by LE domain ASR corrector]"
            except Exception as e:
                logger.warning("Transcript corrector unavailable: %s", e)

        return result

    def transcribe_to_text(
        self,
        file_path: str,
        language: str = WHISPER_LANGUAGE,
        vad_filter: bool = True,
        initial_prompt: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        segments = self.transcribe_file(file_path, language, vad_filter, initial_prompt, progress_callback)
        return self.format_transcript(segments)


# ---------------------------------------------------------------------------
# Module-level API
# ---------------------------------------------------------------------------

transcriber_instance = None
_transcriber_lock = threading.Lock()


def get_transcriber(language: str = WHISPER_LANGUAGE, **kwargs) -> BodyCamTranscriber:
    global transcriber_instance
    if transcriber_instance is None:
        with _transcriber_lock:
            if transcriber_instance is None:
                transcriber_instance = BodyCamTranscriber(language=language, **kwargs)
    return transcriber_instance


def transcribe_bodycam(
    file_path: str,
    language: str = WHISPER_LANGUAGE,
    vad_filter: bool = True,
    initial_prompt: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    transcriber = get_transcriber()
    return transcriber.transcribe_to_text(file_path, language, vad_filter, initial_prompt, progress_callback)


def cancel_transcription() -> bool:
    global transcriber_instance
    if transcriber_instance is not None:
        transcriber_instance.cancel()
        return True
    return False


def cleanup_transcriber():
    global transcriber_instance
    if transcriber_instance is not None:
        model = transcriber_instance.model
        if model is not None:
            del model
        transcriber_instance.model = None
        transcriber_instance._batched_pipeline = None
        transcriber_instance.clear_vram()
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        transcriber_instance = None


def preprocess_audio_only(audio_path: str) -> str:
    preprocessor = AudioPreprocessor()
    return preprocessor.preprocess(audio_path)


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        if os.path.exists(video_path):
            print(f"Transcribing: {video_path}")
            prompt = sys.argv[2] if len(sys.argv) > 2 else None
            transcript = transcribe_bodycam(video_path, initial_prompt=prompt)
            print("\n" + transcript)
            cleanup_transcriber()
        else:
            print(f"File not found: {video_path}")
    else:
        print("Usage: python transcriber.py <path_to_video> [initial_prompt]")
