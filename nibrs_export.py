import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, Dict, Any


def _safe_text(val: Any) -> str:
    if val is None:
        return ""
    return str(val)


def _xml_element(parent: ET.Element, tag: str, text: str = "") -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = _safe_text(text)
    return el


def build_nibrs_xml(
    incident_id: str = "",
    agency_ori: str = "CH999999",
    agency_name: str = "Chronos Police Department",
    officer_name: str = "",
    officer_id: str = "",
    report_type: str = "",
    narrative: str = "",
    call_id: str = "",
    call_type: str = "",
    location: str = "",
    dispatch_time: str = "",
    arrival_time: str = "",
    clear_time: str = "",
    involved_parties: Optional[list] = None,
    nibrs_offense_code: str = "",
    location_type: str = "01",
    weapon_force: str = "",
) -> str:
    root = ET.Element("NIBRS_Submission")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("version", "3.3")

    now = datetime.now().isoformat()

    _xml_element(root, "SubmissionTimestamp", now)
    _xml_element(root, "AgencyORI", agency_ori)
    _xml_element(root, "AgencyName", agency_name)

    incident = ET.SubElement(root, "Incident")
    _xml_element(incident, "IncidentNumber", incident_id)
    _xml_element(incident, "IncidentDate", datetime.now().strftime("%Y-%m-%d"))
    _xml_element(incident, "IncidentTime", datetime.now().strftime("%H:%M:%S"))
    _xml_element(incident, "ReportType", report_type)
    _xml_element(incident, "NIBRSOffenseCode", nibrs_offense_code if nibrs_offense_code else _map_call_type_to_nibrs(call_type))
    _xml_element(incident, "LocationType", location_type)
    _xml_element(incident, "Location", location)

    if officer_name:
        ofc = ET.SubElement(incident, "ReportingOfficer")
        _xml_element(ofc, "OfficerName", officer_name)
        _xml_element(ofc, "BadgeNumber", officer_id)

    if dispatch_time:
        times = ET.SubElement(incident, "Timeline")
        _xml_element(times, "DispatchTime", dispatch_time)
        _xml_element(times, "ArrivalTime", arrival_time)
        _xml_element(times, "ClearTime", clear_time)

    if involved_parties:
        parties_elem = ET.SubElement(incident, "InvolvedParties")
        for party in involved_parties:
            p = ET.SubElement(parties_elem, "Party")
            _xml_element(p, "Name", party.get("name", ""))
            _xml_element(p, "DOB", party.get("dob", ""))
            _xml_element(p, "Sex", party.get("sex", ""))
            _xml_element(p, "Age", party.get("age", ""))

    if weapon_force:
        _xml_element(incident, "WeaponForce", weapon_force)

    if narrative:
        narrative_elem = ET.SubElement(incident, "Narrative")
        narrative_elem.text = narrative

    call_info = ET.SubElement(incident, "CADInformation")
    _xml_element(call_info, "CADCallID", call_id)
    _xml_element(call_info, "CADCallType", call_type)

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode")


