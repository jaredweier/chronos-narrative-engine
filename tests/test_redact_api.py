import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from api_server import app, _API_KEY

client = TestClient(app)
auth_headers = {"X-API-Key": _API_KEY}

def test_analyze_and_apply():
    # 1. Create a dummy text file
    test_text = "Officer John Smith spoke to Jane Doe (DOB 01/15/1990) about the incident. Also my secret word is Pineapple."
    with open("temp_test.txt", "w") as f:
        f.write(test_text)
        
    try:
        # 2. Test Analyze
        with open("temp_test.txt", "rb") as f:
            res = client.post("/api/v1/redact/analyze", files={"file": ("temp_test.txt", f, "text/plain")}, headers=auth_headers)
        
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "Officer John Smith" in test_text
        
        entities = data["entities"]
        assert "name" in entities
        assert "Jane Doe" in entities["name"]["matches"] or "John Smith" in entities["name"]["matches"]
        
        # 3. Test Apply
        apply_payload = {
            "text": test_text,
            "categories": ["name", "dob"],
            "custom_terms": ["Pineapple"]
        }
        res2 = client.post("/api/v1/redact/apply", json=apply_payload, headers=auth_headers)
        
        assert res2.status_code == 200
        data2 = res2.json()
        redacted = data2["redacted_text"]
        
        assert "John Smith" not in redacted
        assert "[REDACTED_NAME]" in redacted
        assert "01/15/1990" not in redacted
        assert "[REDACTED_DOB]" in redacted
        assert "Pineapple" not in redacted
        assert "[REDACTED_CUSTOM]" in redacted
        print("API Redaction tests passed!")
    finally:
        if os.path.exists("temp_test.txt"):
            os.remove("temp_test.txt")

if __name__ == "__main__":
    test_analyze_and_apply()
