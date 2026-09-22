"""Read-only operational overview for the DSO Control Centre UI.

Everything here is a SELECT. No function in this module writes, and none of them participate in the
cycle state machine -- Phase 2's demand/allocation/routing/manifest/tracking services own all of that and
are deliberately left untouched (they are a frozen contract; this module consumes them).

It exists because the control-centre UI needs aggregates and lists that the Phase 2 action endpoints
never had a reason to expose: fleet status, recorded deliveries, telemetry, the closure gate *before* it
is committed, and one cheap summary instead of the UI pulling four 1200-row payloads to count things.

Scoping rule (the lesson Slices 1-5 each learned the hard way): the seeded dataset ships a full synthetic
history for every cycle, so anything that means "what this live workflow produced" filters on the "MFO-"
manifest prefix or on this workflow's own exception entity types, never on cycle alone.
"""
from __future__ import annotations

from backend.services.beneficiary import num, one, rows
from backend.services.manifest import MY_MANIFEST_PREFIX

# exceptions this workflow's own gates raise (allocation.py, routing.py, tracking.py) -- as opposed to
# the seeded dataset's unrelated historical DELIVERY/EPOS/MANIFEST records for the same cycle
LIVE_EXCEPTION_ENTITY_TYPES = ("ALLOCATION", "ROUTING", "CLOSURE")


def _pct_change(current: float | None, baseline: float | None) -> float | None:
    """Percentage change, or None when there is nothing honest to compare against."""
    if current is None or not baseline:
        return None
    return round((current - baseline) / baseline * 100, 1)


