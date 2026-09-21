# PDS PREDICT — Technical Requirements Document (TRD)
## Prototype — Pre-Dispatch Demand Intelligence Layer
**Mode: PROTOTYPE (dataset-driven, no demo data) | K:\DemandSYNC | 2026-09-21**
**Companions: `ARCHITECTURE.md`, `PRD.md`, `pds-predict/database/migrations/001_initial.sql`, `pds-predict/backend/services/constraints/engine.py`**

---

### 1. System Overview

PDS PREDICT Prototype is a **district-pilot-scale, state-adoptable dispatch decision layer** that sits BETWEEN beneficiary preference collection and physical truck movement. It does NOT replace FCI, e-PoS, ONORC, Anna Chakra, or SARTHAK-PDS/SAKSHAM — it consumes them as inputs (Sec 5 of report).

**Decision pipeline (enforced order):**
```
Ingest REAL Dataset → Preference Capture (Flutter) → Aggregate + XGBoost Predict → Choice Window Close (immutable lock) → Constraint Engine (6 gates) → OR-Tools VRP → Route (OSRM) → SHA256 Locked Manifest + QR + Audit → Delivery Verify
```
Rule: `ML predicts, Rules decide, Optimization allocates` — ML output never triggers dispatch without deterministic constraint pass.

### 2. Architecture Decomposition

Per `ARCHITECTURE.md:19` module map — 8 modules, not monolith. Judge-explainable independently.

| Module | Code Path | Responsibility | Tech |
|--------|-----------|----------------|------|
| Beneficiary Channel | `pds-predict/frontend/beneficiary_app` | Login, preferred FPS selection, choice window UX Sec 4.1 | Flutter+Dart |
| Control Centre | `pds-predict/frontend/control_centre` | Live aggregation, lock, exception handling, map Sec 4.2 | React+TS+Plotly |
| FPS Portal | `pds-predict/frontend/fps_portal` | Manifest receive, QR scan, delivery confirm | React Light |
| API Gateway | `pds-predict/backend/api` | REST, auth, OpenAPI docs | FastAPI |
| Demand Engine | `pds-predict/backend/services/demand` | GROUP BY aggregation + XGBoost Sec 4.3 | Pandas, XGBoost, scikit-learn |
| Inventory/Allocation Engine | `backend/services/inventory`, `allocation` | Stock & NFSA allocation checks, entitlement floor | PostgreSQL, SQLAlchemy |
| Constraint Engine | `backend/services/constraints/engine.py` | 6-gate validator Sec 4.6 | Pure Python (deterministic) |
| Optimization Engine | `backend/services/optimization`, `optimization/dispatch_optimizer.py` | VRP + knapsack Sec 4.5 | Google OR-Tools |
| Routing Engine | `backend/services/routing` | Distance matrix, route geometry Sec 4.7 | OSRM + PostGIS + GeoPandas + OSM |
| Manifest Engine | `backend/services/manifest` | SHA256, QR, audit Sec 4.8 | hashlib, qrcode, PostgreSQL |

### 3. Data Layer — Technical Spec

**Engine:** PostgreSQL 15 + PostGIS 3.4 (Docker: `postgis/postgis:15-3.4` per `docker/docker-compose.yml:2`). All geo stored as `GEOGRAPHY(POINT,4326)` for accurate distance.

**Schema:** `database/migrations/001_initial.sql:1` — 14 tables.

**Critical constraints (enforced at DB + app):**

| Table | Constraint | Type | Enforcement |
|-------|------------|------|-------------|
| `preferences` | `UNIQUE(beneficiary_id, cycle)` | DB unique | 409 on duplicate |
| `preferences` | FK `beneficiary_id → beneficiaries.id`, `fps_id → fps.id` | FK | Reject orphan |
| `demand_locks` | `UNIQUE(cycle)`, immutable snapshot | DB unique + app trigger | No UPDATE/DELETE after `locked_at` |
| `dispatch_manifests` | `CHECK status IN (DRAFT,LOCKED,DISPATCHED,DELIVERED,EXCEPTION)` | Check | State machine |
| `dispatch_manifests.hash` | `SHA256(canonical_json(manifest+items))` | App | Verified on read |
| `audit_logs` | Append-only | App | No UPDATE/DELETE |
| `fps.location`, `warehouses.location` | `GEOGRAPHY(POINT,4326) NOT NULL` | DB | Reject null geo |

**Traceability chain (join path):**
```sql
beneficiaries → preferences → demand_predictions → fps → demand_locks
→ dispatch_manifests → manifest_items → vehicles → routes → deliveries → audit_logs
```

**Indexes (prototype):**
```sql
CREATE INDEX idx_pref_cycle ON preferences(cycle);
CREATE INDEX idx_pred_fps_cycle ON demand_predictions(fps_id, cycle);
CREATE INDEX idx_fps_gix ON fps USING GIST (location);
CREATE INDEX idx_wh_gix ON warehouses USING GIST (location);
CREATE INDEX idx_manifest_cycle ON dispatch_manifests(cycle);
```

