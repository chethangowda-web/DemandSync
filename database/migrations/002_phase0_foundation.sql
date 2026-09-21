-- Phase 0 Foundation — Cycles, Dataset Imports, AI Predictions, Audit Enhancements
-- Extends 001_initial.sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- CYCLES
CREATE TABLE IF NOT EXISTS cycles (
  cycle TEXT PRIMARY KEY, -- YYYY-MM e.g. 2026-03
  state TEXT NOT NULL CHECK (state IN ('OPEN','MONITOR','LOCKED','ALLOCATED','OPTIMIZED','AUTHORIZED','TRACKING','DELIVERING','RECONCILING','AUDITING','CLOSED')),
  choice_window_start DATE,
  choice_window_end DATE,
  locked_at TIMESTAMPTZ,
  locked_by TEXT REFERENCES officers_master(officer_id),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- DATASET IMPORTS (Phase 1 Data Trust)
CREATE TABLE IF NOT EXISTS dataset_imports (
  import_id TEXT PRIMARY KEY,
  dataset TEXT NOT NULL,
  version TEXT NOT NULL,
  rows_imported INT NOT NULL,
  source TEXT,
  status TEXT NOT NULL CHECK (status IN ('IMPORTED','VALIDATED','ACTIVE','REJECTED')),
  validation_report JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  approved_by TEXT,
  approved_at TIMESTAMPTZ
);

-- AI PREDICTIONS (Phase 4,6,9 etc — generic)
CREATE TABLE IF NOT EXISTS ai_predictions (
  prediction_id TEXT PRIMARY KEY,
  service TEXT NOT NULL, -- demand_forecast, anomaly, etc
  cycle TEXT REFERENCES cycles(cycle),
  entity_type TEXT,
  entity_id TEXT,
  prediction JSONB NOT NULL,
  confidence NUMERIC,
  reason TEXT,
  supporting_data JSONB,
  model_version TEXT,
  training_dataset_version TEXT,
  generated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_ai_cycle_service ON ai_predictions(cycle, service);

CREATE TABLE IF NOT EXISTS ai_insights (
  insight_id TEXT PRIMARY KEY,
  cycle TEXT REFERENCES cycles(cycle),
  service TEXT NOT NULL,
  insight_type TEXT, -- SIGNAL, RISK, ANOMALY
  title TEXT,
  description TEXT,
  severity TEXT CHECK (severity IN ('LOW','MEDIUM','HIGH')),
  supporting_data JSONB,
  model_version TEXT,
  generated_at TIMESTAMPTZ DEFAULT now()
);

-- Ensure audit_logs is append-only (trigger already planned)
-- Add immutability trigger for demand_locks if not exists
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='prevent_lock_mutation') THEN
    CREATE OR REPLACE FUNCTION prevent_lock_mutation() RETURNS trigger AS $f$
    BEGIN IF OLD.locked_at IS NOT NULL THEN RAISE EXCEPTION 'demand_locks immutable after lock'; END IF; RETURN NEW; END; $f$ LANGUAGE plpgsql;
    DROP TRIGGER IF EXISTS prevent_lock_mutation ON demand_locks;
    CREATE TRIGGER prevent_lock_mutation BEFORE UPDATE OR DELETE ON demand_locks FOR EACH ROW EXECUTE FUNCTION prevent_lock_mutation();
  END IF;
END $$;

-- Indexes for performance (Phase 0)
CREATE INDEX IF NOT EXISTS idx_beneficiaries_fps ON beneficiaries(current_fps_id);
CREATE INDEX IF NOT EXISTS idx_fps_warehouse ON fps(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_fps_gix ON fps USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_warehouse_gix ON warehouses USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_preferences_cycle ON preferences(cycle);
CREATE INDEX IF NOT EXISTS idx_intent_cycle ON intent_signals(cycle);
CREATE INDEX IF NOT EXISTS idx_forecast_cycle ON demand_forecast(cycle);
CREATE INDEX IF NOT EXISTS idx_alloc_cycle ON allocations(cycle);
CREATE INDEX IF NOT EXISTS idx_manifest_cycle ON dispatch_manifests(cycle);
CREATE INDEX IF NOT EXISTS idx_delivery_manifest ON delivery_history(manifest_id);
CREATE INDEX IF NOT EXISTS idx_epos_cycle ON epos_transactions(cycle);
CREATE INDEX IF NOT EXISTS idx_telemetry_vehicle ON vehicle_telemetry(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_audit_cycle ON audit_events(cycle);
CREATE INDEX IF NOT EXISTS idx_exceptions_cycle ON exceptions(cycle);

-- Seed cycles from dataset manifest
INSERT INTO cycles (cycle, state, choice_window_start, choice_window_end) VALUES
  ('2025-01','CLOSED','2025-01-05','2025-01-20'),
  ('2025-02','CLOSED','2025-02-05','2025-02-20'),
  ('2025-03','CLOSED','2025-03-05','2025-03-20'),
  ('2025-04','CLOSED','2025-04-05','2025-04-20'),
  ('2025-05','CLOSED','2025-05-05','2025-05-20'),
  ('2025-06','CLOSED','2025-06-05','2025-06-20'),
  ('2025-07','CLOSED','2025-07-05','2025-07-20'),
  ('2025-08','CLOSED','2025-08-05','2025-08-20'),
  ('2025-09','CLOSED','2025-09-05','2025-09-20'),
  ('2025-10','CLOSED','2025-10-05','2025-10-20'),
  ('2025-11','CLOSED','2025-11-05','2025-11-20'),
  ('2025-12','CLOSED','2025-12-05','2025-12-20'),
  ('2026-01','AUDITING','2026-01-05','2026-01-20'),
  ('2026-02','DELIVERING','2026-02-05','2026-02-20'),
  ('2026-03','MONITOR','2026-03-05','2026-03-20')
ON CONFLICT (cycle) DO NOTHING;
