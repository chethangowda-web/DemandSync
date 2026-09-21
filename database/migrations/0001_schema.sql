-- DemandSYNC schema v1: mirrors the 23 dataset files 1:1, plus platform tables.
-- Geometry: plain latitude/longitude columns for now; PostGIS columns are added in the routing phase.

CREATE TABLE cycles (
  cycle TEXT PRIMARY KEY CHECK (cycle ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
  state TEXT NOT NULL CHECK (state IN ('OPEN','MONITOR','LOCKED','ALLOCATED','OPTIMIZED','AUTHORIZED','TRACKING','DELIVERING','RECONCILING','AUDITING','CLOSED')),
  choice_window_start DATE,
  choice_window_end DATE,
  locked_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE officers (
  officer_id TEXT PRIMARY KEY,
  employee_code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('DISTRICT_OFFICER','FIELD_FOOD_INSPECTOR','FPS_OWNER','ADMIN','AUDITOR')),
  district TEXT,
  phone TEXT,
  status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE warehouses (
  warehouse_id TEXT PRIMARY KEY,
  warehouse_name TEXT NOT NULL,
  district TEXT NOT NULL,
  latitude NUMERIC(9,6) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
  longitude NUMERIC(9,6) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
  rice_stock_kg NUMERIC NOT NULL CHECK (rice_stock_kg >= 0),
  wheat_stock_kg NUMERIC NOT NULL CHECK (wheat_stock_kg >= 0),
  total_capacity_kg NUMERIC NOT NULL CHECK (total_capacity_kg > 0),
  status TEXT NOT NULL
);

CREATE TABLE fps (
  fps_id TEXT PRIMARY KEY,
  fps_name TEXT NOT NULL,
  owner_id TEXT REFERENCES officers(officer_id),
  district TEXT NOT NULL,
  taluk TEXT,
  latitude NUMERIC(9,6) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
  longitude NUMERIC(9,6) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
  capacity_kg NUMERIC NOT NULL CHECK (capacity_kg > 0),
  warehouse_id TEXT NOT NULL REFERENCES warehouses(warehouse_id),
  status TEXT NOT NULL,
  opening_hours TEXT,
  created_at DATE
);
CREATE INDEX idx_fps_warehouse ON fps(warehouse_id);

CREATE TABLE vehicles (
  vehicle_id TEXT PRIMARY KEY,
  vehicle_number TEXT NOT NULL UNIQUE,
  vehicle_type TEXT NOT NULL,
  capacity_kg NUMERIC NOT NULL CHECK (capacity_kg > 0),
  current_status TEXT NOT NULL,
  warehouse_id TEXT NOT NULL REFERENCES warehouses(warehouse_id),
  driver_id TEXT,
  latitude NUMERIC(9,6) CHECK (latitude BETWEEN -90 AND 90),
  longitude NUMERIC(9,6) CHECK (longitude BETWEEN -180 AND 180),
  availability_start TIMESTAMPTZ,
  availability_end TIMESTAMPTZ
);

CREATE TABLE beneficiaries (
  beneficiary_id TEXT PRIMARY KEY,
  ration_card_id TEXT NOT NULL UNIQUE,
  head_of_household TEXT NOT NULL,
  household_size INT NOT NULL CHECK (household_size > 0),
  scheme_type TEXT NOT NULL CHECK (scheme_type IN ('AAY','PHH')),
  entitlement_kg NUMERIC NOT NULL CHECK (entitlement_kg > 0),
  rice_entitlement_kg NUMERIC NOT NULL CHECK (rice_entitlement_kg >= 0),
  wheat_entitlement_kg NUMERIC NOT NULL CHECK (wheat_entitlement_kg >= 0),
  current_fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  district TEXT NOT NULL,
  taluk TEXT,
  latitude NUMERIC(9,6) CHECK (latitude BETWEEN -90 AND 90),
  longitude NUMERIC(9,6) CHECK (longitude BETWEEN -180 AND 180),
  registered_mobile TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at DATE,
  CONSTRAINT entitlement_is_rice_plus_wheat CHECK (entitlement_kg = rice_entitlement_kg + wheat_entitlement_kg)
);
CREATE INDEX idx_beneficiaries_fps ON beneficiaries(current_fps_id);

CREATE TABLE historical_demand (
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  commodity TEXT NOT NULL CHECK (commodity IN ('RICE','WHEAT')),
  demand_kg NUMERIC NOT NULL CHECK (demand_kg >= 0),
  beneficiary_count INT,
  season TEXT,
  month INT CHECK (month BETWEEN 1 AND 12),
  year INT,
  previous_demand_kg NUMERIC,
  trend_factor NUMERIC,
  season_factor NUMERIC,
  stockout_flag INT,
  PRIMARY KEY (fps_id, cycle, commodity)
);

CREATE TABLE intent_signals (
  intent_id TEXT PRIMARY KEY,
  beneficiary_id TEXT NOT NULL REFERENCES beneficiaries(beneficiary_id),
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  rice_quantity_kg NUMERIC NOT NULL CHECK (rice_quantity_kg >= 0),
  wheat_quantity_kg NUMERIC NOT NULL CHECK (wheat_quantity_kg >= 0),
  total_quantity_kg NUMERIC NOT NULL CHECK (total_quantity_kg >= 0),
  collection_mode TEXT NOT NULL,
  submitted_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('SUBMITTED','CANCELLED')),
  CONSTRAINT intent_total CHECK (total_quantity_kg = rice_quantity_kg + wheat_quantity_kg)
);
-- one live intent per beneficiary per cycle
CREATE UNIQUE INDEX uq_intent_beneficiary_cycle ON intent_signals(beneficiary_id, cycle) WHERE status = 'SUBMITTED';
CREATE INDEX idx_intent_cycle_fps ON intent_signals(cycle, fps_id);

CREATE TABLE demand_forecast (
  forecast_id TEXT PRIMARY KEY,
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  commodity TEXT NOT NULL CHECK (commodity IN ('RICE','WHEAT')),
  baseline_demand_kg NUMERIC NOT NULL CHECK (baseline_demand_kg >= 0),
  intent_demand_kg NUMERIC NOT NULL CHECK (intent_demand_kg >= 0),
  forecast_demand_kg NUMERIC NOT NULL CHECK (forecast_demand_kg >= 0),
  model_version TEXT NOT NULL,
  prediction_generated_at TIMESTAMPTZ NOT NULL,
  training_dataset_version TEXT NOT NULL,
  prediction_horizon TEXT
);
CREATE INDEX idx_forecast_cycle ON demand_forecast(cycle, fps_id);

CREATE TABLE allocations (
  allocation_id TEXT PRIMARY KEY,
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  commodity TEXT NOT NULL CHECK (commodity IN ('RICE','WHEAT')),
  requested_kg NUMERIC NOT NULL CHECK (requested_kg >= 0),
  allocated_kg NUMERIC NOT NULL CHECK (allocated_kg >= 0),
  warehouse_id TEXT NOT NULL REFERENCES warehouses(warehouse_id),
  status TEXT NOT NULL CHECK (status IN ('APPROVED','BLOCKED')),
  source TEXT,
  approved_by TEXT REFERENCES officers(officer_id),
  approved_at TIMESTAMPTZ
);
CREATE INDEX idx_alloc_cycle ON allocations(cycle, fps_id);

CREATE TABLE dispatch_manifests (
  manifest_id TEXT PRIMARY KEY,
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  warehouse_id TEXT NOT NULL REFERENCES warehouses(warehouse_id),
  vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),
  manifest_status TEXT NOT NULL CHECK (manifest_status IN ('DRAFT','VALIDATED','LOCKED','DISPATCHED','DELIVERED','RECONCILED')),
  total_kg NUMERIC NOT NULL CHECK (total_kg >= 0),
  route_distance_km NUMERIC,
  route_duration_min NUMERIC,
  constraint_status TEXT NOT NULL CHECK (constraint_status IN ('READY','BLOCKED')),
  created_by TEXT REFERENCES officers(officer_id),
  created_at TIMESTAMPTZ,
  locked_by TEXT REFERENCES officers(officer_id),
  locked_at TIMESTAMPTZ,
  sha256_hash TEXT,
  qr_payload TEXT
);
CREATE INDEX idx_manifest_cycle ON dispatch_manifests(cycle);

