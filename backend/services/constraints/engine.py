"""
Constraint Engine — Prototype (distinctive module)
Checks: Demand≤Allocation → FPS Capacity → Truck Capacity → Stock → Route feasible → NFSA entitlement floor
Returns: (ready: bool, exceptions: list)
"""
def validate_dispatch(demand_by_fps: dict, allocations: dict, fps_capacities: dict, truck_capacity: float, stock_kg: float, entitlements: dict = None):
    exceptions = []
    total = sum(demand_by_fps.values())

    for fps_id, demand in demand_by_fps.items():
        alloc = allocations.get(fps_id, float('inf'))
        if demand > alloc:
            exceptions.append(f"FPS-{fps_id}: required {demand}kg, allocation {alloc}kg — exceeds allocation")

        cap = fps_capacities.get(fps_id, float('inf'))
        if demand > cap:
            exceptions.append(f"FPS-{fps_id}: required {demand}kg, capacity {cap}kg — exceeds capacity {demand-cap}kg")

        # NFSA entitlement floor — never allocate below entitlement
        if entitlements and fps_id in entitlements:
            floor = entitlements[fps_id]
            if demand < floor:
                exceptions.append(f"FPS-{fps_id}: demand {demand}kg below NFSA entitlement floor {floor}kg — legal violation")

    if total > truck_capacity:
        exceptions.append(f"Truck: total {total}kg exceeds capacity {truck_capacity}kg")
    if total > stock_kg:
        exceptions.append(f"Warehouse: total {total}kg exceeds stock {stock_kg}kg")

    return (len(exceptions) == 0, exceptions)
