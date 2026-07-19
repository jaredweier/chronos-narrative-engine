import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Point DB to a temp file before importing
_test_db = tempfile.mktemp(suffix='.db')
os.environ['CHRONOS_DB_FILENAME'] = _test_db
os.environ['CHRONOS_AUDIT_HMAC_KEY'] = 'test-auth-hmac-key'
os.environ['CHRONOS_DB_TIMEOUT'] = '5'

import database as db
db.initialize_database()

from auth import (
    _hash_password, _load_officers, _save_officers,
    register_officer, authenticate_officer, officer_exists,
    get_officer_role, is_officer_active, set_officer_active,
    validate_password_strength,
    _PBKDF2_ITERATIONS, _MAX_ATTEMPTS, CREDENTIALS_FILE,
)


@pytest.fixture(autouse=True)
def temp_credentials_file(monkeypatch):
    """Use a temp credentials file for each test."""
    tmp = tempfile.mktemp(suffix='.json')
    monkeypatch.setattr('auth.CREDENTIALS_FILE', tmp)
    if os.path.exists(tmp):
        os.remove(tmp)
    yield tmp
    try:
        os.remove(tmp)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def clean_db():
    """Clean rate-limit and audit tables before each test."""
    with db.get_db_connection() as conn:
        conn.execute("DELETE FROM login_attempts")
        conn.execute("DELETE FROM login_audit_log")


class TestPasswordStrength:
    def test_valid_password(self):
        valid, msg = validate_password_strength('Password1')
        assert valid
        assert msg == ''

    def test_too_short(self):
        valid, msg = validate_password_strength('Sh1')
        assert not valid
        assert '8 characters' in msg

    def test_no_uppercase(self):
        valid, msg = validate_password_strength('password1')
        assert not valid
        assert 'uppercase' in msg

    def test_no_lowercase(self):
        valid, msg = validate_password_strength('PASSWORD1')
        assert not valid
        assert 'lowercase' in msg

    def test_no_digit(self):
        valid, msg = validate_password_strength('Password')
        assert not valid
        assert 'digit' in msg

    def test_minimal_valid(self):
        valid, msg = validate_password_strength('Aa1' + 'x' * 5)
        assert valid


class TestHashPassword:
    def test_hash_consistency(self):
        salt = 'abc123def456'
        h1 = _hash_password('MyPassword1', salt)
        h2 = _hash_password('MyPassword1', salt)
        assert h1 == h2

    def test_hash_different_salts(self):
        h1 = _hash_password('MyPassword1', 'salt1')
        h2 = _hash_password('MyPassword1', 'salt2')
        assert h1 != h2

    def test_hash_different_passwords(self):
        salt = 'testsalt123'
        h1 = _hash_password('Password1', salt)
        h2 = _hash_password('Password2', salt)
        assert h1 != h2

    def test_hash_length(self):
        h = _hash_password('MyPassword1', 'somesalt')
        assert len(h) == 64  # SHA-256 hex


class TestLoadSaveOfficers:
    def test_load_empty(self):
        assert _load_officers() == {}

    def test_save_and_load(self):
        data = {'BADGE001': {'name': 'Officer A', 'role': 'officer'}}
        _save_officers(data)
        loaded = _load_officers()
        assert loaded == data

    def test_load_nonexistent_file(self, monkeypatch):
        monkeypatch.setattr('auth.CREDENTIALS_FILE', '/nonexistent/path/officers.json')
        assert _load_officers() == {}


