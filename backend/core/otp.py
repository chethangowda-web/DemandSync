"""
OTP Service — abstraction with Development vs Production provider.
No hardcoded universal OTP. Expiry, one-time, attempt limit, cooldown, audit.
"""
import random, hashlib, time
from datetime import datetime, timedelta
from typing import Dict, Optional

class OtpProvider:
    def send(self, identifier: str, otp: str): raise NotImplementedError

class DevelopmentOtpProvider(OtpProvider):
    def send(self, identifier: str, otp: str):
        # Dev: log to console (never in prod), not stored plaintext permanently
        print(f"[DEV OTP] {identifier} -> {otp} (expires 5 min, one-time)")

class ProductionOtpProvider(OtpProvider):
    def send(self, identifier: str, otp: str):
        # Placeholder for Firebase/SMS gateway
        raise NotImplementedError("Production SMS not configured")

class OtpService:
    def __init__(self, provider: OtpProvider, expiry_minutes=5, max_attempts=3, resend_cooldown_seconds=60):
        self.provider = provider
        self.expiry = expiry_minutes
        self.max_attempts = max_attempts
        self.cooldown = resend_cooldown_seconds
        # store: identifier -> {otp_hash, expires_at, attempts, last_sent, verified}
        self._store: Dict[str, dict] = {}
        self._audit = []  # in-memory audit for Phase 0; DB-backed later

    def _hash(self, otp: str) -> str: return hashlib.sha256(otp.encode()).hexdigest()

    def request_otp(self, identifier: str) -> dict:
        now = datetime.utcnow()
        entry = self._store.get(identifier)
        if entry and (now - entry["last_sent"]).total_seconds() < self.cooldown:
            remaining = int(self.cooldown - (now - entry["last_sent"]).total_seconds())
            self._audit.append({"action":"OTP_REQUEST_THROTTLED","identifier":identifier,"timestamp":now.isoformat(),"result":"FAIL","reason":f"Cooldown {remaining}s"})
            return {"error": f"Resend cooldown active. Try again in {remaining}s", "retry_after": remaining}
        otp = f"{random.randint(100000,999999):06d}"  # no universal 123456
        otp_hash = self._hash(otp)
        self._store[identifier] = {
            "otp_hash": otp_hash, "expires_at": now + timedelta(minutes=self.expiry),
            "attempts": 0, "last_sent": now, "verified": False
        }
        self.provider.send(identifier, otp)
        self._audit.append({"action":"OTP_SENT","identifier":identifier,"timestamp":now.isoformat(),"result":"SUCCESS"})
        # Dev mode: return otp in response only when provider is Development (explicitly noted)
        dev_expose = isinstance(self.provider, DevelopmentOtpProvider)
        return {"message":"OTP sent","expires_in":self.expiry*60, "dev_otp": otp if dev_expose else None, "note": "DEV MODE — production uses SMS" if dev_expose else "OTP sent via SMS"}

    def verify_otp(self, identifier: str, otp: str) -> dict:
        now = datetime.utcnow()
        entry = self._store.get(identifier)
        if not entry:
            self._audit.append({"action":"OTP_FAILURE","identifier":identifier,"timestamp":now.isoformat(),"result":"FAIL","reason":"No OTP requested"})
            return {"valid": False, "error": "No OTP requested. Please request OTP first."}
        if entry["verified"]:
            return {"valid": False, "error": "OTP already used. Request new OTP."}
        if now > entry["expires_at"]:
            self._audit.append({"action":"OTP_FAILURE","identifier":identifier,"timestamp":now.isoformat(),"result":"FAIL","reason":"Expired"})
            return {"valid": False, "error": "OTP expired. Please request new OTP."}
        if entry["attempts"] >= self.max_attempts:
            self._audit.append({"action":"OTP_FAILURE","identifier":identifier,"timestamp":now.isoformat(),"result":"FAIL","reason":"Max attempts exceeded"})
            return {"valid": False, "error": "Too many attempts. Request new OTP."}
        if self._hash(otp) != entry["otp_hash"]:
            entry["attempts"] += 1
            remaining = self.max_attempts - entry["attempts"]
            self._audit.append({"action":"OTP_FAILURE","identifier":identifier,"timestamp":now.isoformat(),"result":"FAIL","reason":"Invalid OTP"})
            return {"valid": False, "error": f"Invalid OTP. {remaining} attempts remaining." if remaining>0 else "Invalid OTP. Max attempts exceeded. Request new OTP."}
        # success — one-time
        entry["verified"] = True
        # do not store plaintext OTP; keep hash only until expiry then allow cleanup
        self._audit.append({"action":"OTP_VERIFIED","identifier":identifier,"timestamp":now.isoformat(),"result":"SUCCESS"})
        # mark as consumed (prevent reuse)
        entry["otp_hash"] = "CONSUMED"
        return {"valid": True}

    def get_audit(self): return self._audit

# Singleton for Phase 0
otp_service = OtpService(DevelopmentOtpProvider())
