# DemandSYNC — Phase Plan & Dependency Graph
**K:\DemandSYNC | 2026-09-21 | Master Build Prompt Sec 27-29**

---

## 1. Implementation Order — Strict

Do NOT build everything at once.

```
PHASE 0  Foundation (DB + PostGIS + RBAC + Audit)
  ↓
PHASE 1  Data Trust (System Admin)
  ↓
PHASE 2  Cycle Command Centre (DSO — WOW screen)
  ↓
PHASE 3  Beneficiary Intent
  ↓
PHASE 4  AI Demand Intelligence
  ↓
PHASE 5  Demand Validation + Lock
  ↓
PHASE 6  AI Resource Allocation
  ↓
PHASE 7  OR-Tools Dispatch Optimization
  ↓
PHASE 8  Dispatch Authorization (Manifest QR+Hash)
  ↓
PHASE 9  Vehicle Tracking (Live telemetry)
  ↓
PHASE 10 FPS Dealer Portal
  ↓
PHASE 11 Beneficiary Delivery & ePOS
  ↓
PHASE 12 Delivery Reconciliation
  ↓
PHASE 13 Field Inspector
  ↓
PHASE 14 Grievance Intelligence
  ↓
PHASE 15 Auditor Portal
  ↓
PHASE 16 Cycle Evaluation
  ↓
PHASE 17 Cycle Closure
  ↓
PHASE 18 Full Integration + Testing + Demo Flow
```

## 2. Dependency Graph

```
datasets (83k, 7 scenarios, all PASS)
   │
   ├→ PHASE 0: migrations 001_initial.sql + 002_phase0 (cycles, dataset_imports, ai_predictions, extensions)
   │       ↓
   │   PHASE 1: /datasets/import → validation → ACTIVE (uses data_quality_report.csv)
   │       ↓
   │   PHASE 2: /cycles + workflow rail 13-stage + <WorkflowRail> (needs cycles, forecast, stock)
   │       ↓
   ├──────→ PHASE 3: /preferences (beneficiary) → intent_signals 14k
   │       │
   │       ├→ PHASE 4: /ai/forecast (xgb-v1.0, baseline/intent/forecast separate)
   │       │       ↓
   │       │   PHASE 5: /choice-window/close + constraint engine 6 gates → demand_locks + exceptions
   │       │       ↓
   │       │   PHASE 6: /ai/allocation-support + /cycles/{cycle}/allocate → allocations 3.6k
   │       │       ↓
   │       │   PHASE 7: /cycles/{cycle}/optimize (OR-Tools) → routes 3577, manifest DRAFT
   │       │       ↓
   │       │   PHASE 8: /manifests/lock → LOCKED + sha256 + qr + audit (300 manifests)
   │       │
   │       └→ PHASE 9: /telemetry + /routes → tracking (5170 points, 12% gap)
   │
   ├→ PHASE 10: /fps + /epos + /deliveries/verify → delivery_history 2824 + epos 14.4k + inventory 3900
   │       ↓
   │   PHASE 11: /beneficiaries/me/entitlement (remaining) + /epos/me
   │       ↓
   │   PHASE 12: /cycles/{cycle}/reconcile (planned vs delivered variance)
   │
   ├→ PHASE 13: /inspections → 400 sealed
   ├→ PHASE 14: /grievances + /ai/triage → 500
   ├→ PHASE 15: /audit/trace → audit_events 313 + intelligence
   │
   └→ PHASE 16-17: /ai/cycle-evaluation + /cycles/{cycle}/close (gate checks)
           ↓
       PHASE 18: E2E demo flow (ADMIN→DSO→Beneficiary→...→Auditor→Close) single cycle trace
```

**Critical path:** Datasets → Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 → Phase 9 → Phase 18. Other phases branch after Phase 8 but must integrate before Phase 18.

## 3. Phase Completion Rule (Sec 28)

A phase is NOT complete because "UI exists". Complete only when **all** work:

| Deliverable | Must Exist |
|-------------|------------|
| Database | Migrations, constraints, indexes, seed from datasets |
| Backend API | Endpoint + RBAC + validation + audit event |
| Business Rules | Entitlement floor, capacity, hash, immutability |
| AI | Service returns `prediction, confidence, reason, supporting_data, model_version, generated_at` if applicable |
| UI | Screen with workflow state, status, input, AI, rule checks, human decision, output, next action |
| Audit | `audit_events` row(s) + before/after + hash |
| Tests | Pytest + Playwright/Flutter Test covering happy + BLOCKED + missing data |
| Dataset used | Real CSV rows, no frontend arrays |

