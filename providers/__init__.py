from providers.base import (
    LLMProvider,
    LLMResponse,
    TranscriberProvider,
    PDFParserProvider,
)

from providers.registry import (
    register_llm,
    register_transcriber,
    register_pdf_parser,
    get_llm,
    get_transcriber,
    get_pdf_parser,
    list_llm_providers,
    list_transcriber_providers,
    list_pdf_providers,
    set_active_llm,
    set_active_transcriber,
    set_active_pdf_parser,
)

try:
    from providers.llm_ollama import OllamaLLMProvider
    register_llm("ollama", OllamaLLMProvider)
except ImportError:
    pass

try:
    from providers.transcribe_whisper import WhisperTranscriberProvider
    register_transcriber("whisper", WhisperTranscriberProvider)
except ImportError:
    pass

try:
    from providers.pdf_zuercher import ZuercherPDFParserProvider
    register_pdf_parser("zuercher", ZuercherPDFParserProvider)
except ImportError:
    pass
