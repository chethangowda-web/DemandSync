-- Phase 3: Field Food Inspector workflow fields on the existing inspections table.
-- Existing columns (stock_*, finding, evidence_reference, ...) are kept; the structured
-- field workflow (verification checklist, inspection checklist, findings, evidence items,
-- notes) is stored as JSONB so the pre-dispatch schema stays stable.
ALTER TABLE inspections
  ADD COLUMN IF NOT EXISTS verification JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS checklist JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS findings JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS notes TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_inspections_inspector_status ON inspections (inspector_id, status);
CREATE INDEX IF NOT EXISTS idx_inspections_fps ON inspections (fps_id);