CREATE TABLE dispatch_manifest_items (
  manifest_item_id TEXT PRIMARY KEY,
  manifest_id TEXT NOT NULL REFERENCES dispatch_manifests(manifest_id),
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  commodity TEXT NOT NULL CHECK (commodity IN ('RICE','WHEAT')),
  planned_kg NUMERIC NOT NULL CHECK (planned_kg >= 0),
  sequence_number INT NOT NULL,
  allocation_id TEXT REFERENCES allocations(allocation_id)
);
CREATE INDEX idx_manifest_items_manifest ON dispatch_manifest_items(manifest_id);

CREATE TABLE delivery_history (
  delivery_id TEXT PRIMARY KEY,
  manifest_id TEXT NOT NULL REFERENCES dispatch_manifests(manifest_id),
  manifest_item_id TEXT NOT NULL REFERENCES dispatch_manifest_items(manifest_item_id),
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),
  planned_kg NUMERIC NOT NULL CHECK (planned_kg >= 0),
  delivered_kg NUMERIC NOT NULL CHECK (delivered_kg >= 0),
  delivery_date TIMESTAMPTZ,
  rice_kg NUMERIC,
  wheat_kg NUMERIC,
  status TEXT NOT NULL CHECK (status IN ('VERIFIED','VARIANCE','REJECTED')),
  verified_by TEXT REFERENCES officers(officer_id)
);
CREATE INDEX idx_delivery_manifest ON delivery_history(manifest_id);