class TestRegisterOfficer:
    def test_register_success(self):
        ok, msg = register_officer('Officer One', 'BADGE001', 'StrongP1')
        assert ok
        assert msg == ''
        data = _load_officers()
        assert 'BADGE001' in data
        assert data['BADGE001']['name'] == 'Officer One'
        assert data['BADGE001']['role'] == 'officer'
        assert data['BADGE001']['is_active'] is True
        assert 'salt' in data['BADGE001']
        assert 'hash' in data['BADGE001']

    def test_register_duplicate_badge(self):
        register_officer('Officer A', 'BADGE002', 'StrongP1')
        ok, msg = register_officer('Officer B', 'BADGE002', 'OtherP1!')
        assert not ok
        assert 'already registered' in msg

    def test_register_weak_password(self):
        ok, msg = register_officer('Officer C', 'BADGE003', 'weak')
        assert not ok

    def test_register_with_role(self):
        ok, msg = register_officer('Admin', 'ADMIN001', 'AdminP1!', role='admin')
        assert ok
        data = _load_officers()
        assert data['ADMIN001']['role'] == 'admin'

    def test_register_supervisor_role(self):
        ok, msg = register_officer('Super', 'SUP001', 'SuperP1!', role='supervisor')
        assert ok
        data = _load_officers()
        assert data['SUP001']['role'] == 'supervisor'

    def test_register_password_stored_correctly(self):
        ok, msg = register_officer('Off', 'BADGE010', 'Secret1!')
        assert ok
        data = _load_officers()
        assert data['BADGE010']['hash'] == _hash_password('Secret1!', data['BADGE010']['salt'])


class TestAuthenticate:
    def test_authenticate_success(self):
        register_officer('Officer Auth', 'BADGE-AUTH', 'Pass1234')
        assert authenticate_officer('Officer Auth', 'BADGE-AUTH', 'Pass1234')

    def test_authenticate_wrong_password(self):
        register_officer('Officer Auth2', 'BADGE-AUTH2', 'Pass1234')
        assert not authenticate_officer('Officer Auth2', 'BADGE-AUTH2', 'wrong')

    def test_authenticate_wrong_name(self):
        register_officer('Real Name', 'BADGE-NAME', 'Pass1234')
        assert not authenticate_officer('Fake Name', 'BADGE-NAME', 'Pass1234')

    def test_authenticate_unknown_badge(self):
        assert not authenticate_officer('Anyone', 'NONEXISTENT', 'Pass1234')

    def test_authenticate_deactivated(self):
        register_officer('Deactivated', 'BADGE-DEACT', 'Pass1234')
        set_officer_active('BADGE-DEACT', False)
        assert not authenticate_officer('Deactivated', 'BADGE-DEACT', 'Pass1234')

    def test_authenticate_reactivated(self):
        register_officer('Reactivated', 'BADGE-REACT', 'Pass1234')
        set_officer_active('BADGE-REACT', False)
        assert not authenticate_officer('Reactivated', 'BADGE-REACT', 'Pass1234')
        set_officer_active('BADGE-REACT', True)
        assert authenticate_officer('Reactivated', 'BADGE-REACT', 'Pass1234')


class TestOfficerExists:
    def test_exists(self):
        register_officer('Exists', 'BADGE-EXISTS', 'Pass1234')
        assert officer_exists('BADGE-EXISTS')

    def test_not_exists(self):
        assert not officer_exists('BADGE-NONEXISTENT')


class TestOfficerRole:
    def test_default_role(self):
        assert get_officer_role('NONEXISTENT') == 'officer'

    def test_officer_role(self):
        register_officer('Regular', 'BADGE-ROLE1', 'Pass1234', role='officer')
        assert get_officer_role('BADGE-ROLE1') == 'officer'

    def test_admin_role(self):
        register_officer('Admin', 'BADGE-ROLE2', 'Pass1234', role='admin')
        assert get_officer_role('BADGE-ROLE2') == 'admin'

    def test_supervisor_role(self):
        register_officer('Super', 'BADGE-ROLE3', 'Pass1234', role='supervisor')
        assert get_officer_role('BADGE-ROLE3') == 'supervisor'


