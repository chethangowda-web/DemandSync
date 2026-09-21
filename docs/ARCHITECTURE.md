# PDS PREDICT — Prototype Architecture (Not Demo)

> **Mode: PROTOTYPE** — Dataset-driven, persistent, constraint-validated. No 5-10 fake demo data.
> Source: `K:\DemandSYNC\report_pds_complete.docx` Sec 8, 12-15 — adapted for prototype.

## 1. Design Philosophy

**Demo (rejected):** 5-10 hardcoded beneficiaries, simulated aggregation, no persistence, no real constraints, memory-only manifest.

**Prototype (this):**
*   REAL dataset ingestion → PostgreSQL/PostGIS persistent layer
*   Full decision chain: `Preference → Demand Lock → Constraint Engine → OR-Tools → Locked Manifest`
*   Hard rule: `ML predicts, Rules decide, Optimization allocates` — no unaudited ML dispatch
*   NFSA entitlement-floor: system can NEVER allocate < legal entitlement
*   Tamper-evident manifest: SHA256 + QR, hash stored in `audit_logs`

## 2. High-Level Module Map

```
BENEFICIARY CHANNELS          CONTROL CENTRE              FPS/DEALER PORTAL
 (Flutter App)                 (React+TS Dashboard)         (React Light)
      │                               │                          │
      └───────────────┬───────────────┴──────────────────────────┘
                      ▼
              FastAPI Backend (Python)
                      │
      ┌───────────────┼───────────────┐
      ▼               ▼               ▼
 DEMAND ENGINE  INVENTORY ENGINE  ALLOCATION ENGINE
 (Pandas/XGBoost) (PostgreSQL)    (PostgreSQL + NFSA rules)
      │               │               │
      └───────────────┼───────────────┘
                      ▼
              CONSTRAINT ENGINE (PDS Validator)
                      ▼
              OR-TOOLS OPTIMIZER (VRP + Knapsack)
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
     ROUTE ENGINE              MANIFEST ENGINE
     (OSRM + PostGIS)          (PostgreSQL + SHA256)
          │                       │
          └───────────┬───────────┘
                      ▼
              🔒 DISPATCH MANIFEST
                      ▼
              🚛 + AUDIT LOG
```

## 3. Tech Stack — Prototype (Free/Open-Source, Locally Runnable)

| Layer | Technology | Why |
|-------|------------|-----|
| Mobile App | Flutter + Dart | Single codebase, beneficiary flow Sec 4.1 |
| Web Dashboard | React + TypeScript + Plotly | Control centre Sec 4.2, analytics Sec 11 |
| Portal (FPS) | React Light | Dealer confirmations |
| Backend | Python 3.11+ + FastAPI | Auto OpenAPI docs, fast REST |
| Database | PostgreSQL 15 + PostGIS | Relational + geospatial |
| Data Processing | Pandas, NumPy, GeoPandas | Demand/stock/spatial |
| ML (Prediction ONLY) | scikit-learn, XGBoost | Expected demand per FPS Sec 4.3 — never direct dispatch |
| Optimization | Google OR-Tools | VRP + capacity Sec 4.5 |
| Routing | OpenStreetMap + OSRM | Free routing Sec 4.7 |
| Auth | JWT (FastAPI) | RBAC: beneficiary / FPS dealer / district officer / admin |
| Notifications | Firebase Cloud Messaging | Simulated first, real FCM later Sec 7 |
| Prototype Channels | WhatsApp Cloud API (sim), Asterisk IVR (optional) | Sec 8-9 — simulator fallback, not blocking |
| Containers | Docker + Docker Compose | Reproducible |
| Tests | Pytest (backend), Playwright/Flutter Test (frontend) | |

NO paid AI APIs. NO blockchain — SHA256 hash suffices (Sec 4.8).

## 4. Core Decision Chain (Prototype vs Demo)

| Step | Demo (Sim) | Prototype (Real) |
|------|------------|------------------|
| Preference Capture | 5-10 hardcoded clicks | Ingested from dataset + Flutter app POST `/preferences` → DB `preferences` |
| Demand Aggregation | In-memory count | SQL `GROUP BY fps_id` + XGBoost prediction per FPS → `demand_predictions` |
| Demand Lock | Button toggles bool | `POST /choice-window/close` → locks snapshot, creates `demand_lock` row, immutable |
| Constraint Validation | If/else mock | Dedicated `constraint_engine` : `Demand≤Allocation? → FPS Capacity? → Truck Capacity? → Stock? → Route feasible? → NFSA floor?` → rows in `exceptions` if fail |
| Optimization | Fixed route | OR-Tools VRP with real distances (OSRM), capacities, stock |
| Manifest | JSON display | Hashed, locked row in `dispatch_manifests` + `manifest_items` + QR code, `audit_logs` entry |
| Audit | Console log | Full `WHO/WHAT/WHEN/WHY/RESULT` + SHA256 — feeds Vigilance Committee/DGRO per NFSA Sec 5 |

