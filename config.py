import os
try:
    import torch
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False

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
    if _HAS_TORCH:
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

WHISPER_MODEL_SIZE = _env("WHISPER_MODEL", "large-v3-turbo")
WHISPER_DEVICE = _detected_device
WHISPER_COMPUTE_TYPE = _detected_compute
WHISPER_CPU_THREADS = _env_int("WHISPER_CPU_THREADS", 4)
WHISPER_BATCH_SIZE = _env_int("WHISPER_BATCH_SIZE", 4)
WHISPER_BEAM_SIZE = _env_int("WHISPER_BEAM_SIZE", 5)
WHISPER_VAD_MIN_SILENCE_MS = _env_int("WHISPER_VAD_SILENCE_MS", 300)
WHISPER_VAD_SPEECH_PAD_MS = _env_int("WHISPER_VAD_SPEECH_PAD_MS", 300)
WHISPER_VAD_THRESHOLD = _env_int("WHISPER_VAD_THRESHOLD", 30) / 100
WHISPER_VAD_MIN_SPEECH_MS = _env_int("WHISPER_VAD_MIN_SPEECH_MS", 200)
WHISPER_AUDIO_PREPROCESS = _env("WHISPER_AUDIO_PREPROCESS", "true").lower() == "true"
WHISPER_INITIAL_PROMPT = _env("WHISPER_INITIAL_PROMPT", "The following is a law enforcement body camera recording. Officer, dispatch, suspect, traffic stop, investigation, patrol, squad, domestic, battery, OWI, PBT, Miranda.")
WHISPER_NOISE_REDUCE_STRENGTH = _env_int("WHISPER_NOISE_REDUCE_STRENGTH", 75) / 100
WHISPER_NOISE_REDUCE_METHOD = _env("WHISPER_NOISE_METHOD", "noisereduce")
WHISPER_DEEPFILTER_ATTEN_LIM_DB = _env_int("WHISPER_DEEPFILTER_ATTEN", -1)
WHISPER_WORD_TIMESTAMPS = _env("WHISPER_WORD_TIMESTAMPS", "true").lower() == "true"
WHISPER_TRANSCRIPT_CORRECTOR_ENABLED = _env("WHISPER_TRANSCRIPT_CORRECTOR", "true").lower() == "true"
WHISPER_TWO_PASS_ENABLED = _env("WHISPER_TWO_PASS", "false").lower() == "true"
WHISPER_TWO_PASS_QUICK_MODEL = _env("WHISPER_TWO_PASS_QUICK_MODEL", "base")

# --- Advanced transcription features ---
WHISPER_USE_BATCHED = _env("WHISPER_USE_BATCHED", "true").lower() == "true"
WHISPER_ENABLE_ALIGNMENT = _env("WHISPER_ENABLE_ALIGNMENT", "true").lower() == "true"
WHISPER_ENABLE_DIARIZATION = _env("WHISPER_ENABLE_DIARIZATION", "false").lower() == "true"

# --- Limits ---
MAX_STYLE_EXAMPLES = _env_int("MAX_STYLE_EXAMPLES", 5)
MAX_TRANSCRIPT_CHARS = _env_int("MAX_TRANSCRIPT_CHARS", 4000)
MAX_STYLE_EXAMPLE_CHARS = _env_int("MAX_STYLE_EXAMPLE_CHARS", 1500)
MAX_CAD_TEXT_CHARS = _env_int("MAX_CAD_TEXT_CHARS", 8000)
MAX_TOTAL_PROMPT_CHARS = _env_int("MAX_TOTAL_PROMPT_CHARS", 12000)

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
VRAM_BUDGET_FRACTION = _env_int("VRAM_BUDGET_FRACTION", 85) / 100

# --- Provider selection ---
LLM_PROVIDER = _env("LLM_PROVIDER", "ollama")
LLM_FALLBACK_ENABLED = _env("LLM_FALLBACK", "true").lower() == "true"
TRANSCRIBER_PROVIDER = _env("TRANSCRIBER_PROVIDER", "whisper")
PDF_PARSER_PROVIDER = _env("PDF_PARSER_PROVIDER", "zuercher")

# --- Department letterhead ---
DEPARTMENT_NAME = _env("DEPT_NAME", "Sheriff's Department")
DEPARTMENT_ADDRESS = _env("DEPT_ADDRESS", "123 Main Street")
DEPARTMENT_CITY_STATE_ZIP = _env("DEPT_CITY", "Anytown, WI 12345")
DEPARTMENT_PHONE = _env("DEPT_PHONE", "(555) 123-4567")
DEPARTMENT_LOGO_PATH = _env("DEPT_LOGO", "")

# --- Session ---
SESSION_TIMEOUT_SECONDS = _env_int("SESSION_TIMEOUT", 1800)

# --- Data retention ---
DATA_RETENTION_DAYS = _env_int("DATA_RETENTION_DAYS", 0)  # 0 = disabled

# --- Evidence ---
EVIDENCE_DIR = os.path.join(BASE_DIR, _env("EVIDENCE_DIR", "evidence_storage"))
EVIDENCE_MAX_FILES = _env_int("EVIDENCE_MAX_FILES", 100)

# --- Spell check ---
SPELL_CHECK_ENABLED = _env("SPELL_CHECK", "true").lower() == "true"

# --- Signature ---
SIGNATURE_ENABLED = _env("SIGNATURE_ENABLED", "true").lower() == "true"

# --- API ---
API_KEY = _env("API_KEY", "")
API_BIND_HOST = _env("API_BIND", "127.0.0.1")
API_PORT = _env_int("API_PORT", 8765)

# --- Database ---
DB_TIMEOUT = _env_int("DB_TIMEOUT", 30)


if __name__ == '__main__':
    print("Chronos Configuration:")
    for k, v in sorted({k: v for k, v in globals().items() if k.isupper()}.items()):
        if not k.startswith('_'):
            print(f"  {k} = {v}")
