"""Security primitives: password hashing, JWT issue/verify, secret handling.

The JWT secret comes from the environment. In production a missing or short secret is a startup error;
there is no silent fallback. The signing algorithm is fixed (never read from the environment or token).
"""
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from jose import ExpiredSignatureError, JWTError, jwt  # noqa: F401  (re-exported for callers)
from passlib.context import CryptContext

APP_ENV = os.getenv("APP_ENV", "development")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
_DEV_ONLY_SECRET = "dev-only-secret-never-use-in-production-0123456789"


def _load_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if APP_ENV == "production":
        if not secret or len(secret) < 32:
            raise RuntimeError("JWT_SECRET must be set to at least 32 characters when APP_ENV=production")
        return secret
    return secret or _DEV_ONLY_SECRET


JWT_SECRET = _load_secret()

pwd_ctx = CryptContext(schemes=["argon2"], deprecated="auto")

PASSWORD_MIN_LENGTH = 10


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return pwd_ctx.verify(password, hashed)
    except Exception:
        return False


def password_policy_error(password: str, user_id: str = "") -> str | None:
    """Return a human-readable reason if the password is unacceptable, else None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain both letters and digits."
    if user_id and user_id.lower() in password.lower():
        return "Password must not contain your user ID."
    return None


def create_access_token(sub: str, role: str, minutes: int | None = None) -> str:
    """Minimal claims only: subject, role, unique id, issue/expiry times. No PII."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes or JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises ExpiredSignatureError / JWTError. Pins the algorithm; requires exp."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require_exp": True})