**Immutability trigger (to be added in 002):**
```sql
CREATE OR REPLACE FUNCTION prevent_lock_mutation() RETURNS trigger AS $$
BEGIN IF OLD.locked_at IS NOT NULL THEN RAISE EXCEPTION 'demand_locks immutable after lock'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql;
```

### 4. API Specification (FastAPI — OpenAPI at `/docs`)

Base: `/api/v1` , Auth: Bearer JWT, RBAC: `beneficiary | fps_dealer | district_officer | admin`

| Method | Path | Role | Request | Response | Logic |
|--------|------|------|---------|----------|-------|
| POST | `/auth/login` | public | `{id, password}` | `{access_token}` | bcrypt verify → JWT |
| POST | `/preferences` | beneficiary | `{beneficiary_id, fps_id, cycle, quantity_kg}` | `201 {id}` / `409 duplicate` / `400 window closed` | Validate window open, FK, qty>0, unique |
| GET | `/preferences?cycle=` | officer | `cycle` | `{aggregated: {fps: kg}, count}` | `GROUP BY fps_id` |
| POST | `/choice-window/close` | district_officer | `{cycle}` | `201 {lock_id, snapshot, hash}` | Create `demand_locks` snapshot, set window closed, audit |
| POST | `/constraint/validate` | officer | `{cycle}` | `{ready: bool, exceptions: []}` | Calls `engine.py:validate_dispatch()` with real DB values + NFSA floor |
| POST | `/optimize/dispatch` | officer | `{cycle, warehouse_id, vehicle_id}` | `{assignments, route, total_kg, utilization, feasible}` | OR-Tools VRP; distance matrix from OSRM/PostGIS |
| POST | `/manifests/lock` | officer | `{cycle, dispatch_plan}` | `{manifest_id, hash, qr_payload}` | Only if `ready==true`; SHA256, insert `dispatch_manifests`+`manifest_items`, audit |
| GET | `/manifests/{id}` | any auth | — | `{manifest, items, hash, verified}` | Recompute hash, compare |
| GET | `/manifests/{id}/qr` | any auth | — | PNG | `qrcode` of `qr_payload` |
| POST | `/deliveries/verify` | fps_dealer | `{manifest_id, fps_id, delivered_kg, qr_hash}` | `{verified, variance}` | Compare delivered vs planned, hash check |
| GET | `/dashboard/summary?cycle=` | officer | `cycle` | `{requests, locked, ready, exceptions, demand/stock/allocation kgs}` | Aggregated KPIs for Sec 4.2 mockup |
| GET | `/exceptions?cycle=` | officer | `cycle` | `[{fps_id, reason}]` | From `exceptions` table |

**Error contract:** `{detail, code, reason}` — exceptions always include explicit reason (e.g. `FPS-102: required 2000kg, capacity 1500kg`).

### 5. Constraint Engine — Deterministic Spec

File: `backend/services/constraints/engine.py:7`

**Signature:**
```python
validate_dispatch(demand_by_fps: dict[str,float], allocations: dict[str,float],
                  fps_capacities: dict[str,float], truck_capacity: float,
                  stock_kg: float, entitlements: dict[str,float]|None) -> (bool, list[str])
```

**Gate order (all evaluated, all failures collected):**
1. `demand[fps] ≤ allocation[fps]` — per FPS, per cycle
2. `demand[fps] ≤ fps.capacity_kg`
3. `sum(demand) ≤ vehicle.capacity_kg`
4. `sum(demand) ≤ warehouse.stock_kg`
5. `route feasible` — OSRM returns route with `distance < threshold` (or PostGIS `ST_Distance` fallback)
6. `demand[fps] ≥ entitlement_floor[fps]` — aggregated entitlement for FPS; violation = legal violation, hard block.

**Output:** `(True, [])` → `🟢 READY`; `(False, [reasons])` → `🔴 EXCEPTION` + rows in `exceptions`. Judge live exception (reduce FPS capacity) triggers gate 2 immediately.

**Tests required:**
```python
assert validate_dispatch({FPS102:2000}, {FPS102:2500}, {FPS102:1500}, 5000, 10000)[0]==False
assert "capacity 1500kg" in exceptions[0]
assert validate_dispatch({FPS102:1000}, {FPS102:2500}, {FPS102:1500}, 5000, 10000, entitlements={FPS102:1200})[0]==False # NFSA floor
```

### 6. ML Layer — Prediction Only

**Location:** `ml/training`, `ml/inference`, `backend/services/demand`

**Model:** XGBoost regressor (or fallback `RandomForest` if XGBoost unavailable). **Never** decides dispatch.

