# DemandSYNC — Data Dictionary (Human-readable)
**K:\DemandSYNC | 2026-09-21 | Generated from `data/07_generated/data_dictionary.csv:237 rows` + `dataset_manifest.json`**

See CSV for machine-readable: `data/07_generated/data_dictionary.csv`, `relationship_map.csv`, `dataset_manifest.json`.

---

## 1. Overview — 23 Datasets, 83,763 Rows, 6 Districts, 15 Cycles (2025-01..2026-03)

Geography: Bengaluru Urban, Mysuru, Tumakuru, Mandya, Hassan, Shivamogga — coords deterministic seed 20260921.

## 2. Master (01_master)

| Dataset | Rows | PK | Key Columns | Business Rules |
|---------|------|----|-------------|----------------|
| **beneficiaries_master.csv** | 10,000 | `beneficiary_id` BEN-000001 | `ration_card_id` RC2023xxxxx, `household_size` 1-7, `scheme_type` PHH (82%)/AAY (18%), `entitlement_kg = rice+wheat`, `current_fps_id → fps`, `district/taluk`, `lat/lon` near FPS ±0.04°, `phone` 90000xxxxx synthetic | `entitlement` derived: AAY=35, PHH=5×hh; `rice ~60%`; no placeholder names; entitlement never changed by intent |
| **fps_master.csv** | 600 | `fps_id` FPS-0001 | `fps_name` unique ("Shakti FPS 001"), `owner_id → officers`, `capacity_kg` 800-3500 (8% low for scenario B), `warehouse_id → warehouse`, `status` ACTIVE/SUSPENDED | Each FPS exactly 1 warehouse; capacity varies |
| **warehouse_master.csv** | 25 | `warehouse_id` WH-001 | `rice_stock_kg`, `wheat_stock_kg`, `total_capacity_kg` 50k-150k, `lat/lon` | Stock sufficient for READY, constrained for BLOCKED scenarios |
| **vehicle_fleet.csv** | 150 | `vehicle_id` VEH-0001 | `vehicle_number` KA-##-XX-####, `vehicle_type` SMALL 800/MEDIUM 1500/LARGE 3000/HEAVY 5000 (±10%), `capacity_kg`, `status` AVAILABLE/ASSIGNED/IN_TRANSIT/DELIVERED/MAINTENANCE, `warehouse_id → warehouse` | MAINTENANCE not assigned to active manifests |
| **officers_master.csv** | 673 | `officer_id` | `employee_code`, `name` (Faker en_IN), `role` DISTRICT_OFFICER (6)/FIELD_FOOD_INSPECTOR (60)/FPS_OWNER (600)/ADMIN (2)/AUDITOR (5), `district` |  |

## 3. Demand (02_demand)

| Dataset | Rows | PK | Columns | Notes |
|---------|------|----|---------|-------|
| **historical_demand.csv** | 14,400 | `fps_id+cycle+commodity` | `fps_id, cycle (2025-01..12), commodity RICE/WHEAT, demand_kg, beneficiary_count, season KHARIF/RABI/SUMMER, month, year, previous_demand_kg, trend_factor -0.05..0.08, season_factor 0.96-1.08, stockout_flag 3%` | Temporal patterns, not random |
| **intent_signals.csv** | 14,000 | `intent_id` INT-xxxxxxx | `beneficiary_id → beneficiaries, fps_id → fps, cycle 2026-01/02, rice_quantity, wheat_quantity, total = rice+wheat, collection_mode SELF/AUTHORIZED_PERSON, submitted_at (Day 5-20), status SUBMITTED (97%)/CANCELLED` | Intent ≤ entitlement, not modifying statutory entitlement |
| **demand_forecast.csv** | 3,600 | `forecast_id` FC-xxxxxxx | `fps_id, cycle 2026-01..03, commodity, baseline_demand_kg (hist avg last 3), intent_demand_kg (aggregated), forecast_demand_kg (0.45 baseline+0.55 intent ×season ×noise), model_version xgb-v1.0, prediction_generated_at, training_dataset_version hist-v1-202512, horizon 30d` | Baseline/intent/forecast kept separate; Intent-Forecast and Forecast-Baseline diff calculable |
| **allocations.csv** | 3,600 | `allocation_id` ALLOC-xxxxxxx | `cycle, fps_id, commodity, requested_kg (forecast×0.95-1.05), allocated_kg (min requested, wh stock, fps capacity), warehouse_id, status APPROVED/BLOCKED, source SYSTEM, approved_by OFF-00001` | Never exceeds warehouse stock / fps / vehicle capacity; includes FPS_CAPACITY/ENTITLEMENT_FLOOR BLOCKED rows |

## 4. Operations (03_operations)

