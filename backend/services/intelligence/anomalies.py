"""Statistical anomaly detection over real history.

Basis (documented per anomaly in `detection_method`): submitted intent is a
partial drawdown, while historical_demand records full demand — comparing raw
kg would flag every FPS whenever participation is partial. The primary method
is therefore PER-CAPITA: current intent per submitting beneficiary vs the
per-capita demand series (demand_kg / beneficiary_count) from history.

Methods, in order of preference:
1. PER_CAPITA_ZSCORE — z of current intent-per-submitter vs historical
   per-capita series (needs >= MIN_HISTORY_POINTS with beneficiary_count > 0).
2. INTENT_HISTORY_ZSCORE — z of current intent vs prior cycles' intent
   aggregates (needs >= MIN_HISTORY_POINTS prior intent cycles).
3. Tukey IQR fence on the same series when stdev is 0 / skewed.
4. INTENT_VS_FORECAST percentage — last resort only, when no history exists
   at all; labelled as such.

Thresholds are explicit constants with reasons, never silent magic numbers.
No ML model is trained here; the XGBoost forecast is consumed (forecast.py),
not duplicated.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone

from backend.services.beneficiary import num, rows
from backend.services import demand as demand_svc

# Documented thresholds -----------------------------------------------------
# |z| >= 2.0: ~5% tail under normality — a conventional "worth a look" line.
Z_THRESHOLD = 2.0
# |z| >= 3.0: HIGH severity — under 0.3% tail, genuinely unusual.
Z_HIGH_THRESHOLD = 3.0
# |intent - forecast| / forecast >= 25%: material planning gap for a PDS cycle.
INTENT_VS_FORECAST_PCT = 25.0
# IQR factor 1.5: Tukey's standard fence for skewed series.
IQR_FACTOR = 1.5
# Minimum history points for a z-score to mean anything.
MIN_HISTORY_POINTS = 4


def _per_capita_history(conn, fps_id: str, commodity: str, before_cycle: str) -> list[float]:
    out = []
    for r in rows(conn, """SELECT demand_kg, beneficiary_count FROM historical_demand
                           WHERE fps_id = %s AND commodity = %s AND cycle < %s
                             AND beneficiary_count IS NOT NULL AND beneficiary_count > 0
                           ORDER BY cycle""", (fps_id, commodity, before_cycle)):
        out.append(num(r["demand_kg"]) / r["beneficiary_count"])
    return out


def _intent_history(conn, fps_id: str, commodity: str, before_cycle: str) -> list[float]:
    col = "rice_quantity_kg" if commodity == "RICE" else "wheat_quantity_kg"
    out = []
    for r in rows(conn, f"""SELECT COALESCE(sum({col}),0) AS kg FROM intent_signals
                            WHERE fps_id = %s AND cycle < %s AND status='SUBMITTED'
                            GROUP BY cycle ORDER BY cycle""", (fps_id, before_cycle)):
        if num(r["kg"]):
            out.append(num(r["kg"]))
    return out


def _z_anomaly(fps_id, commodity, observed, observed_label, history, history_label,
               intent_n, detected_at) -> dict | None:
    mean = statistics.fmean(history)
    stdev = statistics.pstdev(history) or 0
    if stdev > 0:
        z = (observed - mean) / stdev
        if abs(z) >= Z_THRESHOLD:
            obs_r, exp_r = round(observed, 3), round(mean, 3)
            return _mk(fps_id, commodity, "DEMAND_ZSCORE",
                       "HIGH" if abs(z) >= Z_HIGH_THRESHOLD else "MEDIUM",
                       obs_r, exp_r, round(obs_r - exp_r, 3),
                       f"z-score {z:+.2f} of {observed_label} vs {history_label}"
                       f" over {len(history)} points (mean {mean:.3f}, sd {stdev:.3f};"
                       f" |z| >= {Z_THRESHOLD} threshold)",
                       intent_n, detected_at)
        return None
    q = statistics.quantiles(history, n=4) if len(history) >= MIN_HISTORY_POINTS else None
    if q:
        q1, q3 = q[0], q[2]
        iqr = q3 - q1
        upper, lower = q3 + IQR_FACTOR * iqr, q1 - IQR_FACTOR * iqr
        # Materiality floor: on flat synthetic series (IQR = 0) any dust
        # breaches the fence — require a >=20% move from the mean as well.
        material = abs(observed - mean) / mean >= 0.20 if mean else bool(observed)
        if (observed > upper or observed < lower) and material:
            obs_r, exp_r = round(observed, 3), round(mean, 3)
            return _mk(fps_id, commodity, "DEMAND_IQR_OUTLIER", "MEDIUM",
                       obs_r, exp_r, round(obs_r - exp_r, 3),
                       f"Tukey fence breach: {observed_label} {observed} outside"
                       f" [{lower:.3f}, {upper:.3f}] (Q1 {q1:.3f}, Q3 {q3:.3f},"
                       f" factor {IQR_FACTOR}); series stdev is 0",
                       intent_n, detected_at)
    return None


def _detect_one(conn, fps_id: str, commodity: str, intent_kg: float, intent_n: int,
                forecast_kg: float | None, cycle: str, detected_at: str) -> dict | None:
    per_cap = _per_capita_history(conn, fps_id, commodity, cycle)
    if len(per_cap) >= MIN_HISTORY_POINTS and intent_n > 0:
        a = _z_anomaly(fps_id, commodity, round(intent_kg / intent_n, 3),
                       "current intent per submitter (kg/person)",
                       [round(v, 3) for v in per_cap],
                       "historical demand per beneficiary (kg/person)",
                       intent_n, detected_at)
        if a:
            a["metric"] = "intent_kg_per_person"
            return a
        return None
    hist = _intent_history(conn, fps_id, commodity, cycle)
    if len(hist) >= MIN_HISTORY_POINTS:
        a = _z_anomaly(fps_id, commodity, intent_kg, "current intent (kg)", hist,
                       "prior-cycle intent (kg)", intent_n, detected_at)
        if a:
            return a
        return None
    if forecast_kg:
        pct = abs(intent_kg - forecast_kg) / forecast_kg * 100 if forecast_kg else 0
        if pct >= INTENT_VS_FORECAST_PCT:
            return _mk(fps_id, commodity, "INTENT_VS_FORECAST",
                       "HIGH" if pct >= 50 else "MEDIUM", intent_kg, forecast_kg,
                       round(intent_kg - forecast_kg, 1),
                       f"percentage deviation vs forecast ({pct:.1f}% >="
                       f" {INTENT_VS_FORECAST_PCT}% threshold; only {len(per_cap)} per-capita"
                       f" points and {len(hist)} prior intent cycles — insufficient for"
                       f" z-score (needs {MIN_HISTORY_POINTS}))",
                       intent_n, detected_at)
    return None


def _mk(fps_id, commodity, atype, severity, observed, expected, diff, method, n_intents, detected_at):
    return {
        "anomaly_id": f"ANOM-{fps_id}-{commodity}-{atype}",
        "type": atype, "severity": severity,
        "entity_type": "FPS", "entity_id": fps_id, "commodity": commodity,
        "metric": "intent_demand_kg", "observed_value": observed,
        "expected_value": expected, "difference": diff,
        "detection_method": method,
        "evidence": [
            {"record": "intent_signals", "field": "SUM(quantity_kg)",
             "value": observed, "detail": f"{n_intents} submitted intents aggregated"},
            {"record": "historical_demand", "value": expected, "detail": method},
            {"record": "demand_forecast", "field": "forecast_demand_kg",
             "value": expected if atype == "INTENT_VS_FORECAST" else None,
             "detail": "persisted XGBoost forecast" if atype == "INTENT_VS_FORECAST" else "per-capita baseline"},
        ],
        "detected_at": detected_at,
    }


def demand_anomalies(conn, cycle: str) -> list[dict]:
    """Anomaly per FPS+commodity with intent in this cycle. Normal demand -> no anomaly."""
    detected_at = datetime.now(timezone.utc).isoformat()
    intent = demand_svc.aggregate_intent(conn, cycle)
    forecast = demand_svc.read_forecast(conn, cycle)
    out = []
    for (fps_id, commodity), agg in sorted(intent.items()):
        if not agg["kg"]:
            continue
        f = forecast.get((fps_id, commodity))
        a = _detect_one(conn, fps_id, commodity, num(agg["kg"]), agg["intents"],
                        (num(f["forecast_kg"]) if f and f["forecast_kg"] is not None else None),
                        cycle, detected_at)
        if a:
            out.append(a)
    return out


def reconciliation_anomalies(conn, cycle: str) -> list[dict]:
    """Expected vs Actual vs Difference per mass-balance leg, with source records."""
    from backend.services.intelligence import signals as sig
    detected_at = datetime.now(timezone.utc).isoformat()
    out = []
    for leg in sig.mass_balance(conn, cycle):
        for label, exp, act, diff in (
                ("ALLOCATED_VS_DISPATCHED", leg["allocated_kg"], leg["dispatched_kg"],
                 leg["allocated_minus_dispatched"]),
                ("DISPATCHED_VS_RECEIVED", leg["dispatched_kg"], leg["received_kg"],
                 leg["dispatched_minus_received"])):
            if exp is None or act is None:
                continue  # never infer a missing leg
            tol = max(abs(exp) * 0.05, 1.0)
            if abs(diff) > tol:
                pct = round(abs(diff) / abs(exp) * 100, 1) if exp else None
                out.append({
                    "anomaly_id": f"ANOM-REC-{leg['fps_id']}-{leg['commodity']}-{label}",
                    "type": "RECONCILIATION_" + label, "severity": "HIGH" if (pct or 0) >= 20 else "MEDIUM",
                    "entity_type": "FPS", "entity_id": leg["fps_id"], "commodity": leg["commodity"],
                    "metric": label.lower(), "observed_value": act, "expected_value": exp,
                    "difference": diff,
                    "detection_method": f"mass-balance tolerance: |actual - expected| > max(5% of expected, 1 kg)"
                                        f" (observed {pct}% deviation)",
                    "evidence": [
                        {"record": "allocations", "field": "allocated_kg", "value": leg["allocated_kg"]},
                        {"record": "dispatch_manifest_items", "field": "planned_kg",
                         "value": leg["dispatched_kg"]},
                        {"record": "delivery_history", "field": "delivered_kg",
                         "value": leg["received_kg"]},
                    ],
                    "detected_at": detected_at,
                })
        if leg["delivery_rejected_lines"]:
            out.append({
                "anomaly_id": f"ANOM-REC-{leg['fps_id']}-{leg['commodity']}-REJECTED",
                "type": "RECONCILIATION_REJECTED_DELIVERY", "severity": "HIGH",
                "entity_type": "FPS", "entity_id": leg["fps_id"], "commodity": leg["commodity"],
                "metric": "rejected_deliveries", "observed_value": leg["delivery_rejected_lines"],
                "expected_value": 0, "difference": leg["delivery_rejected_lines"],
                "detection_method": "rule: any delivery_history row with status REJECTED",
                "evidence": [{"record": "delivery_history", "field": "status",
                              "value": "REJECTED",
                              "detail": f"{leg['delivery_rejected_lines']} rejected line(s)"}],
                "detected_at": detected_at,
            })
    return out
