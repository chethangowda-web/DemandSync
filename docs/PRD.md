# PDS PREDICT — Product Requirements Document (PRD)
## Prototype — Pre-Dispatch Demand Intelligence Layer for PDS
**Mode: PROTOTYPE (not demo) | Location: K:\DemandSYNC | Date: 2026-09-21**
**Source: `report_pds_complete.docx` | Companion: `ARCHITECTURE.md`, `pds-predict/database/migrations/001_initial.sql`**

---

### 1. Purpose & Vision

**One-line:** Turn PDS dispatch from “plan → dispatch → react” into “prepare demand → validate constraints → lock manifest → dispatch” — as an integration layer inside the existing state-run PDS stack (FCI, e-PoS, ONORC, Anna Chakra, SARTHAK-PDS/SAKSHAM), not a replacement.

**Vision:** A state-adoptable, B2G module that consumes a real beneficiary preference dataset, produces a cryptographically hashed, constraint-validated dispatch manifest before truck movement, and feeds the existing NFSA statutory audit/grievance structure (DGRO, State Food Commission, Vigilance Committees).

**Out of scope for prototype:** Replacing SARTHAK/Anna Chakra, beneficiary monetisation, blockchain, invented savings claims, real government DB integration (uses provided dataset via ingestion).

### 2. Goals & Success Criteria

| Goal | Prototype Success Criteria | Measurement |
|------|---------------------------|-------------|
| G1 Dataset-driven E2E | Full chain works on YOUR dataset (no 5-10 fake rows): `preference → aggregation → lock → constraint → optimization → manifest → audit` | E2E test passes on ingested dataset; `demand_locks` immutable, `dispatch_manifests.hash` verified |
| G2 Constraint correctness | Constraint engine blocks invalid dispatches with explicit reason | Unit tests in `engine.py` : 100% cases where `demand>allocation/capacity/stock/truck` → `exceptions` row with reason |
| G3 Entitlement safety | Never allocates < NFSA legal entitlement | `entitlements` floor check; any violation → exception, never `READY` |
| G4 Auditability | Every lock/dispatch logged `WHO/WHAT/WHEN/WHY/RESULT` + SHA256 | `audit_logs` entry per `POST /manifests/lock` and QR-verifiable at FPS |
| G5 Judge-defensible | No false claims (no “no route optimization exists”) | PRD + demo script explicitly frames as “input layer to SAKSHAM/Anna Chakra” |

**Prototype NOT measured by:** Demo click-through; invented ₹/%. Those are pilot metrics post-prototype (Sec 10 of doc: dispatch accuracy, exception catch rate, utilization, variance, resolution time, participation).

### 3. Stakeholders & Users

| Persona | Role | Need | Access |
|---------|------|------|--------|
| Beneficiary (NFSA household) | Submits preferred FPS/quantity per cycle | Simple, low-literacy channel; legal entitlement preserved | Flutter app (JWT: beneficiary) |
| FPS Dealer | Receives manifest, confirms delivery, scans QR | Early visibility, reduced disputes | FPS Portal (JWT: fps_dealer) |
| District Officer / Control Centre | Closes choice window, validates, locks, dispatches, handles exceptions | Real-time aggregation, one-click lock, explainable blocks | React Control Centre (JWT: district_officer) |
| State Food & Civil Supplies Dept | Owns data, approves pilot, consumes audit | B2G integration via SARTHAK-PDS | Admin API + audit export |
| DGRO / Vigilance Committee | Grievance/audit consumption | Tamper-evident evidence | `audit_logs` + delivery verification |
| Transport contractor/driver | Executes locked manifest | Clear route/load | Manifest + OSRM route sheet |

### 4. Scope

#### 4.1 In Scope (Prototype Must-Have = P0)

