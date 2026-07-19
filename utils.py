import os
import re
import base64
import hashlib
import json

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

_ENCRYPTION_KEY: bytes | None = None


def _get_encryption_key(master_key: str = "") -> bytes:
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is not None:
        return _ENCRYPTION_KEY
    key_material = master_key or os.environ.get("CHRONOS_ENCRYPTION_KEY", "").encode()
    if isinstance(key_material, str):
        key_material = key_material.encode()
    if not key_material:
        key_material = hashlib.sha256(b"CHRONOS_DEFAULT_KEY_FALLBACK").digest()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"CHRONOS_SALT_FIXED", iterations=600000)
    key = base64.urlsafe_b64encode(kdf.derive(key_material[:32] if len(key_material) > 32 else key_material))
    _ENCRYPTION_KEY = key
    return key


def encrypt_data(data: str, master_key: str = "") -> str:
    if not _HAS_CRYPTO:
        return data
    key = _get_encryption_key(master_key)
    f = Fernet(key)
    return f.encrypt(data.encode()).decode()


def decrypt_data(token: str, master_key: str = "") -> str:
    if not _HAS_CRYPTO:
        return token
    key = _get_encryption_key(master_key)
    f = Fernet(key)
    return f.decrypt(token.encode()).decode()


def encrypt_file(file_path: str, master_key: str = "") -> bool:
    if not _HAS_CRYPTO:
        return False
    try:
        with open(file_path, "rb") as f:
            plaintext = f.read()
        key = _get_encryption_key(master_key)
        fernet = Fernet(key)
        encrypted = fernet.encrypt(plaintext)
        with open(file_path, "wb") as f:
            f.write(encrypted)
        return True
    except Exception:
        return False


def decrypt_file(file_path: str, master_key: str = "") -> bool:
    if not _HAS_CRYPTO:
        return False
    try:
        with open(file_path, "rb") as f:
            encrypted = f.read()
        key = _get_encryption_key(master_key)
        fernet = Fernet(key)
        plaintext = fernet.decrypt(encrypted)
        with open(file_path, "wb") as f:
            f.write(plaintext)
        return True
    except Exception:
        return False


def extract_text_from_pdf(pdf_path: str, separator: str = "\n") -> str:
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return separator.join(text_parts)
    except ImportError:
        return ""


def extract_json(text: str) -> str:
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text)

    pairs = {'{': '}', '[': ']'}
    start = -1
    for ch in ('{', '['):
        pos = text.find(ch)
        if pos >= 0 and (start < 0 or pos < start):
            start = pos

    if start < 0:
        return ""

    stack = []
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]

        if escape:
            escape = False
            continue

        if ch == '\\':
            escape = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch in pairs:
            stack.append(pairs[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
            if not stack:
                return text[start:i + 1]

    return ""


def safe_filename(name: str) -> str:
    return re.sub(r'[^\w\-.]', '_', os.path.basename(name))
