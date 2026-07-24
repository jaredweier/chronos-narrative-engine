from typing import Dict, Type
from threading import Lock
from config import LLM_PROVIDER, TRANSCRIBER_PROVIDER, PDF_PARSER_PROVIDER
from providers.base import LLMProvider, TranscriberProvider, PDFParserProvider


class ProviderRegistry:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._llm_providers: Dict[str, Type[LLMProvider]] = {}
                    cls._instance._transcriber_providers: Dict[str, Type[TranscriberProvider]] = {}
                    cls._instance._pdf_providers: Dict[str, Type[PDFParserProvider]] = {}
                    cls._instance._active_llm: str = ""
                    cls._instance._active_transcriber: str = ""
                    cls._instance._active_pdf: str = ""
        return cls._instance


_registry = ProviderRegistry()


def register_llm(name: str, provider_cls: Type[LLMProvider]):
    _registry._llm_providers[name] = provider_cls


def register_transcriber(name: str, provider_cls: Type[TranscriberProvider]):
    _registry._transcriber_providers[name] = provider_cls


def register_pdf_parser(name: str, provider_cls: Type[PDFParserProvider]):
    _registry._pdf_providers[name] = provider_cls


def list_llm_providers() -> list:
    return list(_registry._llm_providers.keys())


def list_transcriber_providers() -> list:
    return list(_registry._transcriber_providers.keys())


def list_pdf_providers() -> list:
    return list(_registry._pdf_providers.keys())


_llm_instance = None
def get_llm() -> LLMProvider:
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance
    active = _registry._active_llm or LLM_PROVIDER
    cls = _registry._llm_providers.get(active)
    if cls is None:
        raise ValueError(
            f"LLM provider '{active}' not registered. "
            f"Available: {list_llm_providers()}. "
            f"Set CHRONOS_LLM_PROVIDER or call register_llm()."
        )
    _llm_instance = cls()
    return _llm_instance


_transcriber_instance = None
def get_transcriber() -> TranscriberProvider:
    global _transcriber_instance
    if _transcriber_instance is not None:
        return _transcriber_instance
    active = _registry._active_transcriber or TRANSCRIBER_PROVIDER
    cls = _registry._transcriber_providers.get(active)
    if cls is None:
        raise ValueError(
            f"Transcriber provider '{active}' not registered. "
            f"Available: {list_transcriber_providers()}. "
            f"Set CHRONOS_TRANSCRIBER_PROVIDER or call register_transcriber()."
        )
    _transcriber_instance = cls()
    return _transcriber_instance


_pdf_parser_instance = None
def get_pdf_parser() -> PDFParserProvider:
    global _pdf_parser_instance
    if _pdf_parser_instance is not None:
        return _pdf_parser_instance
    active = _registry._active_pdf or PDF_PARSER_PROVIDER
    cls = _registry._pdf_providers.get(active)
    if cls is None:
        raise ValueError(
            f"PDF parser provider '{active}' not registered. "
            f"Available: {list_pdf_providers()}. "
            f"Set CHRONOS_PDF_PARSER_PROVIDER or call register_pdf_parser()."
        )
    _pdf_parser_instance = cls()
    return _pdf_parser_instance


def set_active_llm(name: str):
    if name not in _registry._llm_providers:
        raise ValueError(f"Unknown LLM provider: {name}. Available: {list_llm_providers()}")
    _registry._active_llm = name


def set_active_transcriber(name: str):
    if name not in _registry._transcriber_providers:
        raise ValueError(f"Unknown transcriber: {name}. Available: {list_transcriber_providers()}")
    _registry._active_transcriber = name


def set_active_pdf_parser(name: str):
    if name not in _registry._pdf_providers:
        raise ValueError(f"Unknown PDF parser: {name}. Available: {list_pdf_providers()}")
    _registry._active_pdf = name


def clear_provider_cache():
    global _llm_instance, _transcriber_instance, _pdf_parser_instance
    if _transcriber_instance is not None:
        _transcriber_instance.cleanup()
    _llm_instance = None
    _transcriber_instance = None
    _pdf_parser_instance = None

