import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_API_ENDPOINT = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_MODEL = "llama3.1:8b"

LLM_DEFAULTS = {
    "temperature": 0.3,
    "num_predict": 2048,
    "top_p": 0.9,
}

LLM_COMPLIANCE_OPTIONS = {
    "temperature": 0.0,
    "num_predict": 1024,
}

LLM_NARRATIVE_TIMEOUT = 120
LLM_COMPLIANCE_TIMEOUT = 60

WHISPER_MODEL_SIZE = "small"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE_TYPE = "float16"
WHISPER_CPU_THREADS = 16
WHISPER_VAD_MIN_SILENCE_MS = 500
WHISPER_VAD_SPEECH_PAD_MS = 200

MAX_STYLE_EXAMPLES = 5
MAX_TRANSCRIPT_CHARS = 4000
MAX_STYLE_EXAMPLE_CHARS = 1500
MAX_CAD_TEXT_CHARS = 8000

TEMP_DIR = os.path.join(BASE_DIR, 'temp_processing')
COMPLETED_DIR = os.path.join(BASE_DIR, 'completed_reports')
PROFILES_DIR = os.path.join(BASE_DIR, 'officer_profiles')
DB_PATH = os.path.join(BASE_DIR, 'department_reports.db')
CUSTOM_CATEGORIES_FILE = os.path.join(BASE_DIR, 'custom_categories.txt')

MAX_UPLOAD_SIZE_GB = 4
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_GB * 1024 * 1024 * 1024

PIPELINE_MAX_WORKERS = 2
DB_TIMEOUT = 30.0
