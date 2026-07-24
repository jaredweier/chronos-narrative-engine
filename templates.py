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
    "Domestic Violence Supplement": {
        "description": "Wisconsin-mandated domestic violence incident supplement with victim notification and DWJ referral documentation",
        "sections": [
            ("Incident Overview", "Date, time, location, type of domestic abuse (physical, verbal, emotional, sexual, threats)"),
            ("Relationship of Parties", "Current/past relationship between suspect and victim (spouse, ex-spouse, cohabitant, dating, familial, parental)"),
            ("Victim Statement", "Detailed account from victim including history of abuse, prior incidents, and immediate safety concerns"),
            ("Suspect Statement", "Suspect's account of events including any admissions or denials"),
            ("Injuries & Medical Treatment", "Documentation of visible injuries, photos taken, medical treatment provided or refused, body map reference"),
            ("Weapons or Dangerous Instruments", "Any weapons used, threatened, or present during incident (firearms, knives, household objects, fists)"),
            ("Witness Statements", "Statements from any witnesses including neighbor accounts and children present"),
            ("Victim Notification & Resources", "Documentation of rights notification provided, Wisconsin Domestic Violence referral form, shelter/advocate contact information provided"),
            ("Mandatory Arrest Determination", "Analysis of probable cause for mandatory arrest under WI 968.075(2), including visible injury, imminent threat, violation of restraining order"),
            ("Children Present", "Names, ages, and disposition of any children who witnessed the incident; CPS notification if applicable"),
            ("Disposition & Charges", "Recommended charges, arrests made, restraining order requested, DWJ referral completed"),
        ],
        "prompt_prefix": "Write a domestic violence supplement report per Wisconsin standards. Include victim notification documentation, mandatory arrest analysis, and DWJ referral information:",
    },
    "Juvenile Offense Report": {
        "description": "Report for incidents involving juvenile suspects (under 18) under Wisconsin juvenile justice jurisdiction",
        "sections": [
            ("Juvenile Information", "Full name, date of birth, address, school, grade, parent/guardian name and contact information"),
            ("Incident Details", "Date, time, location, nature of offense, circumstances of contact"),
            ("Parent/Guardian Notification", "Date, time, and method of parent/guardian notification; name of person notified"),
            ("Offense Description", "Detailed description of the alleged offense including WI statute violated"),
            ("Co-offenders", "Names and DOBs of any other juveniles or adults involved"),
            ("Witness Statements", "Witness accounts including other juveniles, school staff, or community members"),
            ("Property Involved", "Description of any property stolen, damaged, or recovered; value; disposition"),
            ("Evidence Collected", "Physical evidence, photographs, video footage, statements documented"),
            ("Disposition", "Warn and release, citation issued, referral to juvenile court intake, detention, or alternative program"),
            ("School Liaison Notification", "If school-related incident, document notification to school resource officer or administration"),
        ],
        "prompt_prefix": "Write a juvenile offense report. Use appropriate language for juvenile matters per Wisconsin juvenile justice procedures:",
    },
    "Missing Person Report": {
        "description": "Missing person incident documentation including NCIC entry verification and search efforts",
        "sections": [
            ("Missing Person Information", "Full name, date of birth, age, sex, race, height, weight, hair color, eye color, build, complexion, distinguishing features (scars, tattoos, piercings, glasses)"),
            ("Last Seen Information", "Date, time, location last seen, what they were wearing, what they were carrying, direction of travel"),
            ("Circumstances of Disappearance", "Circumstances leading up to disappearance, mental/physical state, any known triggers (arguments, stress, medication changes)"),
            ("Vehicle Information", "Make, model, year, color, license plate, VIN, any known destination or route"),
            ("Medical & Mental Health", "Medical conditions, medications, mental health history, suicidal ideation, substance abuse, special needs or disabilities"),
            ("Contact & Associates", "Family contacts, friends, associates, known hangouts, social media accounts, phone number and carrier"),
            ("NCIC Entry", "NCIC entry number, date and time entered, entering agency ORI, records verification completed"),
            ("Search Efforts", "Canvass of area, K9 track, aerial search, water search, hospital checks, shelter checks, public transit authority contacted"),
            ("Media & Public Notification", "Media notification (date/time), social media posts, reverse 911 calls, fliers distributed, Silver/Amber Alert criteria evaluated"),
            ("Follow-Up Plan", "Assigned investigator, next steps, family contact schedule, multi-agency coordination if applicable"),
        ],
        "prompt_prefix": "Write a missing person report. Include NCIC entry verification, search efforts, and all identifying information:",
    },
    "Narcotics Incident Report": {
        "description": "Drug-related incident documentation including seizure details, field test results, and chain of custody",
        "sections": [
            ("Incident Overview", "Date, time, location, type of drug incident (possession, manufacture, delivery, trafficking, paraphernalia)"),
            ("Suspect Information", "Name, DOB, address, description, known gang affiliations, drug-related history"),
            ("Drugs Seized", "Type of controlled substance, quantity/weight, packaging, estimated street value, field test results and reagent used"),
            ("Paraphernalia Seized", "Description of paraphernalia (pipes, syringes, scales, baggies, cutting agents, manufacturing equipment)"),
            ("Currency & Assets", "Currency seized (amount, denominations, packaging), vehicle, real estate, or other assets subject to forfeiture"),
            ("Evidence Collected", "Evidence item numbers, description of each item, collection method, packaging, chain of custody documentation"),
            ("Witness & Informant Information", "Witness statements, confidential informant details (confidential per DOJ guidelines), controlled buy documentation if applicable"),
            ("Lab Submission", "Submission to Wisconsin State Crime Lab (date, item numbers, lab case number, requested analysis)"),
            ("Charges & Disposition", "Recommended charges with WI statute citations, arrest or summons, bail recommendation, forfeiture proceeding initiation"),
        ],
        "prompt_prefix": "Write a narcotics incident report. Document drug seizures, field test results, evidence chain of custody, and recommended charges:",
    },
    "Sexual Assault Kit (SAK) Documentation": {
        "description": "Sexual assault evidence collection kit documentation per Wisconsin DOJ standards and victim rights compliance",
        "sections": [
            ("Incident Overview", "Date, time, and location of assault; date/time of report; responding officer information"),
            ("Victim Information", "Victim name, age, DOB, address, contact information, preferred language, interpreter needed (Y/N)"),
            ("Assault Details", "Narrative of assault including location type, relationship to suspect, specific acts alleged, use of force or weapons, threats made"),
            ("Medical Screening", "Hospital/Forensic Examiner facility name, SANE/SART nurse name, date/time of exam, medical clearance obtained"),
            ("Evidence Collection Kit", "SAK serial number, collection facility, examiner name, kit type (adult/pediatric), collection date/time"),
            ("Chain of Custody", "Each transfer of kit: from examiner to law enforcement (name/badge/date/time), to evidence locker, to crime lab submission"),
            ("Victim Rights Notification", "Victim informed of rights per WI 950.04 and 949.07, information provided about sexual assault advocate services, compensation fund information provided"),
            ("Suspect Information", "Suspect name, DOB, address, relationship to victim, DNA sample collected (Y/N/warrant status), known prior offenses"),
            ("Supporting Evidence", "Clothing collected, bedding, photographs, 911 recording, text messages, social media evidence, surveillance video, witness statements"),
            ("Law Enforcement Agency Information", "Agency name, ORI, case number, assigned detective, multi-jurisdictional coordination if applicable"),
        ],
        "prompt_prefix": "Write a sexual assault kit documentation report per Wisconsin DOJ standards. Include chain of custody, victim rights notification, and supporting evidence:",
    },
}


def get_template(report_type: str) -> dict:
    return REPORT_TEMPLATES.get(report_type, {})


def get_template_sections(report_type: str) -> list:
    template = REPORT_TEMPLATES.get(report_type, {})
    return template.get("sections", [])


def get_all_template_types() -> list:
    return list(REPORT_TEMPLATES.keys())


def get_all_templates() -> dict:
    return dict(REPORT_TEMPLATES)


def save_template(key: str, description: str, sections_text: str) -> bool:
    if not key or not description or not sections_text:
        return False
    sections = []
    for line in sections_text.strip().split("\n"):
        line = line.strip()
        if "|" in line:
            title, hint = line.split("|", 1)
            sections.append((title.strip(), hint.strip()))
        elif line:
            sections.append((line, ""))
    REPORT_TEMPLATES[key] = {"description": description, "sections": sections}
    return True


def render_template_prompt(report_type: str) -> str:
    template = REPORT_TEMPLATES.get(report_type)
    if not template:
        return ""
    lines = [template["prompt_prefix"]]
    for section_title, section_hint in template["sections"]:
        lines.append(f"\n## {section_title}")
        lines.append(f"({section_hint})")
    return "\n".join(lines)
