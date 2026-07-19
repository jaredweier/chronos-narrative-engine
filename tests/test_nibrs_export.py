import pytest
from nibrs_export import build_nibrs_xml, _map_call_type_to_nibrs


def test_map_call_type_theft():
    assert _map_call_type_to_nibrs("Theft from Vehicle") == "23F"


def test_map_call_type_assault():
    assert _map_call_type_to_nibrs("Domestic Assault") == "13A"


def test_map_call_type_dui():
    assert _map_call_type_to_nibrs("OWI / DUI Report") == "90D"


def test_map_call_type_unknown():
    assert _map_call_type_to_nibrs("") == "99Z"


def test_map_call_type_unmapped():
    assert _map_call_type_to_nibrs("Noise Complaint") == "99Z"


def test_build_nibrs_xml_basic():
    xml = build_nibrs_xml(
        incident_id="INC-20260711-123456",
        officer_name="John Smith",
        officer_id="B1234",
        report_type="Standard Incident Report",
        narrative="On the above date...",
        call_id="CAD-001",
        call_type="Theft",
        location="123 Main St",
    )
    assert "<NIBRS_Submission" in xml
    assert "INC-20260711-123456" in xml
    assert "John Smith" in xml
    assert "B1234" in xml
    assert "CAD-001" in xml
    assert "On the above date..." in xml


def test_build_nibrs_xml_empty():
    xml = build_nibrs_xml()
    assert "<NIBRS_Submission" in xml
    assert "<IncidentNumber" in xml
