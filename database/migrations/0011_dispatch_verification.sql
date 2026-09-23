-- Phase 8: Inspector dispatch verification workflow.
-- Coexists with the existing FPS shop inspections. A dispatch verification
-- records whether the inspector has checked a manifest's vehicle, loading,
-- quantities and destination before or during transit.

CREATE TABLE IF NOT EXISTS dispatch_verifications (
  verification_id TEXT PRIMARY KEY,
  manifest_id TEXT NOT NULL REFERENCES dispatch_manifests(manifest_id),
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  inspector_id TEXT NOT NULL REFERENCES officers(officer_id),
  vehicle_verified BOOLEAN,
  loading_verified BOOLEAN,
  quantities_verified BOOLEAN,
  destination_verified BOOLEAN,
  manifest_hash_verified BOOLEAN,
  observations TEXT NOT NULL DEFAULT '',
  result TEXT NOT NULL DEFAULT 'PENDING'
    CHECK (result IN ('PENDING','VERIFIED','VARIANCE','REJECTED')),
  variance_details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  submitted_at TIMESTAMPTZ,
  UNIQUE(manifest_id, inspector_id)
);

CREATE INDEX IF NOT EXISTS idx_dv_inspector
  ON dispatch_verifications(inspector_id, result);
CREATE INDEX IF NOT EXISTS idx_dv_cycle
  ON dispatch_verifications(cycle);
CREATE INDEX IF NOT EXISTS idx_dv_manifest
  ON dispatch_verifications(manifest_id);
