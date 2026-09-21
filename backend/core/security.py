"""
Security — password hashing, JWT, env-based secrets.
Uses Argon2 if available else bcrypt (passlib).
"""
import os
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-prod-32-bytes-min-recommended")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

# Prefer Argon2, fallback to bcrypt
try:
    pwd_ctx = CryptContext(schemes=["argon2","bcrypt"], deprecated="auto")
    # test argon2 available
    pwd_ctx.hash("test")
except Exception:
    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p: str) -> str:
    return pwd_ctx.hash(p)

def verify_password(p: str, h: str) -> bool:
    try:
        return pwd_ctx.verify(p, h)
    except Exception:
        return False

def create_access_token(sub: str, role: str, extra: dict = None) -> str:
    payload = {"sub": sub, "role": role, "type": "access", "iat": datetime.utcnow()}
    if extra: payload.update(extra)
    payload["exp"] = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
