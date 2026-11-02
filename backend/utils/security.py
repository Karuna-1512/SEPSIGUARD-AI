"""Password hashing and signed-cookie session helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.config import settings

ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(derived).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def serializer():
    return URLSafeTimedSerializer(settings.secret_key, salt="sepsiguard-auth-v1")


def make_session(user_id: int, csrf_token: str) -> str:
    return serializer().dumps({"user_id": user_id, "csrf_token": csrf_token})


def read_session(token: str) -> int | None:
    try:
        payload = serializer().loads(token, max_age=settings.session_hours * 3600)
        return int(payload["user_id"])
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return None


def read_csrf_token(token: str) -> str | None:
    try:
        payload = serializer().loads(token, max_age=settings.session_hours * 3600)
        value = payload.get("csrf_token")
        return value if isinstance(value, str) else None
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return None
