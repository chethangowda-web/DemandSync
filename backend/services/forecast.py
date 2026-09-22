"""Demand Forecast AI (XGBoost). See docs/AI_ARCHITECTURE.md Sec 2.

ML predicts, it never dispatches: this module only ever writes to demand_forecast and ai_predictions.
No downstream table (allocations, manifests) is touched from here.

The model is trained live, in-process, from the historical_demand table on every call. There is no
persisted model artifact; docs/AI_ARCHITECTURE.md's `ml/models/xgb_fps_demand.json` is aspirational for a
production deployment. At this dataset size (12 cycles, ~14k rows) training takes well under a second, so
this is honest and reproducible rather than a caching optimisation pretending to be a real model registry.

Fallback rule (AI_ARCHITECTURE.md Sec 8): fewer than MIN_HISTORY_CYCLES of history for an FPS+commodity ->
no model prediction is made; the forecast falls back to the deterministic aggregated baseline, confidence
is marked low, and the reason says so explicitly. A model is never allowed to guess past insufficient data.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import numpy as np
import xgboost as xgb

from backend.services.beneficiary import num, rows
from backend.services.demand import aggregate_intent, all_fps_commodity_pairs, compute_baseline

MODEL_VERSION = "xgb-v1.0"
MIN_HISTORY_CYCLES = 3
_COMMODITY_CODE = {"RICE": 0, "WHEAT": 1}


def _training_frame(conn) -> list[dict]:
    return rows(conn, """
        SELECT fps_id, cycle, commodity, demand_kg, COALESCE(previous_demand_kg, demand_kg) AS previous_demand_kg,
               COALESCE(trend_factor, 0) AS trend_factor, COALESCE(season_factor, 1) AS season_factor,
               month, COALESCE(beneficiary_count, 0) AS beneficiary_count
        FROM historical_demand ORDER BY fps_id, commodity, cycle""")


def _features(r: dict) -> list[float]:
    return [_COMMODITY_CODE[r["commodity"]], r["month"], r["trend_factor"], r["season_factor"],
            r["previous_demand_kg"], r["beneficiary_count"]]


def _train(conn) -> tuple[xgb.XGBRegressor, dict]:
    """Trains on every historical row except each fps+commodity's own latest cycle, which is held out to
    produce a real (not invented) validation MAE for confidence calibration."""
    data = _training_frame(conn)
    latest_per_key: dict[tuple[str, str], dict] = {}
    for r in data:
        latest_per_key[(r["fps_id"], r["commodity"])] = r  # rows are ordered by cycle ascending
    holdout_ids = {id(r) for r in latest_per_key.values()}
    train_rows = [r for r in data if id(r) not in holdout_ids]
    val_rows = list(latest_per_key.values())

    model = xgb.XGBRegressor(n_estimators=120, max_depth=4, learning_rate=0.1, subsample=0.9, random_state=20260921)
    model.fit(np.array([_features(r) for r in train_rows]), np.array([r["demand_kg"] for r in train_rows]))

    val_pred = model.predict(np.array([_features(r) for r in val_rows]))
    val_actual = np.array([r["demand_kg"] for r in val_rows])
    mape = float(np.mean(np.abs(val_pred - val_actual) / np.maximum(val_actual, 1))) if len(val_rows) else 1.0
    n_cycles = len({r["cycle"] for r in data})
    meta = {"training_dataset_version": f"hist-v1-{n_cycles}cyc-{len(train_rows)}rows",
            "validation_mape": round(mape, 4), "validation_n": len(val_rows)}
    return model, meta


def _latest_features(conn) -> dict[tuple[str, str], dict]:
    """Each FPS+commodity's most recent historical row, used as the feature basis for predicting the next cycle."""
    out: dict[tuple[str, str], dict] = {}
    for r in _training_frame(conn):
        out[(r["fps_id"], r["commodity"])] = r
    return out


