import json
import re
import requests
from typing import List, Dict, Any
from config import OLLAMA_API_ENDPOINT, OLLAMA_MODEL, LLM_COMPLIANCE_OPTIONS, LLM_COMPLIANCE_TIMEOUT
from logger import get_logger

logger = get_logger(__name__)


def _extract_json(text: str) -> str:
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text)
    for open_char, close_char in [("[", "]"), ("{", "}")]:
        start = text.find(open_char)
        if start >= 0:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == open_char:
                    depth += 1
                elif text[i] == close_char:
                    depth -= 1
                    if depth == 0:
                        return text[start:i+1]
    return ""


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
        response = requests.post(
            OLLAMA_API_ENDPOINT,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": LLM_COMPLIANCE_OPTIONS
            },
            timeout=LLM_COMPLIANCE_TIMEOUT
        )
        response.raise_for_status()
        
        result = response.json()
        response_text = result.get("response", "")
        
        json_str = _extract_json(response_text)
        if json_str and json_str[0] == '[':
            return json.loads(json_str)
        
        return []
        
    except requests.RequestException as e:
        logger.error("NIBRS check network error: %s", e)
        return [{
            "element": "system_error",
            "severity": "warning",
            "message": f"NIBRS check could not be completed: {str(e)}",
            "suggestion": "Verify Ollama is running and Llama 3.1:8b is available"
        }]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error("NIBRS check parse error: %s", e)
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
        matches = sum(1 for kw in keywords if kw in narrative_lower)
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

        response = requests.post(
            OLLAMA_API_ENDPOINT,
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": LLM_COMPLIANCE_OPTIONS},
            timeout=LLM_COMPLIANCE_TIMEOUT
        )
        response.raise_for_status()
        text = response.json().get("response", "")
        json_str = _extract_json(text)
        if json_str and json_str[0] == '[':
            return json.loads(json_str)
    except requests.RequestException as e:
        logger.error("Missing fields net error: %s", e)
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug("Missing fields parse error: %s", e)
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
        response = requests.post(
            OLLAMA_API_ENDPOINT,
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": LLM_COMPLIANCE_OPTIONS},
            timeout=LLM_COMPLIANCE_TIMEOUT
        )
        response.raise_for_status()
        text = response.json().get("response", "")
        json_str = _extract_json(text)
        if json_str and json_str[0] == '{':
            return json.loads(json_str)
    except requests.RequestException as e:
        logger.error("Probable cause net error: %s", e)
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug("Probable cause parse error: %s", e)
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


if __name__ == '__main__':
    test_narrative = """
    On January 15, 2024, Officer Smith responded to a domestic disturbance at 123 Main Street.
    Upon arrival, the suspect had fled the scene. The victim reported being assaulted with a baseball bat.
    The suspect is a white male, approximately 6 feet tall, wearing a red jacket.
    Evidence was collected from the scene including the weapon.
    """
    
    warnings = check_nibrs_compliance("Standard Incident Report", test_narrative)
    print(format_compliance_report(warnings))
