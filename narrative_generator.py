import requests
from typing import Optional, List
from config import OLLAMA_API_ENDPOINT, OLLAMA_MODEL, LLM_DEFAULTS, LLM_NARRATIVE_TIMEOUT, MAX_TRANSCRIPT_CHARS, MAX_STYLE_EXAMPLE_CHARS, MAX_CAD_TEXT_CHARS


def generate_narrative(
    cad_text: str = "",
    transcript: str = "",
    officer_style_examples: Optional[List[str]] = None,
    custom_notes: str = "",
    report_type: str = "Standard Incident Report",
    model: str = OLLAMA_MODEL,
) -> str:
    prompt_parts = []

    prompt_parts.append(
        "You are a law enforcement report writing assistant. "
        "Generate a professional, factual incident narrative based on the information provided below. "
        "Use formal police report language. Write in past tense. "
        "Be specific about times, locations, and actions taken. "
        "Do not fabricate details that are not provided. "
        "Structure the narrative with a clear beginning (response), middle (investigation/observations), and end (disposition)."
    )

    if report_type:
        prompt_parts.append(f"\nReport Type: {report_type}")

    if officer_style_examples:
        prompt_parts.append("\nWrite in a style matching these examples:")
        for i, ex in enumerate(officer_style_examples[:3], 1):
            prompt_parts.append(f"\n--- Style Example {i} ---")
            prompt_parts.append(ex[:MAX_STYLE_EXAMPLE_CHARS])
            prompt_parts.append("--- End Example ---")

    if cad_text:
        prompt_parts.append("\n--- CAD REPORT DATA ---")
        prompt_parts.append(cad_text[:MAX_CAD_TEXT_CHARS])
        prompt_parts.append("--- END CAD DATA ---")

    if transcript:
        prompt_parts.append("\n--- BODY CAMERA TRANSCRIPT ---")
        prompt_parts.append(transcript[:MAX_TRANSCRIPT_CHARS])
        prompt_parts.append("--- END TRANSCRIPT ---")

    if custom_notes:
        prompt_parts.append("\n--- ADDITIONAL OFFICER NOTES ---")
        prompt_parts.append(custom_notes)
        prompt_parts.append("--- END NOTES ---")

    prompt_parts.append("\nGenerate the incident narrative now:")

    full_prompt = "\n".join(prompt_parts)

    try:
        response = requests.post(
            OLLAMA_API_ENDPOINT,
            json={
                "model": model,
                "prompt": full_prompt,
                "stream": False,
                "options": LLM_DEFAULTS,
            },
            timeout=LLM_NARRATIVE_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()
    except requests.ConnectionError:
        return "[ERROR] Cannot connect to Ollama. Please ensure Ollama is running (ollama serve)."
    except requests.Timeout:
        return "[ERROR] Generation timed out. The model may be overloaded."
    except Exception as e:
        return f"[ERROR] Narrative generation failed: {e}"


def generate_narrative_stream(
    cad_text: str = "",
    transcript: str = "",
    officer_style_examples: Optional[List[str]] = None,
    custom_notes: str = "",
    report_type: str = "Standard Incident Report",
    model: str = OLLAMA_MODEL,
    chunk_callback=None,
) -> str:
    prompt_parts = []

    prompt_parts.append(
        "You are a law enforcement report writing assistant. "
        "Generate a professional, factual incident narrative based on the information provided below. "
        "Use formal police report language. Write in past tense. "
        "Be specific about times, locations, and actions taken. "
        "Do not fabricate details that are not provided. "
        "Structure the narrative with a clear beginning (response), middle (investigation/observations), and end (disposition)."
    )

    if report_type:
        prompt_parts.append(f"\nReport Type: {report_type}")

    if officer_style_examples:
        prompt_parts.append("\nWrite in a style matching these examples:")
        for i, ex in enumerate(officer_style_examples[:3], 1):
            prompt_parts.append(f"\n--- Style Example {i} ---")
            prompt_parts.append(ex[:MAX_STYLE_EXAMPLE_CHARS])
            prompt_parts.append("--- End Example ---")

    if cad_text:
        prompt_parts.append("\n--- CAD REPORT DATA ---")
        prompt_parts.append(cad_text[:MAX_CAD_TEXT_CHARS])
        prompt_parts.append("--- END CAD DATA ---")

    if transcript:
        prompt_parts.append("\n--- BODY CAMERA TRANSCRIPT ---")
        prompt_parts.append(transcript[:MAX_TRANSCRIPT_CHARS])
        prompt_parts.append("--- END TRANSCRIPT ---")

    if custom_notes:
        prompt_parts.append("\n--- ADDITIONAL OFFICER NOTES ---")
        prompt_parts.append(custom_notes)
        prompt_parts.append("--- END NOTES ---")

    prompt_parts.append("\nGenerate the incident narrative now:")

    full_prompt = "\n".join(prompt_parts)

    try:
        response = requests.post(
            OLLAMA_API_ENDPOINT,
            json={
                "model": model,
                "prompt": full_prompt,
                "stream": True,
                "options": LLM_DEFAULTS,
            },
            timeout=LLM_NARRATIVE_TIMEOUT,
            stream=True,
        )
        response.raise_for_status()
        accumulated = ""
        for line in response.iter_lines():
            if line:
                import json
                data = json.loads(line)
                token = data.get("response", "")
                accumulated += token
                if chunk_callback:
                    chunk_callback(token)
        return accumulated.strip()
    except requests.ConnectionError:
        return "[ERROR] Cannot connect to Ollama. Please ensure Ollama is running (ollama serve)."
    except requests.Timeout:
        return "[ERROR] Generation timed out. The model may be overloaded."
    except Exception as e:
        return f"[ERROR] Narrative generation failed: {e}"


def generate_narrative_from_text(
    raw_text: str,
    officer_style_examples: Optional[List[str]] = None,
    custom_notes: str = "",
    report_type: str = "Standard Incident Report",
    model: str = OLLAMA_MODEL,
) -> str:
    prompt_parts = []

    prompt_parts.append(
        "You are a law enforcement report writing assistant. "
        "Based on the following raw information, generate a professional, formal incident narrative. "
        "Use past tense, formal police report language. "
        "Be factual and do not invent details. "
        "Structure: response -> investigation/observations -> disposition."
    )

    if report_type:
        prompt_parts.append(f"\nReport Type: {report_type}")

    if officer_style_examples:
        prompt_parts.append("\nWrite in a style matching these examples:")
        for i, ex in enumerate(officer_style_examples[:3], 1):
            prompt_parts.append(f"\n--- Style Example {i} ---")
            prompt_parts.append(ex[:MAX_STYLE_EXAMPLE_CHARS])
            prompt_parts.append("--- End Example ---")

    prompt_parts.append("\n--- RAW INCIDENT INFORMATION ---")
    prompt_parts.append(raw_text)
    prompt_parts.append("--- END RAW INFORMATION ---")

    if custom_notes:
        prompt_parts.append("\n--- ADDITIONAL OFFICER NOTES ---")
        prompt_parts.append(custom_notes)
        prompt_parts.append("--- END NOTES ---")

    prompt_parts.append("\nGenerate the incident narrative now:")

    full_prompt = "\n".join(prompt_parts)

    try:
        response = requests.post(
            OLLAMA_API_ENDPOINT,
            json={
                "model": model,
                "prompt": full_prompt,
                "stream": False,
                "options": LLM_DEFAULTS,
            },
            timeout=LLM_NARRATIVE_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()
    except requests.ConnectionError:
        return "[ERROR] Cannot connect to Ollama. Please ensure Ollama is running (ollama serve)."
    except requests.Timeout:
        return "[ERROR] Generation timed out."
    except Exception as e:
        return f"[ERROR] Narrative generation failed: {e}"
