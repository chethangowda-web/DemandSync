-- Phase 8: Cross-officer workflow events.
-- Every important cross-role action persists an event here. Events drive the
-- "ACTION REQUIRED" queues in each portal. They are never deleted; they move
-- through PENDING → ACKNOWLEDGED → COMPLETED (or DISMISSED).

CREATE TABLE IF NOT EXISTS workflow_events (
  event_id TEXT PRIMARY KEY,
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  event_type TEXT NOT NULL,
  source_role TEXT NOT NULL,
  target_role TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING','ACKNOWLEDGED','COMPLETED','DISMISSED')),
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  completed_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_wf_events_target_status
  ON workflow_events(target_role, status);
CREATE INDEX IF NOT EXISTS idx_wf_events_cycle_type
  ON workflow_events(cycle, event_type);
CREATE INDEX IF NOT EXISTS idx_wf_events_entity
  ON workflow_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_wf_events_created
  ON workflow_events(created_at DESC);

-- Auditor review records. An auditor can accept/reject a cycle review,
-- but CANNOT modify operational records.
CREATE TABLE IF NOT EXISTS audit_reviews (
  review_id TEXT PRIMARY KEY,
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  reviewer_id TEXT NOT NULL REFERENCES officers(officer_id),
  result TEXT NOT NULL CHECK (result IN ('ACCEPTED','REJECTED','EXCEPTION')),
  findings JSONB NOT NULL DEFAULT '[]'::jsonb,
  notes TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_reviews_cycle ON audit_reviews(cycle);
