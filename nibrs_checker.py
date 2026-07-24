import json
import re
from typing import List, Dict, Any
from config import OLLAMA_MODEL
from logger import get_logger
from llm_provider import get_llm_provider
from wi_statutes import WI_CRIMINAL_STATUTES, statutes_for_nibrs, nibrs_for_statute

logger = get_logger(__name__)


NIBRS_REQUIREMENTS = {
    "Standard Incident Report": [
        "incident_date_time",
        "location_type",
        "offense_code",
        "weapon_force_involved",
        "suspect_description",
        "victim_statement",
        "evidence_collected",
        "officer_narrative"
    ],
    "Search Warrant Affidavit": [
        "probable_cause_statement",
        "target_location",
        "items_to_seize",
        "judge_signature",
        "affiant_information",
        "warrant_return"
    ],
    "Internal Use-of-Force Review": [
        "officer_identification",
        "subject_identification",
        "force_type_used",
        "injuries_sustained",
        "medical_attention",
        "witness_information",
        "body_camera_status",
        "supervisor_notification"
    ],
    "OWI / DUI Report": [
        "field_sobriety_tests",
        "breathalyzer_results",
        "vehicle_information",
        "driving_behavior",
        "observations_of_impairment",
        "chemical_test_refusal",
        "miranda_warnings"
    ]
}


def check_nibrs_compliance(call_type: str, narrative_text: str, model: str = OLLAMA_MODEL) -> List[Dict[str, Any]]:
    prompt = f"""You are a federal NIBRS (National Incident-Based Reporting System) compliance officer.

Analyze this law enforcement narrative for NIBRS compliance based on the call type: {call_type}

NARRATIVE TEXT:
{narrative_text}

Check if the following critical elements are documented for a {call_type}:
{json.dumps(NIBRS_REQUIREMENTS.get(call_type, []), indent=2)}

Return a JSON array of compliance warnings. Each warning should have:
- "element": The missing or incomplete NIBRS element
- "severity": "critical", "warning", or "info"
- "message": Description of what is missing or needs attention
- "suggestion": How to fix the compliance issue

If the narrative is fully compliant, return an empty array [].

COMPLIANCE CHECK:"""

    try:
        provider = get_llm_provider()
        result = provider.complete_json(prompt=prompt, timeout=60)
        if isinstance(result, list):
            return result
        return []
    except Exception as e:
        logger.error("NIBRS check error: %s", e)
        return []


