REPORT_TEMPLATES = {
    "Standard Incident Report": {
        "description": "General incident report for crimes, disturbances, and calls for service",
        "sections": [
            ("Incident Overview", "Date/time of incident, location, reporting officer, case number"),
            ("Response", "Dispatch time, arrival time, units assigned, initial observations on scene"),
            ("Scene Description", "Physical description of the scene, weather conditions, lighting, evidence of disturbance"),
            ("Victim Information", "Name, DOB, contact information, statement summary, injuries observed"),
            ("Suspect Information", "Name, DOB, physical description, relationship to victim, direction of travel if fled"),
            ("Witness Information", "Names, contact info, brief statements from each witness"),
            ("Evidence Collected", "Items collected, photographs taken, fingerprints, DNA swabs, surveillance footage"),
            ("Investigation", "Actions taken, interviews conducted, canvas of area, records checked"),
            ("NIBRS Elements", "Offense code, location type, weapon/force involved, property descriptions"),
            ("Disposition", "Arrest made, citations issued, case referred, evidence logged, scene cleared"),
        ],
        "prompt_prefix": "Write a standard incident report. Use formal police report language, past tense. Structure with these sections:",
    },
    "Search Warrant Affidavit": {
        "description": "Affidavit supporting application for search warrant",
        "sections": [
            ("Affiant Identification", "Officer name, badge number, agency, training/experience"),
            ("Target Location", "Full address, description of premises, known occupants"),
            ("Probable Cause Statement", "Facts establishing probable cause, observations, informant information, prior investigation"),
            ("Items to Be Seized", "Specific items sought and their relation to the criminal investigation"),
            ("Prior Investigation", "Timeline of events leading to warrant application, surveillance, interviews"),
            ("Source Reliability", "If informant used: basis of reliability, track record, corroboration"),
            ("Requested Authority", "Type of search requested (premises, person, vehicle, digital)"),
        ],
        "prompt_prefix": "Write a search warrant affidavit. Use formal legal language. The affidavit must establish probable cause and be structured for judicial review:",
    },
    "Internal Use-of-Force Review": {
        "description": "Internal affairs use-of-force incident review documentation",
        "sections": [
            ("Officer Identification", "Name, badge number, assignment, years of service, relevant training"),
            ("Subject Identification", "Name, DOB, physical description, disposition of subject"),
            ("Incident Summary", "Date, time, location, call type, narrative of events leading to force"),
            ("Force Used", "Specific technique(s), duration, whether subject was compliant at each stage"),
            ("Injuries", "Injuries to subject, injuries to officer, medical treatment provided/denied"),
            ("De-escalation Attempts", "Verbal commands, time given to comply, alternatives considered before force"),
            ("Body Camera Status", "Recording status, camera angles captured, footage preserved"),
            ("Witness Officers", "Other officers present, their observations, actions taken"),
            ("Supervisor Response", "Notification time, on-scene review, evidence collected, subject condition"),
            ("Policy Compliance", "Assessment against department use-of-force policy, training standards"),
        ],
        "prompt_prefix": "Write an internal use-of-force review. Be objective and factual. Document all actions chronologically. Do not render conclusions - present facts only:",
    },
    "OWI / DUI Report": {
        "description": "Operating While Intoxicated / Driving Under the Influence report",
        "sections": [
            ("Traffic Stop", "Time, location, reason for stop, vehicle description, driving behavior observed"),
            ("Officer Observations", "Odor of alcohol/drugs, slurred speech, bloodshot eyes, demeanor, fumbling"),
            ("Field Sobriety Tests", "Tests administered, conditions (road surface, weather, lighting), subject performance"),
            ("Preliminary Breath Test", "Result, device used, administration procedure"),
            ("Chemical Test", "Breath/blood/urine result, test date/time, agency used, refusal if applicable"),
            ("Vehicle Information", "Make, model, year, plate, registration status, insurance, condition"),
            ("Subject Information", "Name, DOB, license status (valid/suspended/revoked), prior OWI history"),
            ("Miranda Rights", "Time administered, subject responses, invoked or waived"),
            ("Arrest & Processing", "Time of arrest, transport, booking, property inventoried, vehicle impounded"),
            ("Disposition", "Charges filed, bond conditions, DMV notification, ignition interlock recommended"),
        ],
        "prompt_prefix": "Write an OWI/DUI report. Be precise about times, measurements, and test results. Use standard DUI report terminology:",
    },
}


def get_template(report_type: str) -> dict:
    return REPORT_TEMPLATES.get(report_type, {})


def get_template_sections(report_type: str) -> list:
    template = REPORT_TEMPLATES.get(report_type, {})
    return template.get("sections", [])


def get_all_template_types() -> list:
    return list(REPORT_TEMPLATES.keys())


def render_template_prompt(report_type: str) -> str:
    template = REPORT_TEMPLATES.get(report_type)
    if not template:
        return ""
    lines = [template["prompt_prefix"]]
    for section_title, section_hint in template["sections"]:
        lines.append(f"\n## {section_title}")
        lines.append(f"({section_hint})")
    return "\n".join(lines)
