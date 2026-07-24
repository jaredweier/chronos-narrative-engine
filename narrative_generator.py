import re
from typing import Optional, List, Callable, Dict, Any
from config import MAX_TRANSCRIPT_CHARS, MAX_STYLE_EXAMPLE_CHARS, MAX_CAD_TEXT_CHARS, MAX_TOTAL_PROMPT_CHARS
from llm_provider import get_llm_provider
from wi_statutes import format_statutes_for_prompt, find_statutes_in_text


_INJECTION_PATTERNS = [
    re.compile(r'ignore\s+(all\s+)?previous\s+(instructions|directions|prompts)', re.IGNORECASE),
    re.compile(r'forget\s+(all\s+)?(your|prior|previous)\s+(instructions|directions|prompts|training)', re.IGNORECASE),
    re.compile(r'(system|assistant)\s+prompt:', re.IGNORECASE),
    re.compile(r'you\s+are\s+(now|free|no\s+longer)', re.IGNORECASE),
    re.compile(r'new\s+(instructions|prompt|rule)s?\s*:', re.IGNORECASE),
    re.compile(r'disregard\s+(all\s+)?(prior|previous|above)\s+(instructions|content|text)', re.IGNORECASE),
    re.compile(r'rewrite\s+(the\s+)?(narrative|report|output|story)', re.IGNORECASE),
    re.compile(r'output\s+(only|just|solely)\s+(json|xml|raw)', re.IGNORECASE),
    re.compile(r'do\s+not\s+(follow|obey|adhere\s+to)\s+(your|the)\s+(instructions|guidelines|prompt)', re.IGNORECASE),
    re.compile(r'role[-\s]?play\s+(as\s+)?(a\s+)?(different|another|malicious|unrestricted)', re.IGNORECASE),
    re.compile(r'\[SYSTEM\]|\[INST\]|<\|im_start\|>|<\|im_end\|>', re.IGNORECASE),
    re.compile(r'(respond|answer|reply)\s+(as|like|acting\s+as)\s+(a\s+)?(jailbroken|dan|unfiltered|uncensored)', re.IGNORECASE),
]


def _sanitize_llm_input(text: str) -> str:
    if not text:
        return text
    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub('[REMOVED]', text)
    text = text.replace('```', '')
    return text


_INSERT_PLACEHOLDER_RE = re.compile(r'\[INSERT\s+[^\]]*\]', re.IGNORECASE)

_SYSTEM_PROMPT = (
    "You are a law enforcement report writing assistant. "
    "Generate a professional, factual incident narrative based ONLY on the information provided below. "
    "Use formal police report language. Write in past tense. "
    "Be specific about times, locations, and actions taken. "
    "If a required detail (name, time, location, etc.) is NOT present in the provided evidence, "
    "use [INSERT DETAIL] as a placeholder instead of inventing it. "
    "CRITICAL REQUIREMENT (TRACEABILITY): You MUST cite your sources. When stating a fact from the bodycam transcript, "
    "append the exact timestamp in brackets like [MM:SS] next to the fact. Do NOT invent timestamps. "
    "Structure the narrative with a clear beginning (response), middle (investigation/observations), and end (disposition)."
)

def _build_narrative_prompt(
    system_prompt: str,
    cad_text: str = "",
    transcript: str = "",
    dispatch_audio_transcript: str = "",
    officer_style_examples: Optional[List[str]] = None,
    custom_notes: str = "",
    report_type: str = "Standard Incident Report",
    raw_text: str = "",
    statutes: Optional[List[Dict[str, Any]]] = None,
) -> str:
    parts = [system_prompt]

    if report_type:
        parts.append(f"\nReport Type: {report_type}")

    if officer_style_examples:
        parts.append("\nWrite in a style matching these examples:")
        for i, ex in enumerate(officer_style_examples[:3], 1):
            parts.append(f"\n--- Style Example {i} ---")
            parts.append(ex[:MAX_STYLE_EXAMPLE_CHARS])
            parts.append("--- End Example ---")

    if statutes:
        parts.append(format_statutes_for_prompt(statutes))

    if cad_text:
        parts.append("\n--- CAD REPORT DATA ---")
        parts.append(cad_text[:MAX_CAD_TEXT_CHARS])
        parts.append("--- END CAD DATA ---")

    if transcript:
        parts.append("\n--- BODY CAMERA TRANSCRIPT ---")
        parts.append(transcript[:MAX_TRANSCRIPT_CHARS])
        parts.append("--- END TRANSCRIPT ---")

    if dispatch_audio_transcript:
        parts.append("\n--- 911 DISPATCH AUDIO TRANSCRIPT ---")
        parts.append(dispatch_audio_transcript[:MAX_TRANSCRIPT_CHARS])
        parts.append("--- END DISPATCH TRANSCRIPT ---")

    if raw_text:
        parts.append("\n--- RAW INCIDENT INFORMATION ---")
        parts.append(raw_text)
        parts.append("--- END RAW INFORMATION ---")

    if custom_notes:
        parts.append("\n--- ADDITIONAL OFFICER NOTES ---")
        parts.append(_sanitize_llm_input(custom_notes))
        parts.append("--- END NOTES ---")

    parts.append("\nGenerate the incident narrative now:")
    full_prompt = "\n".join(parts)
    if len(full_prompt) > MAX_TOTAL_PROMPT_CHARS:
        full_prompt = full_prompt[:MAX_TOTAL_PROMPT_CHARS] + "\n\n[TRUNCATED - remaining context omitted due to length]\nGenerate the incident narrative now:"
    return full_prompt


def _call_llm(prompt: str, stream: bool = False, chunk_callback: Optional[Callable[[str], None]] = None) -> str:
    provider = get_llm_provider()
    response = provider.complete(prompt=prompt, stream=stream, chunk_callback=chunk_callback)
    return response.text


def _stream_llm(prompt: str):
    provider = get_llm_provider()
    for chunk in provider.stream_complete(prompt=prompt):
        yield chunk


def count_insert_placeholders(text: str) -> int:
    return len(_INSERT_PLACEHOLDER_RE.findall(text))


def has_unfilled_placeholders(text: str) -> bool:
    return count_insert_placeholders(text) > 0


def generate_narrative(
    cad_text: str = "",
    transcript: str = "",
    dispatch_audio_transcript: str = "",
    officer_style_examples: Optional[List[str]] = None,
    custom_notes: str = "",
    report_type: str = "Standard Incident Report",
    statutes: Optional[List[Dict[str, Any]]] = None,
) -> str:
    prompt = _build_narrative_prompt(
        _SYSTEM_PROMPT, cad_text, transcript, dispatch_audio_transcript,
        officer_style_examples, custom_notes, report_type,
        statutes=statutes,
    )
    narrative = _call_llm(prompt)
    found = find_statutes_in_text(narrative)
    if found:
        parts = [narrative, "\n\n---\nReferenced Statutes:"]
        for s in found:
            parts.append(f"\n- {s['code']}: {s['title']}")
        narrative = "".join(parts)
    return narrative


def generate_narrative_stream(
    cad_text: str = "",
    transcript: str = "",
    dispatch_audio_transcript: str = "",
    officer_style_examples: Optional[List[str]] = None,
    custom_notes: str = "",
    report_type: str = "Standard Incident Report",
    statutes: Optional[List[Dict[str, Any]]] = None,
):
    prompt = _build_narrative_prompt(
        _SYSTEM_PROMPT, cad_text, transcript, dispatch_audio_transcript,
        officer_style_examples, custom_notes, report_type,
        statutes=statutes,
    )
    for chunk in _stream_llm(prompt):
        yield chunk