| Dataset | Rows | Columns |
|---------|------|---------|
| **inventory.csv** | 3,900 | `inventory_id, location_type WAREHOUSE/FPS, location_id, commodity, opening_stock, received, dispatched, distributed, closing = opening+received-dispatched-distributed, cycle` — no negatives, all PASS |
| **dispatch_manifests.csv** | 300 | `manifest_id MAN-000001, cycle, warehouse_id, vehicle_id, manifest_status DRAFT/VALIDATED/LOCKED/DISPATCHED/DELIVERED/RECONCILED, total_kg (=sum items), route_distance_km, route_duration_min, constraint_status READY/BLOCKED, created_by/locked_by, sha256_hash (canonical), qr_payload MAN|hash[0:16]` — READY→LOCKED only |
| **dispatch_manifest_items.csv** | 3,577 | `manifest_item_id, manifest_id → manifests, fps_id → fps, commodity, planned_kg, sequence_number, allocation_id → allocations` — sum equals manifest total |
| **delivery_history.csv** | 2,824 | `delivery_id, manifest_id, manifest_item_id → items, fps_id, vehicle_id, planned_kg, delivered_kg (variance -2%..+1%, 12% >3% VARIANCE/REJECTED), delivery_date, rice_kg, wheat_kg, status VERIFIED/VARIANCE/REJECTED, verified_by → inspector` |
| **epos_transactions.csv** | 14,400 | `transaction_id EPOS-xxxxxxxx, beneficiary_id → beneficiaries, fps_id → fps, cycle, commodity, quantity_kg ≤ entitlement, transaction_time, status SUCCESS (85%)/CANCELLED/FAILED, receipt_number` — SUCCESS never exceeds remaining entitlement |

## 5. Tracking (04_tracking)

| Dataset | Rows | Columns |
|---------|------|---------|
| **vehicle_telemetry.csv** | 5,170 | `telemetry_id, vehicle_id → vehicle, timestamp, lat/lon (interpolated along route), speed_kmph 18-38, status IDLE/MOVING/STOPPED/DELIVERED, manifest_id` — 12% missing → "Live location unavailable" |
| **vehicle_routes.csv** | 3,577 | `route_id, manifest_id, vehicle_id, warehouse_id, stop_sequence, fps_id, lat/lon, distance_from_previous_km (haversine), eta_minutes (2.2×km), route_status PLANNED/DRAFT` — coherent geography |

## 6. Compliance (05_compliance)

| Dataset | Rows | Columns |
|---------|------|---------|
| **inspections.csv** | 400 | `inspection_id INSP-xxxxxx, fps_id → fps, inspector_id → OFF (INSPECTOR), inspection_date, stock_expected, stock_observed, variance, weighing_accuracy 0.97-1.0, moisture NORMAL/HIGH/LOW, shop_condition, stock_register_verified YES/NO, epos_verified, finding STOCK_VARIANCE/NORMAL, status DRAFT/SUBMITTED/SEALED, evidence_reference, sealed_hash sha256` |
| **grievances.csv** | 500 | `grievance_id GRV-xxxxxx, beneficiary_id → beneficiaries, fps_id → fps, category SHORT_DELIVERY/WRONG_QUANTITY/FPS_CLOSED/QUALITY/TRANSACTION_FAILURE/ENTITLEMENT_QUERY/OTHER, description, created_at, status OPEN/IN_REVIEW/RESOLVED/CLOSED, resolution, resolved_at` |
| **audit_events.csv** | 313 | `audit_event_id AUD-xxxxxxx, cycle, actor_user_id → officers/beneficiaries, actor_role, action PREFERENCE_SUBMITTED..CYCLE_CLOSED (11 types), entity_type, entity_id, reason, result SUCCESS, timestamp, before_state, after_state, hash sha256` |
| **exceptions.csv** | 251 | `exception_id EXC-xxxxxx, cycle, entity_type MANIFEST/DELIVERY/EPOS/ALLOCATION, entity_id, rule_code FPS_CAPACITY/WAREHOUSE_STOCK/VEHICLE_CAPACITY/ROUTE_INFEASIBLE/ENTITLEMENT_FLOOR/DELIVERY_VARIANCE/EPOS_VARIANCE/STOCK_VARIANCE, severity HIGH/MEDIUM/LOW, reason, detected_at, assigned_to → officers, status OPEN/ACKNOWLEDGED/ACTION_REQUIRED/RESOLVED/CLOSED` |

## 7. Context (06_context)

| Dataset | Rows | Columns |
|---------|------|---------|
| **weather.csv** | 1,080 | `date 2025-09-01+180d, district, rainfall_mm (exp), temperature_c 28+6sin+noise, weather_condition SUNNY/CLOUDY/RAINY` — seasonal |
| **calendar_events.csv** | 48 | `date, district, event_name (Makar Sankranti etc + random Mela), event_type FESTIVAL/PUBLIC_HOLIDAY/LOCAL_EVENT, impact_factor -0.05..0.12` |
| **historical_stockouts.csv** | 375 | `fps_id, cycle, commodity, stockout_flag 1, stockout_days 1-7, shortage_kg 100-600` — for forecasting |

## 8. Generated (07_generated)

| File | Rows | Content |
|------|------|---------|
| **dataset_manifest.json** | — | `dataset_name PDS_DEMANDSYNC v1.0.0 synthetic, seed 20260921, row_counts, primary_keys, foreign_keys, operating_geography 6 districts, cycles 15, scenarios 7` |
| **data_dictionary.csv** | 237 | `dataset,column,data_type,description,nullable,primary_key,foreign_key,allowed_values,example` — every column |
| **relationship_map.csv** | 29 | `parent_dataset,parent_key,child_dataset,child_key,relationship_type 1:N` — every FK |
| **data_quality_report.csv** | 57 | `dataset,check_name,status,failed_rows,details` — all 57 PASS |

Full machine dictionary: `K:\DemandSYNC\data\07_generated\data_dictionary.csv`