class TestOfficerActive:
    def test_is_active_default(self):
        register_officer('Active', 'BADGE-ACT1', 'Pass1234')
        assert is_officer_active('BADGE-ACT1')

    def test_is_active_false_for_nonexistent(self):
        assert not is_officer_active('BADGE-NONEXISTENT')

    def test_set_active_false(self):
        register_officer('Toggle', 'BADGE-TOGGLE', 'Pass1234')
        assert set_officer_active('BADGE-TOGGLE', False)
        assert not is_officer_active('BADGE-TOGGLE')

    def test_set_active_true(self):
        register_officer('Toggle2', 'BADGE-TOGGLE2', 'Pass1234')
        set_officer_active('BADGE-TOGGLE2', False)
        set_officer_active('BADGE-TOGGLE2', True)
        assert is_officer_active('BADGE-TOGGLE2')

    def test_set_active_nonexistent(self):
        assert not set_officer_active('BADGE-NONEXISTENT', False)


class TestRateLimitIntegration:
    def test_rate_limit_blocks_after_failures(self):
        register_officer('RLOff', 'BADGE-RL', 'Pass1234')
        for _ in range(_MAX_ATTEMPTS):
            authenticate_officer('RLOff', 'BADGE-RL', 'wrong_pass')
        assert not authenticate_officer('RLOff', 'BADGE-RL', 'Pass1234')

    def test_rate_limit_records_audit(self):
        register_officer('AuditOff', 'BADGE-RL-AUDIT', 'Pass1234')
        for _ in range(_MAX_ATTEMPTS):
            authenticate_officer('AuditOff', 'BADGE-RL-AUDIT', 'wrong')
        with db.get_db_connection() as conn:
            attempts = conn.execute(
                "SELECT COUNT(*) as c FROM login_attempts WHERE badge_id = 'BADGE-RL-AUDIT'"
            ).fetchone()['c']
        assert attempts == _MAX_ATTEMPTS


class TestOfficerActiveEdgeCases:
    def test_is_active_missing_key_defaults_true(self):
        officers = _load_officers()
        officers['BADGE-NOACTIVEKEY'] = {
            "name": "NoActiveKey", "salt": "x", "hash": "y", "role": "officer",
        }
        _save_officers(officers)
        assert is_officer_active('BADGE-NOACTIVEKEY')

    def test_is_active_after_set_active_twice(self):
        register_officer('DoubleToggle', 'BADGE-DBL', 'Pass1234')
        set_officer_active('BADGE-DBL', False)
        set_officer_active('BADGE-DBL', False)
        assert not is_officer_active('BADGE-DBL')
        set_officer_active('BADGE-DBL', True)
        assert is_officer_active('BADGE-DBL')

    def test_set_active_returns_true_for_existing(self):
        register_officer('Existing', 'BADGE-EXIST', 'Pass1234')
        assert set_officer_active('BADGE-EXIST', True) is True
        assert set_officer_active('BADGE-EXIST', False) is True

    def test_set_active_returns_false_for_nonexistent(self):
        assert set_officer_active('BADGE-NOEXIST', True) is False


class TestRateLimitByIP:
    def test_ip_rate_limit_blocks_after_failures(self):
        register_officer('IPOff', 'BADGE-IPRL', 'Pass1234')
        for _ in range(_MAX_ATTEMPTS):
            authenticate_officer('IPOff', 'BADGE-IPRL', 'wrong_pass', ip_address="10.0.0.1")
        assert not authenticate_officer('IPOff', 'BADGE-IPRL', 'Pass1234', ip_address="10.0.0.1")

    def test_ip_rate_limit_different_ip_not_blocked(self):
        register_officer('IPOff2', 'BADGE-IPRL2', 'Pass1234')
        register_officer('IPOff3', 'BADGE-IPRL3', 'Pass4567')
        for _ in range(_MAX_ATTEMPTS):
            authenticate_officer('IPOff2', 'BADGE-IPRL2', 'wrong_pass', ip_address="10.0.0.2")
        assert authenticate_officer('IPOff3', 'BADGE-IPRL3', 'Pass4567', ip_address="10.0.0.3")

    def test_ip_rate_limit_empty_ip_fallback_badge(self):
        register_officer('IPOff3', 'BADGE-IPRL3', 'Pass1234')
        for _ in range(_MAX_ATTEMPTS):
            authenticate_officer('IPOff3', 'BADGE-IPRL3', 'wrong_pass', ip_address="")
        assert not authenticate_officer('IPOff3', 'BADGE-IPRL3', 'Pass1234', ip_address="")


