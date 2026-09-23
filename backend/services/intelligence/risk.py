"""Risk surfaces: stock, allocation, route/fleet, dispatch, delivery, audit,
data-quality and system-health — all from persisted records.

Severity guide (documented, deterministic):
- HIGH: blocks or will imminently block dispatch/reconciliation/closure.
- MEDIUM: needs officer attention before authorisation.
- LOW: informational.
"""
from __future__ import annotations

from datetime import datetime, timezone

from backend.services.beneficiary import num, one, rows
from backend.services import demand as demand_svc
from backend.services.intelligence import signals as sig
from backend.services.manifest import MY_MANIFEST_PREFIX

# Exception entity types raised by this live workflow's own gates
# (allocation.py / routing.py / tracking.py). The seeded dataset ships its own
# unrelated historical DELIVERY/EPOS/MANIFEST exceptions per cycle — those are
# history, not dispatch blockers, and must never gate dispatch readiness.
LIVE_EXCEPTION_ENTITY_TYPES = ("ALLOCATION", "ROUTING", "CLOSURE")

# Cycle states whose allocations are workflow-produced (not seeded
# placeholders). Per-FPS depletion risk is only meaningful once the workflow
# has actually allocated.
ALLOCATED_STATES = ("ALLOCATED", "OPTIMIZED", "AUTHORIZED", "TRACKING",
                    "DELIVERING", "RECONCILING", "AUDITING", "CLOSED")

_seq = 0


def _id(prefix: str) -> str:
    global _seq
    _seq += 1
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{_seq:04d}"


def stockout_risks(conn, cycle: str) -> list[dict]:
    """Warehouse remaining stock and FPS depletion vs expected demand."""
    pos = sig.stock_positions(conn, cycle)
    out = []
    for w in pos["warehouses"]:
        for commodity, remaining in (("RICE", w["rice_remaining_kg"]), ("WHEAT", w["wheat_remaining_kg"])):
            if remaining is None:
                continue
            if remaining < 0:
                out.append(_risk("STOCK_RISK", "HIGH", f"Warehouse {w['warehouse_id']} over-committed on {commodity}",
                                 f"Committed allocations exceed recorded {commodity} stock by {abs(remaining)} kg.",
                                 "Reduce an allocation via the audited override workflow, or correct the stock record.",
                                 "WAREHOUSE", w["warehouse_id"], commodity,
                                 [{"record": "warehouses", "field": f"{commodity.lower()}_stock_kg",
                                   "value": num(w[f"{commodity.lower()}_stock_kg"])},
                                  {"record": "allocations", "field": "SUM(allocated_kg)",
                                   "value": w[f"{commodity.lower()}_committed_kg"]}],
                                 {"remaining_kg": remaining}))
            elif remaining == 0 and w[f"{commodity.lower()}_committed_kg"] > 0:
                out.append(_risk("STOCK_RISK", "MEDIUM",
                                 f"Warehouse {w['warehouse_id']} fully committed on {commodity}",
                                 f"No {commodity} buffer remains after this cycle's allocations.",
                                 "Avoid further overrides that increase load on this warehouse.",
                                 "WAREHOUSE", w["warehouse_id"], commodity,
                                 [{"record": "warehouses", "value": num(w[f"{commodity.lower()}_stock_kg"])},
                                  {"record": "allocations",
                                   "value": w[f"{commodity.lower()}_committed_kg"]}],
                                 {"remaining_kg": remaining}))
    # FPS-level: expected demand (allocated + incoming) vs closing stock snapshot.
    # Only meaningful once the workflow has actually allocated — before that,
    # allocations are seeded placeholders (source='SYSTEM') and a depletion
    # verdict would be noise. Live engine rows carry source ENGINE/DSO_OVERRIDE.
    cycle_state = (one(conn, "SELECT state FROM cycles WHERE cycle = %s", (cycle,)) or {}).get("state")
    live_allocs = (one(conn, "SELECT count(*) AS n FROM allocations WHERE cycle = %s"
                             " AND source IN ('ENGINE','DSO_OVERRIDE')", (cycle,)) or {}).get("n", 0)
    if cycle_state not in ALLOCATED_STATES or not live_allocs:
        return out
    alloc_by_fps: dict[str, float] = {}
    for r in rows(conn, "SELECT fps_id, COALESCE(sum(allocated_kg),0) AS kg FROM allocations"
                        " WHERE cycle = %s GROUP BY fps_id", (cycle,)):
        alloc_by_fps[r["fps_id"]] = num(r["kg"])
    for inv in pos["fps_inventory"]:
        fps_id = inv["fps_id"]
        demand = alloc_by_fps.get(fps_id, 0)
        incoming = pos["incoming_dispatch"].get(f"{fps_id}:{inv['commodity']}", 0)
        available = num(inv["closing_stock_kg"]) + incoming
        if demand and available < demand:
            out.append(_risk("STOCKOUT_RISK", "HIGH" if available <= 0 else "MEDIUM",
                             f"FPS {fps_id} may run short on {inv['commodity']}",
                             f"Available {available} kg (stock {inv['closing_stock_kg']} kg + incoming {incoming} kg)"
                             f" is below allocated demand {demand} kg.",
                             "Prioritise replenishment or review the allocation before authorisation.",
                             "FPS", fps_id, inv["commodity"],
                             [{"record": "inventory", "field": "closing_stock_kg",
                               "value": num(inv["closing_stock_kg"])},
                              {"record": "allocations", "field": "SUM(allocated_kg)", "value": demand},
                              {"record": "dispatch_manifest_items", "field": "incoming planned_kg",
                               "value": incoming}],
                             {"available_kg": available, "demand_kg": demand}))
    return out