**Features (from REAL dataset):**
*   `historical_demand.fps_id, cycle` → lag features (prev 1-3 cycles), rolling mean
*   `season_factor` (1.08 etc), `trend` (+6%), `household_count` per FPS, `allocation` per cycle

**Training:** `ml/training/train.py` — `train_test_split` by cycle (temporal), `XGBoost(max_depth=6, n_estimators=200)`, metric `RMSE`. Saves to `ml/models/xgb_fps_demand.json`.

**Inference:** `ml/inference/predict.py` — load model → predict per FPS for `cycle+1` → write `demand_predictions` with `method='xgboost'`. Fallback: `method='aggregated'` = `GROUP BY` sum if model absent.

**Worked example (doc Sec 4.3):**
```
FPS-102: hist 1900kg, current pref 420 users, season 1.08, trend +6% → predicted 2250kg → passed to constraint engine, not dispatched directly.
```

**Separation enforced:** API flow `POST /constraint/validate` always runs after `demand_predictions` — no endpoint allows `predicted_kg` → `dispatch_manifests` without constraint pass.

### 7. Optimization Layer — OR-Tools

**File:** `optimization/dispatch_optimizer.py` (scaffold) + `backend/services/optimization`

**Problem:** Capacitated Vehicle Routing (CVRP) + assignment.

**Input:**
*   `demands: {fps: kg}` (validated)
*   `fps_coords: {fps: (lat,lon)}`, `warehouse_coord`
*   `truck_capacity`, `fps_capacities`, `stock_kg`
*   `distance_matrix: n x n` from OSRM `POST /route` or PostGIS `ST_Distance(warehouse, fps)` haversine fallback.

**OR-Tools formulation:**
```python
manager = pywrapcp.RoutingIndexManager(n_nodes, 1, depot=0)
routing = pywrapcp.RoutingModel(manager)
def demand_callback(i): return demands[i]
routing.AddDimensionWithVehicleCapacity(demand_callback, 0, [truck_capacity], True, "Capacity")
routing.SetArcCostEvaluatorOfAllVehicles(distance_callback)
search = pywrapcp.DefaultRoutingSearchParameters()
search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
```

**Output:** `route: [Hub, FPS-101, FPS-102, FPS-103]`, `assignments: {FPS-101:1300, FPS-102:2000, FPS-103:1000}`, `total=4300, utilization=86%` (doc Sec 4.5 example). Infeasible → `exceptions` with reason `No feasible route with capacity 5000 for total 6200`.

**Constraints:** `total ≤ truck_capacity` and `per FPS ≤ fps.capacity` already validated; OR-Tools re-validates.

### 8. Geospatial & Routing

**Stack:** OSM (base), OSRM (route), PostGIS (store/query), GeoPandas (analysis).

**Data:** FPS/warehouse `GEOGRAPHY` points from dataset. No hardcoded coords.

**Flow:**
1. Ingest writes `ST_SetSRID(ST_MakePoint(lon,lat),4326)::geography`
2. Distance matrix: try `OSRM /table` → fallback `ST_Distance` (haversine, meters)
3. Route geometry: `OSRM /route` → polyline for dashboard map; fallback straight lines.

**Docker:** `osrm` service in `docker-compose.yml:12` — profile `car`, data volume `osrm-data`. For prototype, if OSRM data not loaded, use PostGIS fallback (acceptable for judge laptop).

### 9. Manifest & Audit — Cryptographic Spec

**Canonical JSON:** `json.dumps(manifest, sort_keys=True, separators=(',',':'))` including `id, cycle, warehouse_id, vehicle_id, items[{fps_id, quantity_kg}], total_kg`.

**Hash:** `hashlib.sha256(canonical.encode()).hexdigest()` → `dispatch_manifests.hash`.

**QR:** `qrcode.make(f"{manifest_id}|{hash}")` PNG, stored as `qr_payload` or generated on `GET /qr`.

**State machine:** `DRAFT → LOCKED → DISPATCHED → DELIVERED`, or `DRAFT → EXCEPTION`. Only `LOCKED` manifests trigger `DISPATCHED` on truck leave. `LOCKED` is immutable (app + DB trigger).

**Audit:** `audit_logs` append-only. Example per doc Sec 6:
```
who: district_officer_01
what: LOCK_MANIFEST
when_at: 2026-08-25 14:35 IST
why: demand lock validated, constraints READY
result: LOCKED
manifest_id: DSP-2026-001
hash: a3f5c...
```

### 10. Security & Compliance

