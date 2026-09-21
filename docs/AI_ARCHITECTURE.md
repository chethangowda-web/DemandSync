# DemandSYNC — AI Intelligence Layer
**PDS PREDICT | 11 AI Services | K:\DemandSYNC | 2026-09-21**
**Principle: AI PREDICTS → RULES VALIDATE → OPTIMIZATION ALLOCATES → HUMAN AUTHORIZES**

---

## 1. Philosophy — Embedded, Not Chatbot

No standalone chatbot. AI is **11 specialized services** embedded at workflow stages. Every insight contains: `prediction | confidence | reason | supporting_data | model_version | generated_at` and explains WHY.

Language: `AI detected/estimates/identified/suggests review` — never `AI decided/approved/authorized`.

Visual tags: `AI SIGNAL | AI FORECAST | AI RISK | AI ANOMALY | AI EXPLANATION | AI PRIORITY | AI RECONCILIATION`

## 2. Service Catalog

| # | Service | Stage | Input | Output | Model | UI Location |
|---|---------|-------|-------|--------|-------|-------------|
| 1 | **Demand Forecast AI** | 01 MONITOR, 04 INTELLIGENCE | `historical_demand 14.4k ×12 cycles, intent 14k, season, weather` | `forecast_demand_kg, confidence 0-100, why {trend +6.2%, intent +4.1%, seasonal +2%}, affected FPS` | XGBoost v1.0 (`xgb-v1.0`, training_dataset_version `hist-v1-202512`, horizon 30d) | DSO forecast explainer |
| 2 | **Intent Analysis AI** | 01-04 | `intent_signals per beneficiary, household, scheme` | Intent vs baseline variance, unexpected intent spikes per FPS, collection_mode pattern | Rule + statistical (z-score) | Intent compare panel |
| 3 | **Anomaly Detection AI** | 01,04,12 | `historical_demand, forecast, delivery` | Flags: "FPS-102 demand 2,250kg vs baseline 1,900kg +18% anomaly" | IsolationForest / scikit-learn | Anomaly banner |
| 4 | **Allocation Decision Support AI** | 06 | `locked demand, warehouse stock, fps capacity, vehicle capacity` | "FPS-102 requires 1850kg, warehouse 1620kg → 230kg shortage — allocate BLOCKED" | Rule + optimization pre-check | Allocation plan |
| 5 | **Route Risk AI** | 07 | `route distance, historical duration, weather, calendar` | "High congestion risk stop 3" | Heuristic + historical aggregates | Optimization detail |
| 6 | **Dispatch Risk AI** | 08-09 | `telemetry 5k, routes 3.5k, speed, stops` | "ETA risk: stationary 18min at non-planned location" | Statistical threshold + route deviation calc | Tracking alerts |
| 7 | **Delivery Variance AI** | 10,12 | `planned vs delivered 2824 rows` | Variance classification VERIFIED/VARIANCE/REJECTED, contributing records | Rule (diff%) | Reconciliation panel |
| 8 | **Inspection Risk AI** | 13 | `stock variance, delivery variance, ePOS anomalies, grievances, history` | Prioritized FPS list for inspection — never guilt | Scoring model (weighted sum) | Inspector target picker |
| 9 | **Grievance Triage AI** | 14 | `grievance text, beneficiary, fps, transactions` | `{category, urgency, related FPS/txn/cycle, routing suggestion}` | Classifier (rule + keyword) | Grievance queue |
| 10 | **Audit Intelligence AI** | 15 | `full trace chain 83k records` | Observations: "planned vs delivered mismatch repeated at FPS-102 (4 cycles)" + evidence + confidence | Cross-table anomaly joins | Auditor trace panel |
| 11 | **Cycle Evaluation AI** | 16 | `cycle aggregates: intent/forecast/baseline/actual, allocation, logistics, exceptions` | Structured insights: forecast deviation, warehouse pressure, reliability patterns | Aggregation + trend analysis | Cycle review report |

Plus: **Data Quality Assistant** (Phase 1): "FPS-102 has high missing capacity" — pattern detection over `data_quality_report.csv`.

## 3. Contract — Every AI Response

