"""Role-aware intelligence orchestration.

Each role gets only what its RBAC scope allows. Server-side scoping happens
here AND in the API layer (defence in depth): beneficiary -> own id only,
FPS owner -> owned fps_id only, inspector -> district FPS list, DSO/auditor/
admin -> cycle-wide but through their permission gates.
"""
from __future__ import annotations

from backend.services.beneficiary import one, rows
from backend.services.intelligence import anomalies as an
from backend.services.intelligence import explain as ex
from backend.services.intelligence import risk as rk
from backend.services.intelligence import signals as sig


def _cycle_or_none(conn, cycle: str | None) -> str | None:
    if cycle:
        return cycle
    r = one(conn, "SELECT cycle FROM cycles ORDER BY cycle DESC LIMIT 1")
    return r["cycle"] if r else None


def dso_summary(conn, cycle: str) -> dict:
    cycle = _cycle_or_none(conn, cycle)
    if cycle is None:
        return {"cycle": None, "insights": [], "brief": None, "note": "DATA UNAVAILABLE — no cycles exist."}
    insights: list[dict] = []
    anomalies = an.demand_anomalies(conn, cycle)
    # Systemic collapse: when a large share of FPS deviate in the same
    # direction it is a participation-level shift (e.g. partial drawdown vs
    # full-demand history), not hundreds of independent anomalies. Emit one
    # systemic card with the extremes as evidence; the full evidence-backed
    # list stays available at GET /intelligence/dso/anomalies.
    try:
        from backend.services import demand as _demand
        intent_keys = len(_demand.aggregate_intent(conn, cycle))
    except Exception:
        intent_keys = 0
    if intent_keys and len(anomalies) > max(10, intent_keys * 0.25):
        below = sum(1 for a in anomalies if (a["difference"] or 0) < 0)
        above = len(anomalies) - below
        direction = "below" if below >= above else "above"
        extremes = sorted(anomalies, key=lambda a: abs(a["difference"] or 0), reverse=True)[:10]
        insights.append({
            "insight_id": f"DEMAND_SHIFT-{cycle}", "type": "DEMAND_SHIFT", "severity": "MEDIUM",
            "title": f"Widespread demand shift in {cycle}",
            "summary": (f"{len(anomalies)} of {intent_keys} FPS+commodity intents deviate {direction}"
                        f" historical per-capita demand. This pattern points to a participation-level"
                        f" effect (e.g. partial drawdown vs full-demand history), not isolated spikes."
                        f" Extremes: " + "; ".join(
                            f"{e['entity_id']}/{e.get('commodity')} {e['observed_value']} vs"
                            f" {e['expected_value']}" for e in extremes[:5]) + "."),
            "recommendation": "Check participation and entitlement drawdown before treating any single"
                              " FPS as anomalous; review the full list for genuine outliers.",
            "entity_type": "CYCLE", "entity_id": cycle,
            "evidence": [{"record": "intent_signals + historical_demand",
                          "value": f"{len(anomalies)}/{intent_keys} deviating {direction}",
                          "detail": a["detection_method"]} for a in extremes[:5]],
            "calculation": {"deviating": len(anomalies), "total_with_intent": intent_keys,
                            "below": below, "above": above},
            "source_records": ["intent_signals", "historical_demand"],
            "model_type": "statistical", "model_version": None, "dataset_version": None,
            "generated_at": extremes[0]["detected_at"] if extremes else None,
            "confidence": None, "confidence_display": "Confidence unavailable",
            "status": "ADVISORY"})
    else:
        for a in anomalies:
            direction = "above" if (a["difference"] or 0) > 0 else "below"
            insights.append({
                "insight_id": a["anomaly_id"], "type": "DEMAND_ANOMALY", "severity": a["severity"],
                "title": f"Demand anomaly: {a['entity_id']}/{a['commodity']}",
                "summary": (f"FPS {a['entity_id']} intent ({a['observed_value']} kg) is {direction}"
                            f" expected ({a['expected_value']} kg, difference {a['difference']} kg)."
                            f" {a['detection_method']}."),
                "recommendation": "Review allocation before authorisation.",
                "entity_type": a["entity_type"], "entity_id": a["entity_id"],
                "commodity": a.get("commodity"), "evidence": a["evidence"],
                "calculation": {"observed": a["observed_value"], "expected": a["expected_value"],
                                "difference": a["difference"]},
                "source_records": ["intent_signals", "historical_demand", "demand_forecast"],
                "model_type": "statistical", "model_version": None, "dataset_version": None,
                "generated_at": a["detected_at"], "confidence": None,
                "confidence_display": "Confidence unavailable", "status": "ADVISORY"})
    insights.extend(rk.stockout_risks(conn, cycle))
    insights.extend(rk.allocation_insights(conn, cycle))
    insights.extend(rk.route_fleet_risks(conn, cycle))
    insights.extend(rk.dispatch_risks(conn, cycle))
    insights.extend(rk.delivery_risks(conn, cycle))
    return {"cycle": cycle, "brief": ex.ops_brief(conn, cycle), "insights": insights,
            "counts": _count(insights)}