def allocation_insights(conn, cycle: str) -> list[dict]:
    """Why each allocation exists — requested, validated, allocated, gates, overrides."""
    out = []
    for a in sig.allocation_records(conn, cycle):
        gates = a.pop("gates")
        override = a.pop("override")
        blocked = a["status"] == "BLOCKED"
        high = [g for g in gates if g["severity"] == "HIGH"]
        if blocked or high or a["source"] == "DSO_OVERRIDE":
            from backend.services.intelligence import explain as _ex
            req, alc = a["requested_kg"], a["allocated_kg"]
            why = _ex.explain_allocation(conn, cycle, a["fps_id"], a["commodity"])["answer"]
            if why == "DATA NOT AVAILABLE":
                why = (f"FPS {a['fps_id']} requested {req} kg {a['commodity']}."
                       f" {alc} kg is allocated (status {a['status']}).")
            out.append(_risk("ALLOCATION_RISK", "HIGH" if blocked else "MEDIUM",
                             f"Allocation needs attention: {a['fps_id']}/{a['commodity']}", why,
                             "Open the allocation, read the gate that fired, then correct data or record"
                             " an audited override. AI cannot change this.",
                             "FPS", a["fps_id"], a["commodity"],
                             [{"record": "allocations", "field": "requested_kg", "value": req},
                              {"record": "allocations", "field": "allocated_kg", "value": alc},
                              {"record": "exceptions", "value": [g["rule_code"] for g in gates],
                               "detail": "; ".join(g["reason"] for g in gates) or "no gate fired"},
                              {"record": "audit_events", "field": "ALLOCATION_OVERRIDDEN",
                               "value": bool(override)}],
                             {"requested_kg": req, "allocated_kg": alc,
                              "difference_kg": round(alc - req, 1), "status": a["status"],
                              "source": a["source"]}))
    return out


