import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ['CHRONOS_AUDIT_HMAC_KEY'] = 'integration-test-hmac-key'
os.environ['CHRONOS_DB_TIMEOUT'] = '30'

import database as db

from auth import register_officer, authenticate_officer
from nibrs_export import build_nibrs_xml, validate_nibrs_xml, get_nibrs_quality_stats
from nibrs_checker import check_nibrs_compliance, check_probable_cause, suggest_missing_fields
from redactor import sanitize_pii_content
from utils import extract_json, safe_filename
from wi_statutes import search_statutes, format_statutes_for_prompt


_INTEGRATION_DB = None

@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    global _INTEGRATION_DB
    if _INTEGRATION_DB is None:
        _INTEGRATION_DB = tempfile.mktemp(suffix='.db')
    monkeypatch.setattr(db, 'DB_PATH', _INTEGRATION_DB)
    monkeypatch.setattr('config.DB_PATH', _INTEGRATION_DB)
    db.initialize_database()


class TestFullReportLifecycle:
    def test_register_authenticate_submit_and_search(self):
        register_officer('Integration Officer', 'INT-BADGE', 'IntP@ss1')
        assert authenticate_officer('Integration Officer', 'INT-BADGE', 'IntP@ss1', '127.0.0.1')

        incident_id = "INT-20260711-000001"
        narrative = "On the above date at approximately 1400 hours, I responded to 123 Main St."

        row_id = db.log_submission(
            incident_id=incident_id,
            officer_name='Integration Officer',
            officer_id='INT-BADGE',
            document_type='Standard Incident Report',
            ai_draft=narrative,
            final_report=narrative + " Additional details noted.",
            was_modified=True,
            verified=True,
        )
        assert row_id > 0

        db.rebuild_search_index()
        results = db.search_reports("responded", limit=10)
        assert len(results) >= 1
        assert results[0]['incident_id'] == incident_id

        incident = db.get_incident(incident_id)
        assert incident is not None
        assert incident['officer_name'] == 'Integration Officer'

        history = db.get_officer_history('Integration Officer')
        assert len(history) >= 1

    def test_audit_chain_integrity(self):
        db.log_submission('INT-002', 'Off A', 'B001', 'Theft', 'Draft A', 'Final A', False, True)
        db.log_submission('INT-003', 'Off B', 'B002', 'Assault', 'Draft B', 'Final B', True, True)

        results = db.verify_audit_chain()
        assert len(results) == 1
        assert results[0]['status'] == 'INTACT'

    def test_nibrs_xml_round_trip(self):
        xml = build_nibrs_xml(
            incident_id="INT-NIBRS-001",
            officer_name="Jane Doe",
            officer_id="B999",
            report_type="Domestic Assault",
            narrative="Narrative text here.",
            call_id="CAD-999",
            call_type="Domestic",
            location="456 Oak Ave",
            nibrs_offense_code="13A",
        )
        assert "<NIBRS_Submission" in xml
        assert "13A" in xml
        assert "Jane Doe" in xml

        errors = validate_nibrs_xml(xml)
        critical = [e for e in errors if e.get('severity') == 'critical']
        assert len(critical) == 0

    def test_nibrs_quality_stats(self):
        submissions = [
            {"nibrs_offense_code": "13A", "final_approved_report": "Report 1", "officer_name": "A"},
            {"nibrs_offense_code": "", "final_approved_report": "", "officer_name": "B"},
        ]
        stats = get_nibrs_quality_stats(submissions)
        assert stats['total'] == 2
        assert stats['with_nibrs_code'] == 1
        assert stats['with_narrative'] == 1

    def test_compliance_and_pc_check(self):
        narrative = "I observed the suspect and had probable cause to believe a crime occurred."
        warnings = check_nibrs_compliance("Domestic Assault", narrative)
        assert isinstance(warnings, list)

        pc = check_probable_cause(narrative)
        assert pc is not None
        assert 'strength' in pc

        fields = suggest_missing_fields("Domestic Assault", narrative)
        assert isinstance(fields, list)

    def test_pii_redaction(self):
        raw = "SSN: 123-45-6789, Phone: (555) 123-4567"
        redacted = sanitize_pii_content(raw)
        assert "123-45-6789" not in redacted
        assert "[REDACTED_SSN]" in redacted
        assert "(555) 123-4567" not in redacted
        assert "[REDACTED_PHONE]" in redacted

    def test_statute_search(self):
        results = search_statutes("theft", limit=3)
        assert len(results) <= 3
        for r in results:
            assert "code" in r
            assert "title" in r

    def test_evidence_chain_full(self):
        db.add_evidence_event(
            'INT-EVI-001', 'EVI-001', 'Bodycam footage',
            'Bodycam Footage', 'Collected', 'Officer A', 'Seized from scene'
        )
        db.add_evidence_event(
            'INT-EVI-001', 'EVI-001', 'Bodycam footage',
            'Bodycam Footage', 'Stored', 'Officer A', 'Placed in evidence locker'
        )
        chain = db.get_evidence_chain('INT-EVI-001')
        assert len(chain) == 2
        assert chain[0]['action'] == 'Collected'
        assert chain[1]['action'] == 'Stored'

    def test_db_backup_restore_roundtrip(self):
        db.log_submission('INT-BR-001', 'Off', 'B001', 'Test', 'draft', 'final', False, False)
        backup = db.backup_database()
        assert len(backup) > 0

        db.log_submission('INT-BR-002', 'Off2', 'B002', 'Test2', 'draft2', 'final2', False, False)
        assert db.restore_database(backup) is True

        restored = db.get_incident('INT-BR-001')
        assert restored is not None

    def test_user_management_flow(self):
        db.upsert_user('USER-001', 'Test User', 'officer', 'test@dept.org', '555-0100', True)
        db.upsert_user('USER-002', 'Admin User', 'admin', 'admin@dept.org', '', True)

        users = db.get_all_users()
        assert len(users) >= 2

        user = db.get_user('USER-001')
        assert user is not None
        assert user['name'] == 'Test User'

        db.deactivate_user('USER-001')
        user = db.get_user('USER-001')
        assert user['is_active'] == 0

        db.activate_user('USER-001')
        user = db.get_user('USER-001')
        assert user['is_active'] == 1

        db.record_user_login('USER-001', '10.0.0.1')
        sessions = db.get_user_sessions('USER-001')
        assert len(sessions) >= 1

    def test_utility_functions(self):
        json_str = extract_json('{"a": 1}')
        assert json_str == '{"a": 1}'

        assert safe_filename("hello world.txt") == "hello_world.txt"
        assert safe_filename("../evil.txt") == "evil.txt"

    def test_evidence_file_persistence(self):
        db.save_evidence_file(
            'INT-EVI-FILE', 'photo.jpg', '/tmp/photo.jpg',
            1024, 'image/jpeg', 'Officer A', 'Booking photo', 'photo'
        )
        files = db.get_evidence_files('INT-EVI-FILE')
        assert len(files) == 1
        assert files[0]['file_name'] == 'photo.jpg'

        categories = db.get_all_evidence_file_categories()
        assert 'photo' in categories

    def test_dashboard_analytics(self):
        db.log_submission('INT-DASH-001', 'OffDash', 'B-DASH', 'Theft', 'd', 'f', False, True)
        stats = db.get_statistics()
        assert stats['total_submissions'] >= 1

        analytics = db.get_dashboard_analytics(days=30)
        assert analytics['total_reports'] >= 1

    def test_case_linking(self):
        db.log_submission('INT-CL-001', 'Off', 'B001', 'Theft', 'd1', 'f1', False, False)
        db.log_submission('INT-CL-002', 'Off', 'B001', 'Burglary', 'd2', 'f2', False, False)
        db.link_cases('INT-CL-001', 'INT-CL-002', 'related')

        related = db.get_related_cases('INT-CL-001')
        assert len(related) >= 1
        assert related[0]['incident_id'] == 'INT-CL-002'

    def test_login_audit_log(self):
        from database import log_login_audit
        log_login_audit('BADGE-LOG', 'Officer Log', True, '', '10.0.0.1')
        log_login_audit('BADGE-LOG', 'Officer Log', False, 'bad password', '10.0.0.1')

        logs = db.get_login_audit_logs(limit=10)
        assert len(logs) >= 2

        badge_logs = db.get_login_audit_logs(limit=10, badge_id='BADGE-LOG')
        assert len(badge_logs) >= 2


def teardown_module(module):
    try:
        os.remove(_INTEGRATION_DB)
    except OSError:
        pass
    try:
        os.remove(_INTEGRATION_DB + '.bak')
    except OSError:
        pass