NIBRS_2025_OFFENSES: dict[str, str] = {
    "09A": "Murder/Nonnegligent Manslaughter",
    "09B": "Negligent Manslaughter",
    "09C": "Justifiable Homicide",
    "10A": "Kidnapping/Abduction",
    "11A": "Rape",
    "11B": "Sodomy",
    "11C": "Sexual Assault With An Object",
    "11D": "Fondling",
    "12A": "Robbery",
    "13A": "Aggravated Assault",
    "13B": "Simple Assault",
    "13C": "Intimidation",
    "20A": "Arson",
    "21A": "Extortion/Blackmail",
    "22A": "Burglary/Breaking & Entering",
    "22B": "Burglary (Attempted)",
    "23A": "Pocket-picking",
    "23B": "Purse-snatching",
    "23C": "Shoplifting",
    "23D": "Theft From Building",
    "23E": "Theft From Coin-Operated Machine",
    "23F": "Theft From Motor Vehicle",
    "23G": "Theft Of Motor Vehicle Parts/Accessories",
    "23H": "All Other Larceny",
    "24A": "Motor Vehicle Theft",
    "24B": "Motor Vehicle Theft (Attempted)",
    "26A": "Counterfeiting/Forgery",
    "26B": "Fraud (False Pretenses)",
    "26C": "Fraud (Credit Card/ATM)",
    "26D": "Fraud (Impersonation)",
    "26E": "Welfare Fraud",
    "26F": "Wire Fraud",
    "30A": "Embezzlement",
    "35A": "Drug/Narcotic Violations",
    "35B": "Drug Equipment Violations",
    "36A": "Bribery",
    "39A": "Gambling (Betting/Wagering)",
    "39B": "Gambling (Operating/Promoting)",
    "39C": "Gambling (Gambling Equipment)",
    "39D": "Gambling (Sports Tampering)",
    "40A": "Prostitution",
    "40B": "Prostitution (Promoting)",
    "40C": "Prostitution (Purchasing)",
    "48A": "Stolen Property (Receiving/Fencing)",
    "52A": "Weapon Law Violations",
    "64A": "Missing Person/Kidnapped Person",
    "70A": "Sex Offender (Failure to Register)",
    "71A": "Drug/Narcotic (Sale/Distribution)",
    "72A": "Animal Cruelty",
    "90A": "Bad Checks",
    "90B": "Curfew/Loitering/Vagrancy Violations",
    "90C": "Disorderly Conduct",
    "90D": "Driving Under The Influence",
    "90E": "Drunkenness",
    "90F": "Family Offenses (Nonviolent)",
    "90G": "Federal Offenses",
    "90H": "Health/Safety Code Violations",
    "90I": "Immigration Violations",
    "90J": "Import/Export Violations",
    "90K": "Liquor Law Violations",
    "90L": "Peeping Tom",
    "90M": "Runaway",
    "90N": "Suicide (Attempted)",
    "90O": "Trespass Of Real Property",
    "90P": "Trespass Of Motor Vehicle Or Boat",
    "90Q": "All Other Offenses",
    "90R": "Commercialized Vice (Promoting)",
    "90S": "Contempt Of Court",
    "90T": "Failure To Appear",
    "90U": "Harassment/Stalking",
    "90V": "Harboring A Fugitive",
    "90W": "Littering",
    "90X": "Obstructing Justice/Resisting Arrest",
    "90Y": "Traffic Violation (Non-DUI)",
    "90Z": "NIBRS Error Code (Miscode)",
    "99Z": "Unknown/Not Applicable",
}

LOCATION_TYPES: dict[str, str] = {
    "01": "Air/Bus/Train Terminal",
    "02": "Bank/Savings And Loan",
    "03": "Bar/Nightclub",
    "04": "Church/Synagogue/Temple",
    "05": "Commercial/Office Building",
    "06": "Construction Site",
    "07": "Convenience Store",
    "08": "Department/Discount Store",
    "09": "Drug Store/Doctor's Office/Hospital",
    "10": "Field/Woods",
    "11": "Government/Public Building",
    "12": "Grocery/Supermarket",
    "13": "Highway/Road/Alley",
    "14": "Hotel/Motel",
    "15": "Jail/Prison",
    "16": "Lake/Waterway",
    "17": "Parking Lot/Garage",
    "18": "Rental Storage Facility",
    "19": "Residence/Home",
    "20": "Restaurant",
    "21": "School/College",
    "22": "Service/Gas Station",
    "23": "Specialty Store (TV, Fur, etc.)",
    "24": "Other/Unknown",
    "25": "Military Installation",
    "26": "Park/Playground",
    "27": "Shelter (Homeless, Domestic Violence)",
    "28": "Daycare Facility",
    "29": "Gambling Facility/Casino",
}


def lookup_nibrs_code(code: str) -> str:
    return NIBRS_2025_OFFENSES.get(code.upper(), f"Unknown code: {code}")


def lookup_location_type(code: str) -> str:
    return LOCATION_TYPES.get(code, f"Unknown code: {code}")


def validate_nibrs_xml(xml_str: str) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as e:
        return [{"severity": "critical", "field": "xml_structure", "message": f"XML parse error: {e}"}]

    required_top = ["SubmissionTimestamp", "AgencyORI", "AgencyName"]
    for tag in required_top:
        if root.find(tag) is None:
            errors.append({"severity": "critical", "field": tag, "message": f"Missing required element: {tag}"})

    incident = root.find("Incident")
    if incident is None:
        errors.append({"severity": "critical", "field": "Incident", "message": "Missing Incident element"})
        return errors

    required_incident = ["IncidentNumber", "IncidentDate", "IncidentTime", "NIBRSOffenseCode"]
    for tag in required_incident:
        el = incident.find(tag)
        if el is None or not el.text:
            errors.append({"severity": "critical", "field": tag, "message": f"Missing or empty: {tag}"})

    offense_el = incident.find("NIBRSOffenseCode")
    if offense_el is not None and offense_el.text:
        code = offense_el.text.strip().upper()
        if code not in NIBRS_2025_OFFENSES:
            errors.append({"severity": "warning", "field": "NIBRSOffenseCode", "message": f"Unrecognized NIBRS offense code: {code}"})

    if incident.find("ReportingOfficer") is None:
        errors.append({"severity": "warning", "field": "ReportingOfficer", "message": "Missing ReportingOfficer element"})

    narrative_el = incident.find("Narrative")
    if narrative_el is None or not narrative_el.text:
        errors.append({"severity": "warning", "field": "Narrative", "message": "Narrative is empty"})

    parties = incident.find("InvolvedParties")
    if parties is not None:
        for party in parties.findall("Party"):
            name = party.find("Name")
            if name is None or not name.text:
                errors.append({"severity": "warning", "field": "Party.Name", "message": "Party missing name"})

    return errors


