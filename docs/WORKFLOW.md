# DemandSYNC — Workflow Specification
**PDS PREDICT | 13-Stage Government Operation Lifecycle | K:\DemandSYNC | 2026-09-21**
**Source: Master Build Prompt Sec 0,1,2 + report_pds_complete.docx**

---

## 1. Lifecycle Vision — Not a Dashboard

```
SENSE → UNDERSTAND → PREDICT → VALIDATE → DECIDE → OPTIMIZE → AUTHORIZE → DISPATCH → TRACK → DELIVER → VERIFY → RECONCILE → LEARN → CLOSE
        collapsed into 13 operational stages for UI:
01 MONITOR → 02 VALIDATE → 03 LOCK → 04 ALLOCATE → 05 OPTIMIZE → 06 AUTHORIZE → 07 TRACK → 08 DELIVER → 09 VERIFY → 10 RECONCILE → 11 INSPECT → 12 AUDIT → 13 CLOSE
```

Every stage has: `STATUS | INPUT | AI SIGNAL | RULE CHECKS | HUMAN DECISION | OUTPUT | NEXT ACTION`
Current stage visually dominant (progress ring, not sidebar highlight).

## 2. Stage Definitions

### 01 MONITOR (DSO — Cycle Command Centre)
* **Input:** `beneficiaries (10k), fps (600), warehouses (25), historical_demand (14.4k), intent_signals (14k pending), stock`
* **AI:** Demand Forecast AI (baseline vs intent), Anomaly Detection (FPS outliers)
* **Rules:** Data completeness >98%, no broken FK
* **Human:** DSO observes cycle `2026-03` window open
* **Output:** Intent participation `70%`, forecast preview
* **Gate:** Choice window open until Day 20 → [Close Window] action

### 02 VALIDATE (DSO — Data Trust)
* **Input:** Same + `data_quality_report.csv` (57 checks, all PASS)
* **AI:** Data Quality Assistant — "3.2% telemetry unavailable — not data error, real gap"
* **Rules:** Schema, referential, business (entitlement, capacity) — from `07_generated`
* **Human:** System Admin APPROVES dataset version `v1.0.0`
* **Output:** `dataset_imports.status=ACTIVE`
* **Gate:** `REFERENTIAL PASS + BUSINESS PASS → ACTIVE`

### 03 LOCK (DSO)
* **Input:** `intent_demand (aggregated per FPS), baseline (historical), forecast (xgb-v1.0)`
* **AI:** Forecast explainer (WHY +6.2% trend +4.1% intent)
* **Rules:** Demand Lock Gate:
  ```
  Entitlement Safety   PASS  (no intent > entitlement)
  FPS Capacity         PASS/FAIL per FPS
  Warehouse Stock      PASS/FAIL per warehouse
  Duplicate Intent     PASS (unique beneficiary+cycle)
  Data Integrity       PASS
  AI Confidence        87%
  ```
* **Human:** DSO clicks [LOCK DEMAND] → immutable `demand_locks` snapshot + SHA256 + audit
* **Output:** `demand_locks.cycle=2026-03, hash, locked_by OFF-00001`
* **Gate:** IMMUTABLE — no UPDATE after lock (DB trigger)

### 04 ALLOCATE (AI Resource Allocation + Rules)
* **Input:** Locked demand + `warehouse stock + fps capacity + vehicle capacity`
* **AI:** Allocation Decision Support — "FPS-102 requires 1850kg, warehouse 1620kg → 230kg shortage"
* **Rules:** Constraint Engine (6 gates: allocation→capacity→truck→stock→route→entitlement floor). `BLOCKED` → exception `FPS_CAPACITY/WAREHOUSE_STOCK/ENTITLEMENT_FLOOR`
* **Human:** DSO reviews allocation plan, approves per FPS
* **Output:** `allocations.status APPROVED/BLOCKED` (3600 rows across 3 cycles)

### 05 OPTIMIZE (OR-Tools)
* **Input:** Locked demand, allocations, FPS coords, vehicles (150), capacity
* **AI:** Route Risk AI — "Congestion risk stop 3 based on historical duration"
* **Rules:** OR-Tools CVRP: `total ≤ vehicle capacity`, `per FPS ≤ fps capacity`, `route feasible (OSRM/PostGIS)`
* **Human:** DSO reviews vehicle assignment, sequence
* **Output:** `dispatch_manifests DRAFT → VALIDATED`, `vehicle_routes (3577 rows)`, utilization `86-92%`, distance, ETA

### 06 AUTHORIZE (Dispatch Authorization)
* **Input:** Demand + allocation + vehicle + route + constraint `READY`
* **AI:** Dispatch Risk AI — lists risks, not decisions
* **Rules:** All constraints `READY` → DRAFT→VALIDATED→LOCKED; `BLOCKED` → cannot AUTHORIZE
* **Human:** DSO [AUTHORIZE DISPATCH] → generates `manifest_id MAN-xxxxxx, QR, SHA256` + audit
* **Output:** `manifest_status=LOCKED` (immutable), 300 manifests

### 07 TRACK (Vehicle Tracking)
* **Input:** `vehicle_telemetry (5170 rows), vehicle_routes`
* **AI:** Dispatch Risk Engine — deviation, stationary 18min at non-planned location, ETA risk
* **Rules:** Telemetry must reference valid vehicle/manifest; missing → display "Live location unavailable" (12% gap real)
* **Human:** Officer monitors, acts on AI signal
* **Output:** Live map, speed, last update, progress

