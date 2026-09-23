"""Explanations: deterministic natural-language rendering of signals.

LLM-style free text is deliberately NOT used: every sentence is a template
filled with database values, so no statement can outrun its evidence.
"""
from __future__ import annotations

from backend.services.beneficiary import num
from backend.services import demand as demand_svc
from backend.services.intelligence import signals as sig


def explain_allocation(conn, cycle: str, fps_id: str, commodity: str) -> dict:
    """Answers 'Why is this FPS receiving more/less than requested?' from records."""
    allocs = {f"{a['fps_id']}:{a['commodity']}": a
              for a in sig.allocation_records(conn, cycle)}
    key = f"{fps_id}:{commodity}"
    a = allocs.get(key)
    if a is None:
        return {"answer": "DATA NOT AVAILABLE",
                "detail": f"No allocation record exists for {fps_id}/{commodity} in cycle {cycle}.",
                "evidence": [], "advisory": True}
    req, alc = a["requested_kg"], a["allocated_kg"]
    parts = [f"FPS {fps_id} requested {req} kg {commodity} based on locked beneficiary intent.",
             f"{alc} kg was allocated from warehouse {a['warehouse_id']} (status {a['status']},"
             f" source {a['source']})."]
    if alc < req:
        gates = a.get("gates", [])
        if gates:
            parts.append("Less than requested because: " + " ".join(g["reason"] for g in gates))
        else:
            parts.append("The reason for the shortfall is not recorded in the constraint findings.")
    elif alc > req:
        parts.append("More than requested because the NFSA entitlement floor for active beneficiaries"
                     " exceeds submitted intent; the engine raised the proposal to the legal floor.")
    ov = a.get("override")
    if ov:
        parts.append(f"Overridden by {ov['actor_user_id']}: {ov['before_state']} kg ->"
                     f" {ov['after_state']} kg. Recorded reason: {ov['reason']}.")
    return {"answer": " ".join(parts),
            "detail": {"requested_kg": req, "allocated_kg": alc,
                       "difference_kg": round(alc - req, 1), "status": a["status"],
                       "source": a["source"], "warehouse_id": a["warehouse_id"],
                       "approved_by": a["approved_by"]},
            "evidence": [{"record": "allocations", "value": a["allocation_id"]},
                         {"record": "exceptions",
                          "value": [g["rule_code"] for g in a.get("gates", [])]},
                         {"record": "audit_events", "value": bool(ov)}],
            "advisory": True}


def explain_closure_blockers(conn, cycle: str) -> dict:
    """Answers 'Explain why this cycle cannot close' from live closure checks."""
    from backend.services import tracking as tracking_svc
    try:
        checks = tracking_svc.run_closure_checks(conn, cycle)
    except Exception as exc:
        return {"answer": "DATA NOT AVAILABLE",
                "detail": f"Closure checks could not be computed: {exc}.", "evidence": [],
                "advisory": True}
    failed = [k for k, v in checks.items() if not v]
    if not failed:
        return {"answer": f"Cycle {cycle} passes all {len(checks)} closure checks and can proceed"
                          " to closure through the normal authorised workflow.",
                "detail": checks, "evidence": [{"record": "cycles", "value": cycle}],
                "advisory": True}
    lines = []
    for name in failed:
        if name == "ALL_MANIFESTS_DELIVERED":
            lines.append("Not every manifest has been delivered yet.")
        elif name == "NO_REJECTED_DELIVERIES":
            lines.append("At least one delivery was rejected outright.")
        elif name == "DELIVERIES_WITHIN_TOLERANCE":
            lines.append("At least one delivery is outside the 5% tolerance of plan.")
        elif name == "ALLOCATION_MATCHES_DELIVERY":
            lines.append("Aggregate delivered quantity does not match allocated quantity"
                          " (beyond max(5%, 1 kg)).")
        elif name == "AUDIT_CHAIN_INTACT":
            lines.append("The audit hash chain does not verify.")
        elif name == "MANIFEST_HASHES_VERIFIED":
            lines.append("At least one sealed manifest hash no longer matches its content.")
        elif name == "NO_OPEN_BLOCKING_EXCEPTIONS":
            lines.append("Open HIGH-severity exceptions remain on manifested items.")
        else:
            lines.append(f"Check {name} failed.")
    return {"answer": f"Cycle {cycle} cannot close because {len(failed)} closure check(s) fail: "
                      + " ".join(lines),
            "detail": checks, "evidence": [{"record": "cycles", "value": cycle},
                                           {"record": "delivery_history", "value": "see reconciliation"},
                                           {"record": "exceptions", "value": "open HIGH"}],
            "advisory": True}


def ops_brief(conn, cycle: str) -> dict:
    """Concise role-neutral operations brief; every line counts real records."""
    from backend.services.intelligence import anomalies as an
    from backend.services.intelligence import risk as rk
    anomalies = an.demand_anomalies(conn, cycle)
    stock = rk.stockout_risks(conn, cycle)
    dispatch = rk.dispatch_risks(conn, cycle)
    rec = an.reconciliation_anomalies(conn, cycle)
    audit = rk.audit_intel(conn, cycle)
    fps_attention = sorted({a["entity_id"] for a in anomalies
                            if a["severity"] in ("HIGH", "MEDIUM")})
    brief = [
        {"title": "DEMAND",
         "lines": [f"{len(anomalies)} significant demand deviation(s) detected."
                   if anomalies else "No significant demand deviations detected."]},
        {"title": "INVENTORY",
         "lines": [f"{len([s for s in stock if s['severity']=='HIGH'])} location(s) with high stock/stockout risk."
                   if stock else "No stock risks detected."]},
        {"title": "DISPATCH",
         "lines": [f"{len([d for d in dispatch if d['severity']=='HIGH'])} blocking issue(s) remain."
                   if dispatch else "No dispatch blockers detected."]},
        {"title": "DELIVERY",
         "lines": [f"{len(rec)} unresolved reconciliation variance(s) detected."
                   if rec else "No reconciliation variances detected."]},
        {"title": "AUDIT",
         "lines": [f"{len(audit)} audit pattern(s) require review."
                   if audit else "No unusual audit patterns detected."]},
    ]
    return {"cycle": cycle, "sections": brief,
            "fps_needing_attention": fps_attention,
            "counts": {"demand_anomalies": len(anomalies), "stock_risks": len(stock),
                       "dispatch_risks": len(dispatch), "reconciliation": len(rec),
                       "audit_patterns": len(audit)}}
