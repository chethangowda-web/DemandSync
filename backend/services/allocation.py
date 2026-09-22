"""Allocation engine for the DSO: LOCKED -> ALLOCATED. See docs/AI_ARCHITECTURE.md / the constraint gates.

Rules never allocate, they only validate; the engine proposes a clamped allocation from the locked demand
and flags what it had to clamp as an exception. A human (the DSO) decides what to do with an exception —
either accept the clamp or override it, always with a reason, always audited with before/after values.

The prior backend/services/constraints/engine.py prototype defined the 6 gates this reuses conceptually
(Demand<=Allocation, FPS Capacity, Truck Capacity, Stock, Route feasible, NFSA entitlement floor), but was
never wired to the database (dict params, no persistence). This module is the real, DB-integrated version;
that prototype is left in place unreferenced, as a design note, not duplicated logic.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from backend.core.errors import ApiError
from backend.services.beneficiary import num, one, rows
from backend.services.demand import COMMODITIES, get_lock

# rule codes, one per gate -------------------------------------------------
GATE_DEMAND_EXCEEDS_CAPACITY = "FPS_CAPACITY_EXCEEDED"
GATE_WAREHOUSE_STOCK = "WAREHOUSE_STOCK_SHORTFALL"
GATE_TRUCK_CAPACITY = "WAREHOUSE_TRUCK_CAPACITY_SHORTFALL"
GATE_ROUTE_FEASIBLE = "ROUTE_NOT_FEASIBLE"
GATE_ENTITLEMENT_FLOOR = "BELOW_NFSA_ENTITLEMENT_FLOOR"
GATE_DEMAND_VS_ALLOCATION = "ALLOCATION_BELOW_DEMAND"

_COMMODITY_STOCK_COL = {"RICE": "rice_stock_kg", "WHEAT": "wheat_stock_kg"}


def _locked_demand_by_fps(conn, cycle: str) -> dict[tuple[str, str], float]:
    """The frozen, hashed demand_locks snapshot — never re-read live intent past LOCKED."""
    lock = get_lock(conn, cycle)
    if lock is None:
        raise ApiError(409, "CYCLE_NOT_LOCKED", f"Cycle {cycle} has not been demand-locked yet.")
    out: dict[tuple[str, str], float] = {}
    for fps_id, by_commodity in lock["snapshot"]["demand_by_fps"].items():
        for commodity, kg in by_commodity.items():
            out[(fps_id, commodity)] = num(kg)
    return out


def _fps_meta(conn) -> dict[str, dict]:
    return {r["fps_id"]: r for r in rows(conn, "SELECT fps_id, capacity_kg, warehouse_id, status, latitude, longitude FROM fps")}


def _warehouse_meta(conn) -> dict[str, dict]:
    return {r["warehouse_id"]: r for r in rows(
        conn, "SELECT warehouse_id, rice_stock_kg, wheat_stock_kg, total_capacity_kg, status, latitude, longitude FROM warehouses")}


def _truck_capacity_by_warehouse(conn) -> dict[str, float]:
    """Sum of capacity of vehicles based at each warehouse — the truck-capacity gate proxy until Slice 3's
    OR-Tools routing assigns specific vehicles to specific manifests."""
    out: dict[str, float] = {}
    for r in rows(conn, "SELECT warehouse_id, sum(capacity_kg) AS cap FROM vehicles WHERE current_status != 'OUT_OF_SERVICE' GROUP BY warehouse_id"):
        out[r["warehouse_id"]] = num(r["cap"])
    return out


def _entitlement_floor(conn, cycle: str) -> dict[tuple[str, str], float]:
    """Sum of active beneficiaries' entitlement per FPS+commodity: the legal floor NFSA sets. Never allocate below it."""
    out: dict[tuple[str, str], float] = {}
    for r in rows(conn, """
            SELECT current_fps_id AS fps_id, 'RICE' AS commodity, sum(rice_entitlement_kg) AS kg
            FROM beneficiaries WHERE status = 'ACTIVE' GROUP BY current_fps_id
            UNION ALL
            SELECT current_fps_id AS fps_id, 'WHEAT' AS commodity, sum(wheat_entitlement_kg) AS kg
            FROM beneficiaries WHERE status = 'ACTIVE' GROUP BY current_fps_id"""):
        out[(r["fps_id"], r["commodity"])] = num(r["kg"]) or 0
    return out


