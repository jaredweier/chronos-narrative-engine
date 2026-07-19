from typing import Optional, Callable
from providers.base import TranscriberProvider


class WhisperTranscriberProvider(TranscriberProvider):
    def __init__(self):
        self._transcriber = None

    def _get(self):
        if self._transcriber is None:
            from transcriber import get_transcriber
            self._transcriber = get_transcriber()
        return self._transcriber

    def transcribe(self, audio_path: str, language: str = "en", initial_prompt: Optional[str] = None, progress_callback: Optional[Callable[[int, int], None]] = None) -> str:
        return self._get().transcribe_to_text(audio_path, language, initial_prompt=initial_prompt, progress_callback=progress_callback)

    def cancel(self):
        if self._transcriber is not None:
            self._transcriber.cancel()

    def cleanup(self):
        if self._transcriber is not None:
            from transcriber import cleanup_transcriber
            cleanup_transcriber()
            self._transcriber = None
