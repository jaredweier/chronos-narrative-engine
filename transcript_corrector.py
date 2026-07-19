from typing import Optional
from config import (
    WHISPER_TRANSCRIPT_CORRECTOR_ENABLED,
    WHISPER_TWO_PASS_ENABLED,
    WHISPER_TWO_PASS_QUICK_MODEL,
    OLLAMA_MODEL,
)
from llm_provider import get_llm_provider
from logger import get_logger

logger = get_logger(__name__)

_CORRECTOR_SYSTEM_PROMPT = (
    "You are a law enforcement transcription editor. "
    "Fix the following body camera transcript for accuracy. "
    "Rules:\n"
    "1. Correct misheard law enforcement terminology (statutes, codes, radio jargon, equipment)\n"
    "2. Fix phonetic misrecognitions of names, places, badge numbers, license plates\n"
    "3. Add proper punctuation and capitalization\n"
    "4. Fix obvious homophone errors (e.g. 'their/there/they're', 'your/you're')\n"
    "5. Format times, dates, numerical values correctly\n"
    "6. Do NOT change the factual content, speaker meaning, or timestamp markers\n"
    "7. If unsure about a correction, leave the original text unchanged\n"
    "8. Preserve all [TIMESTAMP] markers exactly as they appear\n"
    "Return ONLY the corrected transcript, nothing else."
)


def correct_transcript(transcript: str, model: Optional[str] = None) -> str:
    if not WHISPER_TRANSCRIPT_CORRECTOR_ENABLED or not transcript.strip():
        return transcript

    try:
        provider = get_llm_provider()
        prompt = (
            f"[INST] {_CORRECTOR_SYSTEM_PROMPT}\n\n"
            f"Correct this body camera transcript for law enforcement terminology:\n\n"
            f"{transcript}[/INST]"
        )
        response = provider.complete(
            prompt=prompt,
            temperature=0.1,
            max_tokens=len(transcript) + 512,
            timeout=60,
        )
        corrected = response.text.strip()

        if not corrected or corrected.startswith("[ERROR]"):
            logger.warning("Transcript correction failed: %s", corrected)
            return transcript

        logger.info(
            "Transcript correction applied: %d chars -> %d chars (%.1f%% change)",
            len(transcript), len(corrected),
            (1 - len(corrected) / max(len(transcript), 1)) * 100,
        )
        return corrected

    except Exception as e:
        logger.error("Transcript correction error: %s", e)
        return transcript


def extract_domain_terms(transcript: str, model: Optional[str] = None) -> str:
    if not WHISPER_TWO_PASS_ENABLED or not transcript.strip():
        return ""

    try:
        provider = get_llm_provider()
        prompt = (
            "[INST] Extract key law enforcement terms, names, codes, and locations "
            "from this body camera transcript. Return ONLY a comma-separated list "
            "of the most important domain-specific terms (statutes, badge numbers, "
            "locations, person names, radio codes, equipment, etc):\n\n"
            f"{transcript[:2000]}[/INST]"
        )
        response = provider.complete(
            prompt=prompt,
            temperature=0.0,
            max_tokens=256,
            timeout=30,
        )
        terms = response.text.strip()
        if terms.startswith("[ERROR]"):
            return ""
        logger.info("Extracted domain terms for prompt enrichment: %s", terms[:200])
        return terms

    except Exception as e:
        logger.error("Domain term extraction error: %s", e)
        return ""