def run_constraint_checks(conn, cycle: str) -> dict:
    """The 6-gate engine over the locked demand. Read-only: computes what *would* be clamped/flagged, does
    not write allocations or exceptions itself (allocate() does, so both stay in the same transaction)."""
    demand = _locked_demand_by_fps(conn, cycle)
    fps = _fps_meta(conn)
    warehouses = _warehouse_meta(conn)
    truck_cap = _truck_capacity_by_warehouse(conn)
    floor = _entitlement_floor(conn, cycle)

    # running totals per warehouse+commodity, to catch stock/truck shortfalls that only show up in aggregate
    warehouse_committed: dict[tuple[str, str], float] = {}
    findings: list[dict] = []
    proposed: dict[tuple[str, str], dict] = {}

    for (fps_id, commodity), demand_kg in sorted(demand.items()):
        f = fps.get(fps_id)
        gates: list[dict] = []

        if f is None or f["status"] != "ACTIVE":
            gates.append({"rule_code": GATE_ROUTE_FEASIBLE, "severity": "HIGH",
                          "reason": f"FPS {fps_id} is not ACTIVE; cannot receive a dispatch."})
        elif f["latitude"] is None or f["longitude"] is None:
            gates.append({"rule_code": GATE_ROUTE_FEASIBLE, "severity": "HIGH",
                          "reason": f"FPS {fps_id} has no coordinates on file; a route cannot be planned to it."})

        # start from locked demand, raised (never lowered) to the legal entitlement floor. Submitted intent
        # is a discretionary request, almost always below full entitlement, so this fires routinely — it is
        # MEDIUM (visible, auto-corrected) unless a physical gate below can't actually deliver the floor,
        # in which case that gate escalates to HIGH and blocks the allocation.
        floor_kg = floor.get((fps_id, commodity), 0)
        allocated_kg = max(demand_kg, floor_kg)
        if demand_kg < floor_kg:
            gates.append({"rule_code": GATE_ENTITLEMENT_FLOOR, "severity": "MEDIUM",
                          "reason": f"Locked demand {demand_kg}kg is below the NFSA entitlement floor {floor_kg}kg "
                                    f"for {fps_id}'s active beneficiaries; raising the proposal to the floor."})

        # physical ceilings clamp downward regardless of the legal floor — a floor a warehouse physically
        # cannot meet is a real operational crisis, flagged HIGH, not something the engine silently resolves
        if f is not None and allocated_kg > f["capacity_kg"]:
            gates.append({"rule_code": GATE_DEMAND_EXCEEDS_CAPACITY, "severity": "HIGH" if demand_kg < floor_kg else "MEDIUM",
                          "reason": f"Proposed {round(allocated_kg, 1)}kg exceeds FPS storage capacity {f['capacity_kg']}kg."})
            allocated_kg = min(allocated_kg, num(f["capacity_kg"]))

        if f is not None:
            wh_id = f["warehouse_id"]
            w = warehouses.get(wh_id)
            stock_col = _COMMODITY_STOCK_COL[commodity]
            key = (wh_id, commodity)
            already = warehouse_committed.get(key, 0)
            if w is not None and already + allocated_kg > w[stock_col]:
                remaining = max(0, w[stock_col] - already)
                gates.append({"rule_code": GATE_WAREHOUSE_STOCK, "severity": "HIGH",
                              "reason": f"Warehouse {wh_id} has {w[stock_col]}kg {commodity} stock; "
                                        f"{already}kg already committed this cycle leaves {remaining}kg, "
                                        f"short of the {round(allocated_kg, 1)}kg needed for {fps_id}."})
                allocated_kg = min(allocated_kg, remaining)
            cap = truck_cap.get(wh_id, 0)
            committed_total = sum(v for (w2, _), v in warehouse_committed.items() if w2 == wh_id) + allocated_kg
            if cap and committed_total > cap:
                gates.append({"rule_code": GATE_TRUCK_CAPACITY, "severity": "MEDIUM",
                              "reason": f"Warehouse {wh_id}'s available vehicle capacity is {cap}kg; "
                                        f"{round(committed_total, 1)}kg would be committed this cycle."})
            warehouse_committed[key] = already + allocated_kg

        if allocated_kg < demand_kg:
            gates.append({"rule_code": GATE_DEMAND_VS_ALLOCATION, "severity": "MEDIUM",
                          "reason": f"Allocated {round(allocated_kg, 1)}kg is below the {demand_kg}kg locked demand "
                                    f"for {fps_id}/{commodity}."})

        proposed[(fps_id, commodity)] = {"demand_kg": demand_kg, "allocated_kg": round(max(0, allocated_kg), 1),
                                         "warehouse_id": f["warehouse_id"] if f else None, "gates": gates}
        for g in gates:
            findings.append({**g, "fps_id": fps_id, "commodity": commodity})

    return {"cycle": cycle, "proposed": proposed, "findings": findings,
            "blocking": sum(1 for x in findings if x["severity"] == "HIGH"),
            "warnings": sum(1 for x in findings if x["severity"] != "HIGH")}


