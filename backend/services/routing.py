"""Route optimization for the DSO: ALLOCATED -> OPTIMIZED. OR-Tools CVRP over haversine (great-circle)
distance. See docs/AI_ARCHITECTURE.md / the Phase 2 plan's decision #2.

Distance is explicitly geodesic, not road distance: there is no road network or routing-engine data in
this dataset, so a straight-line distance is what's honestly available. route_distance_km/eta_minutes are
labelled accordingly everywhere they're surfaced, never presented as an actual driving distance/time.

One manifest is one vehicle's one trip; dispatch_manifests has no natural uniqueness (a vehicle can make
several trips a cycle — the seeded dataset's own historical manifests confirm this), so this only ever adds
new manifests for the cycle's real APPROVED allocations. It never touches pre-existing manifests, sealed
or not. Idempotency is enforced by the cycle state machine (ALLOCATED -> OPTIMIZED), exactly like
allocation.py's LOCKED -> ALLOCATED: this can only run once per cycle in the live app.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from backend.core.errors import ApiError
from backend.services.beneficiary import num, one, rows

AVG_SPEED_KMPH = 35  # a documented assumption for a rural PDS delivery route; not a measured figure
# Each warehouse is solved independently (typically <30 stops, a handful of vehicles): a first-solution
# heuristic alone is fast and sufficient at this scale, so no local-search metaheuristic (which would run
# for the full time budget on every warehouse, however small) is used.
SOLVE_TIME_LIMIT_SECONDS = 2
DROP_PENALTY_KG_MULTIPLIER = 10_000  # strongly prefer routing every stop; only drop if truly infeasible

RULE_NO_VEHICLE_AVAILABLE = "NO_VEHICLE_AVAILABLE"
RULE_INSUFFICIENT_FLEET_CAPACITY = "INSUFFICIENT_FLEET_CAPACITY"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km. Not a road distance — see this module's docstring."""
    r = 6371.0088
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlmb = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _warehouse_stops(conn, cycle: str) -> dict[str, dict]:
    """Every warehouse with APPROVED allocations this cycle, and its stops (one per FPS, combining
    RICE+WHEAT kg — a truck carries both in one trip). Not filtered by "already has a manifest_item":
    the seeded dataset's own historical manifests already reference these same allocation_id values
    (allocate() upserts onto them, per migration 0007), so that would wrongly skip every real allocation.
    optimize() is state-gated to run once per cycle (ALLOCATED -> OPTIMIZED), which is what actually
    keeps this idempotent — not a row-level check here."""
    alloc_rows = rows(conn, """
        SELECT a.allocation_id, a.fps_id, a.commodity, a.allocated_kg, a.warehouse_id, f.latitude, f.longitude
        FROM allocations a JOIN fps f ON f.fps_id = a.fps_id
        WHERE a.cycle = %s AND a.status = 'APPROVED'
        ORDER BY a.warehouse_id, a.fps_id""", (cycle,))
    by_warehouse: dict[str, dict] = {}
    for r in alloc_rows:
        wh = by_warehouse.setdefault(r["warehouse_id"], {})
        stop = wh.setdefault(r["fps_id"], {"fps_id": r["fps_id"], "latitude": r["latitude"], "longitude": r["longitude"],
                                           "demand_kg": 0.0, "items": []})
        stop["demand_kg"] += num(r["allocated_kg"])
        stop["items"].append({"allocation_id": r["allocation_id"], "commodity": r["commodity"], "kg": num(r["allocated_kg"])})
    return {wh: list(stops.values()) for wh, stops in by_warehouse.items()}


def _available_vehicles(conn, warehouse_id: str) -> list[dict]:
    return rows(conn, """SELECT vehicle_id, capacity_kg FROM vehicles
                         WHERE warehouse_id = %s AND current_status = 'AVAILABLE' ORDER BY vehicle_id""", (warehouse_id,))


