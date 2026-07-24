import json
from typing import Dict, Any, List
from logger import get_logger
from llm_provider import get_llm_provider
from config import OLLAMA_MODEL

logger = get_logger(__name__)

def _chunk_text(text: str, max_chars: int = 15000) -> List[str]:
    words = text.split()
    chunks = []
    current_chunk = []
    current_len = 0
    
    for word in words:
        if current_len + len(word) > max_chars:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_len = len(word)
        else:
            current_chunk.append(word)
            current_len += len(word) + 1
            
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

def generate_case_brief(text: str, model: str = OLLAMA_MODEL) -> Dict[str, Any]:
    provider = get_llm_provider()
    
    chunks = _chunk_text(text, max_chars=12000)
    
    if len(chunks) == 1:
        return _summarize_chunk(chunks[0], provider)
    
    chunk_summaries = []
    for i, chunk in enumerate(chunks[:5]): 
        logger.info(f"Summarizing chunk {i+1}/{len(chunks)}")
        prompt = f"Summarize the key facts, involved persons, and evidence in this excerpt from a case file:\n\n{chunk}"
        summary = provider.complete(prompt=prompt, timeout=60)
        chunk_summaries.append(summary)
        
    combined_summary = "\n\n".join(chunk_summaries)
    return _summarize_chunk(combined_summary, provider)

def _summarize_chunk(text: str, provider) -> Dict[str, Any]:
    prompt = f"""You are a senior detective assistant. Analyze the following case file text and generate a comprehensive Case Brief.

CASE FILE EXCERPT:
{text}

Extract and structure the information into the following JSON format:
- "key_facts": list of strings (chronological bullet points of the incident)
- "suspects": list of strings (names and descriptions of suspects)
- "evidence": list of strings (items collected or mentioned as evidence)
- "summary_narrative": string (a 2-3 paragraph professional executive summary)

Return ONLY valid JSON."""

    try:
        result = provider.complete_json(prompt=prompt, timeout=120)
        if isinstance(result, dict):
            # Fill missing keys just in case
            return {
                "key_facts": result.get("key_facts", []),
                "suspects": result.get("suspects", []),
                "evidence": result.get("evidence", []),
                "summary_narrative": result.get("summary_narrative", "")
            }
    except Exception as e:
        logger.error(f"Error generating case brief: {e}")
        
    return {
        "key_facts": ["Failed to generate key facts."],
        "suspects": [],
        "evidence": [],
        "summary_narrative": "Error generating case brief."
    }
