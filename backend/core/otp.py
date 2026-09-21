"""Beneficiary OTP service, backed by the otp_challenges table (survives restarts, works across instances).

- 6-digit code from a CSPRNG; no universal/fixed code.
- Only an HMAC of the code is stored, never the code.
- 5 minute expiry, single use, 3 attempts, 60 second resend cooldown.
- Delivery goes through a provider chosen by OTP_PROVIDER: "dev" (returns the code in the API response, for
  synthetic-data demos only) or unset/"none" (no delivery configured -> the request is refused).
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import psycopg

from backend.core.security import JWT_SECRET

EXPIRY_MINUTES = 5
MAX_ATTEMPTS = 3
COOLDOWN_SECONDS = 60


class OtpProviderNotConfigured(RuntimeError):
    pass


class OtpThrottled(RuntimeError):
    def __init__(self, retry_after: int):
        super().__init__(f"Resend cooldown active. Try again in {retry_after}s")
        self.retry_after = retry_after


def provider_name() -> str:
    return os.getenv("OTP_PROVIDER", "none").lower()


def _mac(identifier: str, otp: str) -> str:
    return hmac.new(JWT_SECRET.encode(), f"{identifier}:{otp}".encode(), hashlib.sha256).hexdigest()


def request_otp(conn: psycopg.Connection, ration_card_id: str) -> dict:
    """Create a challenge and 'deliver' it. Raises OtpProviderNotConfigured or OtpThrottled."""
    provider = provider_name()
    if provider != "dev":
        # A real SMS gateway would be wired in here. Refuse rather than pretend a code was sent.
        raise OtpProviderNotConfigured("SMS delivery is not configured")
    now = datetime.now(timezone.utc)
    row = conn.execute("SELECT last_sent_at FROM otp_challenges WHERE ration_card_id = %s FOR UPDATE",
                       (ration_card_id,)).fetchone()
    if row:
        elapsed = (now - row[0]).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            raise OtpThrottled(int(COOLDOWN_SECONDS - elapsed) + 1)
    otp = f"{secrets.randbelow(900_000) + 100_000:06d}"
    conn.execute(
        """INSERT INTO otp_challenges (ration_card_id, otp_hash, expires_at, attempts, last_sent_at, consumed)
           VALUES (%s, %s, %s, 0, %s, false)
           ON CONFLICT (ration_card_id) DO UPDATE SET otp_hash = EXCLUDED.otp_hash, expires_at = EXCLUDED.expires_at,
               attempts = 0, last_sent_at = EXCLUDED.last_sent_at, consumed = false""",
        (ration_card_id, _mac(ration_card_id, otp), now + timedelta(minutes=EXPIRY_MINUTES), now))
    return {"message": "OTP sent", "expires_in": EXPIRY_MINUTES * 60, "provider": "dev", "dev_otp": otp,
            "note": "DEV MODE: the code is returned here because no SMS gateway is configured"}


def verify_otp(conn: psycopg.Connection, ration_card_id: str, otp: str) -> tuple[bool, str]:
    """Returns (valid, reason). The caller must commit so failed attempts persist."""
    now = datetime.now(timezone.utc)
    row = conn.execute(
        "SELECT otp_hash, expires_at, attempts, consumed FROM otp_challenges WHERE ration_card_id = %s FOR UPDATE",
        (ration_card_id,)).fetchone()
    if not row:
        return False, "No OTP requested. Please request an OTP first."
    otp_hash, expires_at, attempts, consumed = row
    if consumed:
        return False, "OTP already used. Request a new OTP."
    if now > expires_at:
        return False, "OTP expired. Please request a new OTP."
    if attempts >= MAX_ATTEMPTS:
        return False, "Too many attempts. Request a new OTP."
    if not hmac.compare_digest(otp_hash, _mac(ration_card_id, otp)):
        conn.execute("UPDATE otp_challenges SET attempts = attempts + 1 WHERE ration_card_id = %s", (ration_card_id,))
        left = MAX_ATTEMPTS - attempts - 1
        return False, f"Invalid OTP. {left} attempts remaining." if left > 0 else "Invalid OTP. Request a new OTP."
    conn.execute("UPDATE otp_challenges SET consumed = true WHERE ration_card_id = %s", (ration_card_id,))
    return True, ""
