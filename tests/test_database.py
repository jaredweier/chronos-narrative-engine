import os
import sys
import tempfile
import time
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Point DB to a temp file before importing database module
_test_db = tempfile.mktemp(suffix='.db')
os.environ['CHRONOS_DB_FILENAME'] = _test_db
os.environ['CHRONOS_AUDIT_HMAC_KEY'] = 'test-hmac-key-for-testing-123'
os.environ['CHRONOS_DB_TIMEOUT'] = '5'

import database as db
from database import (
    get_db_connection, log_submission, _compute_row_hash, _get_last_audit_hash,
    verify_audit_chain, get_incident, get_statistics, get_dashboard_analytics,
    add_evidence_event, get_evidence_chain,
    check_login_rate_limit, record_login_attempt,
    log_login_audit, get_login_audit_logs,
    update_review_status, get_pending_reviews, get_review_counts,
    search_reports, search_officer_reports,
    upsert_user, get_all_users, get_user, deactivate_user, activate_user,
    record_user_login, get_user_sessions,
    link_cases, get_related_cases,
    save_evidence_file, get_evidence_files, delete_evidence_file,
    get_all_evidence_file_categories,
    get_officer_history, get_recent_corrections,
    purge_old_records, backup_database, restore_database,
    rebuild_search_index, _MIGRATIONS, _tokenize_or_query,
)


def setup_module(module):
    db._db_initialized = False
    db.DB_PATH = _test_db
    db.initialize_database()


def teardown_module(module):
    try:
        os.remove(_test_db)
    except OSError:
        pass
    try:
        os.remove(_test_db + '.bak')
    except OSError:
        pass


class TestDatabaseInit:
    def test_db_initialized(self):
        assert os.path.exists(_test_db)

    def test_hmac_key_from_env(self):
        assert isinstance(db._AUDIT_HMAC_KEY, bytes)
        assert len(db._AUDIT_HMAC_KEY) > 0


