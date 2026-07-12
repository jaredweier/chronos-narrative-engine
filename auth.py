import hashlib
import json
import os
import secrets

CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "officers.json")


def _load_officers() -> dict:
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_officers(officers: dict) -> None:
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(officers, f, indent=2)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def _ensure_default_admin() -> None:
    officers = _load_officers()
    if "0000" not in officers:
        salt = secrets.token_hex(16)
        officers["0000"] = {
            "name": "Admin",
            "salt": salt,
            "hash": _hash_password("chronos", salt),
        }
        _save_officers(officers)


def register_officer(name: str, badge_id: str, password: str) -> bool:
    officers = _load_officers()
    if badge_id in officers:
        return False
    salt = secrets.token_hex(16)
    officers[badge_id] = {
        "name": name,
        "salt": salt,
        "hash": _hash_password(password, salt),
    }
    _save_officers(officers)
    return True


def authenticate_officer(name: str, badge_id: str, password: str) -> bool:
    _ensure_default_admin()
    officers = _load_officers()
    officer = officers.get(badge_id)
    if not officer:
        return False
    return (
        officer["name"] == name
        and officer["hash"] == _hash_password(password, officer["salt"])
    )


def officer_exists(badge_id: str) -> bool:
    _ensure_default_admin()
    officers = _load_officers()
    return badge_id in officers


_ensure_default_admin()
