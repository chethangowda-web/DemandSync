"""Delivery tracking and cycle closure for the DSO: AUTHORIZED -> TRACKING -> DELIVERING -> RECONCILING ->
AUDITING -> CLOSED. See docs/AI_ARCHITECTURE.md / the Phase 2 plan's Slice 5.

Scoped to this workflow's own manifests (the "MFO-" prefix from routing.py/manifest.py) throughout, for
the same reason Slices 1-4 all needed it: the seeded dataset already ships a full delivery_history for
every historical cycle, entirely unrelated to what this live workflow is tracking.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from backend.core.audit import verify_chain
from backend.core.errors import ApiError
from backend.services.beneficiary import num, one, rows
from backend.services.manifest import MY_MANIFEST_PREFIX, _canonical_manifest, manifest_hash

DELIVERY_VARIANCE_TOLERANCE_PCT = 5  # within this of planned_kg counts as VERIFIED, not VARIANCE


def dispatch_cycle(conn, cycle: str, officer_id: str) -> dict:
    """AUTHORIZED -> TRACKING. Every LOCKED manifest this workflow produced is marked DISPATCHED, its
    vehicle moves to IN_TRANSIT, and an initial telemetry point is dropped at its warehouse."""
    c = one(conn, "SELECT state FROM cycles WHERE cycle = %s FOR UPDATE", (cycle,))
    if not c:
        raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
    if c["state"] == "TRACKING":
        raise ApiError(409, "CYCLE_ALREADY_DISPATCHED", f"Cycle {cycle} has already been dispatched.")
    if c["state"] != "AUTHORIZED":
        raise ApiError(409, "CYCLE_NOT_AUTHORIZED", f"Cycle {cycle} is {c['state']}, not AUTHORIZED. It cannot be dispatched.",
                       {"state": c["state"]})

    manifests = rows(conn, f"""SELECT manifest_id, vehicle_id, warehouse_id FROM dispatch_manifests
                               WHERE cycle = %s AND manifest_status = 'LOCKED' AND manifest_id LIKE '{MY_MANIFEST_PREFIX}%%'""", (cycle,))
    now = datetime.now(timezone.utc)
    with conn.transaction():
        for m in manifests:
            conn.execute("UPDATE dispatch_manifests SET manifest_status = 'DISPATCHED' WHERE manifest_id = %s", (m["manifest_id"],))
            conn.execute("UPDATE vehicles SET current_status = 'IN_TRANSIT' WHERE vehicle_id = %s", (m["vehicle_id"],))
            wh = one(conn, "SELECT latitude, longitude FROM warehouses WHERE warehouse_id = %s", (m["warehouse_id"],))
            conn.execute(
                """INSERT INTO vehicle_telemetry (telemetry_id, vehicle_id, timestamp, latitude, longitude, speed_kmph, status, manifest_id)
                   VALUES (%s, %s, %s, %s, %s, 0, 'DEPARTED', %s)""",
                ("TEL-" + uuid.uuid4().hex[:12].upper(), m["vehicle_id"], now, wh["latitude"] if wh else None,
                 wh["longitude"] if wh else None, m["manifest_id"]))
        conn.execute("UPDATE cycles SET state = 'TRACKING' WHERE cycle = %s", (cycle,))
    return {"cycle": cycle, "state": "TRACKING", "manifests_dispatched": len(manifests)}


def record_delivery(conn, manifest_id: str, officer_id: str, items: list[dict]) -> dict:
    """DISPATCHED -> DELIVERED for one manifest. `items` are the DSO/field inspector's actually observed
    delivered_kg per FPS+commodity -- never inferred or assumed equal to what was planned. The cycle
    itself advances TRACKING -> DELIVERING the first time any delivery is recorded."""
    m = one(conn, "SELECT manifest_id, cycle, vehicle_id, manifest_status FROM dispatch_manifests WHERE manifest_id = %s FOR UPDATE", (manifest_id,))
    if not m:
        raise ApiError(404, "MANIFEST_NOT_FOUND", f"No manifest {manifest_id}.")
    if not m["manifest_id"].startswith(MY_MANIFEST_PREFIX):
        raise ApiError(422, "NOT_A_LIVE_MANIFEST", f"{manifest_id} is historical seed data, not a manifest this workflow produced.")
    if m["manifest_status"] != "DISPATCHED":
        raise ApiError(409, "MANIFEST_NOT_DISPATCHED", f"Manifest {manifest_id} is {m['manifest_status']}, not DISPATCHED.",
                       {"manifest_status": m["manifest_status"]})

    plan_items = rows(conn, """SELECT manifest_item_id, fps_id, commodity, planned_kg FROM dispatch_manifest_items
                               WHERE manifest_id = %s""", (manifest_id,))
    by_key = {(i["fps_id"], i["commodity"]): i for i in plan_items}
    if not items:
        raise ApiError(422, "NO_DELIVERY_ITEMS", "At least one delivered item is required.")

    now = datetime.now(timezone.utc)
    recorded = []
    with conn.transaction():
        for it in items:
            key = (it.get("fps_id"), it.get("commodity"))
            plan = by_key.get(key)
            if not plan:
                raise ApiError(422, "UNKNOWN_MANIFEST_ITEM", f"{key[0]}/{key[1]} is not on manifest {manifest_id}.")
            delivered = num(it.get("delivered_kg"))
            if delivered is None or delivered < 0:
                raise ApiError(422, "INVALID_QUANTITY", f"delivered_kg for {key[0]}/{key[1]} must be a non-negative number.")
            planned = num(plan["planned_kg"])
            variance_pct = (abs(delivered - planned) / planned * 100) if planned else (100 if delivered else 0)
            status = "REJECTED" if delivered == 0 and planned > 0 else (
                "VERIFIED" if variance_pct <= DELIVERY_VARIANCE_TOLERANCE_PCT else "VARIANCE")
            conn.execute(
                """INSERT INTO delivery_history (delivery_id, manifest_id, manifest_item_id, fps_id, vehicle_id,
                       planned_kg, delivered_kg, delivery_date, rice_kg, wheat_kg, status, verified_by)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                ("DLV-" + uuid.uuid4().hex[:12].upper(), manifest_id, plan["manifest_item_id"], key[0], m["vehicle_id"],
                 planned, delivered, now, delivered if key[1] == "RICE" else 0, delivered if key[1] == "WHEAT" else 0,
                 status, officer_id))
            recorded.append({"fps_id": key[0], "commodity": key[1], "planned_kg": planned, "delivered_kg": delivered, "status": status})
        conn.execute("UPDATE dispatch_manifests SET manifest_status = 'DELIVERED' WHERE manifest_id = %s", (manifest_id,))
        conn.execute("UPDATE vehicles SET current_status = 'DELIVERED' WHERE vehicle_id = %s", (m["vehicle_id"],))
        conn.execute(
            """INSERT INTO vehicle_telemetry (telemetry_id, vehicle_id, timestamp, status, manifest_id)
               VALUES (%s, %s, %s, 'ARRIVED', %s)""",
            ("TEL-" + uuid.uuid4().hex[:12].upper(), m["vehicle_id"], now, manifest_id))
        c = one(conn, "SELECT state FROM cycles WHERE cycle = %s", (m["cycle"],))
        if c["state"] == "TRACKING":
            conn.execute("UPDATE cycles SET state = 'DELIVERING' WHERE cycle = %s", (m["cycle"],))
    return {"manifest_id": manifest_id, "manifest_status": "DELIVERED", "items": recorded}


