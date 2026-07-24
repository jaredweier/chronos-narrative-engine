from typing import List, Optional, Any
from pydantic import BaseModel, Field

class NCLocation(BaseModel):
    location_description_text: Optional[str] = Field(default=None, alias="nc:LocationDescriptionText")
    location_name: Optional[str] = Field(default=None, alias="nc:LocationName")

class JCharge(BaseModel):
    charge_description_text: Optional[str] = Field(default=None, alias="j:ChargeDescriptionText")
    charge_severity_text: Optional[str] = Field(default=None, alias="j:ChargeSeverityText")

class JArrest(BaseModel):
    arrest_agency_record_identification: Optional[Any] = Field(default=None, alias="j:ArrestAgencyRecordIdentification")
    arrest_charge: Optional[List[JCharge]] = Field(default_factory=list, alias="j:ArrestCharge")

class NCIncident(BaseModel):
    activity_identification: Optional[Any] = Field(default=None, alias="nc:ActivityIdentification")
    activity_category_text: Optional[str] = Field(default=None, alias="nc:ActivityCategoryText")
    incident_location: Optional[NCLocation] = Field(default=None, alias="nc:IncidentLocation")

class NIEMPayload(BaseModel):
    incident: Optional[NCIncident] = Field(default=None, alias="nc:Incident")
    arrest: Optional[JArrest] = Field(default=None, alias="j:Arrest")

def parse_niem_incident(payload: dict) -> dict:
    parsed = NIEMPayload(**payload)
    call_id = None
    call_type = None
    location_str = None
    if parsed.incident:
        if parsed.incident.activity_identification:
            ident = parsed.incident.activity_identification
            if isinstance(ident, dict):
                call_id = ident.get("nc:IdentificationID")
            else:
                call_id = str(ident)
        call_type = parsed.incident.activity_category_text
        if parsed.incident.incident_location:
            loc = parsed.incident.incident_location
            if loc.location_description_text:
                location_str = loc.location_description_text
            elif loc.location_name:
                location_str = loc.location_name
    charges = []
    if parsed.arrest and parsed.arrest.arrest_charge:
        for charge in parsed.arrest.arrest_charge:
            desc = charge.charge_description_text
            sev = charge.charge_severity_text
            if desc:
                if sev:
                    charges.append(f"{desc} ({sev})")
                else:
                    charges.append(desc)
    return {
        "call_id": call_id,
        "call_type": call_type,
        "location": location_str,
        "charges": charges
    }