def allocate(conn, cycle: str, officer_id: str) -> dict:
    """LOCKED -> ALLOCATED. Runs the constraint engine and upserts one allocations row per FPS+commodity
    (APPROVED if no HIGH-severity gate fired, else BLOCKED pending DSO override) plus one exceptions row
    per gate finding. The seeded dataset already ships a placeholder allocations row for every cycle
    (like demand_forecast in Slice 1); this overwrites it with the real, constraint-checked proposal
    rather than being blocked by it or duplicating it (migration 0007's unique constraint enforces this).
    Idempotency is keyed on cycle state, not row presence: ALLOCATED means "an allocation round has run",
    not "every exception is resolved" — Slice 3's optimizer is the gate that requires exceptions cleared."""
    c = one(conn, "SELECT state FROM cycles WHERE cycle = %s FOR UPDATE", (cycle,))
    if not c:
        raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
    if c["state"] == "ALLOCATED":
        raise ApiError(409, "CYCLE_ALREADY_ALLOCATED", f"Cycle {cycle} has already been allocated.")
    if c["state"] != "LOCKED":
        raise ApiError(409, "CYCLE_NOT_LOCKED", f"Cycle {cycle} is {c['state']}, not LOCKED. It cannot be allocated.",
                       {"state": c["state"]})

    result = run_constraint_checks(conn, cycle)
    now = datetime.now(timezone.utc)
    with conn.transaction():
        for (fps_id, commodity), p in result["proposed"].items():
            blocked = any(g["severity"] == "HIGH" for g in p["gates"])
            conn.execute(
                """INSERT INTO allocations (allocation_id, cycle, fps_id, commodity, requested_kg, allocated_kg,
                       warehouse_id, status, source, approved_by, approved_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ENGINE', %s, %s)
                   ON CONFLICT (cycle, fps_id, commodity) DO UPDATE SET requested_kg = EXCLUDED.requested_kg,
                       allocated_kg = EXCLUDED.allocated_kg, warehouse_id = EXCLUDED.warehouse_id,
                       status = EXCLUDED.status, source = EXCLUDED.source, approved_by = EXCLUDED.approved_by,
                       approved_at = EXCLUDED.approved_at""",
                ("ALC-" + uuid.uuid4().hex[:12].upper(), cycle, fps_id, commodity, p["demand_kg"], p["allocated_kg"],
                 p["warehouse_id"], "BLOCKED" if blocked else "APPROVED", officer_id, now))
            for g in p["gates"]:
                conn.execute(
                    """INSERT INTO exceptions (exception_id, cycle, entity_type, entity_id, rule_code, severity,
                           reason, detected_at, assigned_to, status)
                       VALUES (%s, %s, 'ALLOCATION', %s, %s, %s, %s, %s, %s, 'OPEN')""",
                    ("EXC-" + uuid.uuid4().hex[:12].upper(), cycle, f"{fps_id}:{commodity}", g["rule_code"],
                     g["severity"], g["reason"], now, officer_id))
        conn.execute("UPDATE cycles SET state = 'ALLOCATED' WHERE cycle = %s", (cycle,))
    # write_audit is deliberately NOT called here: it opens its own connection and audit_events.cycle
    # references cycles(cycle), which this request's `conn` still holds FOR UPDATE until its caller commits.
    # Calling it before that commit is a real deadlock (this request's lock vs write_audit's FK check on
    # it) — audit happens in the API layer, after conn.commit(), matching demand.py's Slice 1 pattern.
    return {"cycle": cycle, "state": "ALLOCATED", "fps_commodity_pairs": len(result["proposed"]),
            "blocking_exceptions": result["blocking"], "warning_exceptions": result["warnings"]}


def list_allocations(conn, cycle: str) -> list[dict]:
    return rows(conn, """SELECT allocation_id, fps_id, commodity, requested_kg, allocated_kg, warehouse_id, status,
                                source, approved_by, approved_at
                         FROM allocations WHERE cycle = %s ORDER BY fps_id, commodity""", (cycle,))