def route_fleet_risks(conn, cycle: str) -> list[dict]:
    """Overload, low utilisation, infeasible distance legs, concentration."""
    fleet = sig.fleet_signals(conn, cycle)
    out = []
    for v in fleet["vehicles"]:
        if v["manifest_id"] and v["overloaded"]:
            out.append(_risk("ROUTE_FLEET_RISK", "HIGH",
                             f"Vehicle {v['vehicle_id']} overloaded",
                             f"Assigned {v['assigned_kg']} kg exceeds capacity {v['capacity_kg']} kg.",
                             "Re-run optimisation after correcting the load; do not dispatch overloaded.",
                             "VEHICLE", v["vehicle_id"], None,
                             [{"record": "vehicles", "field": "capacity_kg",
                               "value": num(v["capacity_kg"])},
                              {"record": "dispatch_manifests", "field": "total_kg",
                               "value": num(v["assigned_kg"])}],
                             {"assigned_kg": num(v["assigned_kg"]),
                              "capacity_kg": num(v["capacity_kg"])}))
        elif v["manifest_id"] and v["utilisation_pct"] is not None and v["utilisation_pct"] < 30:
            out.append(_risk("ROUTE_FLEET_RISK", "LOW",
                             f"Vehicle {v['vehicle_id']} under-utilised",
                             f"Assigned {v['assigned_kg']} kg is {v['utilisation_pct']}% of"
                             f" {v['capacity_kg']} kg capacity.",
                             "Consider consolidating trips in a future optimisation round.",
                             "VEHICLE", v["vehicle_id"], None,
                             [{"record": "dispatch_manifests", "field": "total_kg",
                               "value": num(v["assigned_kg"])}],
                             {"utilisation_pct": v["utilisation_pct"]}))
    for r in fleet["routes"]:
        leg = num(r["distance_from_previous_km"])
        if leg and leg > 150:
            out.append(_risk("ROUTE_FLEET_RISK", "MEDIUM",
                             f"Long geodesic leg to {r['fps_id']}",
                             f"Leg of {leg} km (GEODESIC DISTANCE — NOT ROAD DISTANCE) on manifest"
                             f" {r['manifest_id']}.",
                             "Verify the stop sequencing before locking the manifest.",
                             "MANIFEST", r["manifest_id"], None,
                             [{"record": "vehicle_routes", "field": "distance_from_previous_km",
                               "value": leg, "detail": "GEODESIC DISTANCE — NOT ROAD DISTANCE"}],
                             {"leg_km": leg}))
    return out