_CALL_TYPE_WORDS: dict[re.Pattern, str] = {}


def _build_call_type_patterns():
    if _CALL_TYPE_WORDS:
        return
    raw = {
        "theft": "23F", "burglary": "22A", "robbery": "12A",
        "assault": "13A", "battery": "13A", "domestic": "13A",
        "homicide": "09A", "murder": "09A", "death": "09A/09D",
        "rape": "11A", "sexual": "11A", "arson": "20A", "fire": "20A",
        "vandalism": "24A", "drug": "35A", "narcotics": "35A",
        "dui": "90D", "owi": "90D",
        "traffic": "90Y", "accident": "90Y", "crash": "90Y",
        "warrant": "90S", "trespass": "90O", "disorderly": "90C",
        "weapon": "52A", "fraud": "26B", "missing": "64A",
        "suicide": "90N", "mental": "90Q", "welfare": "90Q",
        "kidnap": "10A", "stalking": "90U", "harassment": "90U",
        "prostitution": "40A", "embezzle": "30A", "bribery": "36A",
    }
    for word, code in raw.items():
        _CALL_TYPE_WORDS[re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)] = code


def _map_call_type_to_nibrs(call_type: str) -> str:
    if not call_type:
        return "99Z"
    _build_call_type_patterns()
    for pattern, code in _CALL_TYPE_WORDS.items():
        if pattern.search(call_type):
            return code
    return "99Z"


def export_nibrs_xml(
    incidents: list[Dict[str, Any]],
    agency_ori: str = "CH999999",
    agency_name: str = "Chronos Police Department",
) -> str:
    root = ET.Element("NIBRS_Batch")
    root.set("version", "3.3")
    _xml_element(root, "AgencyORI", agency_ori)
    _xml_element(root, "AgencyName", agency_name)
    _xml_element(root, "BatchDate", datetime.now().isoformat())
    _xml_element(root, "RecordCount", str(len(incidents)))

    for incident in incidents:
        inc_root = ET.Element("NIBRS_Submission")
        inc_root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        inc_root.set("version", "3.3")
        _xml_element(inc_root, "SubmissionTimestamp", datetime.now().isoformat())
        _xml_element(inc_root, "AgencyORI", agency_ori)
        _xml_element(inc_root, "AgencyName", agency_name)
        inc_incident = ET.SubElement(inc_root, "Incident")
        _xml_element(inc_incident, "IncidentNumber", incident.get("incident_id", ""))
        _xml_element(inc_incident, "IncidentDate", datetime.now().strftime("%Y-%m-%d"))
        _xml_element(inc_incident, "IncidentTime", datetime.now().strftime("%H:%M:%S"))
        _xml_element(inc_incident, "ReportType", incident.get("document_type", ""))
        _xml_element(inc_incident, "NIBRSOffenseCode", incident.get("nibrs_offense_code", ""))
        _xml_element(inc_incident, "Location", incident.get("location", ""))
        ofc = ET.SubElement(inc_incident, "ReportingOfficer")
        _xml_element(ofc, "OfficerName", incident.get("officer_name", ""))
        _xml_element(ofc, "BadgeNumber", incident.get("officer_id", ""))
        narrative_text = incident.get("final_approved_report", incident.get("unedited_ai_draft", ""))
        if narrative_text:
            _xml_element(inc_incident, "Narrative", narrative_text)
        root.append(inc_root)

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode")


def get_nibrs_quality_stats(submissions: list[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(submissions)
    if total == 0:
        return {"total": 0, "with_nibrs_code": 0, "with_narrative": 0, "with_officer": 0, "completeness_pct": 0}

    with_code = sum(1 for s in submissions if s.get("nibrs_offense_code", "").strip())
    with_narrative = sum(1 for s in submissions if s.get("final_approved_report") or s.get("unedited_ai_draft"))
    with_officer = sum(1 for s in submissions if s.get("officer_name", "").strip())
    code_valid = sum(1 for s in submissions if s.get("nibrs_offense_code", "").upper() in NIBRS_2025_OFFENSES)
    completeness = round((with_code + with_narrative + with_officer) / (total * 3) * 100, 1)

    return {
        "total": total,
        "with_nibrs_code": with_code,
        "code_valid": code_valid,
        "with_narrative": with_narrative,
        "with_officer": with_officer,
        "completeness_pct": completeness,
    }
