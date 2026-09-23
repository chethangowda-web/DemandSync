"""Grounded operational assistant (not a generic chatbot).

USER QUESTION -> AUTHENTICATE -> AUTHORIZE (server-side scoping) -> READ real
rows -> DETERMINISTIC calculation -> EXPLAIN with evidence -> ANSWER + evidence.

Rule-based templates only: no generative model, no invented context. Unknown
or out-of-scope questions get a help message, never a guess. Questions about
records that do not exist get DATA NOT AVAILABLE, never an invented answer.
"""
from __future__ import annotations

import re

from backend.services.beneficiary import one
from backend.services.intelligence import signals as sig
from backend.services.intelligence import explain as ex

_PATTERNS = [
    ("ALLOCATION_WHY", r"why.*(less|more|receiv|allocat|request)|allocation.*(lower|higher|less|more)|"
                       r"requiring more allocation"),
    ("CLOSE_WHY", r"why.*(cannot|can't|not).*(close|closure)|closure.*block|close.*block|explain.*clos"),
    ("STOCK", r"stockout|stock.*(risk|left|remain|short)|deplet|inventory|replenish"),
    ("DISPATCH_READY", r"dispatch.*(risk|ready|block)|ready.*dispatch|authori[sz]"),
    ("ATTENTION", r"which.*(needs|require).*attention|needs attention|requir.*attention|prioriti"),
    ("DELIVERY", r"deliver.*(varian|discrepan|missing|partial|reject)|variance|discrepan"),
    ("EXCEPTION", r"exception|block.*issue|unresolved|open.*issue"),
    ("FPS_STATUS", r"\bfps[- ]?(\d+)\b"),
    ("DEMAND", r"demand|intent.*forecast|forecast.*intent|anomal"),
]


def classify(question: str) -> str:
    q = (question or "").lower()
    for key, pattern in _PATTERNS:
        if re.search(pattern, q):
            return key
    return "HELP"


def _fps_in_scope(conn, fps_id: str) -> bool:
    return bool(one(conn, "SELECT 1 FROM fps WHERE fps_id = %s", (fps_id,)))


def _fps_ids_in(text: str) -> list[str]:
    return [f"FPS-{m}" for m in re.findall(r"fps[- ]?0*(\d+)", (text or "").lower())]


def answer_dso(conn, cycle: str, question: str) -> dict:
    """DSO-scoped grounded answer. All data reads are cycle-scoped real rows."""
    from backend.services.intelligence import anomalies as an
    from backend.services.intelligence import risk as rk
    intent = classify(question)
    fps_refs = _fps_ids_in(question)
    evidence: list[dict] = []
    calcs: list[dict] = []
    sources = ["intent_signals", "demand_forecast", "allocations", "exceptions",
               "dispatch_manifests", "delivery_history", "audit_events"]

    if intent == "ALLOCATION_WHY" and fps_refs:
        parts = []
        for fps_id in fps_refs:
            if not _fps_in_scope(conn, fps_id):
                parts.append(f"{fps_id}: DATA NOT AVAILABLE — no such FPS record exists.")
                continue
            for commodity in ("RICE", "WHEAT"):
                r = ex.explain_allocation(conn, cycle, fps_id, commodity)
                if r["answer"] != "DATA NOT AVAILABLE":
                    parts.append(f"[{commodity}] {r['answer']}")
                    evidence.extend(r["evidence"])
        answer = " ".join(parts) if parts else "DATA NOT AVAILABLE — no allocation records match."
        return _resp(answer, evidence, calcs, sources, intent)
    if intent == "CLOSE_WHY":
        r = ex.explain_closure_blockers(conn, cycle)
        return _resp(r["answer"], r["evidence"], [r["detail"]], sources, intent)
    if intent == "ATTENTION":
        brief = ex.ops_brief(conn, cycle)
        fps_all = brief["fps_needing_attention"]
        shown = ", ".join(fps_all[:10]) or "none"
        extra = f" (+{len(fps_all) - 10} more — see the anomalies list)" if len(fps_all) > 10 else ""
        answer = (f"FPS locations needing attention in {cycle}: {shown}{extra}."
                  f" Demand anomalies: {brief['counts']['demand_anomalies']}."
                  f" Stock risks: {brief['counts']['stock_risks']}."
                  f" Dispatch risks: {brief['counts']['dispatch_risks']}.")
        return _resp(answer, [{"record": t, "value": brief["counts"].get(t, 0)}
                              for t in ("demand_anomalies", "stock_risks", "dispatch_risks")],
                     [brief["counts"]], sources, intent)
    if intent == "STOCK":
        risks = rk.stockout_risks(conn, cycle)
        highs = [r for r in risks if r["severity"] == "HIGH"]
        answer = (f"{len(risks)} stock signal(s) in {cycle}"
                  + (f", {len(highs)} high: " + "; ".join(r["summary"] for r in highs[:3]) if highs
                     else ", none high.") if risks else f"No stock risks detected in {cycle}.")
        return _resp(answer, [e for r in risks[:5] for e in r["evidence"]], [], sources, intent)
    if intent == "DISPATCH_READY":
        risks = rk.dispatch_risks(conn, cycle)
        highs = [r for r in risks if r["severity"] == "HIGH"]
        answer = ("DISPATCH RISK " + ("HIGH" if highs else "LOW") + ". "
                  + ("Reasons: " + " ".join("• " + r["summary"] for r in risks[:5]) if risks
                     else "No blockers detected in current records."))
        return _resp(answer, [e for r in risks[:5] for e in r["evidence"]], [], sources, intent)
    if intent == "DELIVERY":
        rec = an.reconciliation_anomalies(conn, cycle)
        answer = (f"{len(rec)} reconciliation variance(s) in {cycle}."
                  + ("" if not rec else " " + " ".join(
                      f"{r['entity_id']}/{r.get('commodity')}: expected {r['expected_value']} kg,"
                      f" actual {r['observed_value']} kg." for r in rec[:3])))
        if not rec:
            answer = f"No reconciliation variances detected in {cycle}."
        return _resp(answer, [e for r in rec[:3] for e in r["evidence"]], [], sources, intent)
    if intent == "EXCEPTION":
        items = rk.exception_intel(conn, cycle, limit=5)
        answer = (f"{len(items)} exception(s) on record for {cycle}."
                  + ("" if not items else " Latest: " + "; ".join(
                      i["title"] + f" ({i['severity']}, {i['calculation'].get('status')})"
                      for i in items[:3])))
        if not items:
            answer = f"No exceptions recorded for {cycle}."
        return _resp(answer, [e for i in items[:3] for e in i["evidence"]], [], sources, intent)
    if intent == "FPS_STATUS" and fps_refs:
        parts = []
        for fps_id in fps_refs:
            if not _fps_in_scope(conn, fps_id):
                parts.append(f"{fps_id}: DATA NOT AVAILABLE — no such FPS record exists.")
                continue
            bal = [b for b in sig.mass_balance(conn, cycle) if b["fps_id"] == fps_id]
            if not bal:
                parts.append(f"{fps_id}: DATA NOT AVAILABLE — no cycle records for {cycle}.")
                continue
            for b in bal:
                parts.append(f"{fps_id}/{b['commodity']}: allocated {b['allocated_kg']} kg,"
                             f" dispatched {b['dispatched_kg']} kg, received {b['received_kg']} kg.")
                evidence.append({"record": "allocations+dispatch+delivery", "value": fps_id})
        return _resp(" ".join(parts) if parts else "DATA NOT AVAILABLE.", evidence, [], sources, intent)
    if intent == "DEMAND":
        anomalies = an.demand_anomalies(conn, cycle)
        answer = (f"{len(anomalies)} demand anomalie(s) in {cycle}."
                  + ("" if not anomalies else " " + " ".join(
                      f"{a['entity_id']}/{a['commodity']}: observed {a['observed_value']} kg vs"
                      f" expected {a['expected_value']} kg ({a['detection_method']})."
                      for a in anomalies[:3])))
        if not anomalies:
            answer = f"No significant demand deviations detected in {cycle}."
        return _resp(answer, [e for a in anomalies[:3] for e in a["evidence"]], [], sources, intent)
    return _resp("I can explain allocations, demand anomalies, stock risk, dispatch readiness,"
                 " delivery variances, exceptions, closure blockers, or which FPS need attention —"
                 f" all from {cycle} records. Ask with an FPS id for specifics.",
                 [], [], sources, "HELP")


