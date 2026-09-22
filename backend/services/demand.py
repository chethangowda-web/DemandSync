"""Demand intelligence for the DSO: real aggregation from intent_signals, a deterministic baseline from
historical_demand, and the XGBoost forecast (see backend/services/forecast.py). Also owns the demand-lock
(choice-window close): an immutable snapshot of aggregated intent per FPS, hashed and audited.

Separation the report requires is kept literal here:
  baseline  = what historically happened (deterministic average of past cycles)
  intent    = what beneficiaries currently ask for (real aggregation of intent_signals)
  forecast  = what the model predicts (backend/services/forecast.py)
Differences are always labelled by what was subtracted from what; never a bare "variance".
"""
from __future__ import annotations

import hashlib
import json

import psycopg

from backend.core.errors import ApiError
from backend.services.beneficiary import num, one, rows

COMMODITIES = ("RICE", "WHEAT")
BASELINE_LOOKBACK_CYCLES = 3


def aggregate_intent(conn, cycle: str) -> dict[tuple[str, str], dict]:
    """Real aggregation of submitted intent per FPS + commodity for a cycle. Never invented."""
    out: dict[tuple[str, str], dict] = {}
    for r in rows(conn, """
            SELECT fps_id, 'RICE' AS commodity, COALESCE(sum(rice_quantity_kg), 0) AS kg, count(*) AS n
            FROM intent_signals WHERE cycle = %(cycle)s AND status = 'SUBMITTED' GROUP BY fps_id
            UNION ALL
            SELECT fps_id, 'WHEAT' AS commodity, COALESCE(sum(wheat_quantity_kg), 0) AS kg, count(*) AS n
            FROM intent_signals WHERE cycle = %(cycle)s AND status = 'SUBMITTED' GROUP BY fps_id""", {"cycle": cycle}):
        out[(r["fps_id"], r["commodity"])] = {"kg": r["kg"], "intents": r["n"]}
    return out


def compute_baseline(conn, cycle: str) -> dict[tuple[str, str], dict]:
    """Deterministic average of demand_kg over the last N cycles strictly before this one, per FPS+commodity."""
    out: dict[tuple[str, str], dict] = {}
    for r in rows(conn, """
            WITH ranked AS (
              SELECT fps_id, commodity, demand_kg, cycle,
                     row_number() OVER (PARTITION BY fps_id, commodity ORDER BY cycle DESC) AS rn
              FROM historical_demand WHERE cycle < %(cycle)s)
            SELECT fps_id, commodity, avg(demand_kg) AS baseline_kg, count(*) AS cycles_used
            FROM ranked WHERE rn <= %(n)s GROUP BY fps_id, commodity""",
                  {"cycle": cycle, "n": BASELINE_LOOKBACK_CYCLES}):
        out[(r["fps_id"], r["commodity"])] = {"kg": round(r["baseline_kg"], 1), "cycles_used": r["cycles_used"]}
    return out


def all_fps_commodity_pairs(conn) -> list[tuple[str, str]]:
    return [(r["fps_id"], c) for r in rows(conn, "SELECT fps_id FROM fps ORDER BY fps_id") for c in COMMODITIES]


def read_forecast(conn, cycle: str) -> dict[tuple[str, str], dict]:
    """Persisted demand_forecast rows for a cycle (no retraining). demand_forecast.csv's schema has no
    confidence column by design: confidence is an AI-signal concept, surfaced only via GET /ai/forecast
    per FPS (backend/services/forecast.py:forecast_one), not stored on the authoritative number."""
    return {(r["fps_id"], r["commodity"]): {"forecast_kg": r["forecast_demand_kg"], "confidence": None}
            for r in rows(conn, "SELECT fps_id, commodity, forecast_demand_kg FROM demand_forecast WHERE cycle = %s", (cycle,))}