### 08 DELIVER (FPS Portal)
* **Input:** Locked manifest + truck arrival
* **AI:** FPS Stock Risk — "Projected stockout in X days", Delivery Variance analysis
* **Rules:** `delivery_history` planned vs delivered (variance -2% to +1%, 340 VARIANCE flagged)
* **Human:** FPS dealer verifies truck, manifest, updates inventory
* **Output:** `deliveries.status VERIFIED/VARIANCE/REJECTED` (2824 rows)

### 09 VERIFY (Beneficiary e-PoS)
* **Input:** `epos_transactions (14.4k)` + entitlement
* **AI:** Transaction Anomaly — "Pattern requires review" (neutral)
* **Rules:** `SUCCESS ≤ remaining entitlement`, `quantity >0`, real beneficiary/fps
* **Human:** Beneficiary collects, POSTMAN verifies
* **Output:** `remaining_entitlement = entitlement - sum(SUCCESS)`, receipt

### 10 RECONCILE (Delivery Reconciliation)
* **Input:** Planned (alloc) vs Dispatched (manifest) vs Received (delivery) vs Distributed (ePOS) vs Inventory closing
* **AI:** Reconciliation Assistant — "40kg variance: delivery variance + inventory timing"
* **Rules:** `inventory.closing = opening+received-dispatched-distributed` (all 3900 PASS)
* **Human:** DSO creates exception if variance > threshold
* **Output:** Reconciliation report per cycle

### 11 INSPECT (Field Inspector)
* **Input:** Inspector portal — select target (AI prioritized by stock/delivery/ePOS variance), travel, verify, evidence
* **AI:** Inspection Risk Prioritization — never guilt determination
* **Rules:** Inspector must be `FIELD_FOOD_INSPECTOR`, FPS exists, sealed hash
* **Human:** Inspector captures evidence, submits `SEALED` (SHA256)
* **Output:** `inspections (400 rows)` sealed

### 12 AUDIT (Auditor Portal)
* **Input:** Full trace chain: beneficiary→intent→forecast→lock→allocation→manifest→vehicle→delivery→ePOS→inspection→exceptions→audit
* **AI:** Audit Intelligence — planned vs delivered mismatch, repeated FPS variance, route anomalies
* **Rules:** Append-only `audit_logs`, immutable locked records, DB constraints
* **Human:** Auditor traces, generates finding, seals audit
* **Output:** `audit_events (313 rows)` hash-chained

### 13 CLOSE (DSO + System)
* **Closure Gate (all PASS required):**
  ```
  Demand locked          PASS
  Allocation complete    PASS (no OPEN BLOCKED without resolution)
  Manifest reconciled    PASS (totals = items)
  Delivery reconciled    PASS
  Open critical issues   0
  Required inspections   PASS (≥1 per flagged FPS)
  Audit trail complete   PASS
  ```
* **Human:** DSO [CLOSE CYCLE] → generates closure record, SHA256, audit event `CYCLE_CLOSED`
* **Output:** Cycle `2026-03` closed, next cycle `2026-04` opens, learnings feed next forecast model_version

## 3. State Machines

**Manifest:** `DRAFT → VALIDATED → LOCKED → DISPATCHED → DELIVERED → RECONCILED` (BLOCKED branches to `ACTION_REQUIRED → RESOLVED`)
**Inspection:** `DRAFT → SUBMITTED → SEALED` (sealed hash immutable)
**Grievance:** `OPEN → IN_REVIEW → RESOLVED → CLOSED`
**Cycle:** `OPEN → MONITOR → LOCKED → ALLOCATED → OPTIMIZED → AUTHORIZED → TRACKING → DELIVERING → RECONCILING → AUDITING → CLOSED`

## 4. Traceability Chain (Every record traceable)

```
BENEFICIARY → INTENT → FORECAST → LOCK → ALLOCATION → MANIFEST → VEHICLE → ROUTE → DELIVERY → ePOS → RECONCILIATION → INSPECTION → AUDIT
   10k      14k      3.6k    snapshot  3.6k       300      150    3.5k    2.8k    14k         report        400    313
```
Component: `<TraceRecord>` — click any node opens evidence panel backwards/forwards.

## 5. No Fake Data Rule
If data missing: "Data unavailable" / "Live location unavailable" / "Forecast unavailable" — never invent GPS, beneficiaries, entitlements, transactions. Dashboards show only what CSVs + DB contain.

## 6. Mapping to Master Prompt Phases
| Workflow Stage | Master Phase | Portal |
|---|---|---|
| 01-02 | PHASE 0-1 Foundation/Data Trust | System Admin |
| 03 | PHASE 5 Lock | DSO |
| 04 | PHASE 6 Allocation | DSO |
| 05 | PHASE 7 Optimization | DSO |
| 06 | PHASE 8 Authorization | DSO |
| 07 | PHASE 9 Tracking | DSO/Field |
| 08-09 | PHASE 10-11 FPS/ePOS | FPS/Beneficiary |
| 10 | PHASE 12 Reconciliation | DSO |
| 11 | PHASE 13 Inspector | Inspector |
| 12 | PHASE 15 Auditor | Auditor |
| 13 | PHASE 16-17 Evaluation/Closure | DSO/Auditor |
