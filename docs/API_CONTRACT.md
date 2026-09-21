# DemandSYNC — API Contract
**FastAPI + PostgreSQL/PostGIS | Base: `/api/v1` | OpenAPI at `/docs` | K:\DemandSYNC | 2026-09-21**

---

## 1. Auth

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/auth/login` | `{identifier, password}` → `{access_token, role}` | public |
| POST | `/auth/beneficiary/login` | `{ration_card_id, mobile_last4}` → JWT BENEFICIARY | public |
| GET | `/auth/me` | Current user | Bearer |

JWT `HS256`, `Authorization: Bearer <token>`, RBAC enforced per endpoint.

## 2. Data Trust (Phase 1 — Admin)

| Method | Path | Role | Request | Response |
|--------|------|------|---------|----------|
| POST | `/datasets/import` | ADMIN | multipart CSV/JSON + `{dataset, cycle, version}` | `{import_id, rows, status: IMPORTED}` |
| GET | `/datasets/{import_id}/validation` | ADMIN | — | `{schema_checks, referential_checks, business_rule_checks, quality_report}` (mirrors `data_quality_report.csv`) |
| POST | `/datasets/{import_id}/approve` | ADMIN | `{approve: true}` | `{status: ACTIVE, dataset_manifest}` |
| GET | `/datasets/manifest` | any | — | `dataset_manifest.json` |

## 3. Cycle Command Centre (DSO)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | `/cycles` | DSO | List cycles `2025-01..2026-03`, state |
| POST | `/cycles` | ADMIN/DSO | Create cycle `2026-04` |
| GET | `/cycles/{cycle}` | DSO | Cycle state, window, participation, forecast summary |
| POST | `/cycles/{cycle}/choice-window/close` | DSO | Lock demand — creates immutable `demand_locks` snapshot + SHA256 + audit `CHOICE_WINDOW_CLOSED` → `DEMAND_LOCKED` |
| GET | `/cycles/{cycle}/demand?view=intent|forecast|baseline` | DSO | Aggregated per FPS, with model_version |
| POST | `/cycles/{cycle}/validate` | DSO | Run 6-gate constraint engine → `{ready, exceptions[]}` |
| POST | `/cycles/{cycle}/allocate` | DSO | Allocation plan → writes `allocations` (uses AI Allocation Support) |
| POST | `/cycles/{cycle}/optimize` | DSO | OR-Tools → `{assignments, routes, utilization, feasibility}` |
| POST | `/cycles/{cycle}/manifests/lock` | DSO | `DRAFT→LOCKED` + QR + hash + audit `MANIFEST_LOCKED` (only if READY) |
| GET | `/cycles/{cycle}/summary` | DSO | KPIs for control room: `requests, locked, ready/exceptions, stock/allocation kgs` |
| GET | `/cycles/{cycle}/exceptions` | DSO | `exceptions` with `rule_code, severity, reason` |
| POST | `/cycles/{cycle}/reconcile` | DSO | Planned vs delivered vs distributed reconciliation |
| POST | `/cycles/{cycle}/close` | ADMIN/DSO | Closure gate check → `CYCLE_CLOSED` + SHA256 |

## 4. Beneficiary Portal

| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | `/beneficiaries/me` | BENEFICIARY | Own `beneficiaries_master` row + `entitlement = rice+wheat` |
| GET | `/beneficiaries/me/entitlement?cycle=` | BENEFICIARY | `entitlement, received, remaining` (from `epos_transactions SUCCESS`) |
| POST | `/preferences` | BENEFICIARY | `{fps_id, rice_quantity, wheat_quantity, cycle}` → `intent_signals` (unique beneficiary+cycle, ≤ entitlement) |
| GET | `/preferences/me?cycle=` | BENEFICIARY | Own intents |
| GET | `/preferences?cycle=&fps_id=` | DSO | Aggregated intent per FPS (for AI) |
| POST | `/grievances` | BENEFICIARY | `{fps_id, category, description, cycle}` → `grievances` |
| GET | `/epos/me?cycle=` | BENEFICIARY | Own `epos_transactions` + receipts |

## 5. AI Intelligence

| Method | Path | Description | Returns |
|--------|------|-------------|---------|
| GET | `/ai/forecast?cycle=&fps_id=` | Demand Forecast AI | `{prediction, confidence, reason, supporting_data, model_version, generated_at}` |
| GET | `/ai/intent-analysis?cycle=` | Intent vs baseline | `{variance, anomalies[]}` |
| GET | `/ai/anomalies?cycle=` | Anomaly Detection | `{fps_id, baseline, intent, forecast, anomaly_score}` |
| GET | `/ai/allocation-support?cycle=` | Allocation Decision Support | `{fps_id, demand, stock, capacity, insight, will_block}` |
| GET | `/ai/route-risk?manifest_id=` | Route Risk | `{risk_level, reason}` |
| GET | `/ai/delivery-variance?cycle=` | Delivery Variance | `{planned, delivered, variance, classification}` |
| GET | `/ai/inspection-priority` | Inspection Risk | `[{fps_id, score, reasons}]` sorted |
| GET | `/ai/grievances/triage?grievance_id=` | Grievance Triage | `{category, urgency, routing, related_records}` |
| GET | `/ai/audit?cycle=&entity=` | Audit Intelligence | `{observations[], evidence, confidence}` |
| GET | `/ai/cycle-evaluation?cycle=` | Cycle Evaluation | `{facts, ai_signals, officer_actions, outcomes}` |

Every AI response includes `model_version, generated_at, confidence, reason, supporting_data`. No "AI says approve".

## 6. Dispatch & Logistics

| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | `/manifests/{id}` | any auth | Manifest + items + `verified (hash recomputed)` |
| GET | `/manifests/{id}/qr` | any | PNG QR `manifest_id|hash[0:16]` |
| GET | `/manifests?cycle=&warehouse_id=` | DSO | List manifests |
| POST | `/deliveries/verify` | FPS_OWNER/INSPECTOR | `{manifest_id, fps_id, delivered_kg, qr_hash}` → compare + status |
| GET | `/vehicles?warehouse_id=` | DSO | `vehicle_fleet` filtered |
| GET | `/telemetry?vehicle_id=&manifest_id=` | DSO | `vehicle_telemetry` — if empty → frontend shows "Live location unavailable" |
| GET | `/routes?manifest_id=` | DSO | `vehicle_routes` ordered by `stop_sequence`, with `distance_from_previous_km, eta_minutes` |

## 7. FPS / ePOS

| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | `/fps/me` | FPS_OWNER | Own FPS master row + inventory |
| GET | `/fps/{id}/inventory?cycle=` | FPS_OWNER/DSO | `inventory` where `location_type=FPS` |
| POST | `/epos` | FPS_OWNER | `{beneficiary_id, fps_id, cycle, commodity, quantity}` → `epos_transactions` (checks remaining entitlement) |
| GET | `/epos?fps_id=&cycle=` | FPS_OWNER/DSO | Transactions for FPS |

## 8. Inspector & Auditor

| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | `/inspections` | INSPECTOR | List own inspections |
| POST | `/inspections` | INSPECTOR | `{fps_id, stock_expected, stock_observed, findings}` → DRAFT |
| POST | `/inspections/{id}/seal` | INSPECTOR | `SEALED` + `sealed_hash = sha256(canonical)` + audit `INSPECTION_SUBMITTED` |
| GET | `/inspections/{id}` | INSPECTOR/AUDITOR | Detail + evidence |
| GET | `/audit/trace?entity_type=&entity_id=` | AUDITOR | Full chain backwards/forwards (beneficiary→...→audit) |
| POST | `/audit/findings` | AUDITOR | `{cycle, entity, finding, evidence}` → `audit_events` |

## 9. Common Responses

**Success:** `{data, meta: {cycle, total, model_version}}`
**Error:** `{detail, code, reason}` — exceptions include `rule_code (FPS_CAPACITY)` and human-readable reason.
**AI Envelope:** Always `{prediction, confidence, reason, supporting_data, model_version, generated_at}`.

**State transitions append `audit_events`:** `PREFERENCE_SUBMITTED, CHOICE_WINDOW_CLOSED, DEMAND_LOCKED, CONSTRAINT_VALIDATED, ALLOCATION_CREATED, OPTIMIZATION_COMPLETED, MANIFEST_LOCKED, DISPATCH_STARTED, DELIVERY_VERIFIED, INSPECTION_SUBMITTED, CYCLE_CLOSED`.

## 10. Testing Contract

`tests/test_api.py` asserts: RBAC (beneficiary cannot POST /choice-window/close → 403), FK orphans 0, entanglement: intent ≤ entitlement, manifest totals, hash round-trip, telemetry missing handled.
