# DemandSYNC — UI/UX System
**K:\DemandSYNC | 2026-09-21**

---

## 1. Design Language — Government Operational Infrastructure

Not banking SaaS, not glassmorphism, not startup dashboard.

**Tone:** serious, premium, trustworthy, institutional, highly legible, calm, dense but not cluttered.

**Primitives:** workflow timelines, state indicators, decision gates, maps, evidence panels, trace panels, progressive disclosure, large operational typography (cycle ID, manifest ID), clear status hierarchy, contextual actions.

**Avoid:** excessive gradients, floating cards everywhere, giant meaningless numbers, decorative charts, random animations.

## 2. Layout Rule — No Sidebar Dashboard

**Instead:** Top cycle header + stage flow rail (horizontal or vertical) + stage detail panel + evidence drawer.

```
┌─ DemandSYNC | SEPTEMBER 2026 CYCLE  [CLOSED] ─────────────────────┐
│ 01 MONITOR ●  02 VALIDATE ●  03 LOCK ● 04 ALLOCATE → 05 OPTIMIZE → 06 AUTHORIZE → 07 TRACK → 08 DELIVER → 09 VERIFY → 10 RECONCILE → 11 INSPECT → 12 AUDIT → 13 CLOSE │
│ [current stage visually dominant — large, filled, pulsing]                                                              │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
│ Stage Detail: LOCK GATE — Entitlement PASS · FPS Capacity 3 BLOCKED · Warehouse PASS · Duplicate PASS · Confidence 87% [LOCK DEMAND] │
├─ Evidence: forecast xgb-v1.0 | historical 12 cycles | intent 7,920kg | baseline 7,680kg | forecast 8,420kg [VIEW SOURCE] ├
│ AI SIGNAL badges inline, not popups                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 3. Portals

| Portal | Entry | Core UI | Key Components |
|--------|-------|---------|----------------|
| **System Admin — Data Trust** | `/admin` | Dataset lifecycle timeline: IMPORT → SCHEMA → REFERENTIAL → BUSINESS → QUALITY → APPROVE → ACTIVE | Validation matrix (57 checks), row counts, duplicates, orphans, Data Quality AI banner |
| **DSO — Cycle Command Centre** | `/dso` | 13-stage flow rail + stage detail + map (Leaflet/MapLibre) + exception list | Lock gate, allocation plan, optimization route, manifest QR, telemetry map |
| **Beneficiary** | `/beneficiary` | Mobile-first (Flutter mirror): MY PDS → Entitlement → Current Cycle → Plan → Choose → Receipt → Track | Entitlement `rice X + wheat Y = total Z` (real dataset, never generic 25kg), Intent receipt, Grievance form |
| **Field Inspector** | `/inspector` | Workflow: SELECT TARGET (AI priority) → TRAVEL → VERIFY → INSPECT → EVIDENCE → SEAL | Priority list with score/reasons, sealed hash display |
| **FPS Dealer** | `/fps` | RECEIVE → VERIFY TRUCK/MANIFEST → INVENTORY → ePOS → RECEIPT → RECONCILE | Manifest verify, stock risk alert, variance analysis |
| **Auditor** | `/auditor` | Trace workflow: SELECT CYCLE → TRACE DEMAND→...→AUDIT → FINDING → SEAL | `<TraceRecord>` chain, Audit Intelligence observations |

All portals share same backend/db/datasets, no invented data. Empty states: "Data unavailable" / "Live location unavailable".

## 4. AI Visual Identity

Badge styles:
*   `AI SIGNAL` — amber, explains
*   `AI FORECAST` — blue, with confidence
*   `AI RISK` — orange
*   `AI ANOMALY` — red
*   `AI PRIORITY` — purple

Each badge expands to: WHAT | WHY | DATA USED | CONFIDENCE | MODEL | TIMESTAMP + [VIEW SOURCE].

## 5. Component Library (React + TypeScript)

*   `<WorkflowRail stages={13} current={3} />`
*   `<DecisionGate checks={5} action="LOCK DEMAND" />`
*   `<AISignal service="demand_forecast" data={...} />`
*   `<TraceRecord entity="manifest" id="MAN-000007" />` — backwards/forwards
*   `<EvidencePanel source={xgb-v1.0} data={historical 12 cycles} />`
*   `<MapView telemetry={5170} routes={3577} />` — Leaflet, handles missing telemetry
*   `<ForgeHash display hash|qr />`

## 6. Responsive

Beneficiary: mobile-first 360px; DSO/Inspector/Auditor: desktop 1280px+ with density toggle. Print: manifest QR + hash.

## 7. Performance

Stage transitions <300ms; map telemetry <500ms for 5k points; E2E flow (intent→audit) trace <1s.
