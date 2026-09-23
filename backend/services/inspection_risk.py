"""Phase 3: inspection risk assessment boundary.

Uses only real application data (inventory, e-PoS transactions, grievances,
previous inspections, stockouts). Produces a prioritisation score + reasons.
It NEVER fabricates findings — the inspector's own findings are recorded
separately and are never auto-filled from this assessment.
"""
from backend.services.beneficiary import rows as _rows, one as _one


def _fps_list(conn, district: str | None) -> list[dict]:
    if district:
        return _rows(conn,
                     "SELECT fps_id, fps_name, owner_id, district, taluk, latitude, longitude,"
                     " capacity_kg, warehouse_id, status FROM fps WHERE district = %s ORDER BY fps_id",
                     (district,))
    return _rows(conn,
                 "SELECT fps_id, fps_name, owner_id, district, taluk, latitude, longitude,"
                 " capacity_kg, warehouse_id, status FROM fps ORDER BY fps_id")


def _signals(conn, fps_id: str) -> dict:
    last_insp = _one(conn,
                     "SELECT inspection_id, inspection_date, finding, status FROM inspections"
                     " WHERE fps_id = %s ORDER BY inspection_date DESC LIMIT 1", (fps_id,))
    inv = _rows(conn,
                "SELECT commodity, closing_stock_kg, cycle FROM inventory"
                " WHERE location_type = 'FPS' AND location_id = %s ORDER BY cycle DESC LIMIT 4", (fps_id,))
    griev = _one(conn,
                 "SELECT count(*) AS total,"
                 " count(*) FILTER (WHERE status NOT IN ('RESOLVED','CLOSED')) AS open,"
                 " count(*) FILTER (WHERE created_at > now() - interval '90 days') AS recent"
                 " FROM grievances WHERE fps_id = %s", (fps_id,)) or {}
    epos = _one(conn,
                "SELECT count(*) FILTER (WHERE status='SUCCESS') AS ok,"
                 " count(*) FILTER (WHERE status IN ('CANCELLED','FAILED')) AS failed,"
                 " count(*) FILTER (WHERE status='SUCCESS' AND (EXTRACT(HOUR FROM transaction_time) < 6"
                 "  OR EXTRACT(HOUR FROM transaction_time) >= 22)) AS odd_hours"
                " FROM epos_transactions WHERE fps_id = %s"
                " AND transaction_time > now() - interval '90 days'", (fps_id,)) or {}
    stockout = _one(conn,
                    "SELECT COALESCE(sum(stockout_days),0) AS days, COALESCE(sum(shortage_kg),0) AS shortage"
                    " FROM historical_stockouts WHERE fps_id = %s", (fps_id,)) or {}
    variance = _one(conn,
                    "SELECT COALESCE(sum(ABS(stock_variance_kg)),0) AS total_variance, count(*) AS n"
                    " FROM inspections WHERE fps_id = %s", (fps_id,)) or {}
    return {"last_inspection": last_insp, "inventory": inv, "grievances": griev,
            "epos": epos, "stockout": stockout, "variance": variance}


def assess(conn, fps: dict) -> dict:
    """Risk assessment for one FPS row. Returns score/level/factors/focus."""
    s = _signals(conn, fps["fps_id"])
    factors: list[dict] = []

    def add(key: str, label: str, level: str, detail: str, weight: int):
        factors.append({"key": key, "label": label, "level": level, "detail": detail, "weight": weight})

    g = s["grievances"] or {}
    g_total, g_open, g_recent = int(g.get("total") or 0), int(g.get("open") or 0), int(g.get("recent") or 0)
    if g_open >= 3 or g_recent >= 4:
        add("complaints", "Recent complaints", "HIGH", f"{g_recent} in last 90 days, {g_open} open", 30)
    elif g_recent >= 1 or g_total >= 3:
        add("complaints", "Recent complaints", "MEDIUM", f"{g_recent} in last 90 days, {g_total} total", 15)

    v = s["variance"] or {}
    var_total = float(v.get("total_variance") or 0)
    if var_total >= 200:
        add("inventory", "Inventory discrepancy", "HIGH", f"Cumulative stock variance {var_total:.0f} kg", 30)
    elif var_total >= 50:
        add("inventory", "Inventory discrepancy", "MEDIUM", f"Cumulative stock variance {var_total:.0f} kg", 15)

    e = s["epos"] or {}
    failed, odd = int(e.get("failed") or 0), int(e.get("odd_hours") or 0)
    if failed >= 10 or odd >= 5:
        add("transactions", "Transaction anomaly", "HIGH", f"{failed} failed/cancelled, {odd} odd-hour (90d)", 25)
    elif failed >= 3 or odd >= 1:
        add("transactions", "Transaction anomaly", "MEDIUM", f"{failed} failed/cancelled, {odd} odd-hour (90d)", 12)

    st = s["stockout"] or {}
    if int(st.get("days") or 0) >= 5:
        add("stockout", "Stockout history", "MEDIUM",
            f"{st['days']} stockout days, shortage {st['shortage']} kg", 12)

    li = s["last_inspection"]
    if li is None:
        add("never_inspected", "Never inspected", "MEDIUM", "No inspection record for this FPS", 10)
    elif (li.get("finding") or "").upper() not in ("", "NONE", "NO_ISSUE", "OK"):
        add("prior_finding", "Prior adverse finding", "MEDIUM", f"Last: {li.get('finding')}", 10)

    score = min(100, sum(f["weight"] for f in factors))
    level = "HIGH" if score >= 40 else ("MEDIUM" if score >= 15 else "LOW")
    focus = []
    keys = {f["key"] for f in factors}
    if "inventory" in keys or "never_inspected" in keys:
        focus.append("Physical stock verification")
    if "transactions" in keys:
        focus.append("e-PoS transaction review")
    if "complaints" in keys:
        focus.append("Beneficiary transaction verification")
    if "stockout" in keys:
        focus.append("Stock register vs distribution records")
    if not focus:
        focus.append("Routine compliance verification")
    return {"score": score, "level": level, "factors": factors, "focus": focus, "signals": s}
