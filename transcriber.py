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


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    probability: float = 0.0

    def format(self) -> str:
        return f"{self.word}[{self.start:.2f}-{self.end:.2f}]"


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    no_speech_prob: float = 0.0
    compression_ratio: float = 0.0
    avg_logprob: float = 0.0
    words: List[WordTimestamp] = None

    def __post_init__(self):
        if self.words is None:
            self.words = []

    @property
    def confidence(self) -> float:
        probs = [w.probability for w in self.words if w.probability > 0]
        if probs:
            return sum(probs) / len(probs)
        return max(0.0, 1.0 - self.no_speech_prob)


class AudioPreprocessor:
    @staticmethod
    def trim_silence(y: np.ndarray, sr: int, top_db: int = 30) -> np.ndarray:
        import librosa
        y_trimmed, _ = librosa.effects.trim(y, top_db=top_db)
        return y_trimmed

    @staticmethod
    def reduce_noise(y: np.ndarray, sr: int, strength: float = 0.75) -> np.ndarray:
        if WHISPER_NOISE_REDUCE_METHOD == "deepfilter":
            return AudioPreprocessor.reduce_noise_deepfilter(y, sr)
        try:
            import noisereduce as nr
            y_denoised = nr.reduce_noise(
                y=y,
                sr=sr,
                stationary=True,
                prop_decrease=strength,
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
                logger.warning("deepfilter-stream not installed, falling back to noisereduce")
                return None
            except Exception as e:
                logger.warning("Failed to load DeepFilterNet3 model: %s", e)
                return None
        return AudioPreprocessor._deepfilter_model

    @staticmethod
    def reduce_noise_deepfilter(y: np.ndarray, sr: int) -> np.ndarray:
        model = AudioPreprocessor._get_deepfilter_model()
        if model is None:
            return y
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
            logger.warning("DeepFilterNet3 processing failed: %s, falling back to original audio", e)
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


_HALLUCINATION_COMPRESSION_RATIO_MAX = 2.0
_HALLUCINATION_NO_SPEECH_PROB_MAX = 0.5
_HALLUCINATION_AVG_LOGPROB_MIN = -1.0

_MAX_CHUNK_DURATION_SECONDS = 1800


def _is_hallucinated_segment(seg) -> bool:
    if hasattr(seg, 'no_speech_prob') and seg.no_speech_prob > _HALLUCINATION_NO_SPEECH_PROB_MAX:
        return True
    if hasattr(seg, 'compression_ratio') and seg.compression_ratio > _HALLUCINATION_COMPRESSION_RATIO_MAX:
        return True
    if hasattr(seg, 'avg_logprob') and seg.avg_logprob < _HALLUCINATION_AVG_LOGPROB_MIN:
        return True
    return False


def _get_audio_duration(audio_path: str) -> float:
    import librosa
    try:
        dur = librosa.get_duration(filename=audio_path)
        return dur
    except Exception:
        return 0.0


def _split_audio_chunks(audio_path: str, max_duration: int = _MAX_CHUNK_DURATION_SECONDS) -> List[str]:
    import librosa
    import soundfile as sf
    y, sr = librosa.load(audio_path, sr=16000, mono=True)
    total_samples = len(y)
    chunk_samples = max_duration * sr
    if total_samples <= chunk_samples:
        return [audio_path]

    base, ext = os.path.splitext(audio_path)
    chunks = []
    for start_sample in range(0, total_samples, chunk_samples):
        end_sample = min(start_sample + chunk_samples, total_samples)
        chunk_y = y[start_sample:end_sample]
        chunk_path = f"{base}_chunk_{start_sample // chunk_samples}.wav"
        sf.write(chunk_path, chunk_y, sr)
        chunks.append(chunk_path)
    logger.info("Split audio into %d chunks (max %ds each)", len(chunks), max_duration)
    return chunks


class BodyCamTranscriber:
    def __init__(
        self,
        model_size: str = WHISPER_MODEL_SIZE,
        device: str = WHISPER_DEVICE,
        compute_type: str = WHISPER_COMPUTE_TYPE,
        cpu_threads: int = WHISPER_CPU_THREADS,
        batch_size: int = WHISPER_BATCH_SIZE,
        beam_size: int = WHISPER_BEAM_SIZE,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.batch_size = batch_size
        self.beam_size = beam_size
        self.model = None
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

    def _transcribe_single(
        self,
        audio_path: str,
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
            audio_path,
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

        segments = []
        hallucinated_count = 0
        for segment in segments_raw:
            self._check_cancelled()
            if _is_hallucinated_segment(segment):
                hallucinated_count += 1
                continue
            word_list = []
            word_timestamps_raw = getattr(segment, 'words', None)
            if word_timestamps_raw:
                for w in word_timestamps_raw:
                    word_list.append(WordTimestamp(
                        word=w.word,
                        start=w.start,
                        end=w.end,
                        probability=getattr(w, 'probability', 0.0),
                    ))
            segments.append(TranscriptSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text.strip(),
                no_speech_prob=getattr(segment, 'no_speech_prob', 0.0),
                compression_ratio=getattr(segment, 'compression_ratio', 0.0),
                avg_logprob=getattr(segment, 'avg_logprob', 0.0),
                words=word_list,
            ))

        if hallucinated_count > 0:
            logger.info("Chunk %d: filtered %d hallucinated segments", chunk_index, hallucinated_count)

        if progress_callback and total_chunks > 1:
            progress_callback(chunk_index + 1, total_chunks)

        return segments, info

    def transcribe_file(
        self,
        file_path: str,
        language: str = "en",
        vad_filter: bool = True,
        initial_prompt: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[TranscriptSegment]:
        self.reset_cancel()
        model = self.load_model()

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

        duration = _get_audio_duration(processed_path)
        needs_chunking = duration > _MAX_CHUNK_DURATION_SECONDS

        try:
            vad_params = dict(
                threshold=WHISPER_VAD_THRESHOLD,
                min_speech_duration_ms=WHISPER_VAD_MIN_SPEECH_MS,
                min_silence_duration_ms=WHISPER_VAD_MIN_SILENCE_MS,
                speech_pad_ms=WHISPER_VAD_SPEECH_PAD_MS,
            )

            if needs_chunking:
                chunks = _split_audio_chunks(processed_path)
                all_segments = []
                total_chunks = len(chunks)
                cumulative_end = 0.0
                for i, chunk_path in enumerate(chunks):
                    logger.info("Transcribing chunk %d/%d", i + 1, total_chunks)
                    chunk_segments, info = self._transcribe_single(
                        chunk_path, language, vad_filter, vad_params,
                        enriched_prompt, progress_callback, i, total_chunks,
                    )
                    for seg in chunk_segments:
                        seg.start += cumulative_end
                        seg.end += cumulative_end
                    all_segments.extend(chunk_segments)
                    cumulative_end = all_segments[-1].end if all_segments else cumulative_end
                    if chunk_path != processed_path and os.path.exists(chunk_path):
                        try:
                            os.remove(chunk_path)
                        except Exception:
                            pass
                segments = all_segments
            else:
                segments, info = self._transcribe_single(
                    processed_path, language, vad_filter, vad_params,
                    enriched_prompt, progress_callback, 0, 1,
                )

            if progress_callback and not needs_chunking:
                progress_callback(1, 1)

            total_words = sum(len(s.words) for s in segments)
            avg_confidence = 0.0
            if segments:
                avg_confidence = sum(s.confidence for s in segments) / len(segments)

            logger.info(
                "Transcribed %s: %d segments (%d words), confidence=%.2f",
                os.path.basename(file_path), len(segments), total_words,
                avg_confidence,
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
        for seg in segments:
            start_ts = self.format_timestamp(seg.start)
            end_ts = self.format_timestamp(seg.end)
            total_confidence += seg.confidence

            if WHISPER_WORD_TIMESTAMPS and seg.words:
                word_detail = " ".join(w.format() for w in seg.words)
                lines.append(f"[{start_ts} -> {end_ts}] {seg.text}")
                lines.append(f"  ⏱ {word_detail}")
            else:
                lines.append(f"[{start_ts} -> {end_ts}] {seg.text}")

        if segments:
            avg_conf = total_confidence / len(segments)
            total_secs = segments[-1].end - segments[0].start if segments else 0
            lines.append("")
            lines.append(f"[METADATA] segments={len(segments)} duration={total_secs:.0f}s confidence={avg_conf:.2f}")

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
        language: str = "en",
        vad_filter: bool = True,
        initial_prompt: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        segments = self.transcribe_file(file_path, language, vad_filter, initial_prompt, progress_callback)
        return self.format_transcript(segments)


transcriber_instance = None
_transcriber_lock = threading.Lock()


def get_transcriber() -> BodyCamTranscriber:
    global transcriber_instance
    if transcriber_instance is None:
        with _transcriber_lock:
            if transcriber_instance is None:
                transcriber_instance = BodyCamTranscriber()
    return transcriber_instance


def transcribe_bodycam(
    file_path: str,
    language: str = "en",
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