def demand_table(conn, cycle: str, forecast_by_key: dict[tuple[str, str], dict] | None = None) -> list[dict]:
    """Intent, baseline and (if supplied) forecast side by side per FPS+commodity, with labelled differences."""
    intent = aggregate_intent(conn, cycle)
    baseline = compute_baseline(conn, cycle)
    forecast = forecast_by_key or {}
    out = []
    for fps_id, commodity in all_fps_commodity_pairs(conn):
        key = (fps_id, commodity)
        i = intent.get(key, {"kg": 0, "intents": 0})
        b = baseline.get(key, {"kg": None, "cycles_used": 0})
        f = forecast.get(key)
        row = {"fps_id": fps_id, "commodity": commodity, "intent_demand_kg": num(i["kg"]), "intent_count": i["intents"],
               "baseline_demand_kg": num(b["kg"]) if b["kg"] is not None else None, "baseline_cycles_used": b["cycles_used"],
               "forecast_demand_kg": num(f["forecast_kg"]) if f else None, "forecast_confidence": f["confidence"] if f else None}
        if row["forecast_demand_kg"] is not None:
            row["intent_minus_forecast_kg"] = round(row["intent_demand_kg"] - row["forecast_demand_kg"], 1)
        if row["baseline_demand_kg"] is not None and row["forecast_demand_kg"] is not None:
            row["forecast_minus_baseline_kg"] = round(row["forecast_demand_kg"] - row["baseline_demand_kg"], 1)
        if row["intent_demand_kg"] or row["forecast_demand_kg"] or row["baseline_demand_kg"]:
            out.append(row)
    return out


def participation(conn, cycle: str) -> dict:
    r = one(conn, """SELECT count(DISTINCT beneficiary_id) AS submitted, (SELECT count(*) FROM beneficiaries WHERE status = 'ACTIVE') AS total
                     FROM intent_signals WHERE cycle = %s AND status = 'SUBMITTED'""", (cycle,))
    pct = round(100 * r["submitted"] / r["total"], 1) if r["total"] else 0
    return {"submitted": r["submitted"], "eligible": r["total"], "participation_pct": pct}


# ------------------------------------------------------------------ demand lock

def canonical_snapshot(cycle: str, rows_: list[dict]) -> dict:
    """Canonical (key-sorted, no volatile fields) snapshot used for both storage and the SHA256 seal."""
    fps = {}
    for r in sorted(rows_, key=lambda r: (r["fps_id"], r["commodity"])):
        fps.setdefault(r["fps_id"], {})[r["commodity"]] = r["intent_demand_kg"]
    return {"cycle": cycle, "demand_by_fps": fps}


def demand_hash(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def close_choice_window(conn, cycle: str, officer_id: str) -> dict:
    """OPEN -> LOCKED. Freezes an immutable snapshot of aggregated intent, one per cycle, hashed."""
    c = one(conn, "SELECT state FROM cycles WHERE cycle = %s FOR UPDATE", (cycle,))
    if not c:
        raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
    if c["state"] != "OPEN":
        raise ApiError(409, "CYCLE_NOT_OPEN", f"Cycle {cycle} is {c['state']}, not OPEN. It cannot be locked.", {"state": c["state"]})

    table = demand_table(conn, cycle)
    snapshot = canonical_snapshot(cycle, table)
    sha = demand_hash(snapshot)
    try:
        with conn.transaction():
            conn.execute("INSERT INTO demand_locks (cycle, locked_by, snapshot, sha256_hash) VALUES (%s, %s, %s, %s)",
                        (cycle, officer_id, json.dumps(snapshot), sha))
            conn.execute("UPDATE cycles SET state = 'LOCKED', locked_at = now() WHERE cycle = %s", (cycle,))
    except psycopg.errors.UniqueViolation:  # a concurrent close won the race
        raise ApiError(409, "CYCLE_ALREADY_LOCKED", f"Cycle {cycle} is already locked.")
    total_kg = sum(sum(c.values()) for c in snapshot["demand_by_fps"].values())
    return {"cycle": cycle, "state": "LOCKED", "sha256_hash": sha, "locked_by": officer_id, "fps_count": len(snapshot["demand_by_fps"]),
            "total_intent_kg": round(total_kg, 1)}


def get_lock(conn, cycle: str) -> dict | None:
    r = one(conn, "SELECT cycle, locked_at, locked_by, snapshot, sha256_hash FROM demand_locks WHERE cycle = %s", (cycle,))
    if not r:
        return None
    recomputed = demand_hash(r["snapshot"])
    return {"cycle": r["cycle"], "locked_at": r["locked_at"].isoformat(), "locked_by": r["locked_by"],
            "sha256_hash": r["sha256_hash"], "hash_verified": recomputed == r["sha256_hash"], "snapshot": r["snapshot"]}