def list_exceptions(conn, cycle: str, status: str | None = None, entity_type: str | None = None) -> list[dict]:
    """The seeded dataset ships its own historical exceptions for every cycle (entity_type DELIVERY/EPOS/
    MANIFEST from the original demo generation) alongside whatever this live workflow's own gates record
    (entity_type ALLOCATION/ROUTING/CLOSURE) -- the same seeded-data-collision pattern Slices 1-5 all hit.
    `entity_type` lets a caller ask for only its own workflow's exceptions instead of everything ever
    recorded for the cycle."""
    sql = """SELECT exception_id, entity_type, entity_id, rule_code, severity, reason, detected_at,
                    assigned_to, status, resolution, resolved_at FROM exceptions WHERE cycle = %s"""
    params: list = [cycle]
    if status:
        sql += " AND status = %s"
        params.append(status)
    if entity_type:
        sql += " AND entity_type = %s"
        params.append(entity_type)
    sql += " ORDER BY severity, detected_at"
    return rows(conn, sql, params)


def override_allocation(conn, cycle: str, fps_id: str, commodity: str, new_kg: float, officer_id: str, reason: str) -> dict:
    """DSO manual override of one allocation, with a mandatory reason and an audited before/after. Still
    cannot go below the NFSA entitlement floor or above physical warehouse stock — those are hard limits,
    not DSO discretion; every other gate (FPS capacity, truck capacity, route) can be knowingly overridden."""
    if not reason or not reason.strip():
        raise ApiError(422, "REASON_REQUIRED", "An override requires a written reason.")
    if commodity not in COMMODITIES:
        raise ApiError(422, "INVALID_COMMODITY", f"commodity must be one of {COMMODITIES}.")

    a = one(conn, """SELECT allocation_id, allocated_kg, status, warehouse_id FROM allocations
                     WHERE cycle = %s AND fps_id = %s AND commodity = %s FOR UPDATE""", (cycle, fps_id, commodity))
    if not a:
        raise ApiError(404, "ALLOCATION_NOT_FOUND", f"No allocation for {fps_id}/{commodity} in cycle {cycle}.")
    if new_kg < 0:
        raise ApiError(422, "INVALID_QUANTITY", "allocated_kg cannot be negative.")

    floor_kg = _entitlement_floor(conn, cycle).get((fps_id, commodity), 0)
    if new_kg < floor_kg:
        raise ApiError(422, "BELOW_ENTITLEMENT_FLOOR",
                       f"{new_kg}kg is below the NFSA entitlement floor {floor_kg}kg for {fps_id}/{commodity}; this cannot be overridden.",
                       {"floor_kg": floor_kg})
    w = one(conn, "SELECT rice_stock_kg, wheat_stock_kg FROM warehouses WHERE warehouse_id = %s FOR UPDATE", (a["warehouse_id"],))
    stock_col = _COMMODITY_STOCK_COL[commodity]
    committed_elsewhere = one(conn, """SELECT COALESCE(sum(allocated_kg), 0) AS kg FROM allocations
                                       WHERE cycle = %s AND warehouse_id = %s AND commodity = %s AND fps_id != %s""",
                              (cycle, a["warehouse_id"], commodity, fps_id))["kg"]
    if w and new_kg + num(committed_elsewhere) > num(w[stock_col]):
        raise ApiError(422, "EXCEEDS_WAREHOUSE_STOCK",
                       f"{new_kg}kg would exceed warehouse {a['warehouse_id']}'s {w[stock_col]}kg {commodity} stock "
                       f"({num(committed_elsewhere)}kg already committed to other FPS this cycle).",
                       {"available_kg": round(num(w[stock_col]) - num(committed_elsewhere), 1)})

    before_kg = num(a["allocated_kg"])
    now = datetime.now(timezone.utc)
    new_status = "APPROVED"
    with conn.transaction():
        conn.execute("UPDATE allocations SET allocated_kg = %s, status = %s, source = 'DSO_OVERRIDE' WHERE allocation_id = %s",
                    (new_kg, new_status, a["allocation_id"]))
        conn.execute("""UPDATE exceptions SET status = 'RESOLVED', resolution = %s, resolved_at = %s
                        WHERE cycle = %s AND entity_id = %s AND status = 'OPEN'""",
                    (f"DSO override: {reason.strip()}", now, cycle, f"{fps_id}:{commodity}"))
    # audited by the caller after conn.commit() — see the comment in allocate() for why.
    return {"cycle": cycle, "fps_id": fps_id, "commodity": commodity, "allocation_id": a["allocation_id"],
            "before_kg": before_kg, "after_kg": num(new_kg), "status": new_status}
