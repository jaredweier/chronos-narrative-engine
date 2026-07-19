import hashlib
import json
import os
import re
import secrets
import time

from database import check_login_rate_limit, record_login_attempt, log_login_audit

CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "officers.json")

_MAX_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15
_MIN_PASSWORD_LENGTH = 8

_OFFICER_CACHE: dict | None = None
_OFFICER_CACHE_TTL: float = 30.0
_OFFICER_CACHE_TIMESTAMP: float = 0.0
_OFFICER_CACHE_PATH: str = ""


def _check_rate_limit(badge_id: str, ip_address: str = "") -> bool:
    return check_login_rate_limit(badge_id, _MAX_ATTEMPTS, _LOCKOUT_MINUTES, ip_address)


def _load_officers(force_refresh: bool = False) -> dict:
    global _OFFICER_CACHE, _OFFICER_CACHE_TIMESTAMP, _OFFICER_CACHE_PATH
    now = time.time()
    if (
        not force_refresh
        and _OFFICER_CACHE is not None
        and _OFFICER_CACHE_PATH == CREDENTIALS_FILE
        and (now - _OFFICER_CACHE_TIMESTAMP) < _OFFICER_CACHE_TTL
    ):
        return _OFFICER_CACHE
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            _OFFICER_CACHE = json.load(f)
    else:
        _OFFICER_CACHE = {}
    _OFFICER_CACHE_TIMESTAMP = now
    _OFFICER_CACHE_PATH = CREDENTIALS_FILE
    return _OFFICER_CACHE


def _save_officers(officers: dict) -> None:
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(officers, f, indent=2)
    global _OFFICER_CACHE, _OFFICER_CACHE_TIMESTAMP, _OFFICER_CACHE_PATH
    _OFFICER_CACHE = officers
    _OFFICER_CACHE_TIMESTAMP = time.time()
    _OFFICER_CACHE_PATH = CREDENTIALS_FILE


_PBKDF2_ITERATIONS = 600000

def _hash_password(password: str, salt: str) -> str:
    key = hashlib.pbkdf2_hmac(
        'sha256', password.encode(), salt.encode(),
        _PBKDF2_ITERATIONS
    )
    return key.hex()


def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < _MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {_MIN_PASSWORD_LENGTH} characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain an uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain a lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain a digit"
    return True, ""


def register_officer(name: str, badge_id: str, password: str, role: str = 'officer') -> tuple[bool, str]:
    valid, msg = validate_password_strength(password)
    if not valid:
        return False, msg
    officers = _load_officers()
    if badge_id in officers:
        return False, "Badge ID already registered"
    salt = secrets.token_hex(16)
    officers[badge_id] = {
        "name": name,
        "salt": salt,
        "hash": _hash_password(password, salt),
        "role": role,
        "is_active": True,
    }
    _save_officers(officers)
    return True, ""


def authenticate_officer(name: str, badge_id: str, password: str, ip_address: str = "") -> bool:
    if not _check_rate_limit(badge_id, ip_address):
        log_login_audit(badge_id, name, False, "Rate limited - account locked", ip_address)
        return False
    officers = _load_officers()
    officer = officers.get(badge_id)
    if not officer:
        record_login_attempt(badge_id, False, ip_address)
        log_login_audit(badge_id, name, False, "Unknown badge ID", ip_address)
        return False
    if officer.get("is_active") is False:
        record_login_attempt(badge_id, False, ip_address)
        log_login_audit(badge_id, name, False, "Account deactivated", ip_address)
        return False
    valid = officer.get("name") == name and officer.get("hash") == _hash_password(password, officer.get("salt", ""))
    record_login_attempt(badge_id, valid, ip_address)
    if not valid:
        log_login_audit(badge_id, name, False, "Invalid password or name", ip_address)
    else:
        log_login_audit(badge_id, name, True, "", ip_address)
    return valid


def officer_exists(badge_id: str) -> bool:
    officers = _load_officers()
    return badge_id in officers


def get_officer_role(badge_id: str) -> str:
    officers = _load_officers()
    officer = officers.get(badge_id)
    if not officer:
        return "officer"
    return officer.get("role", "officer")


def is_officer_active(badge_id: str) -> bool:
    officers = _load_officers()
    officer = officers.get(badge_id)
    if not officer:
        return False
    return officer.get("is_active", True) is not False


def set_officer_active(badge_id: str, active: bool) -> bool:
    officers = _load_officers()
    if badge_id not in officers:
        return False
    officers[badge_id]["is_active"] = active
    _save_officers(officers)
    return True