def dispatch_risks(conn, cycle: str) -> list[dict]:
    """Readiness before human authorisation: blocking exceptions, manifest state,
    vehicle capacity, warehouse stock, stale data. Every reason cites evidence."""
    out = []
    state = (one(conn, "SELECT state FROM cycles WHERE cycle = %s", (cycle,)) or {}).get("state")
    if state is None:
        return [_risk("DISPATCH_RISK", "HIGH", "Cycle not found",
                      f"No cycle record {cycle} exists.", "Check the cycle identifier.",
                      "CYCLE", cycle, None, [], {})]
    open_high = rows(conn, """SELECT entity_type, entity_id, rule_code, reason FROM exceptions
                              WHERE cycle = %s AND severity='HIGH' AND status='OPEN'
                                AND entity_type = ANY(%s)""", (cycle, list(LIVE_EXCEPTION_ENTITY_TYPES)))
    # Scope like the closure gate (tracking.run_closure_checks): only blockers on
    # items actually manifested for dispatch are HIGH. Unresolved demand that was
    # never routed stays visible as MEDIUM — it needs a decision, but it does not
    # hold the dispatched manifests hostage.
    manifested = {r["entity_id"] for r in rows(
        conn, f"""SELECT mi.fps_id || ':' || mi.commodity AS entity_id FROM dispatch_manifest_items mi
                  JOIN dispatch_manifests m USING (manifest_id)
                  WHERE m.cycle = %s AND m.manifest_id LIKE '{MY_MANIFEST_PREFIX}%%'""", (cycle,))}
    on_manifest = [e for e in open_high if e["entity_id"] in manifested]
    off_manifest = [e for e in open_high if e["entity_id"] not in manifested]
    if on_manifest:
        out.append(_risk("DISPATCH_RISK", "HIGH",
                         f"{len(on_manifest)} blocking exception(s) on dispatched items remain open",
                         "; ".join(f"{e['entity_id']} [{e['rule_code']}]" for e in on_manifest[:5]),
                         "Resolve or audited-override each blocking exception before authorisation.",
                         "CYCLE", cycle, None,
                         [{"record": "exceptions", "field": e["rule_code"], "value": e["entity_id"],
                           "detail": e["reason"]} for e in on_manifest[:5]],
                         {"open_blocking": len(on_manifest)}))
    if off_manifest:
        out.append(_risk("DISPATCH_RISK", "MEDIUM",
                         f"{len(off_manifest)} unresolved blocker(s) outside this dispatch",
                         "Unresolved HIGH exceptions on items with no manifest (never routed): "
                         + "; ".join(f"{e['entity_id']} [{e['rule_code']}]" for e in off_manifest[:5])
                         + (f" (+{len(off_manifest) - 5} more)" if len(off_manifest) > 5 else ""),
                         "Decide each item's fate (correct data or audited override) in a later round;"
                         " they do not block the manifests already routed.",
                         "CYCLE", cycle, None,
                         [{"record": "exceptions", "field": e["rule_code"], "value": e["entity_id"],
                           "detail": e["reason"]} for e in off_manifest[:5]],
                         {"off_manifest_blockers": len(off_manifest)}))
    mine = rows(conn, f"""SELECT manifest_id, manifest_status, total_kg, vehicle_id FROM dispatch_manifests
                          WHERE cycle = %s AND manifest_id LIKE '{MY_MANIFEST_PREFIX}%%'""", (cycle,))
    unlocked = [m for m in mine if m["manifest_status"] not in ("LOCKED", "DISPATCHED", "DELIVERED")]
    if mine and unlocked:
        out.append(_risk("DISPATCH_RISK", "HIGH", f"{len(unlocked)} manifest(s) not sealed",
                         ", ".join(f"{m['manifest_id']} is {m['manifest_status']}" for m in unlocked[:5]),
                         "Validate and lock every manifest before authorisation.",
                         "CYCLE", cycle, None,
                         [{"record": "dispatch_manifests", "field": "manifest_status",
                           "value": m["manifest_status"], "detail": m["manifest_id"]} for m in unlocked[:5]],
                         {"unlocked": len(unlocked)}))
    for m in mine:
        v = one(conn, "SELECT capacity_kg FROM vehicles WHERE vehicle_id = %s", (m["vehicle_id"],))
        if v and num(m["total_kg"]) > num(v["capacity_kg"]):
            out.append(_risk("DISPATCH_RISK", "HIGH", f"Manifest {m['manifest_id']} exceeds vehicle capacity",
                             f"{m['total_kg']} kg vs {v['capacity_kg']} kg capacity.",
                             "Correct the load before authorisation.", "MANIFEST", m["manifest_id"], None,
                             [{"record": "dispatch_manifests", "value": num(m["total_kg"])},
                              {"record": "vehicles", "value": num(v["capacity_kg"])}],
                             {"total_kg": num(m["total_kg"]), "capacity_kg": num(v["capacity_kg"])}))
    neg = [w for w in sig.stock_positions(conn, cycle)["warehouses"]
           if w["rice_remaining_kg"] < 0 or w["wheat_remaining_kg"] < 0]
    if neg:
        out.append(_risk("DISPATCH_RISK", "HIGH", "Warehouse stock shortfall",
                         "; ".join(f"{w['warehouse_id']} RICE {w['rice_remaining_kg']} /"
                                   f" WHEAT {w['wheat_remaining_kg']} kg remaining" for w in neg),
                         "Do not authorise until stock covers allocations.",
                         "CYCLE", cycle, None,
                         [{"record": "warehouses", "value": w["warehouse_id"],
                           "detail": f"remaining RICE {w['rice_remaining_kg']},"
                                     f" WHEAT {w['wheat_remaining_kg']}"} for w in neg], {}))
    if state not in ("OPTIMIZED", "AUTHORIZED", "TRACKING", "DELIVERING", "RECONCILING", "AUDITING", "CLOSED"):
        out.append(_risk("DISPATCH_RISK", "MEDIUM", f"Cycle is {state}, not ready for dispatch",
                         "Required records (allocation/optimisation) are missing for this state.",
                         "Advance the workflow through its normal stages first.",
                         "CYCLE", cycle, None,
                         [{"record": "cycles", "field": "state", "value": state}], {"state": state}))
    return out


