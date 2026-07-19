import pytest
from redactor import sanitize_pii_content, get_redaction_report


def test_sanitize_ssn():
    result = sanitize_pii_content("My SSN is 123-45-6789.")
    assert "123-45-6789" not in result
    assert "[REDACTED_SSN]" in result


def test_sanitize_phone():
    result = sanitize_pii_content("Call me at (555) 123-4567.")
    assert "(555) 123-4567" not in result


def test_sanitize_email():
    result = sanitize_pii_content("Email me at john@example.com.")
    assert "john@example.com" not in result


def test_sanitize_no_pii():
    text = "A disturbance was reported at the intersection."
    result = sanitize_pii_content(text)
    assert result == text


def test_sanitize_credit_card():
    result = sanitize_pii_content("Card: 4111-1111-1111-1111.")
    assert "4111-1111-1111-1111" not in result


def test_get_redaction_report():
    original = "SSN: 123-45-6789"
    redacted = sanitize_pii_content(original)
    report = get_redaction_report(original, redacted)
    assert len(report) > 0
