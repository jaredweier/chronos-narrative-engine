from typing import Optional, Dict
from database import get_incident
from logger import get_logger

logger = get_logger(__name__)


def get_similar_case_data(incident_id: str) -> Optional[Dict]:
    incident = get_incident(incident_id)
    if not incident:
        return None
    result = {
        "incident_id": incident.get("incident_id", ""),
        "officer_name": incident.get("officer_name", ""),
        "document_type": incident.get("document_type", ""),
        "report_text": incident.get("final_approved_report") or incident.get("unedited_ai_draft", ""),
        "modified": bool(incident.get("was_modified_by_human")),
    }
    logger.info("Loaded similar case data from %s", incident_id)
    return result


def apply_similar_case_template(report_text: str, target_officer: str) -> str:
    if not report_text:
        return ""
    import re
    lines = report_text.split("\n")
    cleaned = []
    skip_prefixes = [
        "incident", "case", "report", "narrative", "officer:", "badge",
        "date:", "inc #", "case #", "incident #",
    ]
    for line in lines:
        stripped = line.strip().lower()
        if not stripped:
            continue
        skip = False
        for prefix in skip_prefixes:
            if stripped.startswith(prefix):
                skip = True
                break
        if not skip:
            cleaned.append(line)
    return "\n".join(cleaned)


if __name__ == '__main__':
    sample = """Incident #: INC-001
Officer: John Smith
Badge: B1234
Date: 2026-07-11

On the above date I responded to a call of a disturbance.
Upon arrival I made contact with the subject."""
    print("Original:")
    print(sample)
    print("\nCleaned:")
    print(apply_similar_case_template(sample, "TestOfficer"))
