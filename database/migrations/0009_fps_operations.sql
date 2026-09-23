-- Phase 4: FPS Owner operations.
-- New tables only (plus one additive ledger column); no existing table is redefined except the
-- inventory balance check, which is extended to include posted adjustments (existing rows get
-- adjusted_kg = 0, so their balances are unchanged).

-- Authorized adjustments post to the ledger instead of living only on paper.
ALTER TABLE inventory ADD COLUMN IF NOT EXISTS adjusted_kg NUMERIC NOT NULL DEFAULT 0;
ALTER TABLE inventory DROP CONSTRAINT IF EXISTS inventory_balance;
ALTER TABLE inventory ADD CONSTRAINT inventory_balance
  CHECK (closing_stock_kg = opening_stock_kg + received_kg - dispatched_kg - distributed_kg + adjusted_kg);

-- Replenishment requests with a real lifecycle. Only forward transitions are allowed;
-- the API enforces the transition map, the CHECK keeps stored values honest.
CREATE TABLE IF NOT EXISTS fps_stock_requests (
  request_id TEXT PRIMARY KEY,
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  commodity TEXT NOT NULL CHECK (commodity IN ('RICE','WHEAT')),
  current_stock_kg NUMERIC NOT NULL CHECK (current_stock_kg >= 0),
  requested_kg NUMERIC NOT NULL CHECK (requested_kg > 0),
  reason TEXT NOT NULL,
  requested_delivery_date DATE,
  status TEXT NOT NULL DEFAULT 'DRAFT'
    CHECK (status IN ('DRAFT','SUBMITTED','UNDER_REVIEW','APPROVED','DISPATCHED','RECEIVED','REJECTED')),
  requested_by TEXT NOT NULL REFERENCES officers(officer_id),
  reviewed_by TEXT REFERENCES officers(officer_id),
  decision_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  decided_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_fps_requests_shop ON fps_stock_requests(fps_id, cycle);

-- Day closures: one audited record per shop per business day, with the readiness checks snapshot.
CREATE TABLE IF NOT EXISTS fps_day_closures (
  closure_id TEXT PRIMARY KEY,
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  business_date DATE NOT NULL,
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  beneficiaries_served INT NOT NULL DEFAULT 0,
  transactions INT NOT NULL DEFAULT 0,
  rice_distributed_kg NUMERIC NOT NULL DEFAULT 0,
  wheat_distributed_kg NUMERIC NOT NULL DEFAULT 0,
  stock_remaining_kg NUMERIC NOT NULL DEFAULT 0,
  variances JSONB NOT NULL DEFAULT '[]'::jsonb,
  pending_requests INT NOT NULL DEFAULT 0,
  checks JSONB NOT NULL DEFAULT '{}'::jsonb,
  closed_by TEXT NOT NULL REFERENCES officers(officer_id),
  closed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (fps_id, business_date)
);

-- Stock events behind every FPS-owner ledger write (receipts, adjustments, returns, transfers).
CREATE TABLE IF NOT EXISTS fps_stock_events (
  event_id TEXT PRIMARY KEY,
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  commodity TEXT NOT NULL CHECK (commodity IN ('RICE','WHEAT')),
  event_type TEXT NOT NULL CHECK (event_type IN ('RECEIPT','ADJUSTMENT','RETURN','TRANSFER')),
  quantity_kg NUMERIC NOT NULL,
  reason TEXT NOT NULL,
  reference TEXT,
  recorded_by TEXT NOT NULL REFERENCES officers(officer_id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fps_events_shop ON fps_stock_events(fps_id, cycle);

-- Variance reviews: a detected variance stays visible until a named officer records a review note.
CREATE TABLE IF NOT EXISTS fps_variance_reviews (
  review_id TEXT PRIMARY KEY,
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  commodity TEXT NOT NULL CHECK (commodity IN ('RICE','WHEAT')),
  variance_kg NUMERIC NOT NULL,
  note TEXT NOT NULL,
  reviewed_by TEXT NOT NULL REFERENCES officers(officer_id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fps_reviews_shop ON fps_variance_reviews(fps_id, cycle);

CREATE SEQUENCE IF NOT EXISTS fps_request_seq START 1;
CREATE SEQUENCE IF NOT EXISTS fps_event_seq START 1;
CREATE SEQUENCE IF NOT EXISTS fps_review_seq START 1;
CREATE SEQUENCE IF NOT EXISTS epos_txn_seq START 1;
SELECT setval('epos_txn_seq',
  COALESCE((SELECT max(substring(transaction_id from 6)::int) FROM epos_transactions
            WHERE transaction_id ~ '^EPOS-[0-9]+$'), 0) + 1, false);
