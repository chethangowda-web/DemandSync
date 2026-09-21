-- Phase 0: authentication state lives in the database (nothing in process memory).

-- One credential row per officer who is allowed to sign in. Officers without a row cannot log in.
CREATE TABLE officer_credentials (
  officer_id TEXT PRIMARY KEY REFERENCES officers(officer_id),
  password_hash TEXT NOT NULL,
  must_change_password BOOLEAN NOT NULL DEFAULT false,
  failed_attempts INT NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
  locked_until TIMESTAMPTZ,
  password_changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Beneficiary one-time codes. Only an HMAC of the code is stored, never the code itself.
CREATE TABLE otp_challenges (
  ration_card_id TEXT PRIMARY KEY REFERENCES beneficiaries(ration_card_id),
  otp_hash TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  attempts INT NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_sent_at TIMESTAMPTZ NOT NULL,
  consumed BOOLEAN NOT NULL DEFAULT false
);

-- Logout / revocation list keyed by the JWT id.
CREATE TABLE revoked_tokens (
  jti TEXT PRIMARY KEY,
  expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_revoked_tokens_expiry ON revoked_tokens(expires_at);