def delivery_risks(conn, cycle: str) -> list[dict]:
    from backend.services.intelligence import anomalies as an
    rec = an.reconciliation_anomalies(conn, cycle)
    return [{**a, "insight_id": a["anomaly_id"], "title": a["type"].replace("_", " ").title(),
             "summary": (f"{a['entity_id']}/{a.get('commodity')}: expected {a['expected_value']} kg,"
                         f" actual {a['observed_value']} kg (difference {a['difference']} kg)."
                         f" {a['detection_method']}"),
             "recommendation": "Investigate the variance against delivery records before reconciling.",
             "status": "ADVISORY", "model_type": "deterministic", "model_version": None,
             "dataset_version": None, "confidence": None,
             "confidence_display": "Confidence unavailable",
             "source_records": [e["record"] for e in a["evidence"]],
             "calculation": {"expected": a["expected_value"], "actual": a["observed_value"],
                             "difference": a["difference"]}} for a in rec]


def exception_intel(conn, cycle: str, limit: int = 50) -> list[dict]:
    exc = rows(conn, """SELECT exception_id, entity_type, entity_id, rule_code, severity, reason,
                                status, detected_at, assigned_to, resolution, resolved_at
                         FROM exceptions WHERE cycle = %s ORDER BY detected_at DESC LIMIT %s""",
               (cycle, limit))
    out = []
    for e in exc:
        det = e["detected_at"].isoformat() if e["detected_at"] else None
        out.append({
            "insight_id": e["exception_id"], "type": "EXCEPTION", "severity": e["severity"],
            "title": f"{e['rule_code']} on {e['entity_id']}",
            "summary": f"WHAT HAPPENED: {e['reason']} WHY IT MATTERS: a {e['severity']}-severity"
                       f" {e['entity_type']} gate fired. EVIDENCE: exception {e['exception_id']} recorded"
                       f" {det}, status {e['status']}."
                       + (f" Resolution: {e['resolution']}." if e["resolution"] else ""),
            "recommendation": ("Review the cited records and resolve through the normal workflow."
                               " AI cannot resolve this.") if e["status"] == "OPEN" else None,
            "entity_type": e["entity_type"], "entity_id": e["entity_id"],
            "evidence": [{"record": "exceptions", "field": e["rule_code"], "value": e["entity_id"],
                          "detail": e["reason"]}],
            "calculation": {"required": "see rule", "available": "see evidence",
                            "status": e["status"], "assigned_to": e["assigned_to"]},
            "source_records": ["exceptions"],
            "model_type": "deterministic", "model_version": None, "dataset_version": None,
            "generated_at": det, "confidence": None,
            "confidence_display": "Confidence unavailable", "status": "ADVISORY"})
    return out