CREATE TABLE epos_transactions (
  transaction_id TEXT PRIMARY KEY,
  beneficiary_id TEXT NOT NULL REFERENCES beneficiaries(beneficiary_id),
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  commodity TEXT NOT NULL CHECK (commodity IN ('RICE','WHEAT')),
  quantity_kg NUMERIC NOT NULL CHECK (quantity_kg > 0),
  transaction_time TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('SUCCESS','CANCELLED','FAILED')),
  receipt_number TEXT
);
CREATE INDEX idx_epos_beneficiary_cycle ON epos_transactions(beneficiary_id, cycle);
CREATE INDEX idx_epos_cycle ON epos_transactions(cycle);

CREATE TABLE inventory (
  inventory_id TEXT PRIMARY KEY,
  location_type TEXT NOT NULL CHECK (location_type IN ('WAREHOUSE','FPS')),
  location_id TEXT NOT NULL,
  commodity TEXT NOT NULL CHECK (commodity IN ('RICE','WHEAT')),
  opening_stock_kg NUMERIC NOT NULL CHECK (opening_stock_kg >= 0),
  received_kg NUMERIC NOT NULL CHECK (received_kg >= 0),
  dispatched_kg NUMERIC NOT NULL CHECK (dispatched_kg >= 0),
  distributed_kg NUMERIC NOT NULL CHECK (distributed_kg >= 0),
  closing_stock_kg NUMERIC NOT NULL CHECK (closing_stock_kg >= 0),
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  CONSTRAINT inventory_balance CHECK (closing_stock_kg = opening_stock_kg + received_kg - dispatched_kg - distributed_kg)
);
CREATE INDEX idx_inventory_loc ON inventory(location_type, location_id, cycle);

CREATE TABLE vehicle_routes (
  route_id TEXT PRIMARY KEY,
  manifest_id TEXT NOT NULL REFERENCES dispatch_manifests(manifest_id),
  vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),
  warehouse_id TEXT NOT NULL REFERENCES warehouses(warehouse_id),
  stop_sequence INT NOT NULL,
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  latitude NUMERIC(9,6) NOT NULL CHECK (latitude BETWEEN -90 AND 90),
  longitude NUMERIC(9,6) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
  distance_from_previous_km NUMERIC,
  eta_minutes NUMERIC,
  route_status TEXT NOT NULL
);
CREATE INDEX idx_routes_manifest ON vehicle_routes(manifest_id, stop_sequence);

-- telemetry is intentionally sparse (~12% gaps): coordinates may be absent.
CREATE TABLE vehicle_telemetry (
  telemetry_id TEXT PRIMARY KEY,
  vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),
  timestamp TIMESTAMPTZ NOT NULL,
  latitude NUMERIC(9,6) CHECK (latitude BETWEEN -90 AND 90),
  longitude NUMERIC(9,6) CHECK (longitude BETWEEN -180 AND 180),
  speed_kmph NUMERIC CHECK (speed_kmph >= 0),
  status TEXT NOT NULL,
  manifest_id TEXT REFERENCES dispatch_manifests(manifest_id)
);
CREATE INDEX idx_telemetry_vehicle ON vehicle_telemetry(vehicle_id, timestamp);