def answer_beneficiary(conn, beneficiary_id: str, question: str) -> dict:
    """Strictly scoped to the beneficiary's own records. Never exposes others."""
    from backend.services import assistant as legacy
    ctx = sig.beneficiary_context(conn, beneficiary_id, None)
    if ctx is None or ctx.get("cycle") is None:
        return _resp("Data unavailable — no active cycle or profile found.", [], [], [], "HELP")
    cycle = ctx["cycle"]
    q = (question or "").lower()
    if re.search(r"collect|availab|ration|shop|fps|deliver|dispatch|reach|arriv", q):
        stage = ctx.get("stage") or "NONE"
        ent = ctx.get("entitlement") or {}
        fps = (ctx.get("profile") or {}).get("fps", {})
        answer = (f"For {cycle}: your shop {fps.get('name', fps.get('fps_id'))} stage is {stage}."
                  f" Your remaining entitlement is {ent.get('remaining_total_kg')} kg.")
        evidence = [{"record": "beneficiaries+epos_transactions", "value": beneficiary_id}]
    elif re.search(r"entitle|how much|quota|\bkg\b|remain|left", q):
        ent = ctx.get("entitlement") or {}
        answer = (f"In {cycle} you are entitled to {ent.get('rice_kg')} kg rice and"
                  f" {ent.get('wheat_kg')} kg wheat. {ent.get('collected_total_kg')} kg collected,"
                  f" {ent.get('remaining_total_kg')} kg remains.")
        evidence = [{"record": "beneficiaries + epos_transactions", "value": beneficiary_id}]
    else:
        legacy_ans = legacy.answer(conn, beneficiary_id, question, None, "en")
        return _resp(legacy_ans["answer"],
                     [{"record": legacy_ans.get("source") or "beneficiary records",
                       "value": beneficiary_id}], [], ["intent_signals", "epos_transactions"],
                     legacy_ans.get("intent", "HELP"))
    return _resp(answer, evidence, [],
                 ["beneficiaries", "epos_transactions", "intent_signals"], classify(question))


def _resp(answer, evidence, calculations, sources, intent) -> dict:
    from backend.services.forecast import MODEL_VERSION as XGB_VERSION
    return {"answer": answer, "evidence": evidence, "calculations": calculations,
            "sources": sources, "intent": intent,
            "model": "rule-intelligence-v1 (+ " + XGB_VERSION + " forecast where cited)",
            "model_version": "rule-intelligence-v1", "advisory": True}
