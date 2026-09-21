# Placeholder — Phase 0 RBAC scaffold (JWT + bcrypt)
# Implements: JWT HS256 24h, passlib bcrypt, role decorator @require_role
# To be completed in Phase 0 with officers_master seed
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext

SECRET="dev-secret-change-in-prod"
ALGO="HS256"
pwd_ctx=CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p): return pwd_ctx.hash(p)
def verify_password(p,h): return pwd_ctx.verify(p,h)
def create_token(sub, role, expires_hours=24):
    payload={"sub":sub,"role":role,"exp":datetime.utcnow()+timedelta(hours=expires_hours)}
    return jwt.encode(payload, SECRET, algorithm=ALGO)
def require_role(*roles):
    def dep(user): 
        if user.get("role") not in roles: raise PermissionError("forbidden")
        return user
    return dep