def audit_intel(conn, cycle: str | None = None, limit: int = 100) -> list[dict]:
    filt, params = ("WHERE cycle = %s", [cycle]) if cycle else ("", [])
    events = rows(conn, f"""SELECT audit_event_id, cycle, actor_user_id, actor_role, action, entity_type,
                                   entity_id, reason, result, timestamp, before_state, after_state
                            FROM audit_events {filt} ORDER BY timestamp DESC LIMIT {limit}""", params)
    out = []
    # repeated overrides by same actor
    overrides = [e for e in events if e["action"] == "ALLOCATION_OVERRIDDEN"]
    by_actor: dict[str, int] = {}
    for e in overrides:
        by_actor[e["actor_user_id"]] = by_actor.get(e["actor_user_id"], 0) + 1
    for actor, n in by_actor.items():
        if n >= 3:
            out.append(_risk("AUDIT_INTEL", "MEDIUM", "Unusual override pattern detected",
                             f"Actor {actor} recorded {n} allocation overrides"
                             + (f" in cycle {cycle}." if cycle else "."),
                             "Review the override reasons in the audit trail before closure.",
                             "USER", actor, None,
                             [{"record": "audit_events", "field": "ALLOCATION_OVERRIDDEN",
                               "value": actor, "detail": f"{n} overrides"}],
                             {"overrides": n}))
    fails = [e for e in events if e["result"] in ("FAIL", "PARTIAL")]
    if len(fails) >= 5:
        out.append(_risk("AUDIT_INTEL", "MEDIUM", "Repeated failed actions",
                         f"{len(fails)} actions recorded FAIL/PARTIAL"
                         + (f" in cycle {cycle}." if cycle else "."),
                         "Check whether actors need guidance or records need correction.",
                         "CYCLE", cycle or "ALL", None,
                         [{"record": "audit_events", "value": e["action"],
                           "detail": e["actor_user_id"]} for e in fails[:5]],
                         {"failed": len(fails)}))
    chain = None
    try:
        from backend.core.audit import verify_chain
        chain = verify_chain()
    except Exception:
        chain = None
    if chain is not None and not chain.get("intact"):
        out.append(_risk("AUDIT_INTEL", "HIGH", "Audit hash chain broken",
                         f"Events failing verification: {chain.get('broken')}.",
                         "Escalate to the system administrator; do not close the cycle.",
                         "CYCLE", cycle or "ALL", None,
                         [{"record": "audit_events", "value": chain.get("broken")}],
                         {"broken": chain.get("broken")}))
    return out


def data_quality(conn) -> list[dict]:
    out = []
    checks = [
        ("fps", "SELECT fps_id AS id FROM fps f WHERE NOT EXISTS"
                " (SELECT 1 FROM warehouses w WHERE w.warehouse_id = f.warehouse_id)",
         "FPS records reference warehouses that do not exist"),
        ("inventory", "SELECT inventory_id AS id FROM inventory WHERE closing_stock_kg < 0",
         "Inventory rows with negative closing stock"),
        ("intent", "SELECT intent_id AS id FROM intent_signals i WHERE NOT EXISTS"
                   " (SELECT 1 FROM beneficiaries b WHERE b.beneficiary_id = i.beneficiary_id)",
         "Intent rows referencing unknown beneficiaries"),
        ("alloc", "SELECT allocation_id AS id FROM allocations a WHERE NOT EXISTS"
                  " (SELECT 1 FROM fps f WHERE f.fps_id = a.fps_id)",
         "Allocation rows referencing unknown FPS"),
        ("epos", "SELECT transaction_id AS id FROM epos_transactions t WHERE NOT EXISTS"
                 " (SELECT 1 FROM beneficiaries b WHERE b.beneficiary_id = t.beneficiary_id)",
         "e-POS transactions referencing unknown beneficiaries"),
    ]
    for label, sql, title in checks:
        try:
            bad = rows(conn, sql)
        except Exception:
            continue
        if bad:
            out.append(_risk("DATA_QUALITY", "HIGH" if label in ("fps", "alloc") else "MEDIUM",
                             f"DATA QUALITY ALERT: {title}",
                             f"{len(bad)} record(s): " + ", ".join(str(r["id"]) for r in bad[:10])
                             + ("..." if len(bad) > 10 else ""),
                             "Ask the system administrator to correct or quarantine these records.",
                             "TABLE", label, None,
                             [{"record": label, "value": r["id"]} for r in bad[:10]],
                             {"affected": len(bad)}))
    stale = one(conn, "SELECT max(prediction_generated_at) AS ts FROM demand_forecast")
    if stale and stale["ts"]:
        from datetime import timezone as _tz
        from datetime import datetime as _dt
        age_h = (_dt.now(_tz.utc) - stale["ts"]).total_seconds() / 3600
        if age_h > 24 * 30:
            out.append(_risk("DATA_QUALITY", "MEDIUM", "Forecast data is stale",
                             f"Newest forecast was generated {stale['ts'].isoformat()} ({age_h/24:.0f} days ago).",
                             "Re-run the forecast before relying on it.",
                             "TABLE", "demand_forecast", None,
                             [{"record": "demand_forecast",
                               "value": stale["ts"].isoformat()}],
                             {"age_days": round(age_h / 24, 1)}))
    return out