# ------------------------------------------------------------------ reconciliation: the 7 closure checks

def run_closure_checks(conn, cycle: str) -> dict[str, bool]:
    my_manifests = rows(conn, f"""SELECT manifest_id, manifest_status, sha256_hash FROM dispatch_manifests
                                  WHERE cycle = %s AND manifest_id LIKE '{MY_MANIFEST_PREFIX}%%'""", (cycle,))
    checks: dict[str, bool] = {}

    # 1. every manifest this workflow produced has actually been delivered
    checks["ALL_MANIFESTS_DELIVERED"] = bool(my_manifests) and all(m["manifest_status"] == "DELIVERED" for m in my_manifests)

    deliveries = rows(conn, f"""SELECT status FROM delivery_history WHERE manifest_id IN
                                (SELECT manifest_id FROM dispatch_manifests WHERE cycle = %s AND manifest_id LIKE '{MY_MANIFEST_PREFIX}%%')""", (cycle,))
    # 2. no delivery was outright rejected
    checks["NO_REJECTED_DELIVERIES"] = not any(d["status"] == "REJECTED" for d in deliveries)
    # 3. every recorded delivery is within tolerance of what was planned
    checks["DELIVERIES_WITHIN_TOLERANCE"] = not any(d["status"] == "VARIANCE" for d in deliveries)

    # 4. what was allocated per FPS+commodity is what was actually delivered, in aggregate
    mismatch = one(conn, f"""
        SELECT count(*) AS n FROM (
          SELECT a.allocation_id, a.allocated_kg, COALESCE(sum(dh.delivered_kg), 0) AS delivered
          FROM allocations a
          JOIN dispatch_manifest_items mi ON mi.allocation_id = a.allocation_id
          JOIN dispatch_manifests m ON m.manifest_id = mi.manifest_id AND m.manifest_id LIKE '{MY_MANIFEST_PREFIX}%%'
          LEFT JOIN delivery_history dh ON dh.manifest_item_id = mi.manifest_item_id
          WHERE a.cycle = %s
          GROUP BY a.allocation_id, a.allocated_kg
        ) t WHERE abs(t.delivered - t.allocated_kg) > GREATEST(t.allocated_kg * 0.05, 1)""", (cycle,))
    checks["ALLOCATION_MATCHES_DELIVERY"] = (mismatch["n"] if mismatch else 0) == 0

    # 5. the append-only audit hash chain is intact (the same check core/audit.py:verify_chain performs)
    checks["AUDIT_CHAIN_INTACT"] = verify_chain()["intact"]

    # 6. every sealed manifest's stored hash still matches its (immutable, trigger-protected) content
    all_hashes_ok = True
    for m in my_manifests:
        if m["sha256_hash"]:
            if manifest_hash(_canonical_manifest(conn, m["manifest_id"])) != m["sha256_hash"]:
                all_hashes_ok = False
                break
    checks["MANIFEST_HASHES_VERIFIED"] = all_hashes_ok

    # 7. no unresolved HIGH-severity exception remains open for an FPS+commodity actually on one of this
    # workflow's manifests. A suspended FPS that was never routed this round (see routing.py) still has an
    # OPEN ROUTE_NOT_FEASIBLE exception, correctly -- but it was never part of this delivery, so it can't
    # block reconciling the deliveries that did happen. Scoped by entity_id, not "any exception this cycle".
    open_high = one(conn, f"""SELECT count(*) AS n FROM exceptions e
                             WHERE e.cycle = %s AND e.severity = 'HIGH' AND e.status = 'OPEN'
                               AND e.entity_type IN ('ALLOCATION', 'ROUTING')
                               AND e.entity_id IN (
                                 SELECT mi.fps_id || ':' || mi.commodity FROM dispatch_manifest_items mi
                                 JOIN dispatch_manifests m ON m.manifest_id = mi.manifest_id
                                 WHERE m.cycle = %s AND m.manifest_id LIKE '{MY_MANIFEST_PREFIX}%%')""",
                    (cycle, cycle))["n"]
    checks["NO_OPEN_BLOCKING_EXCEPTIONS"] = open_high == 0

    return checks


