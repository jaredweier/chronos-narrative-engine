import base64
import json
import hmac
import hashlib
import time
from typing import Any, Dict, Optional

def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def _b64decode(data: str) -> bytes:
    padding = '=' * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data + padding)

def encode_jwt(payload: Dict[str, Any], secret: str, algorithm: str = 'HS256') -> str:
    if algorithm != 'HS256':
        raise ValueError("Only HS256 is supported")
    header = {'alg': algorithm, 'typ': 'JWT'}
    header_enc = _b64encode(json.dumps(header).encode('utf-8'))
    payload_enc = _b64encode(json.dumps(payload).encode('utf-8'))
    msg = f"{header_enc}.{payload_enc}"
    sig = hmac.new(secret.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).digest()
    sig_enc = _b64encode(sig)
    return f"{msg}.{sig_enc}"

def decode_jwt(token: str, secret: str) -> Dict[str, Any]:
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    header_enc, payload_enc, sig_enc = parts
    msg = f"{header_enc}.{payload_enc}"
    expected_sig = hmac.new(secret.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64decode(sig_enc), expected_sig):
        raise ValueError("Invalid signature")
    payload = json.loads(_b64decode(payload_enc).decode('utf-8'))
    if 'exp' in payload and payload['exp'] < time.time():
        raise ValueError("Token has expired")
    return payload