def generate_forecast(conn, cycle: str) -> dict[tuple[str, str], dict]:
    """Forecasts every FPS+commodity for `cycle`, upserts demand_forecast, returns a dict of the results."""
    intent = aggregate_intent(conn, cycle)
    baseline = compute_baseline(conn, cycle)
    latest = _latest_features(conn)
    model, meta = _train(conn)
    target_month = int(cycle[5:7])

    out: dict[tuple[str, str], dict] = {}
    to_write = []
    for fps_id, commodity in all_fps_commodity_pairs(conn):
        key = (fps_id, commodity)
        b = baseline.get(key)
        i = intent.get(key, {"kg": 0})
        if b is None or b["cycles_used"] < MIN_HISTORY_CYCLES:
            reason = (f"Insufficient history ({b['cycles_used'] if b else 0} of {MIN_HISTORY_CYCLES} cycles required) "
                      "for a model prediction; showing the aggregated historical average instead.")
            fk = num(b["kg"]) if b else 0
            out[key] = {"forecast_kg": fk, "confidence": 30, "reason": reason, "baseline_kg": fk,
                        "intent_kg": num(i["kg"]), "cycles_used": b["cycles_used"] if b else 0, "fallback": True}
            # still persisted (as the baseline figure), so a previously-modelled value never survives stale
            to_write.append((fps_id, commodity, fk, num(i["kg"]), fk))
            continue
        f = latest.get(key)
        row_features = [_COMMODITY_CODE[commodity], target_month, f["trend_factor"], f["season_factor"],
                       f["demand_kg"], f["beneficiary_count"]]
        pred = max(0.0, float(model.predict(np.array([row_features]))[0]))
        confidence = int(max(35, min(92, round(100 * (1 - meta["validation_mape"])))))
        trend_pct = round(f["trend_factor"] * 100, 1)
        season_pct = round((f["season_factor"] - 1) * 100, 1)
        intent_vs_baseline_pct = round(100 * (num(i["kg"]) - b["kg"]) / b["kg"], 1) if b["kg"] else 0
        reason = (f"Primary signals: {trend_pct:+g}% historical trend, {season_pct:+g}% seasonal factor, "
                 f"intent {intent_vs_baseline_pct:+g}% vs baseline ({num(i['kg'])} kg intent vs {b['kg']} kg baseline).")
        out[key] = {"forecast_kg": round(pred, 1), "confidence": confidence, "reason": reason, "baseline_kg": b["kg"],
                    "intent_kg": num(i["kg"]), "cycles_used": b["cycles_used"], "fallback": False}
        to_write.append((fps_id, commodity, b["kg"], num(i["kg"]), round(pred, 1)))

    now = datetime.now(timezone.utc)
    with conn.transaction():
        for fps_id, commodity, baseline_kg, intent_kg, forecast_kg in to_write:
            fid = f"FC-{cycle}-{fps_id}-{commodity}"
            conn.execute(
                """INSERT INTO demand_forecast (forecast_id, fps_id, cycle, commodity, baseline_demand_kg, intent_demand_kg,
                       forecast_demand_kg, model_version, prediction_generated_at, training_dataset_version, prediction_horizon)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '30d')
                   ON CONFLICT (fps_id, cycle, commodity) DO UPDATE SET baseline_demand_kg = EXCLUDED.baseline_demand_kg,
                       intent_demand_kg = EXCLUDED.intent_demand_kg, forecast_demand_kg = EXCLUDED.forecast_demand_kg,
                       model_version = EXCLUDED.model_version, prediction_generated_at = EXCLUDED.prediction_generated_at,
                       training_dataset_version = EXCLUDED.training_dataset_version""",
                (fid, fps_id, cycle, commodity, baseline_kg, intent_kg, forecast_kg, MODEL_VERSION, now,
                 meta["training_dataset_version"]))
    return out


def forecast_one(conn, cycle: str, fps_id: str, commodity: str) -> dict:
    """The single-signal AI envelope for one FPS+commodity, logged to ai_predictions (docs/AI_ARCHITECTURE.md Sec 3)."""
    results = generate_forecast(conn, cycle)
    r = results.get((fps_id, commodity))
    if r is None:
        from backend.core.errors import ApiError
        raise ApiError(404, "NO_FORECAST", f"No forecast available for {fps_id}/{commodity} in {cycle}.")
    now = datetime.now(timezone.utc)
    envelope = {"service": "demand_forecast", "prediction": r["forecast_kg"], "unit": "kg", "confidence": r["confidence"],
               "reason": r["reason"],
               "supporting_data": {"baseline_kg": r["baseline_kg"], "intent_kg": r["intent_kg"], "historical_cycles": r["cycles_used"],
                                   "fps_id": fps_id, "commodity": commodity, "fallback": r["fallback"]},
               "model_version": MODEL_VERSION, "generated_at": now.isoformat(), "affected_entities": [fps_id],
               "what_next": "Review forecast -> Validate constraints"}
    conn.execute(
        """INSERT INTO ai_predictions (prediction_id, service, cycle, entity_type, entity_id, prediction, confidence,
               reason, supporting_data, model_version, generated_at)
           VALUES (%s, 'demand_forecast', %s, 'FPS', %s, %s, %s, %s, %s, %s, %s)""",
        ("AIP-" + uuid.uuid4().hex[:12].upper(), cycle, fps_id, f'{{"kg": {r["forecast_kg"]}, "commodity": "{commodity}"}}',
         r["confidence"], r["reason"], _json(envelope["supporting_data"]), MODEL_VERSION, now))
    return envelope


def _json(d: dict) -> str:
    import json
    return json.dumps(d)