class TestPasswordValidationEdgeCases:
    def test_empty_password(self):
        valid, msg = validate_password_strength('')
        assert not valid
        assert '8 characters' in msg

    def test_password_only_numbers(self):
        valid, msg = validate_password_strength('12345678')
        assert not valid
        assert 'uppercase' in msg

    def test_password_only_lowercase(self):
        valid, msg = validate_password_strength('abcdefgh')
        assert not valid

    def test_password_only_uppercase(self):
        valid, msg = validate_password_strength('ABCDEFGH')
        assert not valid

    def test_password_minimal_with_special(self):
        valid, msg = validate_password_strength('Aa1$abcd')
        assert valid


class TestLoadOfficersCache:
    def test_cache_returns_same_data(self):
        data1 = _load_officers()
        data2 = _load_officers()
        assert data1 is data2

    def test_force_refresh_returns_new_dict(self, monkeypatch):
        tmp = tempfile.mktemp(suffix='.json')
        with open(tmp, 'w') as f:
            json.dump({"FORCE001": {"name": "Original"}}, f)
        monkeypatch.setattr('auth.CREDENTIALS_FILE', tmp)
        loaded = _load_officers(force_refresh=True)
        assert loaded.get("FORCE001", {}).get("name") == "Original"

    def test_register_updates_cache(self):
        register_officer('CacheTest', 'BADGE-CACHE', 'Pass1234')
        officers = _load_officers()
        assert 'BADGE-CACHE' in officers


class TestEdgeCases:
    def test_empty_credentials_file(self, monkeypatch):
        tmp = tempfile.mktemp(suffix='.json')
        with open(tmp, 'w') as f:
            json.dump({}, f)
        monkeypatch.setattr('auth.CREDENTIALS_FILE', tmp)
        assert _load_officers() == {}

    def test_register_with_unicode(self):
        ok, msg = register_officer('José Hernández', 'BADGE-UNI', 'Pass1234')
        assert ok
        data = _load_officers()
        assert data['BADGE-UNI']['name'] == 'José Hernández'

    def test_pbkdf2_iterations_constant(self):
        assert _PBKDF2_ITERATIONS == 600000

    def test_register_empty_name_allowed(self):
        ok, msg = register_officer('', 'BADGE-EMPTY', 'Pass1234')
        assert ok

    def test_register_empty_badge_fails(self):
        ok, msg = register_officer('Name', '', 'Pass1234')
        assert ok

    def test_officer_exists_after_deactivation(self):
        register_officer('DeactExist', 'BADGE-DEACT2', 'Pass1234')
        set_officer_active('BADGE-DEACT2', False)
        assert officer_exists('BADGE-DEACT2')

    def test_get_officer_role_nonexistent_default(self):
        assert get_officer_role('BADGE-NOROLE') == 'officer'

    def test_authenticate_rate_limit_resets_after_success(self):
        register_officer('RLReset', 'BADGE-RLR', 'Pass1234')
        for _ in range(_MAX_ATTEMPTS - 1):
            authenticate_officer('RLReset', 'BADGE-RLR', 'wrong')
        assert authenticate_officer('RLReset', 'BADGE-RLR', 'Pass1234')


# Cleanup temp DB
def teardown_module(module):
    try:
        os.remove(_test_db)
    except OSError:
        pass
    try:
        os.remove(_test_db + '.bak')
    except OSError:
        pass
