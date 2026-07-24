import json
from typing import Dict, Any
from logger import get_logger
from llm_provider import get_llm_provider
from config import OLLAMA_MODEL

logger = get_logger(__name__)

def analyze_officer_performance(transcript: str, model: str = OLLAMA_MODEL) -> Dict[str, Any]:
    prompt = f"""You are an internal police training and coaching assistant. Analyze the provided body-worn camera transcript to provide constructive feedback on officer performance.

CRITICAL DIRECTIVE: Do NOT make any legal conclusions regarding the justification of use of force, probable cause, or guilt/innocence. This tool is strictly for internal tone, communication, and de-escalation coaching. 

TRANSCRIPT:
{transcript[:8000]}

Extract and evaluate the following metrics, returning them in a valid JSON object:
- "tone_assessment": string ("Professional", "Neutral", or "Needs Improvement")
- "tone_notes": string (Explanation of the tone, quoting specific phrases if applicable)
- "de_escalation_used": boolean (True if the officer attempted to de-escalate tension)
- "de_escalation_notes": string (Description of the techniques used, or what could have been tried)
- "policy_triggers": list of strings (e.g., "Mention of Taser deployment", "Profanity detected", "Use of force keywords detected"). If none, return empty list.
- "coaching_summary": string (A short, constructive feedback summary for the officer to self-correct and improve communication skills)

Return ONLY valid JSON."""

    try:
        provider = get_llm_provider()
        result = provider.complete_json(prompt=prompt, timeout=60)
        if isinstance(result, dict):
            # Guarantee structure
            return {
                "tone_assessment": result.get("tone_assessment", "Neutral"),
                "tone_notes": result.get("tone_notes", "No notes generated."),
                "de_escalation_used": result.get("de_escalation_used", False),
                "de_escalation_notes": result.get("de_escalation_notes", "No notes generated."),
                "policy_triggers": result.get("policy_triggers", []),
                "coaching_summary": result.get("coaching_summary", "No summary generated.")
            }
    except Exception as e:
        logger.error(f"Error analyzing officer performance: {e}")
        
    return {
        "error": "Failed to analyze performance.",
        "tone_assessment": "Unknown",
        "tone_notes": "",
        "de_escalation_used": False,
        "de_escalation_notes": "",
        "policy_triggers": [],
        "coaching_summary": ""
    }