| Area | Spec |
|------|------|
| Auth | JWT (HS256, 24h expiry), `python-jose`, bcrypt (`passlib`). Roles enforced per endpoint (decorator `@require_role('district_officer')`). |
| PII | Minimised: only `beneficiary.id, household_size, entitlement_kg, fps preference` — no Aadhaar, no biometrics. DPDP Act 2023 Sec 7(b) welfare exemption noted, but app still does consent notice + minimisation. |
| NFSA | Entitlement floor hard-coded in constraint engine; any `demand < floor` → block. `Food Security Allowance` note: cannot optimize away legal right. |
| Input Validation | Pydantic models: `quantity_kg >0`, `cycle ~ YYYY-MM`, lat/lon bounds, FK exists. SQL injection prevented via SQLAlchemy. |
| Tamper Evidence | SHA256 stored, recomputed on every read; mismatch → `verified=false` + audit. No blockchain (honest engineering per doc Sec 4.8). |
| Secrets | `DATABASE_URL`, `JWT_SECRET` via env, not hardcoded. |

### 11. Deployment & Runtime

**Local (prototype):**
```bash
docker compose -f pds-predict/docker/docker-compose.yml up  # db + backend + osrm
uvicorn backend.main:app --reload  # alt without docker
flutter run -d chrome  # beneficiary app
npm --prefix pds-predict/frontend/control_centre run dev
```

**Env:**
```
DATABASE_URL=postgresql://pds:pds@localhost:5432/pds_predict
JWT_SECRET=<random>
OSRM_URL=http://localhost:5000
```

**Migrations:** `psql -f database/migrations/001_initial.sql` then `002_immutability_trigger.sql` (future). No ORM auto-migrate without review.

**Dataset ingestion:** `python pds-predict/backend/scripts/ingest_dataset.py --path <your_file>` — validates schema, bulk inserts, reports counts/rejects.

### 12. Testing Strategy

| Layer | Tool | Test | Pass Criteria |
|-------|------|------|---------------|
| Constraint | Pytest | `test_constraints.py` : 6 gates + NFSA floor | 100% cases, explicit reason strings |
| Ingestion | Pytest | `test_ingest.py` : duplicate/orphan/negative/schema | Rejects with correct error |
| Optimizer | Pytest | `test_optimizer.py` : feasible 4300/5000 → 86%, infeasible → exception | Utilization exact |
| ML | Pytest | `test_predict.py` : train on seeded `historical_demand` → RMSE < threshold | Model saves/loads |
| API | Pytest + httpx | `test_e2e.py` : preference → lock → validate → optimize → manifest → verify | Full chain on ingested dataset, no demo data |
| Frontend | Playwright / Flutter Test | Choice window, lock button, exception banner | Judge live exception → `BLOCKED` in <1s |
| Geo | Pytest | OSRM fallback to PostGIS | Distance matrix always returns |

**Coverage target:** `constraints` + `manifest` + `ingest` = 90%+ (critical path).

### 13. Observability & Docs

*   OpenAPI: `http://localhost:8000/docs` (Swagger), `http://localhost:8000/redoc`
*   Logs: `audit_logs` queryable `GET /audit?manifest_id=`; app logs via `uvicorn` stdout.
*   Dashboard KPIs: `GET /dashboard/summary` feeds cards: `Beneficiary Requests, Demand Lock, Ready/Exceptions, Stock/Allocation/Demand kgs`.
*   Map: GeoJSON of FPS/warehouse + OSRM route polyline.

### 14. Risks & Technical Mitigations

| Risk | Mitigation |
|------|------------|
| Dataset lat/lon missing | Ingest rejects; fallback requires manual geocoding or district centroid |
| OSRM data heavy (India OSM ~2GB) | PostGIS `ST_Distance` fallback; prototype uses haversine, acceptable for 15 FPS |
| OR-Tools infeasible due to over-demand | Constraint catches first; exception reason guides officer to reduce allocation/capacity |
| XGBoost overfits small `historical_demand` | Temporal split, fallback to `aggregated` method, RMSE guard |
| Prototype confused with demo by judges | PRD/TRD + code both dataset-driven; no `seed_demo.py`; ingestion requires real file path |

### 15. Build Order (Strict — matches ARCHITECTURE.md:114 & PRD:12)

1. `database/migrations/001_initial.sql` + PostGIS
2. `backend/scripts/ingest_dataset.py` (schema validation)
3. `backend/services/constraints/engine.py` (6 gates + tests)
4. `ml/training` + `inference` (real historical_demand)
5. `optimization/dispatch_optimizer.py` + OR-Tools
6. `backend/services/routing` (OSRM/PostGIS)
7. `backend/api` + `models` + `main.py` (FastAPI)
8. `frontend/beneficiary_app` (Flutter)
9. `frontend/control_centre` (React+Plotly map)
10. `backend/services/manifest` (hash+QR+audit) — after E2E works
11. P1: FCM, WhatsApp/IVR sim, anomaly detection — only after 1-10 green.

---

**Ready for dataset.** Run `python pds-predict/backend/scripts/ingest_dataset.py --path <your_file>` — scaffold validates, no demo rows.
