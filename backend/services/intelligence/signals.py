"""Deterministic signals over persisted records.

No ML here: intent/forecast/baseline arithmetic, mass-balance chain
(ALLOCATED -> DISPATCHED -> RECEIVED -> DISTRIBUTED), warehouse/FPS stock
positions, fleet utilisation, closure-check state. Every number returned is
read from the database at request time; anything the database cannot answer
comes back as None so callers render DATA UNAVAILABLE.
"""
from __future__ import annotations

from backend.services.beneficiary import num, one, rows
from backend.services import demand as demand_svc
from backend.services.manifest import MY_MANIFEST_PREFIX


def _pct(numer: float | None, denom: float | None) -> float | None:
    if numer is None or not denom:
        return None
    return round(numer / denom * 100, 1)


def forecast_signals(conn, cycle: str) -> list[dict]:
    """Intent vs Forecast and Forecast vs Baseline per FPS+commodity.

    Reuses demand.demand_table (real aggregation + deterministic baseline +
    persisted forecast). Formulae are labelled exactly:
        Intent - Forecast = Difference
        Forecast - Baseline = Difference
    """
    persisted = demand_svc.read_forecast(conn, cycle)
    table = demand_svc.demand_table(conn, cycle, persisted)
    meta = {r["fps_id"] + ":" + r["commodity"]: r for r in rows(
        conn, "SELECT fps_id, commodity, model_version, training_dataset_version,"
        " prediction_generated_at FROM demand_forecast WHERE cycle = %s", (cycle,))}
    out = []
    for r in table:
        m = meta.get(r["fps_id"] + ":" + r["commodity"], {})
        gen = m.get("prediction_generated_at")
        out.append({
            "fps_id": r["fps_id"], "commodity": r["commodity"],
            "intent_kg": r["intent_demand_kg"], "intent_count": r["intent_count"],
            "baseline_kg": r["baseline_demand_kg"],
            "baseline_cycles_used": r["baseline_cycles_used"],
            "forecast_kg": r["forecast_demand_kg"],
            "intent_minus_forecast_kg": r.get("intent_minus_forecast_kg"),
            "intent_minus_forecast_pct": _pct(r.get("intent_minus_forecast_kg"), r["forecast_demand_kg"]),
            "forecast_minus_baseline_kg": r.get("forecast_minus_baseline_kg"),
            "forecast_minus_baseline_pct": _pct(r.get("forecast_minus_baseline_kg"), r["baseline_demand_kg"]),
            "model_version": m.get("model_version"),
            "dataset_version": m.get("training_dataset_version"),
            "forecast_generated_at": gen.isoformat() if gen else None,
            # confidence lives on the ai_predictions envelope, not on demand_forecast
            # by design (see demand.read_forecast) -> explicitly unavailable here.
            "confidence": None,
        })
    return out