| ID | Feature | Detail | Acceptance |
|----|---------|--------|------------|
| F1 | Dataset Ingestion | `backend/scripts/ingest_dataset.py` validates schema for `beneficiaries, fps, warehouses, vehicles, allocations, historical_demand` (CSV/JSON/XLSX) → PostgreSQL/PostGIS | Rejects malformed; no demo rows; refer `ARCHITECTURE.md:128` |
| F2 | Beneficiary Preference Capture | Flutter app: Login → Profile → Current FPS → Preferred FPS → Choice Window → Submit → Confirmation. `POST /api/v1/preferences` with `unique(beneficiary,cycle)` | Preference persisted; duplicate in same cycle rejected; visible in dashboard live |
| F3 | Demand Aggregation + Prediction | SQL `GROUP BY fps_id` + XGBoost (trained on REAL `historical_demand`) → `demand_predictions`. Separation: ML predicts, does not dispatch | Predictions in `demand_predictions`; ML output never auto-dispatches without constraint pass |
| F4 | Choice Window & Demand Lock | Defined window (e.g. Day 21-24) → `POST /choice-window/close` → immutable `demand_locks.snapshot` JSONB | After lock, no new preferences for cycle accepted; snapshot hash stored |
| F5 | Constraint Engine (Distinctive) | `backend/services/constraints/engine.py` : `Demand≤Allocation? → FPS Capacity? → Truck Capacity? → Stock? → Route feasible? → NFSA floor?` → `exceptions` | Returns `READY` only if all pass; on fail `🔴 EXCEPTION` with reason e.g. “FPS-102: required 2000kg, capacity 1500kg” |
| F6 | OR-Tools Dispatch Optimizer | Joint VRP: FPS demand, capacities, truck capacity, stock, distances (OSRM) → optimal load + sequence, utilization % | Output: FPS→kg assignments, route Hub→FPS…, utilization; feasible or explicit infeasible reason |
| F7 | Locked Manifest + QR + Hash | `dispatch_manifests` + `manifest_items` + `SHA256(manifest)` + QR payload + `audit_logs` (`WHO/WHAT/WHEN/WHY/RESULT`) | Hash verifiable `GET /manifests/{id}`; QR scan at FPS; tamper-evident without blockchain |
| F8 | Geospatial Layer | PostGIS + OSM + OSRM + GeoPandas: warehouse/FPS points, route computation, distance matrix for optimizer | Route feasible check uses real coordinates from dataset |
| F9 | Control Centre Dashboard | React+TS: KPIs (requests, lock status, ready/exceptions), live map (FPS/vehicle/hub), demand/stock/allocation cards, dispatch status, exception handling | Judge can introduce live exception (reduce FPS capacity) → immediate `BLOCKED` with reason (strongest demo moment Sec 9) |
| F10 | Delivery Verification | FPS scan QR → `POST /deliveries/verify` → compare planned vs delivered → `deliveries.verified` | Variance logged, feeds audit |
| F11 | RBAC + Auth | JWT: `beneficiary, fps_dealer, district_officer, admin`; `users` table | Unauthorized role cannot close window/lock manifest |

#### 4.2 In Scope (P1 — Prototype Should-Have, after P0 E2E works)

| ID | Feature |
|----|---------|
| F12 | Plotly analytics (demand trend, stock status, readiness donut) |
| F13 | Notifications (FCM) — simulated first: beneficiary/dealer/driver/control alerts |
| F14 | WhatsApp/IVR simulators inside dashboard (fallback, not blocking real API approval) |
| F15 | Anomaly detection (scikit-learn: expected 2000kg vs observed 3800kg → flag) |

#### 4.3 Out of Scope (Explicitly NOT in Prototype)

*   Demo shortcuts: hardcoded 5-10 users, in-memory manifest, mock constraints
*   Real SARTHAK/DFPD DB connection (requires MoU)
*   Blockchain
*   Production WhatsApp/IVR approval dependency
*   Revenue/credit features; ads; beneficiary data monetisation

### 5. Functional Requirements (Detailed)

**FR-1 Preference Lifecycle:** `Open window → Submit (validated FK beneficiary/fps, quantity>0, window open) → Aggregate → Lock → Immutable`. Duplicate `beneficiary+cycle` → 409.

**FR-2 Demand Lock Immutability:** `demand_locks.cycle UNIQUE`. Any `UPDATE/DELETE` on locked row prohibited (DB trigger or app check). Snapshot is JSONB of `{fps_id: demand_kg}` at lock time.

**FR-3 Constraint Rules (in order, short-circuit with all reasons collected):**
1. `demand ≤ allocation` (per FPS, per cycle)
2. `demand ≤ fps.capacity_kg`
3. `sum(demand) ≤ vehicle.capacity_kg`
4. `sum(demand) ≤ warehouse.stock_kg`
5. `route feasible` (OSRM returns route; distance < policy threshold)
6. `demand ≥ entitlement_floor` (per beneficiary aggregated per FPS; derived from `beneficiaries.entitlement_kg`) — hard NFSA rule, non-negotiable.

**FR-4 Optimizer Input/Output:** Input: demand_by_fps, fps coords/capacities, warehouse coord/stock, vehicle capacities, distance matrix. Output: `{assignments: {fps: kg}, route: [hub, fps…], total_kg, utilization, feasible}`. Infeasible → exception reason.

**FR-5 Manifest Lock:** `id = DSP-{YEAR}-{SEQ}`, `hash = SHA256(canonical_json(manifest+items))`, `qr_payload = hash + manifest_id`, status transition `DRAFT→LOCKED` only if constraint `READY`.

**FR-6 Audit:** Every `close window`, `validate`, `optimize`, `lock`, `verify` writes `audit_logs` with `who, what, when_at, why, result, manifest_id, hash`.

### 6. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Stack | Free/open-source only (Sec 3 ARCHITECTURE); Docker-compose reproducible; runs on local laptop without paid APIs |
| Performance | Constraint validation <1s for 15 FPS; OR-Tools <5s for 15 FPS/1 vehicle (prototype scale). Dashboard live aggregation <500ms |
| Scalability | Schema supports district pilot (1 warehouse, 5-15 FPS, few thousand beneficiaries) → state scale later; PostGIS indexed |
| Security | JWT RBAC, password hashing (bcrypt), SQL injection safe (ORM), hash tamper-evidence; no PII beyond entitlement+fps signal; data-minimisation per DPDP Act |
| Reliability | `demand_locks` and `dispatch_manifests` immutable after lock; no silent overwrites; exceptions explain failure (not generic error) |
| Observability | Pytest backend, Playwright/Flutter Test frontend; OpenAPI docs at `/docs`; audit trail queryable |
| Legal/Compliance | NFSA entitlement floor hard-coded; DPDP Act 2023 Sec 7(b) welfare exemption acknowledged but consent-notice + minimisation still applied; audit feeds statutory bodies |