class TestSubmissionLogging:
    def setup_method(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM legal_audit_logs")

    def test_log_submission_basic(self):
        row_id = log_submission(
            incident_id='INC-TEST-001',
            officer_name='Officer Test',
            officer_id='BADGE001',
            document_type='Test Report',
            ai_draft='AI generated narrative',
            final_report='Final approved narrative',
            was_modified=True,
            verified=True,
        )
        assert row_id > 0
        incident = get_incident('INC-TEST-001')
        assert incident is not None
        assert incident['officer_name'] == 'Officer Test'
        assert incident['officer_id'] == 'BADGE001'
        assert incident['document_type'] == 'Test Report'
        assert incident['was_modified_by_human'] == 1
        assert incident['verification_signature_flag'] == 1

    def test_log_submission_no_modifications(self):
        row_id = log_submission(
            incident_id='INC-TEST-002',
            officer_name='Officer A',
            document_type='Simple Report',
            ai_draft='Draft text',
        )
        assert row_id > 0
        incident = get_incident('INC-TEST-002')
        assert incident['was_modified_by_human'] == 0
        assert incident['verification_signature_flag'] == 0

    def test_log_multiple_incidents(self):
        log_submission('INC-M-001', 'Off1', document_type='Type A', ai_draft='d1')
        log_submission('INC-M-002', 'Off1', document_type='Type B', ai_draft='d2')
        log_submission('INC-M-003', 'Off2', document_type='Type A', ai_draft='d3')
        stats = get_statistics()
        assert stats['total_submissions'] >= 3
        assert 'Type A' in stats['by_document_type']

    def test_officer_history(self):
        log_submission('INC-H-001', 'OffHist', document_type='T1', ai_draft='d1')
        log_submission('INC-H-002', 'OffHist', document_type='T2', ai_draft='d2')
        history = get_officer_history('OffHist', limit=5)
        assert len(history) >= 2
        assert all(h['incident_id'] in ('INC-H-001', 'INC-H-002') for h in history)
        assert all(h['document_type'] in ('T1', 'T2') for h in history)

    def test_recent_corrections(self):
        log_submission('INC-C-001', 'OffCorr', document_type='T1',
                       ai_draft='draft', final_report='final', was_modified=True)
        log_submission('INC-C-002', 'OffCorr', document_type='T1',
                       ai_draft='draft2', final_report='final2', was_modified=False)
        corrections = get_recent_corrections('OffCorr', 'T1', limit=5)
        assert len(corrections) >= 1
        assert corrections[0]['was_modified_by_human'] == 1


class TestAuditChain:
    def setup_method(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM legal_audit_logs")

    def test_chain_hashes(self):
        id1 = log_submission('INC-A-001', 'Off', document_type='T', ai_draft='d1')
        id2 = log_submission('INC-A-002', 'Off', document_type='T', ai_draft='d2')
        id3 = log_submission('INC-A-003', 'Off', document_type='T', ai_draft='d3')
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, previous_hash, row_hash FROM legal_audit_logs ORDER BY id ASC"
            ).fetchall()
        assert len(rows) == 3
        assert rows[0]['previous_hash'] == ''
        assert rows[1]['previous_hash'] == rows[0]['row_hash']
        assert rows[2]['previous_hash'] == rows[1]['row_hash']

    def test_hash_computation(self):
        row_id = log_submission('INC-A-010', 'Off', document_type='T', ai_draft='d1')
        row_hash = _compute_row_hash(row_id, '', {
            'incident_id': 'INC-A-010',
            'officer_name': 'Off',
            'document_type': 'T',
        })
        assert isinstance(row_hash, str)
        assert len(row_hash) == 64  # SHA-256 hex

    def test_verify_intact_chain(self):
        log_submission('INC-V-001', 'Off', document_type='T', ai_draft='d1')
        log_submission('INC-V-002', 'Off', document_type='T', ai_draft='d2')
        result = verify_audit_chain()
        assert any(r['status'] == 'INTACT' for r in result)

    def test_verify_broken_chain(self):
        log_submission('INC-B-001', 'Off', document_type='T', ai_draft='d1')
        log_submission('INC-B-002', 'Off', document_type='T', ai_draft='d2')
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE legal_audit_logs SET previous_hash = 'tampered' WHERE id = (SELECT MAX(id) FROM legal_audit_logs)"
            )
        result = verify_audit_chain()
        assert any(r.get('status') == 'BROKEN_CHAIN' for r in result)

    def test_get_last_audit_hash_empty(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM legal_audit_logs")
        assert _get_last_audit_hash() == ''


class TestEvidenceChain:
    def setup_method(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM evidence_chain")

    def test_add_evidence_event(self):
        ev_id = add_evidence_event(
            incident_id='INC-E-001',
            evidence_id='EVI-001',
            description='Bodycam footage',
            evidence_type='Video',
            action='Collected',
            actor='Officer A',
            notes='Primary camera',
        )
        assert ev_id > 0

    def test_get_evidence_chain(self):
        add_evidence_event('INC-E-002', 'EVI-001', 'Desc 1', 'Video', 'Collected', 'Off A')
        add_evidence_event('INC-E-002', 'EVI-002', 'Desc 2', 'Photo', 'Stored', 'Off A')
        chain = get_evidence_chain('INC-E-002')
        assert len(chain) == 2
        assert chain[0]['action'] == 'Collected'
        assert chain[1]['action'] == 'Stored'

    def test_evidence_chain_empty(self):
        assert get_evidence_chain('INC-NONEXISTENT') == []


class TestLoginRateLimiting:
    def setup_method(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM login_attempts")

    def test_rate_limit_allows_first_attempts(self):
        assert check_login_rate_limit('BADGE-RL', max_attempts=3, lockout_minutes=15)

    def test_rate_limit_blocks_after_max(self):
        badge = 'BADGE-RL-BLOCK'
        for _ in range(5):
            record_login_attempt(badge, False)
        assert not check_login_rate_limit(badge, max_attempts=4, lockout_minutes=15)

    def test_rate_limit_success_resets(self):
        badge = 'BADGE-RL-SUCCESS'
        for _ in range(3):
            record_login_attempt(badge, False)
        record_login_attempt(badge, True)
        assert check_login_rate_limit(badge, max_attempts=4, lockout_minutes=15)


class TestLoginAudit:
    def setup_method(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM login_audit_log")

    def test_log_login_audit(self):
        log_login_audit('BADGE-LA', 'Officer A', True)
        log_login_audit('BADGE-LA', 'Officer A', False, 'Invalid password')
        logs = get_login_audit_logs(limit=10)
        assert len(logs) >= 2

    def test_login_audit_filter_by_badge(self):
        log_login_audit('BADGE-F1', 'Off A', True)
        log_login_audit('BADGE-F2', 'Off B', False, 'Locked')
        logs = get_login_audit_logs(limit=10, badge_id='BADGE-F1')
        assert len(logs) == 1
        assert logs[0]['badge_id'] == 'BADGE-F1'


class TestReviewWorkflow:
    def setup_method(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM legal_audit_logs")

    def test_update_review_status(self):
        log_submission('INC-R-001', 'Off', document_type='T', ai_draft='draft')
        assert update_review_status('INC-R-001', 'approved', 'Supervisor A', 'Looks good')
        incident = get_incident('INC-R-001')
        assert incident['review_status'] == 'approved'
        assert incident['reviewed_by'] == 'Supervisor A'

    def test_get_pending_reviews(self):
        log_submission('INC-P-001', 'Off1', document_type='T', ai_draft='d1')
        log_submission('INC-P-002', 'Off2', document_type='T', ai_draft='d2')
        update_review_status('INC-P-002', 'approved')
        pending = get_pending_reviews()
        pending_ids = [r['incident_id'] for r in pending]
        assert 'INC-P-001' in pending_ids
        assert 'INC-P-002' not in pending_ids

    def test_review_counts(self):
        log_submission('INC-CNT-001', 'Off', document_type='T', ai_draft='d1')
        log_submission('INC-CNT-002', 'Off', document_type='T', ai_draft='d2')
        update_review_status('INC-CNT-001', 'approved')
        counts = get_review_counts()
        assert counts['pending'] >= 1
        assert counts['approved'] >= 1


class TestFullTextSearch:
    def setup_method(self):
        with get_db_connection() as conn:
            try:
                conn.execute("INSERT INTO report_search_index(report_search_index) VALUES('delete-all')")
            except sqlite3.OperationalError:
                conn.execute("DELETE FROM report_search_index")
            conn.execute("DELETE FROM legal_audit_logs")
        rebuild_search_index()

    def test_search_reports(self):
        log_submission('INC-S-001', 'Off', document_type='Narrative',
                       ai_draft='The suspect fled on foot', final_report='The suspect fled on foot')
        rebuild_search_index()
        results = search_reports('suspect', limit=10)
        assert len(results) >= 1
        assert results[0]['incident_id'] == 'INC-S-001'

    def test_search_no_results(self):
        log_submission('INC-S-002', 'Off', document_type='T', ai_draft='nothing relevant')
        rebuild_search_index()
        results = search_reports('xyznonexistent12345', limit=10)
        assert len(results) == 0

    def test_search_officer_reports(self):
        log_submission('INC-SO-001', 'OfficerSearch', document_type='T',
                       ai_draft='pursuit on highway', final_report='pursuit on highway')
        log_submission('INC-SO-002', 'OtherOfficer', document_type='T',
                       ai_draft='pursuit on highway', final_report='pursuit on highway')
        rebuild_search_index()
        results = search_officer_reports('OfficerSearch', 'pursuit', limit=10)
        assert len(results) >= 1
        assert all(r['officer_name'] == 'OfficerSearch' for r in results)

    def test_search_empty_query(self):
        assert search_reports('') == []
        assert search_officer_reports('Off', '') == []


class TestFts5Tokenizer:
    def test_single_word_passthrough(self):
        assert _tokenize_or_query("suspect") == "suspect"

    def test_multiple_words_ored(self):
        result = _tokenize_or_query("theft main street")
        assert result == "theft OR main OR street"

    def test_advanced_syntax_passthrough(self):
        assert _tokenize_or_query("theft OR burglary") == "theft OR burglary"
        assert _tokenize_or_query("theft AND burglary") == "theft AND burglary"
        assert _tokenize_or_query('"main street"') == '"main street"'

    def test_empty_string(self):
        assert _tokenize_or_query("") == ""

    def test_whitespace_only(self):
        assert _tokenize_or_query("   ") == ""

    def test_strips_special_chars(self):
        result = _tokenize_or_query("theft^ $100 (main)")
        assert "^" not in result
        assert "$" not in result
        assert "(" not in result
        assert ")" not in result
        assert "OR" in result


class TestUserManagement:
    def setup_method(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM officer_users")
            conn.execute("DELETE FROM user_sessions")

    def test_upsert_user_create(self):
        assert upsert_user('BADGE-UM-001', 'Officer One', 'officer', 'o1@test.com', '555-0001')
        user = get_user('BADGE-UM-001')
        assert user is not None
        assert user['name'] == 'Officer One'
        assert user['role'] == 'officer'
        assert user['is_active'] == 1

    def test_upsert_user_update(self):
        upsert_user('BADGE-UM-002', 'Officer Two', 'officer')
        upsert_user('BADGE-UM-002', 'Officer Two Updated', 'supervisor')
        user = get_user('BADGE-UM-002')
        assert user['name'] == 'Officer Two Updated'
        assert user['role'] == 'supervisor'

    def test_get_all_users(self):
        upsert_user('BADGE-GU-001', 'User A', 'officer')
        upsert_user('BADGE-GU-002', 'User B', 'admin')
        users = get_all_users()
        assert len(users) >= 2

    def test_deactivate_activate_user(self):
        upsert_user('BADGE-DA-001', 'User Toggle', 'officer')
        assert deactivate_user('BADGE-DA-001')
        assert get_user('BADGE-DA-001')['is_active'] == 0
        assert activate_user('BADGE-DA-001')
        assert get_user('BADGE-DA-001')['is_active'] == 1

    def test_record_user_login(self):
        upsert_user('BADGE-RL-001', 'Login User', 'officer')
        record_user_login('BADGE-RL-001')
        user = get_user('BADGE-RL-001')
        assert user['last_login'] is not None
        sessions = get_user_sessions('BADGE-RL-001')
        assert len(sessions) >= 1


class TestCaseLinking:
    def setup_method(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM legal_audit_logs")

    def test_link_cases(self):
        log_submission('INC-LK-001', 'Off', document_type='T', ai_draft='d1')
        log_submission('INC-LK-002', 'Off', document_type='T', ai_draft='d2')
        assert link_cases('INC-LK-001', 'INC-LK-002', 'related')
        related = get_related_cases('INC-LK-001')
        assert len(related) >= 1
        assert any(r['incident_id'] == 'INC-LK-002' for r in related)

    def test_get_related_cases_empty(self):
        log_submission('INC-LK-NONE', 'Off', document_type='T', ai_draft='d1')
        assert get_related_cases('INC-LK-NONE') == []


class TestEvidenceFiles:
    def setup_method(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM evidence_files")

    def test_save_and_get_evidence_file(self):
        file_id = save_evidence_file(
            'INC-EF-001', 'test.jpg', '/tmp/test.jpg', 1024,
            'image/jpeg', 'Officer A', 'Test image', 'photo'
        )
        assert file_id > 0
        files = get_evidence_files('INC-EF-001')
        assert len(files) == 1
        assert files[0]['file_name'] == 'test.jpg'
        assert files[0]['category'] == 'photo'

    def test_delete_evidence_file(self):
        file_id = save_evidence_file(
            'INC-EF-002', 'delete.jpg', '/tmp/delete.jpg', 512,
            'image/jpeg', 'Off', 'To delete', 'photo'
        )
        assert delete_evidence_file(file_id)
        assert len(get_evidence_files('INC-EF-002')) == 0

    def test_get_all_categories(self):
        save_evidence_file('INC-EF-003', 'a.jpg', '/tmp/a.jpg', 1, 'image/jpeg', 'Off', category='photo')
        save_evidence_file('INC-EF-003', 'b.mp4', '/tmp/b.mp4', 1, 'video/mp4', 'Off', category='video')
        categories = get_all_evidence_file_categories()
        assert 'photo' in categories
        assert 'video' in categories


class TestDashboardAnalytics:
    def setup_method(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM legal_audit_logs")

    def test_get_statistics(self):
        log_submission('INC-DS-001', 'Off1', document_type='TypeA',
                       ai_draft='d1', final_report='f1', was_modified=True, verified=True)
        log_submission('INC-DS-002', 'Off2', document_type='TypeB',
                       ai_draft='d2', final_report='f2', was_modified=False, verified=True)
        stats = get_statistics()
        assert stats['total_submissions'] >= 2
        assert stats['human_modified'] >= 1
        assert stats['verified'] >= 2

    def test_get_dashboard_analytics(self):
        log_submission('INC-DA-001', 'Off1', document_type='T', ai_draft='d')
        analytics = get_dashboard_analytics(days=365)
        assert analytics['total_reports'] >= 1
        assert analytics['recent_reports'] >= 1


class TestDataRetention:
    def setup_method(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM legal_audit_logs")

    def test_purge_old_records_disabled(self):
        assert purge_old_records(days=0) == 0

    def test_purge_old_records(self):
        log_submission('INC-PURGE-001', 'Off', document_type='T', ai_draft='old record')
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE legal_audit_logs SET submission_timestamp = ? WHERE incident_id = ?",
                ((datetime.now() - timedelta(days=400)).isoformat(), 'INC-PURGE-001')
            )
        purged = purge_old_records(days=365)
        assert purged >= 1
        assert get_incident('INC-PURGE-001') is None


class TestBackupRestore:
    def setup_method(self):
        with get_db_connection() as conn:
            conn.execute("DELETE FROM legal_audit_logs")

    def test_backup(self):
        log_submission('INC-BK-001', 'Off', document_type='T', ai_draft='backup test')
        backup = backup_database()
        assert len(backup) > 0

    def test_restore(self):
        log_submission('INC-RS-001', 'Off', document_type='T', ai_draft='restore test')
        log_submission('INC-RS-002', 'Off', document_type='T', ai_draft='restore test 2')
        backup = backup_database()
        with get_db_connection() as conn:
            conn.execute("DELETE FROM legal_audit_logs")
        assert get_incident('INC-RS-001') is None
        assert restore_database(backup)
        assert get_incident('INC-RS-001') is not None
        assert get_incident('INC-RS-002') is not None


class TestEdgeCases:
    def test_get_incident_nonexistent(self):
        assert get_incident('INC-NONEXISTENT') is None

    def test_get_user_nonexistent(self):
        assert get_user('NONEXISTENT-BADGE') is None

    def test_log_submission_empty_strings(self):
        row_id = log_submission('', '', document_type='', ai_draft='')
        assert row_id > 0
        incident = get_incident('')
        assert incident is not None


class TestMigrations:
    def test_migration_list_not_empty(self):
        assert len(_MIGRATIONS) > 0

    def test_migration_versions_sequential(self):
        versions = [m['version'] for m in sorted(_MIGRATIONS, key=lambda x: x['version'])]
        assert versions == list(range(1, len(versions) + 1))

    def test_migration_descriptions_present(self):
        for m in _MIGRATIONS:
            assert len(m['description']) > 0
            assert callable(m['func'])

    def test_schema_migrations_table_exists(self):
        with get_db_connection() as conn:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchall()
        assert len(rows) == 1

    def test_migrations_applied(self):
        with get_db_connection() as conn:
            applied = conn.execute("SELECT version, description FROM schema_migrations ORDER BY version").fetchall()
        assert len(applied) == len(_MIGRATIONS)
        for i, row in enumerate(applied):
            assert row['version'] == i + 1