def system_health(conn) -> list[dict]:
    out = []
    try:
        imp = one(conn, "SELECT dataset_name, version, status, created_at FROM dataset_imports"
                        " ORDER BY created_at DESC LIMIT 1")
        if imp and imp["status"] not in ("ACTIVE", "VALIDATED", "IMPORTED"):
            out.append(_risk("SYSTEM_HEALTH", "HIGH", f"Dataset {imp['dataset_name']} is {imp['status']}",
                             f"Latest import status is {imp['status']}.",
                             "Investigate the failed import before trusting downstream figures.",
                             "DATASET", imp["dataset_name"], None,
                             [{"record": "dataset_imports", "value": imp["status"]}], {}))
    except Exception:
        pass
    fails = one(conn, "SELECT count(*) AS n FROM audit_events WHERE result='FAIL'"
                      " AND timestamp > now() - interval '24 hours'")
    if fails and fails["n"] >= 20:
        out.append(_risk("SYSTEM_HEALTH", "MEDIUM", "Unusual authentication/activity failures",
                         f"{fails['n']} failed audit events in the last 24 hours.",
                         "Review recent access logs for misuse or misconfiguration.",
                         "SYSTEM", "auth", None,
                         [{"record": "audit_events", "value": fails["n"]}], {"failed_24h": fails["n"]}))
    try:
        model = one(conn, "SELECT model_version, training_dataset_version, max(generated_at) AS ts"
                           " FROM ai_predictions WHERE service='demand_forecast' GROUP BY 1,2"
                           " ORDER BY ts DESC LIMIT 1")
        if model:
            out.append(_risk("SYSTEM_HEALTH", "LOW",
                             f"Model {model['model_version']} active ({model['training_dataset_version']})",
                             f"Last demand_forecast prediction {model['ts'].isoformat() if model['ts'] else 'unknown'}.",
                             None, "MODEL", model["model_version"], None,
                             [{"record": "ai_predictions", "value": model["model_version"]}], {}))
        else:
            out.append(_risk("SYSTEM_HEALTH", "MEDIUM", "No forecast predictions recorded",
                             "ai_predictions has no demand_forecast rows.",
                             "Generate a forecast before relying on demand intelligence.",
                             "MODEL", "demand_forecast", None,
                             [{"record": "ai_predictions", "value": "none"}], {}))
    except Exception:
        pass
    return out


def _risk(type: str, severity: str, title: str, summary: str, recommendation: str | None,
          entity_type: str | None, entity_id: str | None, commodity: str | None,
          evidence: list[dict], calculation: dict) -> dict:
    d = {"insight_id": _id(type), "type": type, "severity": severity, "title": title,
         "summary": summary, "recommendation": recommendation,
         "entity_type": entity_type, "entity_id": entity_id}
    if commodity:
        d["commodity"] = commodity
    d.update({"evidence": evidence, "calculation": calculation,
              "source_records": sorted({e["record"] for e in evidence}),
              "model_type": "deterministic", "model_version": None, "dataset_version": None,
              "generated_at": datetime.now(timezone.utc).isoformat(),
              "confidence": None, "confidence_display": "Confidence unavailable",
              "status": "ADVISORY"})
    return d
