import os
import gc
import threading
import torch
from faster_whisper import WhisperModel
from typing import List, Dict, Optional
from dataclasses import dataclass
from config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_CPU_THREADS, WHISPER_VAD_MIN_SILENCE_MS, WHISPER_VAD_SPEECH_PAD_MS
from logger import get_logger

logger = get_logger(__name__)


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


class BodyCamTranscriber:
    def __init__(
        self,
        model_size: str = WHISPER_MODEL_SIZE,
        device: str = WHISPER_DEVICE,
        compute_type: str = WHISPER_COMPUTE_TYPE,
        cpu_threads: int = WHISPER_CPU_THREADS
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.model = None
        self._model_lock = threading.Lock()
    
    def load_model(self):
        if self.model is None:
            with self._model_lock:
                if self.model is None:
                    try:
                        self.model = WhisperModel(
                            self.model_size,
                            device=self.device,
                            compute_type=self.compute_type,
                            cpu_threads=self.cpu_threads
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
    
    def transcribe_file(
        self,
        file_path: str,
        language: str = "en",
        vad_filter: bool = True
    ) -> List[TranscriptSegment]:
        model = self.load_model()
        
        segments_raw, info = model.transcribe(
            file_path,
            language=language,
            vad_filter=vad_filter,
            vad_parameters=dict(
                min_silence_duration_ms=WHISPER_VAD_MIN_SILENCE_MS,
                speech_pad_ms=WHISPER_VAD_SPEECH_PAD_MS
            )
        )
        
        segments = []
        for segment in segments_raw:
            segments.append(TranscriptSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text.strip()
            ))
        
        return segments
    
    def format_timestamp(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def format_transcript(self, segments: List[TranscriptSegment]) -> str:
        lines = []
        for seg in segments:
            start_ts = self.format_timestamp(seg.start)
            end_ts = self.format_timestamp(seg.end)
            lines.append(f"[{start_ts} -> {end_ts}] {seg.text}")
        return "\n".join(lines)
    
    def transcribe_to_text(
        self,
        file_path: str,
        language: str = "en",
        vad_filter: bool = True
    ) -> str:
        segments = self.transcribe_file(file_path, language, vad_filter)
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


def transcribe_bodycam(file_path: str, language: str = "en", vad_filter: bool = True) -> str:
    transcriber = get_transcriber()
    return transcriber.transcribe_to_text(file_path, language, vad_filter)


def transcribe_bodycam_segments(file_path: str, language: str = "en", vad_filter: bool = True) -> List[TranscriptSegment]:
    transcriber = get_transcriber()
    return transcriber.transcribe_file(file_path, language, vad_filter)


def cleanup_transcriber():
    global transcriber_instance
    if transcriber_instance is not None:
        transcriber_instance.clear_vram()
        transcriber_instance = None


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        if os.path.exists(video_path):
            print(f"Transcribing: {video_path}")
            transcript = transcribe_bodycam(video_path)
            print("\n" + transcript)
            cleanup_transcriber()
        else:
            print(f"File not found: {video_path}")
    else:
        print("Usage: python transcriber.py <path_to_video>")