def cycle_summary(conn, cycle: str) -> dict:
    """The situation summary behind the control centre hero. Every figure is read from a real table;
    anything the database cannot answer comes back as None so the UI can say so explicitly."""
    c = one(conn, "SELECT cycle, state, locked_at, closed_at FROM cycles WHERE cycle = %s", (cycle,))
    if not c:
        return {}

    intent = one(conn, """SELECT count(*) AS submissions, count(DISTINCT beneficiary_id) AS beneficiaries,
                                 COALESCE(sum(total_quantity_kg), 0) AS kg
                          FROM intent_signals WHERE cycle = %s AND status = 'SUBMITTED'""", (cycle,))
    eligible = one(conn, "SELECT count(*) AS n FROM beneficiaries WHERE status = 'ACTIVE'")["n"]

    forecast = one(conn, """SELECT COALESCE(sum(forecast_demand_kg), 0) AS forecast_kg,
                                   COALESCE(sum(baseline_demand_kg), 0) AS baseline_kg, count(*) AS rows
                            FROM demand_forecast WHERE cycle = %s""", (cycle,))

    lock = one(conn, "SELECT sha256_hash, locked_at, locked_by FROM demand_locks WHERE cycle = %s", (cycle,))

    alloc = one(conn, """SELECT count(*) AS rows, COALESCE(sum(allocated_kg), 0) AS allocated_kg,
                                count(*) FILTER (WHERE status = 'BLOCKED') AS blocked,
                                count(*) FILTER (WHERE status = 'APPROVED') AS approved,
                                count(*) FILTER (WHERE source = 'DSO_OVERRIDE') AS overridden
                         FROM allocations WHERE cycle = %s""", (cycle,))

    sev = {r["severity"]: r["n"] for r in rows(conn, f"""
        SELECT severity, count(*) AS n FROM exceptions
        WHERE cycle = %s AND status = 'OPEN' AND entity_type = ANY(%s) GROUP BY severity""",
        (cycle, list(LIVE_EXCEPTION_ENTITY_TYPES)))}

    manifests = {r["manifest_status"]: r["n"] for r in rows(conn, f"""
        SELECT manifest_status, count(*) AS n FROM dispatch_manifests
        WHERE cycle = %s AND manifest_id LIKE '{MY_MANIFEST_PREFIX}%%' GROUP BY manifest_status""", (cycle,))}
    manifest_totals = one(conn, f"""SELECT count(*) AS n, COALESCE(sum(total_kg), 0) AS kg,
                                           COALESCE(sum(route_distance_km), 0) AS km
                                    FROM dispatch_manifests
                                    WHERE cycle = %s AND manifest_id LIKE '{MY_MANIFEST_PREFIX}%%'""", (cycle,))

    fleet = {r["current_status"]: r["n"] for r in rows(conn, "SELECT current_status, count(*) AS n FROM vehicles GROUP BY current_status")}
    fleet_total = one(conn, "SELECT count(*) AS n FROM vehicles")["n"]

    active_fps = one(conn, "SELECT count(*) AS n FROM fps WHERE status = 'ACTIVE'")["n"]
    covered_fps = one(conn, "SELECT count(DISTINCT fps_id) AS n FROM allocations WHERE cycle = %s AND status = 'APPROVED'", (cycle,))["n"]

    delivered = one(conn, f"""SELECT count(*) AS rows, COALESCE(sum(delivered_kg), 0) AS delivered_kg,
                                     count(*) FILTER (WHERE status = 'VARIANCE') AS variance,
                                     count(*) FILTER (WHERE status = 'REJECTED') AS rejected
                              FROM delivery_history WHERE manifest_id IN
                                (SELECT manifest_id FROM dispatch_manifests
                                 WHERE cycle = %s AND manifest_id LIKE '{MY_MANIFEST_PREFIX}%%')""", (cycle,))

    intent_kg = num(intent["kg"])
    forecast_kg = num(forecast["forecast_kg"]) if forecast["rows"] else None
    baseline_kg = num(forecast["baseline_kg"]) if forecast["rows"] else None

    return {
        "cycle": c["cycle"], "state": c["state"],
        "locked_at": c["locked_at"].isoformat() if c["locked_at"] else None,
        "closed_at": c["closed_at"].isoformat() if c["closed_at"] else None,
        "intent": {"submissions": intent["submissions"], "beneficiaries": intent["beneficiaries"], "kg": intent_kg,
                   "eligible_beneficiaries": eligible,
                   "participation_pct": round(100 * intent["beneficiaries"] / eligible, 2) if eligible else None},
        "forecast": {"kg": forecast_kg, "baseline_kg": baseline_kg, "generated": forecast["rows"] > 0,
                     "vs_baseline_pct": _pct_change(forecast_kg, baseline_kg),
                     "intent_vs_forecast_kg": round(intent_kg - forecast_kg, 1) if forecast_kg is not None else None},
        "demand_lock": {"locked": lock is not None, "sha256_hash": lock["sha256_hash"] if lock else None,
                        "locked_at": lock["locked_at"].isoformat() if lock else None,
                        "locked_by": lock["locked_by"] if lock else None},
        "allocation": {"rows": alloc["rows"], "allocated_kg": num(alloc["allocated_kg"]), "approved": alloc["approved"],
                       "blocked": alloc["blocked"], "overridden": alloc["overridden"]},
        "exceptions": {"critical": sev.get("HIGH", 0), "medium": sev.get("MEDIUM", 0), "low": sev.get("LOW", 0),
                       "open_total": sum(sev.values())},
        "manifests": {"by_status": manifests, "count": manifest_totals["n"], "total_kg": num(manifest_totals["kg"]),
                      "route_km": num(manifest_totals["km"])},
        "fleet": {"by_status": fleet, "total": fleet_total, "available": fleet.get("AVAILABLE", 0)},
        "coverage": {"active_fps": active_fps, "fps_with_approved_allocation": covered_fps,
                     "pct": round(100 * covered_fps / active_fps, 1) if active_fps else None},
        "delivery": {"records": delivered["rows"], "delivered_kg": num(delivered["delivered_kg"]),
                     "variance": delivered["variance"], "rejected": delivered["rejected"]},
    }