def _solve_cvrp(depot: dict, stops: list[dict], vehicles: list[dict]) -> tuple[list[list[int]], list[int]]:
    """Returns (routes, dropped) where routes[v] is a list of stop indices (0-based into `stops`) for
    vehicle v, in visiting order, and dropped is the list of stop indices that could not be routed within
    the available fleet's total capacity."""
    n_stops = len(stops)
    nodes = [depot] + stops  # node 0 is the depot
    dist_m = [[0] * (n_stops + 1) for _ in range(n_stops + 1)]
    for i in range(n_stops + 1):
        for j in range(n_stops + 1):
            if i != j:
                dist_m[i][j] = round(haversine_km(nodes[i]["latitude"], nodes[i]["longitude"],
                                                   nodes[j]["latitude"], nodes[j]["longitude"]) * 1000)

    manager = pywrapcp.RoutingIndexManager(n_stops + 1, len(vehicles), 0)
    model = pywrapcp.RoutingModel(manager)

    def distance_cb(from_idx, to_idx):
        return dist_m[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

    transit_idx = model.RegisterTransitCallback(distance_cb)
    model.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    def demand_cb(idx):
        node = manager.IndexToNode(idx)
        return 0 if node == 0 else round(stops[node - 1]["demand_kg"])

    demand_idx = model.RegisterUnaryTransitCallback(demand_cb)
    model.AddDimensionWithVehicleCapacity(demand_idx, 0, [round(v["capacity_kg"]) for v in vehicles], True, "Capacity")

    max_kg = max((round(s["demand_kg"]) for s in stops), default=0)
    for node in range(1, n_stops + 1):
        model.AddDisjunction([manager.NodeToIndex(node)], max(1, max_kg) * DROP_PENALTY_KG_MULTIPLIER)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.time_limit.FromSeconds(SOLVE_TIME_LIMIT_SECONDS)

    solution = model.SolveWithParameters(params)
    routes: list[list[int]] = [[] for _ in vehicles]
    dropped: list[int] = []
    if solution is None:
        return routes, list(range(n_stops))  # infeasible even with drops allowed (shouldn't happen, but never crash)

    for v in range(len(vehicles)):
        idx = model.Start(v)
        while not model.IsEnd(idx):
            node = manager.IndexToNode(idx)
            if node != 0:
                routes[v].append(node - 1)
            idx = solution.Value(model.NextVar(idx))

    routed = {s for r in routes for s in r}
    dropped = [i for i in range(n_stops) if i not in routed]
    return routes, dropped


def optimize(conn, cycle: str, officer_id: str) -> dict:
    """ALLOCATED -> OPTIMIZED. One CVRP solve per warehouse with pending APPROVED allocations; writes one
    DRAFT dispatch_manifests row per vehicle used, its dispatch_manifest_items, and its vehicle_routes
    stops. Stops that no available vehicle can reach (no fleet, or fleet too small) are left unmanifested
    and logged as a HIGH exception — never silently dropped from the record."""
    c = one(conn, "SELECT state FROM cycles WHERE cycle = %s FOR UPDATE", (cycle,))
    if not c:
        raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
    if c["state"] == "OPTIMIZED":
        raise ApiError(409, "CYCLE_ALREADY_OPTIMIZED", f"Cycle {cycle} has already been optimized.")
    if c["state"] != "ALLOCATED":
        raise ApiError(409, "CYCLE_NOT_ALLOCATED", f"Cycle {cycle} is {c['state']}, not ALLOCATED. It cannot be optimized.",
                       {"state": c["state"]})
    # BLOCKED allocations (an unresolved HIGH-severity gate from Slice 2 -- suspended FPS, over capacity,
    # short on stock...) are never routed: _warehouse_stops() below only reads status='APPROVED'. This is
    # the enforcement of "a constraint violation blocks allocation until the DSO fixes or overrides it" --
    # scoped to the specific FPS+commodity it applies to, not a single gate for the whole cycle. A BLOCKED
    # item simply gets no manifest this round (visible via GET /exceptions and /allocations), rather than
    # holding every other, unrelated warehouse's dispatch hostage to one unresolved item.
    blocked_allocations = one(conn, "SELECT count(*) AS n FROM allocations WHERE cycle = %s AND status = 'BLOCKED'", (cycle,))["n"]

    warehouses = _warehouse_stops(conn, cycle)
    now = datetime.now(timezone.utc)
    manifests_created, stops_routed, stops_unroutable = 0, 0, 0

    with conn.transaction():
        for warehouse_id, stops in warehouses.items():
            depot = one(conn, "SELECT latitude, longitude FROM warehouses WHERE warehouse_id = %s", (warehouse_id,))
            vehicles = _available_vehicles(conn, warehouse_id)
            if not vehicles:
                for s in stops:
                    conn.execute(
                        """INSERT INTO exceptions (exception_id, cycle, entity_type, entity_id, rule_code, severity,
                               reason, detected_at, assigned_to, status)
                           VALUES (%s, %s, 'ROUTING', %s, %s, 'HIGH', %s, %s, %s, 'OPEN')""",
                        ("EXC-" + uuid.uuid4().hex[:12].upper(), cycle, s["fps_id"], RULE_NO_VEHICLE_AVAILABLE,
                         f"No AVAILABLE vehicle at warehouse {warehouse_id} to carry {s['fps_id']}'s {round(s['demand_kg'], 1)}kg.",
                         now, officer_id))
                    stops_unroutable += 1
                continue

            routes, dropped = _solve_cvrp(depot, stops, vehicles)
            for v_idx, stop_indices in enumerate(routes):
                if not stop_indices:
                    continue
                vehicle = vehicles[v_idx]
                mid = "MAN-" + uuid.uuid4().hex[:12].upper()
                total_kg = round(sum(stops[i]["demand_kg"] for i in stop_indices), 1)

                # compute every leg first (dispatch_manifests must exist before vehicle_routes/items can
                # reference it via FK)
                legs, prev, cum_km, cum_min = [], depot, 0.0, 0.0
                for seq, i in enumerate(stop_indices, start=1):
                    s = stops[i]
                    leg_km = haversine_km(prev["latitude"], prev["longitude"], s["latitude"], s["longitude"])
                    cum_km += leg_km
                    cum_min += leg_km / AVG_SPEED_KMPH * 60
                    legs.append({"seq": seq, "stop": s, "leg_km": leg_km, "cum_min": cum_min})
                    prev = s

                conn.execute(
                    """INSERT INTO dispatch_manifests (manifest_id, cycle, warehouse_id, vehicle_id, manifest_status,
                           total_kg, route_distance_km, route_duration_min, constraint_status, created_by, created_at)
                       VALUES (%s, %s, %s, %s, 'DRAFT', %s, %s, %s, 'READY', %s, %s)""",
                    (mid, cycle, warehouse_id, vehicle["vehicle_id"], total_kg, round(cum_km, 2), round(cum_min, 1),
                     officer_id, now))
                for leg in legs:
                    s = leg["stop"]
                    conn.execute(
                        """INSERT INTO vehicle_routes (route_id, manifest_id, vehicle_id, warehouse_id, stop_sequence,
                               fps_id, latitude, longitude, distance_from_previous_km, eta_minutes, route_status)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PLANNED')""",
                        ("RTE-" + uuid.uuid4().hex[:12].upper(), mid, vehicle["vehicle_id"], warehouse_id, leg["seq"],
                         s["fps_id"], s["latitude"], s["longitude"], round(leg["leg_km"], 2), round(leg["cum_min"], 1)))
                    for item in s["items"]:
                        conn.execute(
                            """INSERT INTO dispatch_manifest_items (manifest_item_id, manifest_id, fps_id, commodity,
                                   planned_kg, sequence_number, allocation_id)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                            ("MI-" + uuid.uuid4().hex[:12].upper(), mid, s["fps_id"], item["commodity"], item["kg"],
                             leg["seq"], item["allocation_id"]))
                    stops_routed += 1
                manifests_created += 1

            for i in dropped:
                s = stops[i]
                conn.execute(
                    """INSERT INTO exceptions (exception_id, cycle, entity_type, entity_id, rule_code, severity,
                           reason, detected_at, assigned_to, status)
                       VALUES (%s, %s, 'ROUTING', %s, %s, 'HIGH', %s, %s, %s, 'OPEN')""",
                    ("EXC-" + uuid.uuid4().hex[:12].upper(), cycle, s["fps_id"], RULE_INSUFFICIENT_FLEET_CAPACITY,
                     f"Warehouse {warehouse_id}'s available fleet cannot cover {s['fps_id']}'s {round(s['demand_kg'], 1)}kg "
                     f"this cycle after routing every other stop.", now, officer_id))
                stops_unroutable += 1

        conn.execute("UPDATE cycles SET state = 'OPTIMIZED' WHERE cycle = %s", (cycle,))

    return {"cycle": cycle, "state": "OPTIMIZED", "manifests_created": manifests_created,
            "stops_routed": stops_routed, "stops_unroutable": stops_unroutable,
            "allocations_blocked": blocked_allocations}


def list_manifests(conn, cycle: str) -> list[dict]:
    return rows(conn, """SELECT manifest_id, warehouse_id, vehicle_id, manifest_status, total_kg, route_distance_km,
                                route_duration_min, constraint_status, created_by, created_at
                         FROM dispatch_manifests WHERE cycle = %s ORDER BY warehouse_id, manifest_id""", (cycle,))


def manifest_detail(conn, manifest_id: str) -> dict:
    m = one(conn, """SELECT manifest_id, cycle, warehouse_id, vehicle_id, manifest_status, total_kg, route_distance_km,
                            route_duration_min, constraint_status, created_by, created_at
                     FROM dispatch_manifests WHERE manifest_id = %s""", (manifest_id,))
    if not m:
        raise ApiError(404, "MANIFEST_NOT_FOUND", f"No manifest {manifest_id}.")
    items = rows(conn, """SELECT manifest_item_id, fps_id, commodity, planned_kg, sequence_number, allocation_id
                          FROM dispatch_manifest_items WHERE manifest_id = %s ORDER BY sequence_number""", (manifest_id,))
    route = rows(conn, """SELECT fps_id, stop_sequence, latitude, longitude, distance_from_previous_km, eta_minutes, route_status
                          FROM vehicle_routes WHERE manifest_id = %s ORDER BY stop_sequence""", (manifest_id,))
    return {**m, "distance_basis": "haversine (great-circle), not road distance", "items": items, "route": route}
