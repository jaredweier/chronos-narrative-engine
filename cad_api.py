import requests
import json
from typing import Dict, Any, Optional
from config import _env
from logger import get_logger

logger = get_logger(__name__)

# Constants
ZUERCHER_API_URL = _env("CHRONOS_ZUERCHER_API_URL", "http://localhost:8501/mock-zuercher/api/v1")
ZUERCHER_API_KEY = _env("CHRONOS_ZUERCHER_API_KEY", "mock_key")

def fetch_incident_from_zuercher(incident_id: str) -> Optional[Dict[str, Any]]:
    """
    Connects to the Zuercher CAD REST API and retrieves the structured incident data.
    """
    headers = {
        "Authorization": f"Bearer {ZUERCHER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    endpoint = f"{ZUERCHER_API_URL}/incidents/{incident_id}"
    
    try:
        logger.info(f"Fetching Zuercher CAD data for incident {incident_id} at {endpoint}")
        response = requests.get(endpoint, headers=headers, timeout=10)
        
        if response.status_code == 404:
            logger.warning(f"Zuercher CAD: Incident {incident_id} not found.")
            return None
            
        response.raise_for_status()
        
        # Zuercher API returns a specific schema, we map it to our internal CadData schema
        data = response.json()
        
        # Mapping logic (Mock implementation mapping from Zuercher schema)
        normalized_data = {
            "call_id": data.get("IncidentNumber", incident_id),
            "call_type": data.get("CallNature", "Unknown"),
            "location": data.get("Address", "Unknown"),
            "dispatch_time": data.get("TimeDispatched", ""),
            "arrival_time": data.get("TimeArrived", ""),
            "clear_time": data.get("TimeCleared", ""),
            "involved_parties": [],
            "raw_text": json.dumps(data, indent=2)
        }
        
        # Map involved parties
        for party in data.get("InvolvedPersons", []):
            normalized_data["involved_parties"].append({
                "name": f"{party.get('FirstName', '')} {party.get('LastName', '')}".strip(),
                "dob": party.get("DateOfBirth", ""),
                "sex": party.get("Gender", ""),
                "age": str(party.get("Age", ""))
            })
            
        return normalized_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to Zuercher CAD API: {e}")
        raise RuntimeError(f"CAD API Error: {e}")
