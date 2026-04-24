"""Security utilities -- JWT token & password hashing.

Uses only stdlib (hmac, json, base64, hashlib) + bcrypt (already installed).
No external JWT library required.
"""

import json
import hmac
import hashlib
import base64
import time
import os

from passlib.context import CryptContext

# -- Password hashing ---------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# -- Lightweight JWT (HS256) --------------------------------------------------

_SECRET_KEY = os.environ.get("JWT_SECRET", "loanfibo-dev-secret-change-in-prod")
_ALG = "HS256"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_token(payload: dict, expires_sec: int = 86400) -> str:
    """Create a signed JWT-like token."""
    header = {"alg": _ALG, "typ": "JWT"}
    now = int(time.time())
    payload = {**payload, "iat": now, "exp": now + expires_sec}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        _SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(signature)
    return f"{signing_input}.{sig_b64}"


def decode_token(token: str) -> dict | None:
    """Decode and verify a JWT-like token. Returns payload or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            _SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        # Check expiration
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None