CREATE TABLE inspections (
  inspection_id TEXT PRIMARY KEY,
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  inspector_id TEXT NOT NULL REFERENCES officers(officer_id),
  inspection_date TIMESTAMPTZ NOT NULL,
  stock_expected_kg NUMERIC,
  stock_observed_kg NUMERIC,
  stock_variance_kg NUMERIC,
  weighing_accuracy NUMERIC,
  moisture_status TEXT,
  shop_condition TEXT,
  stock_register_verified TEXT,
  epos_verified TEXT,
  finding TEXT,
  status TEXT NOT NULL CHECK (status IN ('DRAFT','SUBMITTED','SEALED')),
  evidence_reference TEXT,
  sealed_hash TEXT
);

CREATE TABLE grievances (
  grievance_id TEXT PRIMARY KEY,
  beneficiary_id TEXT NOT NULL REFERENCES beneficiaries(beneficiary_id),
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  category TEXT NOT NULL,
  description TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('OPEN','IN_REVIEW','RESOLVED','CLOSED')),
  resolution TEXT,
  resolved_at TIMESTAMPTZ
);

-- audit_events is append-only (see 0002_immutability.sql)
CREATE TABLE audit_events (
  audit_event_id TEXT PRIMARY KEY,
  cycle TEXT REFERENCES cycles(cycle),
  actor_user_id TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  reason TEXT,
  result TEXT NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL,
  before_state TEXT,
  after_state TEXT,
  hash TEXT
);
CREATE INDEX idx_audit_cycle ON audit_events(cycle);
CREATE INDEX idx_audit_entity ON audit_events(entity_type, entity_id);

CREATE TABLE exceptions (
  exception_id TEXT PRIMARY KEY,
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  rule_code TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('HIGH','MEDIUM','LOW')),
  reason TEXT NOT NULL,
  detected_at TIMESTAMPTZ NOT NULL,
  assigned_to TEXT REFERENCES officers(officer_id),
  status TEXT NOT NULL CHECK (status IN ('OPEN','ACKNOWLEDGED','ACTION_REQUIRED','RESOLVED','CLOSED')),
  resolution TEXT,
  resolved_at TIMESTAMPTZ
);
CREATE INDEX idx_exceptions_cycle ON exceptions(cycle);

CREATE TABLE weather (
  date DATE NOT NULL,
  district TEXT NOT NULL,
  rainfall_mm NUMERIC,
  temperature_c NUMERIC,
  weather_condition TEXT,
  PRIMARY KEY (date, district)
);

CREATE TABLE calendar_events (
  date DATE NOT NULL,
  district TEXT NOT NULL,
  event_name TEXT NOT NULL,
  event_type TEXT NOT NULL,
  impact_factor NUMERIC,
  PRIMARY KEY (date, district, event_name)
);

CREATE TABLE historical_stockouts (
  fps_id TEXT NOT NULL REFERENCES fps(fps_id),
  cycle TEXT NOT NULL REFERENCES cycles(cycle),
  commodity TEXT NOT NULL CHECK (commodity IN ('RICE','WHEAT')),
  stockout_flag INT,
  stockout_days INT,
  shortage_kg NUMERIC,
  PRIMARY KEY (fps_id, cycle, commodity)
);

-- Platform tables ---------------------------------------------------------

CREATE TABLE dataset_imports (
  import_id TEXT PRIMARY KEY,
  dataset_name TEXT NOT NULL,
  version TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('IMPORTED','VALIDATED','ACTIVE','REJECTED')),
  total_rows INT NOT NULL,
  row_counts JSONB NOT NULL,
  checksum TEXT NOT NULL,
  validation_report JSONB NOT NULL,
  imported_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE demand_locks (
  cycle TEXT PRIMARY KEY REFERENCES cycles(cycle),
  locked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  locked_by TEXT NOT NULL,
  snapshot JSONB NOT NULL,
  sha256_hash TEXT NOT NULL
);

CREATE TABLE ai_predictions (
  prediction_id TEXT PRIMARY KEY,
  service TEXT NOT NULL,
  cycle TEXT REFERENCES cycles(cycle),
  entity_type TEXT,
  entity_id TEXT,
  prediction JSONB NOT NULL,
  confidence NUMERIC CHECK (confidence BETWEEN 0 AND 100),
  reason TEXT NOT NULL,
  supporting_data JSONB,
  model_version TEXT NOT NULL,
  training_dataset_version TEXT,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ai_cycle_service ON ai_predictions(cycle, service);