Provide for every phase: 1. DB changes 2. APIs 3. AI service 4. Screens 5. States 6. RBAC 7. Dataset 8. Audit 9. Validation 10. Tests

## 4. Current Status — Foundation Documents

| Doc | Status | Path |
|-----|--------|------|
| ARCHITECTURE.md | FROZEN v1.0 (prototype, 8 modules) | `K:\DemandSYNC\ARCHITECTURE.md` |
| PRD.md | FROZEN v1.0 (13 P0 features) | `K:\DemandSYNC\PRD.md` |
| TRD.md | FROZEN v1.0 (PostGIS, 14 tables, API spec) | `K:\DemandSYNC\TRD.md` |
| WORKFLOW.md | FROZEN v1.0 (13 stages, trace chain) | `K:\DemandSYNC\WORKFLOW.md` |
| AI_ARCHITECTURE.md | FROZEN v1.0 (11 services) | `K:\DemandSYNC\AI_ARCHITECTURE.md` |
| DATA_DICTIONARY.md | FROZEN v1.0 (23 datasets) | `K:\DemandSYNC\DATA_DICTIONARY.md` |
| RBAC.md | FROZEN v1.0 (6 roles) | `K:\DemandSYNC\RBAC.md` |
| API_CONTRACT.md | FROZEN v1.0 (~35 endpoints) | `K:\DemandSYNC\API_CONTRACT.md` |
| UI_UX_SYSTEM.md | FROZEN v1.0 (gov operational) | `K:\DemandSYNC\UI_UX_SYSTEM.md` |
| PHASE_PLAN.md | FROZEN v1.0 (this) | `K:\DemandSYNC\PHASE_PLAN.md` |
| Datasets | VALIDATED 83,763 rows, 57/57 PASS, 7 scenarios | `K:\DemandSYNC\data\` |
| DB Migration 001 | Exists | `pds-predict/database/migrations/001_initial.sql` |

**Architecture frozen 2026-09-21. No code changes to docs without version bump.**

## 5. Next — Phase 0 Implementation

Tasks (Sec PHASE 0):
1. Inspect datasets ✓
2. Validate schema ✓
3. Import into PostgreSQL (PostGIS)
4. Create migrations (002_phase0: cycles, dataset_imports, ai_predictions, ai_insights, extensions)
5. Relationships + indexes + constraints (FK, CHECK, triggers)
6. Cycle management
7. Audit infrastructure (audit_logs immutable)
8. RBAC (JWT, bcrypt, seed officers)
9. API architecture scaffold (FastAPI `main.py`)

Will implement ONE PHASE AT A TIME with verification: `RUN TESTS → VERIFY DB → VERIFY API → VERIFY UI → VERIFY DATA FLOW → VERIFY AI → VERIFY AUDIT → ONLY THEN NEXT PHASE`.

## 6. Final Demo Flow (Phase 18 Target)

```
ADMIN LOAD DATASET → DSO OPEN SEPTEMBER CYCLE → BENEFICIARIES SUBMIT INTENT → AI ANALYZES DEMAND → DSO REVIEWS FORECAST → DEMAND LOCK → AI RESOURCE ANALYSIS → CONSTRAINT VALIDATION → ALLOCATION → OR-TOOLS OPTIMIZATION → MANIFEST → DSO AUTHORIZES → TRUCK STARTS → LIVE TRACKING → FPS RECEIVES → BENEFICIARY COLLECTS → ePOS → RECONCILIATION → AI ANOMALY → INSPECTOR REVIEWS → AUDITOR TRACES → AI CYCLE EVALUATION → DSO CLOSES CYCLE
```
Same underlying records throughout — single cycle `2026-03` trace demonstration.

## 7. Repo Structure Post-Phase 18

```
K:\DemandSYNC\
  ARCHITECTURE.md, PRD.md, TRD.md, WORKFLOW.md, AI_ARCHITECTURE.md, DATA_DICTIONARY.md, RBAC.md, API_CONTRACT.md, UI_UX_SYSTEM.md, PHASE_PLAN.md
  data/ (27 files, 83k rows)
  scripts/generate_datasets.py (seed 20260921)
  pds-predict/
    backend/ (FastAPI + services + ai)
    frontend/ (React beneficiary, control_centre, fps_portal, inspector, auditor)
    database/migrations/
    docker/docker-compose.yml
    ml/models/
```
