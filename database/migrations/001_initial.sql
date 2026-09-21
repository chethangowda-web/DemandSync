-- PDS PREDICT Prototype — Initial Schema (PostgreSQL + PostGIS)
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE beneficiaries (
  id TEXT PRIMARY KEY,
  household_size INT NOT NULL,
  entitlement_kg NUMERIC NOT NULL CHECK (entitlement_kg > 0),
  current_fps_id TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE fps (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  capacity_kg NUMERIC NOT NULL,
  location GEOGRAPHY(POINT, 4326) NOT NULL,
  warehouse_id TEXT,
  district TEXT
);

CREATE TABLE warehouses (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  location GEOGRAPHY(POINT, 4326) NOT NULL,
  stock_kg NUMERIC NOT NULL
);

CREATE TABLE vehicles (
  id TEXT PRIMARY KEY,
  capacity_kg NUMERIC NOT NULL,
  status TEXT DEFAULT 'available'
);

CREATE TABLE allocations (
  id SERIAL PRIMARY KEY,
  fps_id TEXT REFERENCES fps(id),
  cycle TEXT NOT NULL,
  allocated_kg NUMERIC NOT NULL,
  UNIQUE(fps_id, cycle)
);

CREATE TABLE preferences (
  id SERIAL PRIMARY KEY,
  beneficiary_id TEXT REFERENCES beneficiaries(id),
  fps_id TEXT REFERENCES fps(id),
  cycle TEXT NOT NULL,
  quantity_kg NUMERIC NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(beneficiary_id, cycle)
);

CREATE TABLE demand_predictions (
  id SERIAL PRIMARY KEY,
  fps_id TEXT REFERENCES fps(id),
  cycle TEXT NOT NULL,
  predicted_kg NUMERIC NOT NULL,
  method TEXT, -- 'aggregated' | 'xgboost'
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE demand_locks (
  id SERIAL PRIMARY KEY,
  cycle TEXT UNIQUE NOT NULL,
  locked_at TIMESTAMPTZ DEFAULT now(),
  locked_by TEXT,
  snapshot JSONB NOT NULL -- immutable snapshot of demand per FPS
);

CREATE TABLE dispatch_manifests (
  id TEXT PRIMARY KEY, -- e.g. DSP-2026-001
  cycle TEXT NOT NULL,
  warehouse_id TEXT REFERENCES warehouses(id),
  vehicle_id TEXT REFERENCES vehicles(id),
  total_kg NUMERIC NOT NULL,
  utilization_pct NUMERIC,
  status TEXT NOT NULL CHECK (status IN ('DRAFT','LOCKED','DISPATCHED','DELIVERED','EXCEPTION')),
  hash TEXT NOT NULL, -- SHA256
  qr_payload TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE manifest_items (
  id SERIAL PRIMARY KEY,
  manifest_id TEXT REFERENCES dispatch_manifests(id) ON DELETE CASCADE,
  fps_id TEXT REFERENCES fps(id),
  quantity_kg NUMERIC NOT NULL
);

CREATE TABLE exceptions (
  id SERIAL PRIMARY KEY,
  manifest_id TEXT REFERENCES dispatch_manifests(id),
  fps_id TEXT,
  reason TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE deliveries (
  id SERIAL PRIMARY KEY,
  manifest_id TEXT REFERENCES dispatch_manifests(id),
  fps_id TEXT REFERENCES fps(id),
  delivered_kg NUMERIC,
  verified BOOLEAN DEFAULT false,
  delivered_at TIMESTAMPTZ
);

CREATE TABLE audit_logs (
  id SERIAL PRIMARY KEY,
  who TEXT NOT NULL,
  what TEXT NOT NULL,
  when_at TIMESTAMPTZ DEFAULT now(),
  why TEXT,
  result TEXT,
  manifest_id TEXT,
  hash TEXT
);

CREATE TABLE users (
  id TEXT PRIMARY KEY,
  role TEXT NOT NULL CHECK (role IN ('beneficiary','fps_dealer','district_officer','admin')),
  password_hash TEXT NOT NULL
);
