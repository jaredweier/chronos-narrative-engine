import json
import requests
from typing import Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
import pdfplumber

from redactor import sanitize_pii_content
from config import OLLAMA_API_ENDPOINT, OLLAMA_MODEL, LLM_COMPLIANCE_OPTIONS, LLM_COMPLIANCE_TIMEOUT


class InvolvedParty(BaseModel):
    name: str = Field(default="Unknown")
    dob: str = Field(default="")
    sex: str = Field(default="")
    age: str = Field(default="")


class CadData(BaseModel):
    call_id: str = Field(default="Unknown")
    call_type: str = Field(default="Unknown")
    location: str = Field(default="Unknown")
    dispatch_time: str = Field(default="")
    arrival_time: str = Field(default="")
    clear_time: str = Field(default="")
    involved_parties: list[InvolvedParty] = Field(default_factory=list)
    raw_text: str = Field(default="")


def extract_text_from_pdf(pdf_path: str) -> str:
    text_parts = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    
    return "\n".join(text_parts)


def query_ollama_structured(text: str, model: str = OLLAMA_MODEL) -> Optional[Dict[str, Any]]:
    prompt = f"""Extract the following structured data from this CAD report text. 
Return ONLY a valid JSON object with these fields:
- call_id: The incident/call tracking number
- call_type: The nature of the offense or call type
- location: The address or location of the incident
- dispatch_time: When dispatch was notified
- arrival_time: When officer arrived on scene
- clear_time: When the call was cleared
- involved_parties: An array of objects with name, dob, sex, age fields

If a field is not found, use an empty string or empty array.

CAD REPORT TEXT:
{text}

JSON:"""

    try:
        response = requests.post(
            OLLAMA_API_ENDPOINT,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": LLM_COMPLIANCE_OPTIONS,
            },
            timeout=LLM_COMPLIANCE_TIMEOUT,
        )
        response.raise_for_status()
        
        result = response.json()
        response_text = result.get("response", "")
        
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            return json.loads(json_str)
        
        return None
        
    except Exception as e:
        print(f"Ollama query failed: {e}")
        return None


def _build_cad_data(parsed_data: dict, processed_text: str) -> CadData:
    parties = []
    for party in parsed_data.get("involved_parties", []):
        if isinstance(party, dict):
            parties.append(InvolvedParty(
                name=party.get("name", ""),
                dob=party.get("dob", ""),
                sex=party.get("sex", ""),
                age=party.get("age", "")
            ))

    return CadData(
        call_id=parsed_data.get("call_id", "Unknown"),
        call_type=parsed_data.get("call_type", "Unknown"),
        location=parsed_data.get("location", "Unknown"),
        dispatch_time=parsed_data.get("dispatch_time", ""),
        arrival_time=parsed_data.get("arrival_time", ""),
        clear_time=parsed_data.get("clear_time", ""),
        involved_parties=parties,
        raw_text=processed_text,
    )


def parse_zuercher_pdf(pdf_path: str, redact: bool = True) -> CadData:
    raw_text = extract_text_from_pdf(pdf_path)
    
    if redact:
        processed_text = sanitize_pii_content(raw_text)
    else:
        processed_text = raw_text
    
    parsed_data = query_ollama_structured(processed_text)
    
    if parsed_data:
        return _build_cad_data(parsed_data, processed_text)
    
    return CadData(raw_text=processed_text)


def parse_zuercher_text(text: str, redact: bool = True) -> CadData:
    if redact:
        processed_text = sanitize_pii_content(text)
    else:
        processed_text = text
    
    parsed_data = query_ollama_structured(processed_text)
    
    if parsed_data:
        return _build_cad_data(parsed_data, processed_text)
    
    return CadData(raw_text=processed_text)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        if Path(pdf_path).exists():
            result = parse_zuercher_pdf(pdf_path)
            print(json.dumps(result.model_dump(), indent=2))
        else:
            print(f"File not found: {pdf_path}")
    else:
        print("Usage: python pdf_parser.py <path_to_zuercher_pdf>")
