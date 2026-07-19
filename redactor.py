import re
from typing import List, Tuple, Set, Optional


REDACTION_CATEGORIES = {
    "bank_account": {
        "label": "Bank & Routing Numbers",
        "description": "Routing #, account #, ABA, SWIFT",
        "patterns": [
            r'\b(?:Routing|ABA|ACH)\s*(?:#|Number|No\.?)\s*[:.]?\s*\b\d{9}\b',
            r'\b(?:Account)\s*(?:#|Number|No\.?)\s*[:.]?\s*\b\d{8,17}\b',
            r'\b(?:Bank|Institution)\s*(?:#|Number|No\.?)\s*[:.]?\s*\b\d{4,12}\b',
            r'\bSWIFT\s*(?:#|Code)?\s*[:.]?\s*\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b',
        ],
        "replace": "[REDACTED_BANK]",
    },
    "credit_card": {
        "label": "Credit Card Numbers",
        "description": "16-digit card numbers with optional spaces/dashes",
        "patterns": [
            r'(?<!\d)(?:\d{4}[-\s]?){3}\d{4}(?!\d)',
            r'(?<!\d)(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)',
        ],
        "replace": "[REDACTED_CARD]",
    },
    "drivers_license": {
        "label": "Driver's License Numbers",
        "description": "DL# formats: S123-4567-8901, 123456789012",
        "patterns": [
            r'\b(?:DL|Driver(?:s|\')? ?License|License)\s*(?:#|No\.?|Number)?\s*[:.]?\s*[A-Z]?\d{6,14}\b',
            r'\b(?:DL|Driver(?:s|\')? ?License|License)\s*(?:#|No\.?|Number)?\s*[:.]?\s*[A-Z]{1,2}\d{3,4}[-\s]?\d{4,6}[-\s]?\d{2,4}\b',
        ],
        "replace": "[REDACTED_DL]",
    },
    "medical_record": {
        "label": "Medical Record Numbers",
        "description": "MRN, patient ID",
        "patterns": [
            r'\b(?:MRN|Medical Record(?:s)?|Patient ?ID|Patient ?Number)\s*(?:#|No\.?|Number)?\s*[:.]?\s*[A-Z0-9]{6,15}\b',
        ],
        "replace": "[REDACTED_MRN]",
    },
    "ssn": {
        "label": "Social Security Numbers",
        "description": "123-45-6789, 123 45 6789, 987654321",
        "patterns": [
            r'(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)',
            r'(?<!\d)\d{3}\s\d{2}\s\d{4}(?!\d)',
            r'(?<!\d)\b\d{9}\b(?!\d)',
        ],
        "replace": "[REDACTED_SSN]",
    },
    "phone": {
        "label": "Phone Numbers",
        "description": "(555) 123-4567, 555-123-4567, 555.123.4567",
        "patterns": [
            r'(?<!\d)\(\d{3}\)\s?\d{3}[-.\s]?\d{4}(?!\d)',
            r'(?<!\d)\d{3}[-.\s]\d{3}[-.\s]\d{4}(?!\d)',
        ],
        "replace": "[REDACTED_PHONE]",
    },
    "email": {
        "label": "Email Addresses",
        "description": "user@domain.com",
        "patterns": [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        ],
        "replace": "[REDACTED_EMAIL]",
    },
    "name": {
        "label": "Person Names",
        "description": "Officer John Smith, stated that john doe, etc.",
        "patterns": [
            r'\b(?i:Officer|Det\.|Detective|Sgt\.|Sergeant|Lt\.|Lieutenant|Cpl\.|Corporal|Cpt\.|Captain|Chief|Deputy|Agent|Inspector|Trooper)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'\b(?i:Suspect|Victim|Witness|Complainant|Reporting Party|Subject|Involved Party)\s*[:,]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'\b(?i:Mr\.|Mrs\.|Ms\.|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'\b(?i:Contact)\s*[:,]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'\b(?i:Name|Name of (?:Suspect|Victim|Witness|Complainant|Subject))\s*[:,]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'\b(?i:Male|Female)\s+(?:Subject|Suspect|Victim|Witness)\s*[:,]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'\b(?i:stated that|contacted|registered to|identified as|spoke with|said|told|arrested|detained|interviewed|canvassed|observed|encountered|approached|located|notified|advised|informed|summoned|dispatched)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'\b(?i:vehicle registered to|registered owner)\s*[:,]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'\b([A-Z][a-z]+\'s)\s+(?i:residence|vehicle|home|apartment|statement|account|phone|cell)\b',
            r'\b(?i:of|by|with|from|via)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?i:who|was|were|had|did|has)',
        ],
        "replace": "[REDACTED_NAME]",
    },
    "dob": {
        "label": "Dates of Birth",
        "description": "DOB 01/15/1990, Date of Birth: 01-15-1990",
        "patterns": [
            r'\bDOB\s*[:=]?\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b',
            r'\b(?:Date of Birth|Birthday)\s*[:=]?\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b',
        ],
        "replace": "[REDACTED_DOB]",
    },
    "address": {
        "label": "Street Addresses",
        "description": "123 Main St, 456 Oak Avenue Blvd",
        "patterns": [
            r'\b\d{1,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:St(?:reet)?|Ave(?:nue)?|Blvd|Boulevard|Dr(?:ive)?|Rd|Road|Ln|Lane|Way|Ct|Court|Pl(?:ace)?|Pkwy|Parkway|Cir(?:cle)?)(?:\b|$)',
            r'\b\d{1,5}\s+[A-Z][a-z]+\s+[A-Z][a-z]+\s+(?:St(?:reet)?|Ave(?:nue)?|Blvd|Boulevard|Dr(?:ive)?|Rd|Road|Ln|Lane|Way|Ct|Court|Pl(?:ace)?|Pkwy|Parkway|Cir(?:cle)?)(?:\b|$)',
        ],
        "replace": "[REDACTED_ADDRESS]",
    },
    "juvenile": {
        "label": "Juvenile Names",
        "description": "Minor child / juvenile / child names",
        "patterns": [
            r'(?:minor child|juvenile suspect|juvenile victim|juvenile minor|juvenile)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'(?:child|kid|teen|adolescent|minor)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ],
        "replace": "[REDACTED_JUVENILE]",
        "flags": re.IGNORECASE,
    },
    "badge": {
        "label": "Badge / ID Numbers",
        "description": "Badge #4521, ID# 123456",
        "patterns": [
            r'[Bb]adge\s*#?\s*\d{2,6}\b',
            r'[Ii][Dd]\s*#?\s*\d{3,8}\b',
            r'\bOFF(?:ICER)?\s*(?:ID|#)\s*\d{3,6}\b',
        ],
        "replace": "[REDACTED_BADGE]",
    },
    "vin": {
        "label": "Vehicle Identification Numbers",
        "description": "17-character VIN (requires VIN/Vehicle ID context)",
        "patterns": [
            r'\b(?:VIN|Vehicle\s*(?:ID|#|Number)|Frame\s*#?|Chassis\s*#?)\s*[:.]?\s*[A-HJ-NPR-Z0-9]{17}\b',
            r'\b[A-HJ-NPR-Z0-9]{17}\b(?:\.?\s*(?:VIN|is\s+the\s+VIN))',
        ],
        "replace": "[REDACTED_VIN]",
    },
    "license_plate": {
        "label": "License Plates",
        "description": "Tag/Plate numbers (requires context word or 6+ chars)",
        "patterns": [
            r'\b(?:Plate|Tag|License|LP|Registration)\s*#?\s*[:.]?\s*(?:[A-Z]{2,4}[-\s]?\d{3,4}|\d{3,4}[-\s]?[A-Z]{2,4})\b',
            r'\b(?:[A-Z]{2,4}[-\s]?\d{4,6}|\d{4,6}[-\s]?[A-Z]{2,4})\b',
        ],
        "replace": "[REDACTED_LICENSE_PLATE]",
    },
}


