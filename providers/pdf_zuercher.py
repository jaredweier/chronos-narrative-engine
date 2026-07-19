from typing import Any
from providers.base import PDFParserProvider

from pdf_parser import (
    extract_text_from_pdf,
    sanitize_pii_content,
    query_ollama_structured,
    _build_cad_data,
    CadData,
)


class ZuercherPDFParserProvider(PDFParserProvider):
    def parse(self, pdf_path: str, redact: bool = True) -> CadData:
        raw_text = extract_text_from_pdf(pdf_path)
        if redact:
            processed_text = sanitize_pii_content(raw_text)
        else:
            processed_text = raw_text

        parsed_data = query_ollama_structured(processed_text)
        if parsed_data:
            return _build_cad_data(parsed_data, processed_text)
        return CadData(raw_text=processed_text)

    def extract_text(self, pdf_path: str) -> str:
        return extract_text_from_pdf(pdf_path)