## 5. Database Design (PostgreSQL + PostGIS)

**Core tables:** `beneficiaries`, `fps`, `warehouses`, `vehicles`, `inventory`, `allocations`, `preferences`, `demand_predictions`, `demand_locks`, `dispatch_manifests`, `manifest_items`, `deliveries`, `exceptions`, `audit_logs`, `users`, `routes`

**Traceability chain (Sec 5):**
```
beneficiary → preference → demand_prediction → fps → demand_lock → dispatch_manifest → vehicle → route → delivery → audit_log
```

**Key constraints:**
*   `preferences` : FK beneficiary, fps, cycle, window_id, unique(beneficiary,cycle)
*   `demand_locks` : immutable snapshot (no UPDATE after lock)
*   `dispatch_manifests` : `hash = SHA256(manifest_json)`, `status ∈ {DRAFT, LOCKED, DISPATCHED, DELIVERED, EXCEPTION}`
*   `exceptions` : explicit reason (e.g. `FPS-102: required 2000kg, capacity 1500kg`)

## 6. API Surface (FastAPI)

```
POST   /api/v1/preferences              → submit preference (beneficiary channel)
GET    /api/v1/preferences?cycle=       → aggregated demand
POST   /api/v1/choice-window/close      → lock demand (district officer)
POST   /api/v1/constraint/validate      → run constraint engine on locked demand
POST   /api/v1/optimize/dispatch        → OR-Tools optimization → manifest draft
POST   /api/v1/manifests/lock           → hash + lock manifest + audit log + QR
GET    /api/v1/manifests/{id}           → manifest + items + hash verification
GET    /api/v1/manifests/{id}/qr        → QR code
POST   /api/v1/deliveries/verify        → QR scan at FPS → compare planned vs delivered
GET    /api/v1/dashboard/summary        → KPIs for Control Centre
GET    /api/v1/exceptions               → blocked dispatches with reasons
```

## 7. Prototype Build Order (Strict — Sec 16 Adapted)

1.  **PostgreSQL/PostGIS + Migrations** — dataset ingestion first (you will provide dataset)
2.  **FastAPI Backend** — auth + preferences + demand lock
3.  **Constraint Engine** — the distinctive module, with NFSA floor
4.  **XGBoost Demand Prediction** — trained on REAL historical demand (dataset)
5.  **OR-Tools Dispatch Optimizer** — real capacities/routes
6.  **OSRM + Geo Layer** — real warehouse/FPS coordinates
7.  **Flutter Beneficiary App** — real flow Sec 4.1, posts to API
8.  **React Control Centre** — live map, lock, exception handling
9.  **Locked Manifest + Audit** — hash + QR + audit log

Only after 1-9 works E2E → WhatsApp sim, IVR, anomaly detection.

## 8. Dataset Expectations (You Will Provide)

Prototype expects (CSV/Excel/JSON/SQL):
*   `beneficiaries` : id, household size, entitlement kg, current FPS
*   `fps` : id, location (lat/lon), capacity kg, warehouse linkage
*   `warehouses` : id, location, stock per commodity
*   `vehicles` : id, capacity, status
*   `historical_demand` : per FPS per cycle (for XGBoost training)
*   `allocations` : per FPS per cycle (state allocation)

Place file(s) in `K:\DemandSYNC\data\` or give path — ingestion script will validate schema.

## 9. What This Prototype Explicitly Does NOT Do

*   No demo hardcoding
*   No replacement of FCI/e-PoS/ONORC/Anna Chakra — consumes them as inputs
*   No blockchain buzzword
*   No invented savings % — metrics collected via pilot (Sec 4 in doc): dispatch accuracy, exception catch rate, utilization, variance, resolution time, participation rate

## 10. Next Steps

When dataset arrives:
*   Run `python backend/scripts/ingest_dataset.py --path <your_file>`
*   `docker compose up` → backend + db + OSRM
*   Verify E2E: preference → lock → validate → optimize → manifest

---
Generated: 2026-09-21 | Folder: K:\DemandSYNC | Mode: PROTOTYPE
