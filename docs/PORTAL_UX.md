# DemandSYNC — Portal UX Architecture
**K:\DemandSYNC | 2026-09-21 | Two Experiences, One Workflow, Same Backend/DB/Dataset**

---

## 1. Two Portals, One Truth

| Experience | Platform | User | Info Architecture | Interaction | Data Source |
|------------|----------|------|-------------------|-------------|-------------|
| **Beneficiary** | Flutter mobile | 10k PDS ration holders | Task-oriented: "What can I do right now?" | Large touch targets, bottom nav HOME/MY RATION/HISTORY/HELP, minimal terminology | Same FastAPI `http://10.0.2.2:8000` + PostgreSQL 83k rows |
| **Officer Web** | React+TS desktop (1280px) | DSO/Inspector/FPS/Auditor/Admin | Workflow control centre: 13-stage rail, current stage dominant | Dense, evidence panels, decision gates, trace timelines | Same backend/DB/dataset |

No generic dashboard resized. No mock arrays. Missing → "Data unavailable" / "Live location unavailable".

## 2. Beneficiary Mobile — Flutter (`frontend/beneficiary-mobile`)

**Workflow:** LOGIN → OTP → MY PDS HOME → MY ENTITLEMENT → CURRENT CYCLE → PLAN COLLECTION → CHOOSE PREFERENCE → REVIEW → SUBMIT INTENT → RECEIPT → TRACK → RATION RECEIVED → RECEIPT → GRIEVANCE/HELP

**Screens:**
*   `lib/screens/home_screen.dart` — entitlement `Rice X + Wheat Y = Total Z` (real `beneficiaries_master.entitlement_kg`, never 25kg), current FPS, window `2026-03-05→20`, intent status, CTA PLAN MY COLLECTION / TRACK MY RATION
*   `lib/screens/entitlement_screen.dart` — `Total / Used / Remaining` (remaining = entitlement - sum SUCCESS ePOS)
*   `lib/screens/intent_screen.dart` — rice/wheat/mode SELF/AUTHORIZED, backend validation ≤ remaining
*   `lib/screens/track_screen.dart` — parcel-style 7 steps INTENT→AVAILABLE, telemetry real or "Live location unavailable"
*   `lib/widgets/assistant_sheet.dart` — My PDS Assistant answers with authenticated data, never changes entitlement
*   `lib/services/api.dart` — `GET /beneficiaries/me`, `POST /preferences`, `GET /epos/me`, `GET /ai/...` — real backend

**AI:** My PDS Assistant + Delivery Assistant explain records; Grievance triage classifies but beneficiary sees final submission. Categories: SHORT_DELIVERY etc.

**Style:** Mobile-first 360px, large typography, clear icons, English/Hindi/Kannada ready, trusted/simple/human/premium.

## 3. Officer Web — React+TS (`frontend/officer-web`)

**Workflow Rail (13):** `01 MONITOR ● 02 VALIDATE ● 03 LOCK ● 04 ALLOCATE → 05 OPTIMIZE → 06 AUTHORIZE → 07 TRACK → 08 DELIVER → 09 VERIFY → 10 RECONCILE → 11 INSPECT → 12 AUDIT → 13 CLOSE` — current dominant (filled + pulsing), BLOCKED red, COMPLETE green.

**Pages:**
*   `src/pages/DSOControlCentre.tsx` — CycleHeader + TraceTimeline + AISignal (8,420kg forecast why +6.2% trend) + DecisionGate (5 checks) + ManifestCard (BLOCKED FPS_CAPACITY) + Leaflet map (5170 telemetry)
*   `src/pages/AdminDataTrust.tsx` — IMPORT→...→ACTIVE 7-step, 57/57 PASS, 83k rows, AI Data Quality banner
*   `src/pages/FPSPortal.tsx` — RECEIVE→...→RECONCILE, stock risk, variance neutral language
*   `src/pages/InspectorPortal.tsx` — SELECT TARGET (AI priority score) → SEAL with SHA256
*   `src/pages/AuditorPortal.tsx` — TRACE timeline BEN→...→AUDIT 13-node, AI Audit Intelligence

**Reusable Components (`src/components`):**
`CycleHeader`, `WorkflowStepper`, `DecisionGate`, `AISignal`, `EvidencePanel`, `TraceTimeline`, `ManifestCard`, `HashBadge` — `ConstraintCheck`, `ExceptionPanel`, `SourceViewer`, `AuditTrail`, `VehicleTracker`, `RoutePanel`, `DataQualityPanel`, `ApprovalGate`, `StatusBadge` (stubs for next phases)

**AI per Stage:** Forecast/Anomaly/Resource Risk/Route Risk/Delivery Anomaly — each shows WHAT/WHY/DATA/CONFIDENCE/MODEL/TIMESTAMP + [VIEW SOURCE].

## 4. Shared Backend Contract

`src/api/client.ts` — `fetch BASE/api/v1/...` with `Authorization: Bearer JWT` — RBAC enforced server-side. No frontend mock arrays.

Endpoints used: `/datasets/manifest`, `/beneficiaries/me`, `/preferences`, `/cycles/{cycle}/choice-window/close`, `/ai/forecast`, `/manifests/{id}`, `/telemetry`, `/epos`, `/inspections`, `/audit/trace`.

## 5. Join — One Real Workflow

```
BENEFICIARY submits intent (Flutter POST /preferences)
  ↓ BACKEND stores intent_signals (14k) → PostgreSQL
  ↓ AI analyzes aggregate (xgb-v1.0 baseline 7,680 vs intent 7,920 vs forecast 8,420)
  ↓ DSO reviews demand intelligence (React)
  ↓ RULES validate (6 gates)
  ↓ DSO locks demand (SHA256)
  ↓ ALLOCATION + OR-Tools route (vehicle 5,000kg utilization 92%)
  ↓ DSO authorizes manifest (LOCKED + QR)
  ↓ VEHICLE moves (telemetry 5,170)
  ↓ FPS receives (delivery 2,824)
  ↓ BENEFICIARY tracks (parcel timeline)
  ↓ ePOS records distribution (14,400) → remaining entitlement
  ↓ RECONCILIATION variance 40kg → exception
  ↓ AI anomaly → INSPECTOR priority → SEAL
  ↓ AUDITOR traces 13-node chain → finding → SEAL
  ↓ DSO closes cycle (gate 7 checks)
```
Same `BEN-000001` → `MAN-000001` → `DEL-000001` → `EPOS-00000001` chain throughout.

## 6. E2E Test (24 Steps)

1 Login beneficiary (BEN-000001) → 2 View entitlement (real rice+wheat) → 3 Submit intent (POST) → 4 DSO sees intent → 5 AI analyzes → 6 Validate → 7 Lock → 8 Allocation → 9 Optimize → 10 Manifest → 11 Authorize → 12 Tracking → 13 FPS receive → 14 Receipt → 15 Beneficiary track → 16 ePOS → 17 Verify transaction → 18 Reconciliation → 19 Inspector sees → 20 Auditor traces → 21 Close cycle. Fails if any step uses mock data.

## 7. Build Commands

```bash
# Officer web (React)
cd frontend/officer-web && npm install && npm run dev # http://localhost:3000
# Beneficiary mobile (Flutter)
cd frontend/beneficiary-mobile && flutter pub get && flutter run -d chrome
# Backend
cd pds-predict && uvicorn backend.main:app --reload # http://localhost:8000/docs
```

---

**UX frozen 2026-09-21 — two portals, one workflow, same truth.**
