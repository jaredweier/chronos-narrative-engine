import os
import torch

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _env(key: str, default: str) -> str:
    return os.environ.get(f"CHRONOS_{key}", default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(f"CHRONOS_{key}", str(default)))
    except (ValueError, TypeError):
        return default


def _detect_device() -> str:
    if _env("WHISPER_DEVICE", ""):
        return _env("WHISPER_DEVICE", "cuda")
    if torch.cuda.is_available():
        return "cuda"
    try:
        if torch.backends.mps.is_available():
            return "mps"
    except AttributeError:
        pass
    return "cpu"


def _detect_compute_type(device: str) -> str:
    env_val = _env("WHISPER_COMPUTE_TYPE", "")
    if env_val:
        return env_val
    if device == "cuda":
        return "float16"
    return "int8"


# --- Ollama ---
OLLAMA_BASE_URL = _env("OLLAMA_URL", "http://localhost:11434")
OLLAMA_API_ENDPOINT = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_MODEL = _env("OLLAMA_MODEL", "llama3.1:8b")

# --- LLM defaults ---
LLM_DEFAULTS = {
    "temperature": _env_int("LLM_TEMPERATURE", 30) / 100,
    "num_predict": _env_int("LLM_MAX_TOKENS", 2048),
    "top_p": _env_int("LLM_TOP_P", 90) / 100,
}

LLM_COMPLIANCE_OPTIONS = {
    "temperature": 0.0,
    "num_predict": _env_int("LLM_COMPLIANCE_TOKENS", 1024),
}

LLM_NARRATIVE_TIMEOUT = _env_int("LLM_NARRATIVE_TIMEOUT", 120)
LLM_COMPLIANCE_TIMEOUT = _env_int("LLM_COMPLIANCE_TIMEOUT", 60)

# --- Whisper ---
_detected_device = _detect_device()
_detected_compute = _detect_compute_type(_detected_device)

WHISPER_MODEL_SIZE = _env("WHISPER_MODEL", "small")
WHISPER_DEVICE = _detected_device
WHISPER_COMPUTE_TYPE = _detected_compute
WHISPER_CPU_THREADS = _env_int("WHISPER_CPU_THREADS", 4)
WHISPER_VAD_MIN_SILENCE_MS = _env_int("WHISPER_VAD_SILENCE_MS", 500)
WHISPER_VAD_SPEECH_PAD_MS = _env_int("WHISPER_VAD_SPEECH_PAD_MS", 200)

# --- Limits ---
MAX_STYLE_EXAMPLES = _env_int("MAX_STYLE_EXAMPLES", 5)
MAX_TRANSCRIPT_CHARS = _env_int("MAX_TRANSCRIPT_CHARS", 4000)
MAX_STYLE_EXAMPLE_CHARS = _env_int("MAX_STYLE_EXAMPLE_CHARS", 1500)
MAX_CAD_TEXT_CHARS = _env_int("MAX_CAD_TEXT_CHARS", 8000)

# --- Paths ---
TEMP_DIR = os.path.join(BASE_DIR, _env("TEMP_DIR", "temp_processing"))
COMPLETED_DIR = os.path.join(BASE_DIR, _env("COMPLETED_DIR", "completed_reports"))
PROFILES_DIR = os.path.join(BASE_DIR, _env("PROFILES_DIR", "officer_profiles"))
DB_PATH = os.path.join(BASE_DIR, _env("DB_FILENAME", "department_reports.db"))
CUSTOM_CATEGORIES_FILE = os.path.join(BASE_DIR, _env("CATEGORIES_FILE", "custom_categories.txt"))

# --- Upload ---
MAX_UPLOAD_SIZE_GB = _env_int("MAX_UPLOAD_GB", 4)
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_GB * 1024 * 1024 * 1024

# --- Pipeline ---
PIPELINE_MAX_WORKERS = _env_int("PIPELINE_WORKERS", 2)

# --- Database ---
DB_TIMEOUT = _env_int("DB_TIMEOUT", 30)