def stock_positions(conn, cycle: str) -> dict:
    """Warehouse stock vs committed allocations; FPS inventory snapshots."""
    warehouses = rows(conn, "SELECT warehouse_id, warehouse_name, rice_stock_kg, wheat_stock_kg,"
                            " total_capacity_kg, status FROM warehouses ORDER BY warehouse_id")
    committed = {}
    for r in rows(conn, "SELECT warehouse_id, commodity, COALESCE(sum(allocated_kg),0) AS kg"
                        " FROM allocations WHERE cycle = %s GROUP BY warehouse_id, commodity", (cycle,)):
        committed[(r["warehouse_id"], r["commodity"])] = num(r["kg"])
    wh = []
    for w in warehouses:
        rice_c = committed.get((w["warehouse_id"], "RICE"), 0)
        wheat_c = committed.get((w["warehouse_id"], "WHEAT"), 0)
        wh.append({**w,
                   "rice_stock_kg": num(w["rice_stock_kg"]), "wheat_stock_kg": num(w["wheat_stock_kg"]),
                   "rice_committed_kg": rice_c, "wheat_committed_kg": wheat_c,
                   "rice_remaining_kg": round(num(w["rice_stock_kg"]) - rice_c, 1),
                   "wheat_remaining_kg": round(num(w["wheat_stock_kg"]) - wheat_c, 1)})
    fps_inv = rows(conn, "SELECT location_id AS fps_id, commodity, closing_stock_kg, cycle"
                         " FROM inventory WHERE location_type='FPS' AND cycle = %s", (cycle,))
    incoming = {}
    for r in rows(conn, f"""SELECT mi.fps_id, mi.commodity, COALESCE(sum(mi.planned_kg),0) AS kg
                            FROM dispatch_manifest_items mi JOIN dispatch_manifests m USING (manifest_id)
                            WHERE m.cycle = %s AND m.manifest_id LIKE '{MY_MANIFEST_PREFIX}%%'
                              AND m.manifest_status IN ('LOCKED','DISPATCHED','DELIVERED')
                            GROUP BY mi.fps_id, mi.commodity""", (cycle,)):
        incoming[(r["fps_id"], r["commodity"])] = num(r["kg"])
    return {"warehouses": wh, "fps_inventory": fps_inv, "incoming_dispatch": {
        f"{k[0]}:{k[1]}": v for k, v in incoming.items()}}


def allocation_records(conn, cycle: str) -> list[dict]:
    """Allocations joined to constraint findings (exceptions) and override audit."""
    allocs = rows(conn, """SELECT allocation_id, fps_id, commodity, requested_kg, allocated_kg,
                                  warehouse_id, status, source, approved_by, approved_at
                           FROM allocations WHERE cycle = %s ORDER BY fps_id, commodity""", (cycle,))
    exc = rows(conn, """SELECT entity_id, rule_code, severity, reason, status, detected_at
                        FROM exceptions WHERE cycle = %s AND entity_type = 'ALLOCATION'""", (cycle,))
    by_entity: dict[str, list] = {}
    for e in exc:
        by_entity.setdefault(e["entity_id"], []).append(e)
    overrides = {}
    for r in rows(conn, """SELECT entity_id, reason, before_state, after_state, actor_user_id, timestamp
                           FROM audit_events WHERE cycle = %s AND action = 'ALLOCATION_OVERRIDDEN'
                           ORDER BY timestamp""", (cycle,)):
        overrides[r["entity_id"]] = r
    out = []
    for a in allocs:
        key = f"{a['fps_id']}:{a['commodity']}"
        out.append({**a, "requested_kg": num(a["requested_kg"]), "allocated_kg": num(a["allocated_kg"]),
                    "gates": by_entity.get(key, []), "override": overrides.get(a["allocation_id"])})
    return out


def fleet_signals(conn, cycle: str) -> dict:
    """Vehicle capacity vs assigned load; route legs with geodesic labelling."""
    vehicles = rows(conn, """SELECT v.vehicle_id, v.capacity_kg, v.current_status, v.warehouse_id,
                                    m.manifest_id, m.total_kg AS assigned_kg, m.route_distance_km,
                                    m.manifest_status
                             FROM vehicles v LEFT JOIN dispatch_manifests m
                               ON m.vehicle_id = v.vehicle_id AND m.cycle = %s
                               AND m.manifest_id LIKE '""" + MY_MANIFEST_PREFIX + """%%'
                             ORDER BY v.vehicle_id""", (cycle,))
    fleet = []
    for v in vehicles:
        cap, load = num(v["capacity_kg"]), num(v["assigned_kg"])
        fleet.append({**v, "utilisation_pct": round(100 * load / cap, 1) if cap and load else None,
                      "overloaded": bool(cap and load and load > cap),
                      "distance_basis": "GEODESIC DISTANCE — NOT ROAD DISTANCE"})
    routes = rows(conn, f"""SELECT r.manifest_id, r.vehicle_id, r.fps_id, r.stop_sequence,
                                   r.distance_from_previous_km, r.eta_minutes
                            FROM vehicle_routes r JOIN dispatch_manifests m USING (manifest_id)
                            WHERE m.cycle = %s AND m.manifest_id LIKE '{MY_MANIFEST_PREFIX}%%'
                            ORDER BY r.manifest_id, r.stop_sequence""", (cycle,))
    for r in routes:
        r["distance_basis"] = "GEODESIC DISTANCE — NOT ROAD DISTANCE"
    return {"vehicles": fleet, "routes": routes}