def fleet_status(conn, cycle: str) -> dict:
    """Every vehicle, its warehouse, and what this cycle's routing assigned it (if anything)."""
    vehicles = rows(conn, f"""
        SELECT v.vehicle_id, v.vehicle_number, v.vehicle_type, v.capacity_kg, v.current_status, v.warehouse_id,
               v.latitude, v.longitude,
               m.manifest_id, m.manifest_status, m.total_kg AS assigned_kg, m.route_distance_km
        FROM vehicles v
        LEFT JOIN dispatch_manifests m
          ON m.vehicle_id = v.vehicle_id AND m.cycle = %s AND m.manifest_id LIKE '{MY_MANIFEST_PREFIX}%%'
        ORDER BY v.warehouse_id, v.vehicle_id""", (cycle,))
    for v in vehicles:
        cap, load = num(v["capacity_kg"]), num(v["assigned_kg"])
        v["utilisation_pct"] = round(100 * load / cap, 1) if cap and load else None
    assigned = [v for v in vehicles if v["manifest_id"]]
    return {
        "cycle": cycle, "vehicles": vehicles,
        "totals": {
            "fleet_size": len(vehicles),
            "available": sum(1 for v in vehicles if v["current_status"] == "AVAILABLE"),
            "assigned_this_cycle": len(assigned),
            "fleet_capacity_kg": round(sum(num(v["capacity_kg"]) or 0 for v in vehicles), 1),
            "assigned_load_kg": round(sum(num(v["assigned_kg"]) or 0 for v in assigned), 1),
        },
    }


def deliveries(conn, cycle: str) -> list[dict]:
    """Recorded deliveries for this workflow's manifests: planned vs delivered, per FPS+commodity."""
    return rows(conn, f"""
        SELECT d.delivery_id, d.manifest_id, d.fps_id, d.vehicle_id, d.planned_kg, d.delivered_kg,
               d.delivery_date, d.status, d.verified_by, mi.commodity, mi.allocation_id,
               (d.delivered_kg - d.planned_kg) AS variance_kg
        FROM delivery_history d
        JOIN dispatch_manifest_items mi ON mi.manifest_item_id = d.manifest_item_id
        WHERE d.manifest_id IN (SELECT manifest_id FROM dispatch_manifests
                                WHERE cycle = %s AND manifest_id LIKE '{MY_MANIFEST_PREFIX}%%')
        ORDER BY d.delivery_date DESC, d.fps_id""", (cycle,))


def telemetry(conn, cycle: str) -> list[dict]:
    """Telemetry points recorded against this workflow's manifests. Often sparse or absent -- the caller
    must say so rather than inventing a position (the dataset's telemetry is ~12% gappy by design)."""
    return rows(conn, f"""
        SELECT t.telemetry_id, t.vehicle_id, t.timestamp, t.latitude, t.longitude, t.speed_kmph, t.status,
               t.manifest_id
        FROM vehicle_telemetry t
        WHERE t.manifest_id IN (SELECT manifest_id FROM dispatch_manifests
                                WHERE cycle = %s AND manifest_id LIKE '{MY_MANIFEST_PREFIX}%%')
        ORDER BY t.timestamp DESC""", (cycle,))


def planned_routes(conn, cycle: str) -> list[dict]:
    """Planned stops for this workflow's manifests -- the route as optimised, distinct from where a
    vehicle actually is (telemetry)."""
    return rows(conn, f"""
        SELECT r.manifest_id, r.vehicle_id, r.warehouse_id, r.stop_sequence, r.fps_id, r.latitude, r.longitude,
               r.distance_from_previous_km, r.eta_minutes, r.route_status
        FROM vehicle_routes r
        WHERE r.manifest_id IN (SELECT manifest_id FROM dispatch_manifests
                                WHERE cycle = %s AND manifest_id LIKE '{MY_MANIFEST_PREFIX}%%')
        ORDER BY r.manifest_id, r.stop_sequence""", (cycle,))