def get_compliance_summary(warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
    critical = sum(1 for w in warnings if w.get("severity") == "critical")
    warning = sum(1 for w in warnings if w.get("severity") == "warning")
    info = sum(1 for w in warnings if w.get("severity") == "info")
    
    return {
        "is_compliant": critical == 0,
        "critical_count": critical,
        "warning_count": warning,
        "info_count": info,
        "total_issues": len(warnings)
    }


def format_compliance_report(warnings: List[Dict[str, Any]]) -> str:
    if not warnings:
        return "✓ NIBRS Compliant - No issues found"
    
    summary = get_compliance_summary(warnings)
    lines = [
        f"NIBRS Compliance Check: {'PASSED' if summary['is_compliant'] else 'FAILED'}",
        f"Critical: {summary['critical_count']} | Warnings: {summary['warning_count']} | Info: {summary['info_count']}",
        ""
    ]
    
    for w in warnings:
        severity_icon = {"critical": "✗", "warning": "⚠", "info": "ℹ"}.get(w.get("severity", "info"), "•")
        lines.append(f"{severity_icon} [{w.get('element', 'unknown').upper()}] {w.get('message', '')}")
        if w.get('suggestion'):
            lines.append(f"  Suggestion: {w['suggestion']}")
        lines.append("")
    
    return "\n".join(lines)


_NEGATION_WORDS = frozenset({
    'no', 'not', 'without', 'never', 'none', 'nobody', 'nothing', 'nowhere',
    'neither', 'nor', "didn't", "wasn't", "weren't", "hadn't", "hasn't",
    "haven't", "isn't", "aren't", "couldn't", "wouldn't", "shouldn't",
    "doesn't", "don't", "did not", "was not", "were not", "had not",
    "has not", "have not", "is not", "are not", "could not", "would not",
    "should not", "does not", "do not", "no evidence", "no sign", "no indication",
})


def _keyword_in_affirmative(text: str, keyword: str) -> bool:
    pattern = re.compile(r'\b' + re.escape(keyword) + r'\b')
    for match in pattern.finditer(text):
        start = max(0, match.start() - 50)
        preceding = text[start:match.start()].strip()
        if not preceding:
            return True
        tokens = preceding.lower().split()
        negated = any(
            ' '.join(tokens[max(0, i-2):i+1]) in _NEGATION_WORDS
            or tokens[i] in _NEGATION_WORDS
            for i in range(len(tokens))
        )
        if not negated:
            return True
    return False


def suggest_missing_fields(call_type: str, narrative_text: str, model: str = OLLAMA_MODEL) -> List[Dict[str, Any]]:
    requirements = NIBRS_REQUIREMENTS.get(call_type, [])
    if not requirements:
        return []

    KEYWORD_REQUIRED = {
        "incident_date_time": ["incident", "date", "time"],
        "location_type": ["location", "address"],
        "offense_code": ["offense", "charge", "crime"],
        "weapon_force_involved": ["weapon", "firearm", "knife", "force", "deadly"],
        "suspect_description": ["suspect", "description", "male", "female", "white", "black", "hispanic"],
        "victim_statement": ["victim", "stated", "reported", "statement"],
        "evidence_collected": ["evidence", "collected", "processed", "gathered"],
        "officer_narrative": ["officer", "narrative", "responded"],
        "probable_cause_statement": ["probable", "cause", "belief", "basis"],
        "target_location": ["location", "premises", "residence", "address"],
        "items_to_seize": ["items", "seize", "contraband", "evidence"],
        "judge_signature": ["judge", "signed", "signature", "authorized"],
        "affiant_information": ["affiant", "officer", "sworn", "deponent"],
        "warrant_return": ["returned", "executed", "service", "return"],
        "officer_identification": ["officer", "badge", "identified", "name"],
        "subject_identification": ["subject", "suspect", "individual", "name"],
        "force_type_used": ["force", "taser", "pepper", "baton", "strikes"],
        "injuries_sustained": ["injuries", "injured", "wounds", "complained"],
        "medical_attention": ["medical", "ems", "ambulance", "treatment"],
        "witness_information": ["witness", "witnessed", "bystander", "observer"],
        "body_camera_status": ["body", "camera", "recording", "activated"],
        "supervisor_notification": ["supervisor", "notified", "sergeant", "command"],
        "field_sobriety_tests": ["field", "sobriety", "walk", "turn", "nystagmus"],
        "breathalyzer_results": ["breath", "alcohol", "bac", "results", "intoxilyzer"],
        "vehicle_information": ["vehicle", "make", "model", "license", "plate", "registration"],
        "driving_behavior": ["driving", "swerving", "lane", "speed", "erratic"],
        "observations_of_impairment": ["impairment", "intoxicated", "odor", "slurred", "glassy"],
        "chemical_test_refusal": ["refused", "refusal", "declined", "chemical", "test"],
        "miranda_warnings": ["miranda", "rights", "warned", "advised", "custody"],
    }

    narrative_lower = narrative_text.lower()
    present = []
    for req in requirements:
        keywords = KEYWORD_REQUIRED.get(req, req.replace("_", " ").lower().split())
        matches = sum(1 for kw in keywords if _keyword_in_affirmative(narrative_lower, kw))
        if matches >= 2:
            present.append(req)

    missing = [r for r in requirements if r not in present]

    if not missing:
        return []

    try:
        prompt = f"""You are a law enforcement report compliance assistant.

The following NIBRS elements are missing or insufficient in this {call_type}:
{json.dumps(missing, indent=2)}

NARRATIVE (truncated):
{narrative_text[:3000]}

For each missing element, provide a brief actionable suggestion of what the officer should add. Return a JSON array where each item has:
- "element": the missing element name
- "suggestion": a specific prompt or question to help the officer fill this in

Return ONLY the JSON array, nothing else."""

        provider = get_llm_provider()
        result = provider.complete_json(prompt=prompt, timeout=60)
        if isinstance(result, list):
            return result
    except Exception as e:
        logger.error("suggest_missing_fields: %s", e)

    return [{"element": m, "suggestion": f"Document the {m.replace('_', ' ')} in your narrative."} for m in missing]


def check_probable_cause(narrative_text: str, model: str = OLLAMA_MODEL) -> Dict[str, Any]:
    prompt = f"""You are a legal compliance reviewer for law enforcement reports.

Analyze this narrative for probable cause sufficiency. Check for:
1. Specific facts establishing the basis for arrest/search/seizure
2. Articulation of criminal activity observed or reported
3. Connection between the suspect and the criminal activity
4. Temporal proximity (recent vs. stale information)
5. Corroboration of informant information
6. Legal standard met for the type of action taken

NARRATIVE:
{narrative_text[:4000]}

Return a JSON object with:
- "has_probable_cause": boolean
- "strength": "strong", "adequate", "weak", or "insufficient"
- "factors_present": array of strong PC factors found
- "factors_missing": array of missing or weak elements
- "recommendations": array of specific improvements to strengthen the PC statement
- "legal_notes": any relevant legal considerations

Return ONLY the JSON object, nothing else."""

    try:
        provider = get_llm_provider()
        result = provider.complete_json(prompt=prompt, timeout=60)
        if isinstance(result, dict):
            return result
    except Exception as e:
        logger.error("check_probable_cause: %s", e)

    return {
        "has_probable_cause": None,
        "strength": "unknown",
        "factors_present": [],
        "factors_missing": ["Unable to analyze - Ollama may be unavailable"],
        "recommendations": ["Verify Ollama is running and try again"],
        "legal_notes": "",
    }


def suggest_statutes_from_narrative(narrative: str, limit: int = 5) -> List[Dict[str, Any]]:
    words = re.findall(r'[a-zA-Z]+', narrative.lower())
    word_freq = {}
    for w in words:
        if len(w) > 2:
            word_freq[w] = word_freq.get(w, 0) + 1

    scored = []
    for statute in WI_CRIMINAL_STATUTES:
        score = 0
        search_text = statute.get("keywords", "") + " " + statute["title"] + " " + statute.get("description", "")
        search_tokens = set(re.findall(r'[a-zA-Z]+', search_text.lower()))
        for token in search_tokens:
            if len(token) > 2:
                score += word_freq.get(token, 0)
        if score > 0:
            scored.append((score, statute))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"code": s["code"], "title": s["title"], "score": sc}
        for sc, s in scored[:limit]
    ]