def mass_balance(conn, cycle: str) -> list[dict]:
    """ALLOCATED -> DISPATCHED -> RECEIVED per FPS+commodity. Never infers a missing leg."""
    alloc = {(r["fps_id"], r["commodity"]): num(r["allocated_kg"]) for r in rows(
        conn, "SELECT fps_id, commodity, allocated_kg FROM allocations WHERE cycle = %s", (cycle,))}
    planned = {}
    for r in rows(conn, f"""SELECT mi.fps_id, mi.commodity, COALESCE(sum(mi.planned_kg),0) AS kg
                            FROM dispatch_manifest_items mi JOIN dispatch_manifests m USING (manifest_id)
                            WHERE m.cycle = %s AND m.manifest_id LIKE '{MY_MANIFEST_PREFIX}%%'
                            GROUP BY mi.fps_id, mi.commodity""", (cycle,)):
        planned[(r["fps_id"], r["commodity"])] = num(r["kg"])
    received = {}
    for r in rows(conn, f"""SELECT d.fps_id, mi.commodity, COALESCE(sum(d.delivered_kg),0) AS kg,
                                   count(*) FILTER (WHERE d.status='VARIANCE') AS variance,
                                   count(*) FILTER (WHERE d.status='REJECTED') AS rejected
                            FROM delivery_history d JOIN dispatch_manifest_items mi USING (manifest_item_id)
                            JOIN dispatch_manifests m ON m.manifest_id = d.manifest_id
                            WHERE m.cycle = %s AND m.manifest_id LIKE '{MY_MANIFEST_PREFIX}%%'
                            GROUP BY d.fps_id, mi.commodity""", (cycle,)):
        received[(r["fps_id"], r["commodity"])] = {
            "kg": num(r["kg"]), "variance": r["variance"], "rejected": r["rejected"]}
    keys = set(alloc) | set(planned) | set(received)
    out = []
    for fps_id, commodity in sorted(keys):
        a, p = alloc.get((fps_id, commodity)), planned.get((fps_id, commodity))
        rec = received.get((fps_id, commodity))
        out.append({"fps_id": fps_id, "commodity": commodity,
                    "allocated_kg": a, "dispatched_kg": p,
                    "received_kg": rec["kg"] if rec else None,
                    "allocated_minus_dispatched": round(a - p, 1) if a is not None and p is not None else None,
                    "dispatched_minus_received": round(p - rec["kg"], 1) if p is not None and rec else None,
                    "delivery_variance_lines": rec["variance"] if rec else 0,
                    "delivery_rejected_lines": rec["rejected"] if rec else 0})
    return out


def beneficiary_context(conn, beneficiary_id: str, cycle: str | None) -> dict | None:
    """Strictly the beneficiary's own records — entitlement, live intent, journey stage."""
    from backend.services import beneficiary as svc
    try:
        profile = svc.get_profile(conn, beneficiary_id)
    except Exception:
        return None
    cyc = svc.get_cycle(conn)
    if cycle is None:
        cycle = cyc["cycle"] if cyc else None
    if cycle is None:
        return {"profile": {"fps_id": profile["fps"]["fps_id"]}, "cycle": None}
    try:
        ent = svc.get_entitlement(conn, beneficiary_id, cycle)
    except Exception:
        ent = None
    intent_row = svc.live_intent(conn, beneficiary_id, cycle)
    try:
        journey = svc.get_journey(conn, beneficiary_id, cycle)
    except Exception:
        journey = {"headline": None}
    return {"profile": profile, "cycle": cycle, "entitlement": ent,
            "intent": intent_row, "stage": (journey or {}).get("headline")}