def inspector_summary(conn, cycle: str, district: str | None = None) -> dict:
    from backend.services import inspection_risk as ir
    cycle = _cycle_or_none(conn, cycle)
    fps_list = ir._fps_list(conn, district) if cycle else []
    ranked = []
    for f in fps_list:
        a = ir.assess(conn, f)
        if a["level"] in ("HIGH", "MEDIUM"):
            ranked.append({"fps_id": f["fps_id"], "fps_name": f["fps_name"],
                           "score": a["score"], "level": a["level"],
                           "factors": a["factors"], "focus": a["focus"]})
    ranked.sort(key=lambda r: -r["score"])
    delivery = [d for d in rk.delivery_risks(conn, cycle)] if cycle else []
    fps_ids = {f["fps_id"] for f in fps_list}
    delivery = [d for d in delivery if d.get("entity_id") in fps_ids] if district else delivery
    return {"cycle": cycle, "district": district,
            "inspection_priorities": ranked[:20],
            "delivery_anomalies": delivery[:20],
            "note": "Prioritisation only. AI cannot create or approve an inspection."}


def fps_summary(conn, cycle: str, fps_id: str) -> dict:
    cycle = _cycle_or_none(conn, cycle)
    incoming = [b for b in sig.mass_balance(conn, cycle) if b["fps_id"] == fps_id] if cycle else []
    inv = rows(conn, "SELECT commodity, closing_stock_kg, cycle FROM inventory"
                     " WHERE location_type='FPS' AND location_id=%s ORDER BY cycle DESC LIMIT 4", (fps_id,))
    exc = rows(conn, "SELECT exception_id, rule_code, severity, reason, status FROM exceptions"
                     " WHERE (entity_id LIKE %s OR entity_id = %s) ORDER BY detected_at DESC LIMIT 20",
               (fps_id + ":%", fps_id))
    depl = []
    if cycle:
        for r in rk.stockout_risks(conn, cycle):
            if r.get("entity_id") == fps_id:
                depl.append(r)
    expl = []
    if cycle:
        for b in incoming:
            for commodity in (b["commodity"],):
                e = ex.explain_allocation(conn, cycle, fps_id, commodity)
                if e["answer"] != "DATA NOT AVAILABLE":
                    expl.append({"commodity": commodity, **e})
    return {"cycle": cycle, "fps_id": fps_id, "incoming": incoming, "inventory": inv,
            "stock_risks": depl, "allocation_explanations": expl, "exceptions": exc}


def auditor_summary(conn, cycle: str) -> dict:
    cycle = _cycle_or_none(conn, cycle)
    if cycle is None:
        return {"cycle": None, "insights": [], "note": "DATA UNAVAILABLE."}
    insights = []
    insights.extend(rk.audit_intel(conn, cycle))
    insights.extend(rk.delivery_risks(conn, cycle))
    insights.extend(rk.exception_intel(conn, cycle))
    closure = ex.explain_closure_blockers(conn, cycle)
    overrides = rows(conn, "SELECT audit_event_id, actor_user_id, entity_id, reason, before_state,"
                           " after_state, timestamp FROM audit_events WHERE cycle=%s"
                           " AND action='ALLOCATION_OVERRIDDEN' ORDER BY timestamp DESC", (cycle,))
    manifests = rows(conn, "SELECT manifest_id, manifest_status, sha256_hash FROM dispatch_manifests"
                           " WHERE cycle=%s ORDER BY manifest_id", (cycle,))
    return {"cycle": cycle, "insights": insights, "closure_explanation": closure,
            "override_history": overrides, "manifests": manifests, "counts": _count(insights)}


def admin_summary(conn) -> dict:
    dq = rk.data_quality(conn)
    health = rk.system_health(conn)
    audit_patterns = rk.audit_intel(conn, None)
    return {"insights": dq + health + audit_patterns, "counts": _count(dq + health + audit_patterns)}


def beneficiary_summary(conn, beneficiary_id: str) -> dict:
    ctx = sig.beneficiary_context(conn, beneficiary_id, None)
    if ctx is None:
        return {"beneficiary_id": beneficiary_id, "note": "DATA UNAVAILABLE — unknown beneficiary."}
    cycle = ctx.get("cycle")
    ent = ctx.get("entitlement") or {}
    cards = []
    if ent:
        cards.append({"type": "ENTITLEMENT", "severity": "LOW", "title": "Your entitlement",
                      "summary": f"In {cycle} you may collect {ent.get('total_kg')} kg in total;"
                                 f" {ent.get('remaining_total_kg')} kg remains.",
                      "recommendation": "Plan collection before the choice window closes.",
                      "evidence": [{"record": "beneficiaries + epos_transactions",
                                    "value": beneficiary_id}],
                      "status": "ADVISORY"})
    if ctx.get("intent"):
        i = ctx["intent"]
        cards.append({"type": "INTENT", "severity": "LOW", "title": "Your collection plan",
                      "summary": f"You asked for {i['total_quantity_kg']} kg at {i['fps_id']}"
                                 f" (ref {i['intent_id']}).",
                      "recommendation": None,
                      "evidence": [{"record": "intent_signals", "value": i["intent_id"]}],
                      "status": "ADVISORY"})
    stage = ctx.get("stage")
    if stage:
        cards.append({"type": "DELIVERY_STATUS", "severity": "LOW",
                      "title": "Where your ration is",
                      "summary": f"Current stage for {cycle}: {stage}.",
                      "recommendation": "Ask the assistant for details.",
                      "evidence": [{"record": "cycles + allocations + delivery",
                                    "value": cycle}],
                      "status": "ADVISORY"})
    return {"beneficiary_id": beneficiary_id, "cycle": cycle, "insights": cards}


def _count(insights: list[dict]) -> dict:
    c: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for i in insights:
        c[i.get("severity", "LOW")] = c.get(i.get("severity", "LOW"), 0) + 1
    c["total"] = len(insights)
    return c