```json
{
  "service": "demand_forecast",
  "prediction": 8420,
  "unit": "kg",
  "confidence": 87,
  "reason": "Primary signals: +6.2% historical trend, +4.1% intent increase, +2.0% seasonal factor (KHARIF)",
  "supporting_data": {"baseline": 7680, "intent": 7920, "historical_cycles": 12, "fps_id":"FPS-0102"},
  "model_version": "xgb-v1.0",
  "training_dataset_version": "hist-v1-202512",
  "generated_at": "2025-12-28T10:00:00",
  "affected_entities": ["FPS-0102"],
  "what_next": "Review forecast → Validate constraints"
}
```

Mandatory fields: `prediction, confidence, reason, supporting_data, model_version, generated_at`. UI always shows VIEW SOURCE button: model, training dataset, FPS, historical cycles, intent vs baseline.

## 4. Explainability — WHY, WHAT DATA, CONFIDENCE, MODEL, TIMESTAMP

Example from prompt Sec 22:
```
AI FORECAST: 8,420 KG | Confidence 87%
WHY: +6.2% historical trend, +4.1% intent increase, +2.0% seasonal
MODEL: XGBoost v1.0 | DATA: 12 historical cycles | Generated: timestamp
```
Every stage's AI insight opens explain drawer with same schema.

## 5. Separation of Concerns — AI Never Overrides

```
ML (XGBoost) → Prediction
      ↓
RULE ENGINE (deterministic, CONSTRAINT_VALIDATED) → PASS/BLOCK
      ↓
OR-TOOLS → Optimal allocation/route
      ↓
HUMAN (DSO/Officer/Inspector/Auditor) → AUTHORIZE
      ↓
SYSTEM → Execute + Hash + Audit
```
Enforced: `demand_forecast.forecast_demand_kg` never writes `allocations.allocated_kg` without lock + constraint pass. Triggers prevent direct write.

## 6. Data Sources Per Service

*   Historical: `historical_demand.csv 14.4k`
*   Intent: `intent_signals.csv 14k`
*   Forecast: `demand_forecast.csv 3.6k` (already has baseline/intent/forecast separate)
*   Stock/Allocation: `allocations.csv 3.6k`, `inventory.csv 3.9k`, `warehouse_master.csv`
*   Logistics: `dispatch_manifests/items 300/3577`, `vehicle_fleet 150`, `routes 3577`, `telemetry 5170`
*   Compliance: `inspections 400`, `grievances 500`, `exceptions 251`, `audit_events 313`
*   Context: `weather 1080`, `calendar 48`, `historical_stockouts 375`

## 7. Model Registry (Synthetic — Marked Generated)

| Model | Version | Training Data | Horizon | Artifact |
|-------|---------|---------------|---------|----------|
| Demand Forecast | `xgb-v1.0` | `historical_demand_v1 (12 cycles) + intent` | 30d | `ml/models/xgb_fps_demand.json` (to be trained) |
| Anomaly | `isolation-forest v0.1` | `historical_demand per FPS` | — | `ml/models/anomaly.json` |
| Grievance Triage | `rule-keyword v0.1` | `grievances 500` | — | `backend/services/ai/triage.py` |

All marked synthetic, with `prediction_generated_at` timestamp.

## 8. Failure Modes — Graceful Degradation

*   Forecast unavailable → "Forecast unavailable" (not fake number)
*   Telemetry gap 12% → "Live location unavailable"
*   Historical insufficient (<3 cycles) → confidence low, show warning, fallback to `aggregated GROUP BY`
*   Model version mismatch → show banner "Model training dataset stale"

## 9. Integration Points

Backend: `pds-predict/backend/services/ai/` — one module per service, called before rule engine. Frontend: `AI_SIGNAL` badge in DSO/Inspector/Auditor portals, progressive disclosure on click. Audit: every AI prediction logged to `ai_predictions` table with `model_version` + `generated_at`.

## 10. Testing AI

Unit: confidence calibration, reason non-empty, supporting_data FK exists. Integration: DSO workflow end-to-end — intent → forecast → lock → allocation — AI signals appear, officer decision gates still require human click. No test asserts "AI approved".