def reconcile_cycle(conn, cycle: str, officer_id: str) -> dict:
    """DELIVERING -> AUDITING if all 7 checks pass, else -> RECONCILING with a HIGH exception per failed
    check, for the DSO to investigate before reconciling again."""
    c = one(conn, "SELECT state FROM cycles WHERE cycle = %s FOR UPDATE", (cycle,))
    if not c:
        raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
    if c["state"] not in ("DELIVERING", "RECONCILING"):
        raise ApiError(409, "CYCLE_NOT_DELIVERING", f"Cycle {cycle} is {c['state']}; it must be DELIVERING (or already RECONCILING) to reconcile.",
                       {"state": c["state"]})

    checks = run_closure_checks(conn, cycle)
    passed = all(checks.values())
    now = datetime.now(timezone.utc)
    new_state = "AUDITING" if passed else "RECONCILING"
    with conn.transaction():
        if not passed:
            for name, ok in checks.items():
                if not ok:
                    conn.execute(
                        """INSERT INTO exceptions (exception_id, cycle, entity_type, entity_id, rule_code, severity,
                               reason, detected_at, assigned_to, status)
                           VALUES (%s, %s, 'CLOSURE', %s, %s, 'HIGH', %s, %s, %s, 'OPEN')""",
                        ("EXC-" + uuid.uuid4().hex[:12].upper(), cycle, cycle, name,
                         f"Closure check {name} failed during reconciliation.", now, officer_id))
        conn.execute("UPDATE cycles SET state = %s WHERE cycle = %s", (new_state, cycle))
    return {"cycle": cycle, "state": new_state, "checks": checks, "passed": passed}


def close_cycle(conn, cycle: str, officer_id: str) -> dict:
    """AUDITING -> CLOSED. Only reachable once reconcile_cycle has actually passed every check."""
    c = one(conn, "SELECT state FROM cycles WHERE cycle = %s FOR UPDATE", (cycle,))
    if not c:
        raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
    if c["state"] == "CLOSED":
        raise ApiError(409, "CYCLE_ALREADY_CLOSED", f"Cycle {cycle} is already closed.")
    if c["state"] != "AUDITING":
        raise ApiError(409, "CYCLE_NOT_AUDITING", f"Cycle {cycle} is {c['state']}, not AUDITING. Reconcile it successfully first.",
                       {"state": c["state"]})
    with conn.transaction():
        conn.execute("UPDATE cycles SET state = 'CLOSED', closed_at = now() WHERE cycle = %s", (cycle,))
    return {"cycle": cycle, "state": "CLOSED"}