def sanitize_pii_content(raw_text: str, categories: Optional[Set[str]] = None) -> str:
    text = raw_text
    active = categories if categories else set(REDACTION_CATEGORIES.keys())

    for cat_id, cat_info in REDACTION_CATEGORIES.items():
        if cat_id not in active:
            continue
        flags = cat_info.get("flags", 0)
        for pattern in cat_info["patterns"]:
            text = re.sub(pattern, cat_info["replace"], text, flags=flags)

    return text


def get_redaction_report(original: str, redacted: str) -> List[Tuple[str, str]]:
    if original == redacted:
        return []
    changes = []
    orig_lines = original.split('\n')
    red_lines = redacted.split('\n')
    max_len = max(len(orig_lines), len(red_lines))
    for i in range(max_len):
        orig = orig_lines[i].strip() if i < len(orig_lines) else ""
        red = red_lines[i].strip() if i < len(red_lines) else ""
        if orig != red:
            changes.append((orig, red))
    return changes


if __name__ == '__main__':
    test = """Officer John Smith (Badge #4521) responded to 123 Main Street.
Contact: Jane Doe, DOB 01/15/1990, (555) 123-4567
Email: jane.doe@email.com
SSN: 123-45-6789
Minor child Tommy Smith was present.
Juvenile suspect Mike Johnson was detained.
Victim: Robert Jones, 456 Oak Avenue.
On 01/15/2024, Officer Smith stated that john doe contacted 911.
Vehicle registered to: Alice Williams, VIN 1HGBH41JXMN109186, plate ABC-1234.
DL# S123-4567-8901, MRN #987654, Routing #123456789
Card: 4532-1234-5678-9012
Bare SSN: 987654321"""
    print(sanitize_pii_content(test))
