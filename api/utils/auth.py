import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from api.constants import OSS_JWT_EXPIRY_HOURS, OSS_JWT_SECRET


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_jwt_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(UTC) + timedelta(hours=OSS_JWT_EXPIRY_HOURS),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, OSS_JWT_SECRET, algorithm="HS256")


def decode_jwt_token(token: str) -> dict:
    return jwt.decode(token, OSS_JWT_SECRET, algorithms=["HS256"])


def generate_reset_token() -> tuple[str, str]:
    """Return a ``(raw_token, token_hash)`` pair for a password reset.

    The raw token is sent to the user (in the reset link) and never stored;
    only its SHA-256 hash is persisted, so the database alone can't be used to
    reset a password.
    """
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_reset_token(raw_token)


def hash_reset_token(raw_token: str) -> str:
    """Hash a raw reset token for storage/lookup. Deterministic (SHA-256)."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