def get_nibrs_for_statute(statute_code: str) -> str:
    nibrs_codes = nibrs_for_statute(statute_code)
    if nibrs_codes:
        return ",".join(nibrs_codes)
    return ""


def check_statute_elements(narrative_text: str, statute_code: str, model: str = OLLAMA_MODEL) -> Dict[str, Any]:
    from wi_statutes import WI_CRIMINAL_STATUTES
    statute = next((s for s in WI_CRIMINAL_STATUTES if s["code"] == statute_code), None)
    
    if not statute:
        return {
            "statute_code": statute_code,
            "error": "Statute not found in database",
            "elements_checked": []
        }
        
    prompt = f"""You are a strict legal compliance reviewer for law enforcement reports.

Analyze this narrative against the legal elements of Wisconsin Statute {statute['code']}: {statute['title']}
Description: {statute['description']}

NARRATIVE:
{narrative_text[:4000]}

Identify the specific legal elements required for this crime, and check if the narrative articulates facts to support EACH element.

Return a JSON object with:
- "statute_code": "{statute['code']}"
- "is_satisfied": boolean (true if all elements are clearly met, false if ANY are missing or weak)
- "elements_checked": array of objects, each containing:
    - "element": string (the legal requirement)
    - "met": boolean (true if facts support it)
    - "evidence": string (quote or summarize the facts from the narrative supporting it, or state "Missing")
- "override_warning": string (a strong warning message if is_satisfied is false, explaining why it might be kicked back by a supervisor)

Return ONLY the JSON object, nothing else."""

    try:
        provider = get_llm_provider()
        result = provider.complete_json(prompt=prompt, timeout=60)
        if isinstance(result, dict):
            return result
    except Exception as e:
        logger.error("check_statute_elements: %s", e)

    return {
        "statute_code": statute_code,
        "error": "Failed to analyze statute elements",
        "elements_checked": []
    }


if __name__ == '__main__':
    test_narrative = """
    On January 15, 2024, Officer Smith responded to a domestic disturbance at 123 Main Street.
    Upon arrival, the suspect had fled the scene. The victim reported being assaulted with a baseball bat.
    The suspect is a white male, approximately 6 feet tall, wearing a red jacket.
    Evidence was collected from the scene including the weapon.
    """
    
    warnings = check_nibrs_compliance("Standard Incident Report", test_narrative)
    print(format_compliance_report(warnings))