### 7. Data Requirements (Prototype Dataset — YOU WILL PROVIDE)

Expected files in `K:\DemandSYNC\pds-predict\data\` or arbitrary path passed to `ingest_dataset.py`:

| Entity | Required Fields | Example | Source in Report |
|--------|----------------|---------|------------------|
| beneficiaries | `id, household_size, entitlement_kg, current_fps_id, lat, lon` | `BEN-001, 4, 20, FPS-101` | Sec 5 DB chain |
| fps | `id, name, capacity_kg, lat, lon, warehouse_id, district` | `FPS-102, Shivaji Nagar, 1500, 12.97, 77.59, WH-01` |  |
| warehouses | `id, name, lat, lon, stock_kg` | `WH-01, Central, 12.97,77.59, 11200` |  |
| vehicles | `id, capacity_kg, status` | `KA-01-AB-1234, 5000, available` |  |
| allocations | `fps_id, cycle, allocated_kg` | `FPS-101, 2026-08, 1300` |  |
| historical_demand | `fps_id, cycle, demand_kg, season_factor, trend` | `FPS-102, 2026-07, 1900, 1.08, +6%` | Sec 4.3 |
| preferences* | `beneficiary_id, fps_id, cycle, quantity_kg` | App-generated or CSV seed | Sec 4.1 |

*If you seed preferences as CSV, ingestion will load them; otherwise app creates them via API.

**Validation:** Ingestion rejects: missing FK, negative quantity, duplicate `beneficiary+cycle`, lat/lon out of range, capacity/stock ≤0.

### 8. User Journeys

**J1 Beneficiary:** Login → See current FPS → Choose preferred FPS + quantity → Submit within window → “Recorded” confirmation → receives FCM when manifest locked.

**J2 District Officer (Control Centre):** Dashboard shows live `12,840 requests → 🔒 LOCKED → 94 READY / 7 EXCEPTIONS` → Clicks `Close Choice Window` → System validates → `🟢 READY` or `🔴 BLOCKED` with reason → Locks manifest → QR generated → Route on map.

**J3 FPS Dealer:** Receives `2,000 kg planned` alert → Scans QR on delivery → System compares planned vs delivered → Verified or variance exception.

**J4 Exception Path (Judge’s favourite):** Judge reduces FPS-102 capacity live → Dashboard immediately `🔴 DISPATCH BLOCKED — FPS-102: required 2000kg, capacity 1500kg` → Officer recalculates → `READY`.

### 9. APIs (Prototype)

See `ARCHITECTURE.md:98` — FastAPI OpenAPI. All under `/api/v1`, JWT protected except docs. Key: `POST /choice-window/close` (officer only), `POST /constraint/validate`, `POST /optimize/dispatch` (OR-Tools), `POST /manifests/lock` (hash+qr+audit).

### 10. Metrics & Acceptance

Prototype accepts if:
*   E2E passes on real dataset (ingested, not demo) — `python -m pytest tests/test_e2e.py` green.
*   Constraint engine unit tests 100% pass, including NFSA floor violation → block.
*   Manifest hash verifies and QR round-trips.
*   Dashboard exception handling live-demoable (Sec 9 doc).
Pilot metrics (post-prototype, not PRD acceptance): dispatch accuracy, exception catch rate, utilization, manifest variance, resolution time, participation — measured vs control cluster.

### 11. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Claiming novelty falsely (“no route optimization”) | Framing: “Input layer to SAKSHAM/Anna Chakra” per doc Sec 12; PRD enforces |
| ML bias causes under-allocation below entitlement | Hard entitlement floor in `engine.py:18`; ML never auto-dispatches |
| Dataset schema mismatch | Strict ingestion validation + clear error messages; scaffold expects fields above |
| OSRM/OR-Tools heavy for judge laptop | Prototype scale 5-15 FPS; Docker fallback to PostGIS distance if OSRM offline |
| DPDP compliance | Data-minimisation, JWT, audit log; built compliant-by-design ahead of 2027 enforcement |

### 12. Build Order & Deliverables

Per `ARCHITECTURE.md:114`: `DB → FastAPI → Constraint → XGBoost → OR-Tools → OSRM/Geo → Flutter → React Dashboard → Manifest/Audit` → then F12-F15. Deliverables: running `docker compose`, `pds-predict/` repo, `PRD.md`, `ARCHITECTURE.md`, test suite, 5-slide deck (if requested).

---

**Sign-off:** Prototype builds when dataset provided. No demo data will be used. Path: `K:\DemandSYNC\pds-predict\backend\scripts\ingest_dataset.py --path <your_file>`
