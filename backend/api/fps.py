"""Phase 4: FPS Owner operations API.

Every value is read from or written to PostgreSQL; nothing is defaulted, mocked, or invented.
The shop is never taken from the client: an FPS_OWNER token is scoped to the shop(s) whose
owner_id matches the officer, while DSO/AUDITOR must name an explicit ?fps_id. All writes are
audited, and official records (e-PoS transactions, ledger postings) are only created through
the validated flows below — never edited or deleted afterwards.
"""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.core.audit import write_audit
from backend.core.auth_middleware import require_permission
from backend.core.errors import ApiError
from backend.core.rbac import Permission, Role
from backend.db.conn import get_db
from backend.services.beneficiary import iso, num, one, rows

router = APIRouter(prefix="/api/v1/fps", tags=["fps"])

ReadShop = Depends(require_permission(Permission.VIEW_FPS))
ReadStock = Depends(require_permission(Permission.VIEW_FPS_INVENTORY))
ReadTxns = Depends(require_permission(Permission.VIEW_FPS_TRANSACTIONS))
WriteOps = Depends(require_permission(Permission.PROCESS_EPOS))
ManageSupply = Depends(require_permission(Permission.MANAGE_CYCLE))

COMMODITIES = ("RICE", "WHEAT")
TERMINAL_TXN = ("SUCCESS", "CANCELLED", "FAILED")
# Forward-only request lifecycle. FPS owners move DRAFT->SUBMITTED and DISPATCHED->RECEIVED;
# DSO moves everything in between (see _OWNER_MOVES / _DSO_MOVES).
_OWNER_MOVES = {("DRAFT", "SUBMITTED"), ("DISPATCHED", "RECEIVED")}
_DSO_MOVES = {("SUBMITTED", "UNDER_REVIEW"), ("SUBMITTED", "REJECTED"),
              ("UNDER_REVIEW", "APPROVED"), ("UNDER_REVIEW", "REJECTED"),
              ("APPROVED", "DISPATCHED"), ("DISPATCHED", "RECEIVED")}
_ALL_STATUSES = ("DRAFT", "SUBMITTED", "UNDER_REVIEW", "APPROVED", "DISPATCHED", "RECEIVED", "REJECTED")
# A cover indicator is derived from the shop's own observed distribution rate. There is no
# statutory minimum-stock configuration in the database, so this is labelled as derived.
COVER_WATCH_DAYS = 7.0


# ------------------------------------------------------------------ helpers

def _cycle(conn, cycle: str | None = None) -> dict:
    if cycle:
        c = one(conn, "SELECT cycle, state FROM cycles WHERE cycle = %s", (cycle,))
        if not c:
            raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
        return c
    c = one(conn, "SELECT cycle, state FROM cycles WHERE state <> 'CLOSED' ORDER BY cycle DESC LIMIT 1")
    if not c:
        raise ApiError(404, "NO_ACTIVE_CYCLE", "There is no active cycle right now.")
    return c


def _shop(conn, user: dict, fps_id: str | None) -> dict:
    role = user["role"]
    if role == Role.FPS_OWNER.value:
        owned = rows(conn, "SELECT fps_id FROM fps WHERE owner_id = %s ORDER BY fps_id", (user["user_id"],))
        if not owned:
            raise ApiError(403, "NO_SHOP_ASSIGNED", "No Fair Price Shop is assigned to this account.")
        if fps_id and fps_id not in {r["fps_id"] for r in owned}:
            raise ApiError(403, "FORBIDDEN", "This shop is not assigned to your account.")
        fps_id = fps_id or owned[0]["fps_id"]
    elif role in (Role.DSO.value, Role.AUDITOR.value, Role.SYSTEM_ADMIN.value):
        if not fps_id:
            raise ApiError(422, "FPS_REQUIRED", "Pass ?fps_id to inspect a shop.")
    else:
        raise ApiError(403, "FORBIDDEN", "This section is for FPS operations staff.")
    shop = one(conn, """SELECT f.fps_id, f.fps_name, f.district, f.taluk, f.latitude, f.longitude,
                               f.capacity_kg, f.warehouse_id, f.status, f.opening_hours,
                               o.officer_id AS owner_id, o.name AS owner_name, o.phone AS owner_phone
                        FROM fps f LEFT JOIN officers o ON o.officer_id = f.owner_id
                        WHERE f.fps_id = %s""", (fps_id,))
    if not shop:
        raise ApiError(404, "FPS_NOT_FOUND", f"FPS {fps_id} does not exist.")
    return shop


def _inventory(conn, fps_id: str, cycle: str) -> list[dict]:
    return rows(conn, """SELECT commodity, opening_stock_kg, received_kg, dispatched_kg,
                                distributed_kg, adjusted_kg, closing_stock_kg
                         FROM inventory WHERE location_type = 'FPS' AND location_id = %s AND cycle = %s
                         ORDER BY commodity""", (fps_id, cycle))


def _inv_map(conn, fps_id: str, cycle: str) -> dict:
    return {r["commodity"]: r for r in _inventory(conn, fps_id, cycle)}


def _epos_sums(conn, fps_id: str, cycle: str) -> dict:
    return {r["commodity"]: r["kg"] for r in rows(conn, """
        SELECT commodity, COALESCE(sum(quantity_kg), 0) AS kg FROM epos_transactions
        WHERE fps_id = %s AND cycle = %s AND status = 'SUCCESS' GROUP BY commodity""", (fps_id, cycle))}


def _delivery_sums(conn, fps_id: str, cycle: str) -> dict:
    return {r["commodity"]: r["kg"] for r in rows(conn, """
        SELECT mi.commodity AS commodity, COALESCE(sum(d.delivered_kg), 0) AS kg
        FROM delivery_history d JOIN dispatch_manifest_items mi ON mi.manifest_item_id = d.manifest_item_id
        JOIN dispatch_manifests m ON m.manifest_id = d.manifest_id
        WHERE d.fps_id = %s AND m.cycle = %s AND d.status IN ('VERIFIED','VARIANCE')
        GROUP BY mi.commodity""", (fps_id, cycle))}


def _today_counts(conn, fps_id: str) -> dict:
    r = one(conn, """SELECT count(*) AS txns,
                            count(*) FILTER (WHERE status = 'SUCCESS') AS success,
                            count(*) FILTER (WHERE status = 'FAILED') AS failed,
                            count(*) FILTER (WHERE status = 'CANCELLED') AS cancelled,
                            COALESCE(sum(quantity_kg) FILTER (WHERE status = 'SUCCESS'), 0) AS kg,
                            count(DISTINCT beneficiary_id) FILTER (WHERE status = 'SUCCESS') AS beneficiaries
                     FROM epos_transactions
                     WHERE fps_id = %s AND transaction_time::date = CURRENT_DATE""", (fps_id,))
    return r or {"txns": 0, "success": 0, "failed": 0, "cancelled": 0, "kg": 0, "beneficiaries": 0}


def _cycle_counts(conn, fps_id: str, cycle: str) -> dict:
    r = one(conn, """SELECT count(*) AS txns,
                            count(*) FILTER (WHERE status = 'SUCCESS') AS success,
                            count(*) FILTER (WHERE status = 'FAILED') AS failed,
                            count(*) FILTER (WHERE status = 'CANCELLED') AS cancelled,
                            COALESCE(sum(quantity_kg) FILTER (WHERE status = 'SUCCESS'), 0) AS kg,
                            count(DISTINCT beneficiary_id) FILTER (WHERE status = 'SUCCESS') AS beneficiaries
                     FROM epos_transactions WHERE fps_id = %s AND cycle = %s""", (fps_id, cycle))
    return r or {"txns": 0, "success": 0, "failed": 0, "cancelled": 0, "kg": 0, "beneficiaries": 0}


def _reconciliation(conn, fps_id: str, cycle: str) -> list[dict]:
    """Ledger vs source records, per commodity. The inventory balance equation always holds by
    constraint; what is genuinely checked is whether the ledger's movements match the records
    behind them: e-PoS SUCCESS lines vs distributed_kg, and verified deliveries vs received_kg."""
    inv = _inv_map(conn, fps_id, cycle)
    epos = _epos_sums(conn, fps_id, cycle)
    delivered = _delivery_sums(conn, fps_id, cycle)
    alloc = {r["commodity"]: r for r in rows(conn,
             "SELECT commodity, allocated_kg, status FROM allocations WHERE fps_id = %s AND cycle = %s",
             (fps_id, cycle))}
    reviews = {(r["commodity"]): r for r in rows(conn, """
        SELECT DISTINCT ON (commodity) commodity, variance_kg, note, reviewed_by, created_at
        FROM fps_variance_reviews WHERE fps_id = %s AND cycle = %s ORDER BY commodity, created_at DESC""",
        (fps_id, cycle))}
    out = []
    for c in COMMODITIES:
        row = inv.get(c, {})
        dist_var = num((row.get("distributed_kg") or 0) - (epos.get(c) or 0))
        recv_var = num((row.get("received_kg") or 0) - (delivered.get(c) or 0))
        rev = reviews.get(c)
        out.append({
            "commodity": c,
            "opening_stock_kg": row.get("opening_stock_kg"),
            "received_kg": row.get("received_kg"),
            "dispatched_kg": row.get("dispatched_kg"),
            "distributed_kg": row.get("distributed_kg"),
            "adjusted_kg": row.get("adjusted_kg"),
            "ledger_closing_kg": row.get("closing_stock_kg"),
            "epos_success_kg": epos.get(c, 0),
            "verified_deliveries_kg": delivered.get(c, 0),
            "allocated_kg": (alloc.get(c) or {}).get("allocated_kg"),
            "allocation_status": (alloc.get(c) or {}).get("status"),
            "distribution_variance_kg": dist_var,
            "receipt_variance_kg": recv_var,
            "has_ledger": bool(row),
            "reconciled": bool(row) and dist_var == 0 and recv_var == 0,
            "review": ({**rev, "created_at": iso(rev["created_at"])} if rev else None),
        })
    return out


def _alerts(conn, fps_id: str, cycle: str) -> list[dict]:
    inv = _inv_map(conn, fps_id, cycle)
    epos = _epos_sums(conn, fps_id, cycle)
    out = []
    for c in COMMODITIES:
        row = inv.get(c)
        if row and (row.get("closing_stock_kg") or 0) <= 0 and (epos.get(c) or 0) > 0:
            out.append({"severity": "HIGH", "code": "STOCK_DEPLETED",
                        "message": f"{c} ledger closing stock is exhausted for {cycle}."})
    failed_today = one(conn, """SELECT count(*) AS n FROM epos_transactions
                                WHERE fps_id = %s AND transaction_time::date = CURRENT_DATE
                                AND status = 'FAILED'""", (fps_id,))["n"]
    if failed_today:
        out.append({"severity": "MEDIUM", "code": "EPOS_FAILURES_TODAY",
                    "message": f"{failed_today} e-PoS transaction(s) failed today."})
    rec = _reconciliation(conn, fps_id, cycle)
    for r in rec:
        if r["has_ledger"] and (r["distribution_variance_kg"] or r["receipt_variance_kg"]) and not r["review"]:
            out.append({"severity": "HIGH", "code": "UNREVIEWED_VARIANCE",
                        "message": f"{r['commodity']} shows an unreviewed ledger variance in {cycle}."})
    pending = one(conn, """SELECT count(*) AS n FROM fps_stock_requests
                           WHERE fps_id = %s AND status IN ('SUBMITTED','UNDER_REVIEW','APPROVED','DISPATCHED')""",
                  (fps_id,))["n"]
    if pending:
        out.append({"severity": "LOW", "code": "REQUESTS_IN_FLIGHT",
                    "message": f"{pending} replenishment request(s) awaiting supply."})
    insp = one(conn, """SELECT inspection_id, inspection_date, status FROM inspections
                        WHERE fps_id = %s ORDER BY inspection_date DESC LIMIT 1""", (fps_id,))
    if insp:
        out.append({"severity": "LOW", "code": "LAST_INSPECTION",
                    "message": f"Last inspection {insp['inspection_id']} ({insp['status']}) on "
                               f"{iso(insp['inspection_date'])}."})
    return out


def _insights(conn, fps_id: str, cycle: str) -> list[dict]:
    """Advisory only: depletion cover from the shop's own observed rate, demand vs allocation,
    and anomalous distribution days. Never a decision, never a write."""
    inv = _inv_map(conn, fps_id, cycle)
    daily = rows(conn, """SELECT transaction_time::date AS d, commodity,
                                 COALESCE(sum(quantity_kg), 0) AS kg, count(*) AS n
                          FROM epos_transactions
                          WHERE fps_id = %s AND cycle = %s AND status = 'SUCCESS'
                          GROUP BY 1, 2 ORDER BY 1""", (fps_id, cycle))
    out = []
    for c in COMMODITIES:
        rows_c = [r for r in daily if r["commodity"] == c]
        if not rows_c:
            continue
        total = sum(r["kg"] for r in rows_c)
        days = len({str(r["d"]) for r in rows_c})
        rate = total / days if days else 0
        closing = (inv.get(c) or {}).get("closing_stock_kg") or 0
        if rate > 0:
            cover = closing / rate
            out.append({
                "type": "DEPLETION_COVER", "commodity": c, "severity": "HIGH" if cover < COVER_WATCH_DAYS else "LOW",
                "headline": f"{c} covers about {cover:.1f} day(s) at the recent distribution rate.",
                "detail": f"Closing {num(closing)} kg / recent rate {rate:.1f} kg per active day "
                          f"over {days} active day(s) in {cycle}. Derived indicator — no statutory "
                          f"minimum is configured.",
                "recommended_action": "Review replenishment requirement." if cover < COVER_WATCH_DAYS else None,
            })
        ns = [r["n"] for r in rows_c]
        if len(ns) >= 5:
            mean = sum(ns) / len(ns)
            var = sum((x - mean) ** 2 for x in ns) / len(ns)
            sd = var ** 0.5
            spikes = [r for r in rows_c if sd > 0 and r["n"] > mean + 3 * sd]
            for s in spikes[:3]:
                out.append({
                    "type": "UNUSUAL_ACTIVITY", "commodity": c, "severity": "MEDIUM",
                    "headline": f"Unusually busy distribution day: {s['d']} ({s['n']} transactions).",
                    "detail": f"Daily mean is {mean:.1f} transactions (sd {sd:.1f}). Flagged for review only.",
                    "recommended_action": "Cross-check the day's transaction list.",
                })
    alloc = {r["commodity"]: r["allocated_kg"] for r in rows(conn,
             "SELECT commodity, allocated_kg FROM allocations WHERE fps_id = %s AND cycle = %s", (fps_id, cycle))}
    epos = _epos_sums(conn, fps_id, cycle)
    for c in COMMODITIES:
        if alloc.get(c) and (epos.get(c) or 0) >= alloc[c]:
            out.append({"type": "ALLOCATION_CONSUMED", "commodity": c, "severity": "MEDIUM",
                        "headline": f"{c} distribution ({num(epos[c])} kg) has reached the allocation ({num(alloc[c])} kg).",
                        "detail": "Further distribution may need a fresh allocation or an approved request.",
                        "recommended_action": "Raise a replenishment request if demand continues."})
    return out


# ------------------------------------------------------------------ context

@router.get("/me")
def my_shop(fps_id: str | None = None, user=ReadShop, conn=Depends(get_db)):
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn)
    return {"shop": shop, "owner": {"owner_id": shop.pop("owner_id"), "name": shop.pop("owner_name"),
                                   "phone": shop.pop("owner_phone")},
            "cycle": c, "today": date.today().isoformat(),
            "operational_status": "NORMAL" if shop["status"] == "ACTIVE" else shop["status"]}


@router.get("/me/shops")
def my_shops(user=ReadShop, conn=Depends(get_db)):
    if user["role"] != Role.FPS_OWNER.value:
        raise ApiError(403, "FORBIDDEN", "Only FPS owners list assigned shops.")
    return {"shops": rows(conn, "SELECT fps_id, fps_name, district, taluk, status FROM fps "
                                "WHERE owner_id = %s ORDER BY fps_id", (user["user_id"],))}


# ------------------------------------------------------------------ overview

@router.get("/me/overview")
def overview(fps_id: str | None = None, cycle: str | None = None, user=ReadShop, conn=Depends(get_db)):
    shop = _shop(conn, user, fps_id)
    fid = shop["fps_id"]
    c = _cycle(conn, cycle)
    cyc = c["cycle"]
    inv = _inventory(conn, fid, cyc)
    epos = _epos_sums(conn, fid, cyc)
    alloc = {r["commodity"]: r for r in rows(conn,
             "SELECT commodity, allocated_kg, status FROM allocations WHERE fps_id = %s AND cycle = %s", (fid, cyc))}
    stock = []
    for r in inv:
        a = alloc.get(r["commodity"], {})
        stock.append({**r, "allocated_kg": a.get("allocated_kg"), "allocation_status": a.get("status"),
                      "distributed_epos_kg": epos.get(r["commodity"], 0)})
    today = _today_counts(conn, fid)
    cyc_counts = _cycle_counts(conn, fid, cyc)
    assigned = one(conn, "SELECT count(*) AS n FROM beneficiaries WHERE current_fps_id = %s AND status = 'ACTIVE'",
                   (fid,))["n"]
    collected = one(conn, """SELECT count(DISTINCT beneficiary_id) AS n FROM epos_transactions
                             WHERE fps_id = %s AND cycle = %s AND status = 'SUCCESS'""", (fid, cyc))["n"]
    last_sync = one(conn, "SELECT max(transaction_time) AS t FROM epos_transactions WHERE fps_id = %s", (fid,))["t"]
    pending = max(assigned - collected, 0)
    return {
        "shop": {"fps_id": fid, "fps_name": shop["fps_name"], "status": shop["status"],
                 "district": shop["district"], "taluk": shop.get("taluk")},
        "cycle": c, "today": date.today().isoformat(),
        "status": {"shop_status": shop["status"], "cycle": cyc, "last_activity_at": iso(last_sync),
                   "today": today, "cycle_totals": cyc_counts},
        "stock": stock,
        "distribution": {"assigned_beneficiaries": assigned, "served_this_cycle": collected,
                         "pending_collections": pending, "today": today, "cycle": cyc_counts},
        "alerts": _alerts(conn, fid, cyc),
        "insights": _insights(conn, fid, cyc)[:5],
        "next_action": (f"{pending} beneficiary collection(s) are pending in {cyc}." if pending
                        else f"All assigned beneficiaries have collected in {cyc}."),
    }


# ------------------------------------------------------------------ stock

@router.get("/me/stock")
def stock(fps_id: str | None = None, cycle: str | None = None, user=ReadStock, conn=Depends(get_db)):
    shop = _shop(conn, user, fps_id)
    fid = shop["fps_id"]
    c = _cycle(conn, cycle)
    cyc = c["cycle"]
    inv = _inv_map(conn, fid, cyc)
    epos = _epos_sums(conn, fid, cyc)
    alloc = {r["commodity"]: r for r in rows(conn,
             "SELECT commodity, allocated_kg, status FROM allocations WHERE fps_id = %s AND cycle = %s", (fid, cyc))}
    cards = []
    for com in COMMODITIES:
        r = inv.get(com, {})
        closing = r.get("closing_stock_kg")
        cards.append({
            "commodity": com, **{k: r.get(k) for k in
              ("opening_stock_kg", "received_kg", "dispatched_kg", "distributed_kg", "adjusted_kg", "closing_stock_kg")},
            "allocated_kg": (alloc.get(com) or {}).get("allocated_kg"),
            "allocation_status": (alloc.get(com) or {}).get("status"),
            "distributed_epos_kg": epos.get(com, 0),
            "has_ledger": bool(r),
            # No statutory minimum is configured: availability is reported, not graded.
            "availability": ("EXHAUSTED" if closing is not None and closing <= 0
                             else "AVAILABLE" if closing is not None else "NO_LEDGER"),
        })
    movements = rows(conn, """SELECT event_id AS id, created_at AS at, commodity, event_type AS type,
                                     quantity_kg AS quantity, reason, reference, recorded_by, 'STOCK_EVENT' AS source
                              FROM fps_stock_events WHERE fps_id = %s AND cycle = %s
                              UNION ALL
                              SELECT delivery_id AS id, delivery_date AS at, mi.commodity, 'DELIVERY' AS type,
                                     d.delivered_kg AS quantity, d.status AS reason, d.manifest_id AS reference,
                                     d.verified_by AS recorded_by, 'DELIVERY' AS source
                              FROM delivery_history d JOIN dispatch_manifest_items mi
                                ON mi.manifest_item_id = d.manifest_item_id
                              JOIN dispatch_manifests m ON m.manifest_id = d.manifest_id
                              WHERE d.fps_id = %s AND m.cycle = %s
                              ORDER BY at DESC LIMIT 50""", (fid, cyc, fid, cyc))
    for m in movements:
        m["at"] = iso(m["at"])
    return {"fps_id": fid, "cycle": cyc, "cards": cards, "movements": movements,
            "note": "Minimum levels are not configured in the system; availability is reported as recorded."}


class ReceiveStock(BaseModel):
    commodity: str = Field(pattern="^(RICE|WHEAT)$")
    quantity_kg: float = Field(gt=0, le=100000)
    reason: str = Field(min_length=3, max_length=500)
    reference: str | None = Field(default=None, max_length=64)
    cycle: str | None = None


@router.post("/me/stock/receive", status_code=201)
def receive_stock(req: ReceiveStock, fps_id: str | None = None, user=WriteOps, conn=Depends(get_db)):
    if user["role"] != Role.FPS_OWNER.value:
        raise ApiError(403, "FORBIDDEN", "Only the FPS owner records stock receipts.")
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, req.cycle)
    cyc = c["cycle"]
    row = one(conn, """SELECT inventory_id, received_kg, closing_stock_kg FROM inventory
                       WHERE location_type = 'FPS' AND location_id = %s AND cycle = %s AND commodity = %s""",
              (shop["fps_id"], cyc, req.commodity))
    if not row:
        raise ApiError(422, "NO_LEDGER", f"No inventory ledger exists for {req.commodity} in {cyc}; "
                                        "receipts can only post against an issued allocation ledger.")
    eid = "FSE-%06d" % conn.execute('SELECT nextval(%s)', ('fps_event_seq',)).fetchone()[0]
    conn.execute("""INSERT INTO fps_stock_events (event_id, fps_id, cycle, commodity, event_type, quantity_kg,
                       reason, reference, recorded_by)
                    VALUES (%s, %s, %s, %s, 'RECEIPT', %s, %s, %s, %s)""",
                 (eid, shop["fps_id"], cyc, req.commodity, req.quantity_kg, req.reason.strip(),
                  req.reference, user["user_id"]))
    conn.execute("""UPDATE inventory SET received_kg = received_kg + %s,
                       closing_stock_kg = closing_stock_kg + %s WHERE inventory_id = %s""",
                 (req.quantity_kg, req.quantity_kg, row["inventory_id"]))
    conn.commit()
    write_audit(user["user_id"], user["role"], "STOCK_RECEIVED", "SUCCESS",
                f"{req.quantity_kg} kg {req.commodity} at {shop['fps_id']}", "STOCK_EVENT", eid, cyc,
                before=str(num(row["closing_stock_kg"])),
                after=str(num(row["closing_stock_kg"]) + req.quantity_kg))
    return {"event_id": eid, "fps_id": shop["fps_id"], "cycle": cyc, "commodity": req.commodity,
            "quantity_kg": req.quantity_kg, "closing_stock_kg": num(row["closing_stock_kg"]) + req.quantity_kg}


class AdjustStock(BaseModel):
    commodity: str = Field(pattern="^(RICE|WHEAT)$")
    quantity_kg: float = Field(ge=-100000, le=100000)
    reason: str = Field(min_length=5, max_length=500)
    cycle: str | None = None


@router.post("/me/stock/adjust", status_code=201)
def adjust_stock(req: AdjustStock, fps_id: str | None = None, user=WriteOps, conn=Depends(get_db)):
    """An authorized adjustment posts to the ledger with a mandatory reason and stays in history;
    it can never erase a variance silently — reconciliation still shows the e-PoS comparison."""
    if user["role"] != Role.FPS_OWNER.value:
        raise ApiError(403, "FORBIDDEN", "Only the FPS owner records adjustments.")
    if req.quantity_kg == 0:
        raise ApiError(422, "INVALID_REQUEST", "Adjustment quantity cannot be zero.")
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, req.cycle)
    cyc = c["cycle"]
    row = one(conn, """SELECT inventory_id, closing_stock_kg FROM inventory
                       WHERE location_type = 'FPS' AND location_id = %s AND cycle = %s AND commodity = %s""",
              (shop["fps_id"], cyc, req.commodity))
    if not row:
        raise ApiError(422, "NO_LEDGER", f"No inventory ledger exists for {req.commodity} in {cyc}.")
    if (row["closing_stock_kg"] or 0) + req.quantity_kg < 0:
        raise ApiError(422, "NEGATIVE_STOCK", "This adjustment would take the ledger below zero.")
    eid = "FSE-%06d" % conn.execute('SELECT nextval(%s)', ('fps_event_seq',)).fetchone()[0]
    conn.execute("""INSERT INTO fps_stock_events (event_id, fps_id, cycle, commodity, event_type, quantity_kg,
                       reason, recorded_by)
                    VALUES (%s, %s, %s, %s, 'ADJUSTMENT', %s, %s, %s)""",
                 (eid, shop["fps_id"], cyc, req.commodity, req.quantity_kg, req.reason.strip(), user["user_id"]))
    conn.execute("""UPDATE inventory SET adjusted_kg = adjusted_kg + %s,
                       closing_stock_kg = closing_stock_kg + %s WHERE inventory_id = %s""",
                 (req.quantity_kg, req.quantity_kg, row["inventory_id"]))
    conn.commit()
    write_audit(user["user_id"], user["role"], "STOCK_ADJUSTED", "SUCCESS",
                f"{req.quantity_kg:+} kg {req.commodity} at {shop['fps_id']}: {req.reason.strip()}",
                "STOCK_EVENT", eid, cyc)
    return {"event_id": eid, "fps_id": shop["fps_id"], "cycle": cyc, "commodity": req.commodity,
            "quantity_kg": req.quantity_kg}


# ------------------------------------------------------------------ incoming dispatch

@router.get("/me/incoming")
def incoming(fps_id: str | None = None, cycle: str | None = None, user=ReadShop, conn=Depends(get_db)):
    """Expected incoming stock for this shop: the same dispatch_manifest rows the DSO
    planned and the delivery records behind them. ETA/telemetry are reported as
    unavailable unless the backend actually holds them — never synthesized."""
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, cycle)
    items = rows(conn, """SELECT m.manifest_id, m.cycle, m.warehouse_id, m.vehicle_id, m.manifest_status,
                                 mi.commodity, mi.planned_kg, mi.sequence_number,
                                 d.delivery_id, d.delivered_kg, d.delivery_date, d.status AS delivery_status,
                                 v.vehicle_number
                          FROM dispatch_manifest_items mi
                          JOIN dispatch_manifests m USING (manifest_id)
                          LEFT JOIN delivery_history d ON d.manifest_item_id = mi.manifest_item_id
                          LEFT JOIN vehicles v ON v.vehicle_id = m.vehicle_id
                          WHERE mi.fps_id = %s AND m.cycle = %s
                          ORDER BY m.manifest_id, mi.sequence_number""", (shop["fps_id"], c["cycle"]))
    for it in items:
        it["delivery_date"] = iso(it["delivery_date"])
        it["eta"] = None
        it["live_location"] = None
    return {"fps_id": shop["fps_id"], "cycle": c["cycle"], "items": items,
            "eta_note": "ETA UNAVAILABLE — the platform holds no routing ETA for these stops.",
            "location_note": "LIVE LOCATION UNAVAILABLE — no vehicle telemetry is reported for these manifests."}


# ------------------------------------------------------------------ e-PoS

@router.get("/me/epos")
def epos(fps_id: str | None = None, cycle: str | None = None, user=ReadTxns, conn=Depends(get_db)):
    shop = _shop(conn, user, fps_id)
    fid = shop["fps_id"]
    c = _cycle(conn, cycle)
    cyc = c["cycle"]
    counts = _cycle_counts(conn, fid, cyc)
    today = _today_counts(conn, fid)
    last = one(conn, "SELECT max(transaction_time) AS t FROM epos_transactions WHERE fps_id = %s", (fid,))["t"]
    by_hour = rows(conn, """SELECT extract(hour FROM transaction_time)::int AS hour, count(*) AS n,
                                   COALESCE(sum(quantity_kg) FILTER (WHERE status = 'SUCCESS'), 0) AS kg
                            FROM epos_transactions WHERE fps_id = %s AND cycle = %s
                            GROUP BY 1 ORDER BY 1""", (fid, cyc))
    by_day = rows(conn, """SELECT transaction_time::date AS d, count(*) AS n,
                                  count(*) FILTER (WHERE status = 'SUCCESS') AS success,
                                  count(*) FILTER (WHERE status = 'FAILED') AS failed
                           FROM epos_transactions WHERE fps_id = %s AND cycle = %s
                           GROUP BY 1 ORDER BY 1""", (fid, cyc))
    for r in by_day:
        r["d"] = iso(r["d"])
    recent = rows(conn, """SELECT t.transaction_id, t.beneficiary_id, b.head_of_household AS beneficiary_name,
                                  t.transaction_time, t.commodity, t.quantity_kg, t.status, t.receipt_number
                           FROM epos_transactions t LEFT JOIN beneficiaries b USING (beneficiary_id)
                           WHERE t.fps_id = %s AND t.cycle = %s
                           ORDER BY t.transaction_time DESC LIMIT 20""", (fid, cyc))
    for r in recent:
        r["transaction_time"] = iso(r["transaction_time"])
    # No device telemetry table exists: activity is reported from transactions, never as a
    # fabricated ONLINE/OFFLINE device state.
    return {"fps_id": fid, "cycle": cyc, "device": {"status": "NOT_INSTRUMENTED",
              "note": "No e-PoS device telemetry is reported to this platform; activity below is from "
                      "recorded transactions only.", "last_activity_at": iso(last)},
            "today": today, "cycle_totals": counts, "by_hour": by_hour, "by_day": by_day, "recent": recent}


@router.get("/me/transactions")
def transactions(fps_id: str | None = None, cycle: str | None = None,
                 status: str | None = Query(None, pattern="^(SUCCESS|FAILED|CANCELLED)$"),
                 limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                 user=ReadTxns, conn=Depends(get_db)):
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, cycle)
    args: list = [shop["fps_id"], c["cycle"]]
    q = """SELECT t.transaction_id, t.beneficiary_id, b.head_of_household AS beneficiary_name,
                  t.transaction_time, t.commodity, t.quantity_kg, t.status, t.receipt_number
           FROM epos_transactions t LEFT JOIN beneficiaries b USING (beneficiary_id)
           WHERE t.fps_id = %s AND t.cycle = %s"""
    if status:
        q += " AND t.status = %s"
        args.append(status)
    q += " ORDER BY t.transaction_time DESC LIMIT %s OFFSET %s"
    args += [limit, offset]
    out = rows(conn, q, tuple(args))
    for r in out:
        r["transaction_time"] = iso(r["transaction_time"])
    total = one(conn, "SELECT count(*) AS n FROM epos_transactions WHERE fps_id = %s AND cycle = %s"
                      + (" AND status = %s" if status else ""),
                tuple(args[:2] + ([status] if status else [])))["n"]
    return {"fps_id": shop["fps_id"], "cycle": c["cycle"], "total": total, "transactions": out}


# ------------------------------------------------------------------ beneficiaries

@router.get("/me/beneficiaries")
def beneficiaries(fps_id: str | None = None, cycle: str | None = None, q: str | None = None,
                  pending_only: bool = False, limit: int = Query(50, ge=1, le=200),
                  offset: int = Query(0, ge=0), user=ReadShop, conn=Depends(get_db)):
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, cycle)
    cyc = c["cycle"]
    args: list = [shop["fps_id"], cyc]
    filt = ""
    if q:
        filt += " AND (b.beneficiary_id ILIKE %s OR b.head_of_household ILIKE %s OR b.ration_card_id ILIKE %s)"
        args += [f"%{q}%"] * 3
    if pending_only:
        filt += """ AND NOT EXISTS (SELECT 1 FROM epos_transactions t WHERE t.beneficiary_id = b.beneficiary_id
                                    AND t.cycle = %s AND t.status = 'SUCCESS')"""
        args.append(cyc)
    out = rows(conn, f"""SELECT b.beneficiary_id, b.ration_card_id, b.head_of_household AS name,
                                b.household_size, b.scheme_type AS scheme, b.entitlement_kg,
                                b.rice_entitlement_kg, b.wheat_entitlement_kg, b.status,
                                COALESCE(s.rice_kg, 0) AS collected_rice_kg,
                                COALESCE(s.wheat_kg, 0) AS collected_wheat_kg
                         FROM beneficiaries b
                         LEFT JOIN (SELECT beneficiary_id,
                                           sum(quantity_kg) FILTER (WHERE commodity = 'RICE') AS rice_kg,
                                           sum(quantity_kg) FILTER (WHERE commodity = 'WHEAT') AS wheat_kg
                                    FROM epos_transactions WHERE cycle = %s AND status = 'SUCCESS' GROUP BY 1
                                   ) s USING (beneficiary_id)
                         WHERE b.current_fps_id = %s AND b.status IN ('ACTIVE','MIGRATED') {filt}
                         ORDER BY b.beneficiary_id LIMIT %s OFFSET %s""",
                tuple([cyc, shop["fps_id"]] + args[2:] + [limit, offset]))
    for r in out:
        r["remaining_rice_kg"] = max(r["rice_entitlement_kg"] - r["collected_rice_kg"], 0)
        r["remaining_wheat_kg"] = max(r["wheat_entitlement_kg"] - r["collected_wheat_kg"], 0)
        r["collection_status"] = ("COLLECTED" if r["remaining_rice_kg"] + r["remaining_wheat_kg"] == 0
                                  else "PARTIAL" if r["collected_rice_kg"] + r["collected_wheat_kg"] > 0
                                  else "PENDING")
    total = one(conn, f"SELECT count(*) AS n FROM beneficiaries b WHERE b.current_fps_id = %s AND b.status IN "
                      "('ACTIVE','MIGRATED')" + filt, tuple([shop["fps_id"]] + args[2:]))["n"]
    served = one(conn, """SELECT count(DISTINCT beneficiary_id) AS n FROM epos_transactions
                          WHERE fps_id = %s AND cycle = %s AND status = 'SUCCESS'""", (shop["fps_id"], cyc))["n"]
    return {"fps_id": shop["fps_id"], "cycle": cyc, "total": total, "served_this_cycle": served,
            "beneficiaries": out}


@router.get("/me/beneficiaries/{beneficiary_id}")
def beneficiary_detail(beneficiary_id: str, fps_id: str | None = None, cycle: str | None = None,
                       user=ReadShop, conn=Depends(get_db)):
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, cycle)
    b = one(conn, """SELECT beneficiary_id, ration_card_id, head_of_household AS name, household_size,
                            scheme_type AS scheme, entitlement_kg, rice_entitlement_kg, wheat_entitlement_kg,
                            status, current_fps_id FROM beneficiaries WHERE beneficiary_id = %s""", (beneficiary_id,))
    if not b:
        raise ApiError(404, "BENEFICIARY_NOT_FOUND", f"Beneficiary {beneficiary_id} does not exist.")
    if b["current_fps_id"] != shop["fps_id"]:
        raise ApiError(403, "FORBIDDEN", "This beneficiary is not assigned to your shop.")
    used = {r["commodity"]: r["kg"] for r in rows(conn, """
        SELECT commodity, COALESCE(sum(quantity_kg), 0) AS kg FROM epos_transactions
        WHERE beneficiary_id = %s AND cycle = %s AND status = 'SUCCESS' GROUP BY commodity""",
        (beneficiary_id, c["cycle"]))}
    txns = rows(conn, """SELECT transaction_id, transaction_time, commodity, quantity_kg, status, receipt_number
                         FROM epos_transactions WHERE beneficiary_id = %s AND cycle = %s
                         ORDER BY transaction_time DESC""", (beneficiary_id, c["cycle"]))
    for t in txns:
        t["transaction_time"] = iso(t["transaction_time"])
    used_rice, used_wheat = used.get("RICE", 0), used.get("WHEAT", 0)
    return {"beneficiary": b, "cycle": c["cycle"],
            "entitlement": {"rice_kg": b["rice_entitlement_kg"], "wheat_kg": b["wheat_entitlement_kg"],
                            "total_kg": b["entitlement_kg"],
                            "collected_rice_kg": used_rice, "collected_wheat_kg": used_wheat,
                            "remaining_rice_kg": max(b["rice_entitlement_kg"] - used_rice, 0),
                            "remaining_wheat_kg": max(b["wheat_entitlement_kg"] - used_wheat, 0),
                            "source": "beneficiaries + epos_transactions (SUCCESS)"},
            "transactions": txns}


# ------------------------------------------------------------------ distribution

class Distribute(BaseModel):
    beneficiary_id: str = Field(min_length=1, max_length=32)
    commodity: str = Field(pattern="^(RICE|WHEAT)$")
    quantity_kg: float = Field(gt=0, le=1000)
    cycle: str | None = None
    client_ref: str | None = Field(default=None, max_length=64)


@router.post("/me/distribute", status_code=201)
def distribute(req: Distribute, fps_id: str | None = None, user=WriteOps, conn=Depends(get_db)):
    """The single real distribution flow: verify beneficiary, verify entitlement, check ledger
    stock, record the e-PoS transaction, post to inventory, update collection status implicitly.
    Idempotent on client_ref (stored as receipt_number): a retried sync returns the original."""
    if user["role"] != Role.FPS_OWNER.value:
        raise ApiError(403, "FORBIDDEN", "Only the FPS owner records distributions.")
    shop = _shop(conn, user, fps_id)
    fid = shop["fps_id"]
    c = _cycle(conn, req.cycle)
    cyc = c["cycle"]
    if c["state"] == "CLOSED":
        raise ApiError(422, "CYCLE_CLOSED", f"Cycle {cyc} is closed; no distribution can be recorded.")
    if req.client_ref:
        dup = one(conn, """SELECT transaction_id, beneficiary_id, commodity, quantity_kg, transaction_time,
                                  status FROM epos_transactions WHERE fps_id = %s AND receipt_number = %s""",
                  (fid, req.client_ref))
        if dup:
            dup["transaction_time"] = iso(dup["transaction_time"])
            return {**dup, "cycle": cyc, "replayed": True}
    b = one(conn, """SELECT beneficiary_id, rice_entitlement_kg, wheat_entitlement_kg, status, current_fps_id
                     FROM beneficiaries WHERE beneficiary_id = %s""", (req.beneficiary_id,))
    if not b:
        raise ApiError(404, "BENEFICIARY_NOT_FOUND", f"Beneficiary {req.beneficiary_id} does not exist.")
    if b["current_fps_id"] != fid:
        raise ApiError(403, "FORBIDDEN", "This beneficiary is not assigned to your shop.")
    if b["status"] not in ("ACTIVE", "MIGRATED"):
        raise ApiError(422, "BENEFICIARY_INACTIVE", f"Beneficiary status is {b['status']}.")
    ent_col = "rice_entitlement_kg" if req.commodity == "RICE" else "wheat_entitlement_kg"
    used = one(conn, """SELECT COALESCE(sum(quantity_kg), 0) AS kg FROM epos_transactions
                        WHERE beneficiary_id = %s AND cycle = %s AND commodity = %s AND status = 'SUCCESS'""",
               (req.beneficiary_id, cyc, req.commodity))["kg"]
    remaining = (b[ent_col] or 0) - (used or 0)
    if req.quantity_kg - remaining > 1e-9:
        raise ApiError(422, "ENTITLEMENT_EXCEEDED",
                       f"Only {num(remaining)} kg of {req.commodity} remains from this beneficiary's "
                       f"{num(b[ent_col])} kg entitlement in {cyc}.")
    inv = one(conn, """SELECT inventory_id, closing_stock_kg FROM inventory
                       WHERE location_type = 'FPS' AND location_id = %s AND cycle = %s AND commodity = %s""",
              (fid, cyc, req.commodity))
    if not inv:
        raise ApiError(422, "NO_LEDGER", f"No inventory ledger exists for {req.commodity} in {cyc}.")
    if (inv["closing_stock_kg"] or 0) - req.quantity_kg < -1e-9:
        raise ApiError(422, "INSUFFICIENT_STOCK",
                       f"Only {num(inv['closing_stock_kg'])} kg of {req.commodity} is available in the ledger.")
    import psycopg.errors
    tid = ""
    now = datetime.now(timezone.utc)
    for _ in range(5):
        # The sequence can lag bulk-loaded rows (COPY never advances it), so re-anchor
        # it to the live maximum before each attempt and retry on a race collision.
        conn.execute("""SELECT setval('epos_txn_seq', COALESCE((SELECT max(substring(transaction_id from 6)::int)
                          FROM epos_transactions WHERE transaction_id ~ '^EPOS-[0-9]+$'), 0) + 1, false)""")
        tid = "EPOS-%08d" % conn.execute("SELECT nextval('epos_txn_seq')").fetchone()[0]
        try:
            with conn.transaction():
                conn.execute("""INSERT INTO epos_transactions (transaction_id, beneficiary_id, fps_id, cycle, commodity,
                                   quantity_kg, transaction_time, status, receipt_number)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, 'SUCCESS', %s)""",
                             (tid, req.beneficiary_id, fid, cyc, req.commodity, req.quantity_kg, now, req.client_ref))
            break
        except psycopg.errors.UniqueViolation:
            continue
    else:
        raise ApiError(503, "ID_ALLOCATION_FAILED", "Could not allocate a transaction id; please retry.")
    conn.execute("""UPDATE inventory SET distributed_kg = distributed_kg + %s,
                       closing_stock_kg = closing_stock_kg - %s WHERE inventory_id = %s""",
                 (req.quantity_kg, req.quantity_kg, inv["inventory_id"]))
    conn.commit()
    write_audit(user["user_id"], user["role"], "DISTRIBUTION_RECORDED", "SUCCESS",
                f"{req.quantity_kg} kg {req.commodity} to {req.beneficiary_id} at {fid}",
                "TRANSACTION", tid, cyc)
    return {"transaction_id": tid, "beneficiary_id": req.beneficiary_id, "fps_id": fid, "cycle": cyc,
            "commodity": req.commodity, "quantity_kg": req.quantity_kg, "status": "SUCCESS",
            "timestamp": now.isoformat(), "receipt_number": req.client_ref, "replayed": False}


# ------------------------------------------------------------------ reconciliation

@router.get("/me/reconciliation")
def reconciliation(fps_id: str | None = None, cycle: str | None = None, user=ReadStock, conn=Depends(get_db)):
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, cycle)
    rec = _reconciliation(conn, shop["fps_id"], c["cycle"])
    return {"fps_id": shop["fps_id"], "cycle": c["cycle"], "lines": rec,
            "reconciled": all(r["reconciled"] for r in rec if r["has_ledger"]),
            "note": "Ledger movements are compared against e-PoS records and verified deliveries. "
                    "A non-zero variance is flagged for review — never an accusation."}


class ReviewVariance(BaseModel):
    commodity: str = Field(pattern="^(RICE|WHEAT)$")
    note: str = Field(min_length=5, max_length=1000)
    cycle: str | None = None


@router.post("/me/reconciliation/review", status_code=201)
def review_variance(req: ReviewVariance, fps_id: str | None = None, user=WriteOps, conn=Depends(get_db)):
    if user["role"] != Role.FPS_OWNER.value:
        raise ApiError(403, "FORBIDDEN", "Only the FPS owner records variance reviews.")
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, req.cycle)
    rec = {r["commodity"]: r for r in _reconciliation(conn, shop["fps_id"], c["cycle"])}
    line = rec.get(req.commodity)
    if not line or not line["has_ledger"]:
        raise ApiError(422, "NO_LEDGER", f"No ledger to review for {req.commodity} in {c['cycle']}.")
    variance = (line["distribution_variance_kg"] or 0) + (line["receipt_variance_kg"] or 0)
    rid = "FVR-%06d" % conn.execute('SELECT nextval(%s)', ('fps_review_seq',)).fetchone()[0]
    conn.execute("""INSERT INTO fps_variance_reviews (review_id, fps_id, cycle, commodity, variance_kg, note,
                       reviewed_by) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                 (rid, shop["fps_id"], c["cycle"], req.commodity, variance, req.note.strip(), user["user_id"]))
    conn.commit()
    write_audit(user["user_id"], user["role"], "VARIANCE_REVIEWED", "SUCCESS",
                f"{req.commodity} variance {variance} kg at {shop['fps_id']}: {req.note.strip()}",
                "VARIANCE_REVIEW", rid, c["cycle"])
    return {"review_id": rid, "variance_kg": variance, "note": req.note.strip()}


# ------------------------------------------------------------------ requests

@router.get("/me/requests")
def list_requests(fps_id: str | None = None, cycle: str | None = None, user=ReadStock, conn=Depends(get_db)):
    shop = _shop(conn, user, fps_id)
    args: list = [shop["fps_id"]]
    q = "SELECT * FROM fps_stock_requests WHERE fps_id = %s"
    if cycle:
        q += " AND cycle = %s"
        args.append(cycle)
    q += " ORDER BY created_at DESC"
    out = rows(conn, q, tuple(args))
    for r in out:
        for k in ("created_at", "updated_at", "decided_at", "requested_delivery_date"):
            r[k] = iso(r[k])
    return {"fps_id": shop["fps_id"], "requests": out}


class CreateRequest(BaseModel):
    commodity: str = Field(pattern="^(RICE|WHEAT)$")
    requested_kg: float = Field(gt=0, le=100000)
    reason: str = Field(min_length=5, max_length=500)
    requested_delivery_date: date | None = None
    cycle: str | None = None


@router.post("/me/requests", status_code=201)
def create_request(req: CreateRequest, fps_id: str | None = None, user=WriteOps, conn=Depends(get_db)):
    if user["role"] != Role.FPS_OWNER.value:
        raise ApiError(403, "FORBIDDEN", "Only the FPS owner raises replenishment requests.")
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, req.cycle)
    if c["state"] == "CLOSED":
        raise ApiError(422, "CYCLE_CLOSED", f"Cycle {c['cycle']} is closed.")
    inv = _inv_map(conn, shop["fps_id"], c["cycle"])
    current = (inv.get(req.commodity) or {}).get("closing_stock_kg") or 0
    # Context the owner sees before submitting: recent rate and derived cover.
    rate_row = one(conn, """SELECT COALESCE(sum(quantity_kg), 0) AS kg,
                                   count(DISTINCT transaction_time::date) AS days
                            FROM epos_transactions WHERE fps_id = %s AND cycle = %s AND commodity = %s
                            AND status = 'SUCCESS'""", (shop["fps_id"], c["cycle"], req.commodity))
    rate = (rate_row["kg"] / rate_row["days"]) if rate_row["days"] else 0
    n = conn.execute("SELECT nextval('fps_request_seq')").fetchone()[0]
    rid = f"REQ-{c['cycle'][:4]}-{n:04d}"
    conn.execute("""INSERT INTO fps_stock_requests (request_id, fps_id, cycle, commodity, current_stock_kg,
                       requested_kg, reason, requested_delivery_date, status, requested_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'DRAFT', %s)""",
                 (rid, shop["fps_id"], c["cycle"], req.commodity, current, req.requested_kg,
                  req.reason.strip(), req.requested_delivery_date, user["user_id"]))
    conn.commit()
    write_audit(user["user_id"], user["role"], "SUPPLY_REQUEST_CREATED", "SUCCESS",
                f"{req.requested_kg} kg {req.commodity} for {shop['fps_id']}", "SUPPLY_REQUEST", rid, c["cycle"])
    return {"request_id": rid, "status": "DRAFT", "current_stock_kg": num(current),
            "recent_daily_rate_kg": round(rate, 1),
            "derived_cover_days": round(current / rate, 1) if rate > 0 else None}


def _move_request(conn, user: dict, request_id: str, to: str, note: str | None, by_owner: bool) -> dict:
    r = one(conn, "SELECT * FROM fps_stock_requests WHERE request_id = %s", (request_id,))
    if not r:
        raise ApiError(404, "REQUEST_NOT_FOUND", f"Request {request_id} does not exist.")
    if by_owner:
        shop = _shop(conn, user, None)
        if r["fps_id"] != shop["fps_id"]:
            raise ApiError(403, "FORBIDDEN", "This request belongs to another shop.")
    allowed = _OWNER_MOVES if by_owner else _DSO_MOVES
    if (r["status"], to) not in allowed:
        raise ApiError(422, "INVALID_TRANSITION", f"Cannot move a request from {r['status']} to {to}.")
    now = datetime.now(timezone.utc)
    conn.execute("""UPDATE fps_stock_requests SET status = %s, updated_at = %s,
                       reviewed_by = COALESCE(%s, reviewed_by),
                       decision_note = COALESCE(%s, decision_note),
                       decided_at = CASE WHEN %s IN ('APPROVED','REJECTED','RECEIVED') THEN %s ELSE decided_at END
                    WHERE request_id = %s""",
                 (to, now, None if by_owner else user["user_id"], note, to, now, request_id))
    conn.commit()
    action = "SUPPLY_REQUEST_SUBMITTED" if to == "SUBMITTED" else f"SUPPLY_REQUEST_{to}"
    write_audit(user["user_id"], user["role"], action, "SUCCESS", note or "", "SUPPLY_REQUEST", request_id, r["cycle"],
                before=r["status"], after=to)
    out = one(conn, "SELECT * FROM fps_stock_requests WHERE request_id = %s", (request_id,))
    for k in ("created_at", "updated_at", "decided_at", "requested_delivery_date"):
        out[k] = iso(out[k])
    return out


class TransitionRequest(BaseModel):
    to: str = Field(pattern="^(UNDER_REVIEW|APPROVED|DISPATCHED|REJECTED|RECEIVED)$")
    note: str | None = Field(default=None, max_length=500)


@router.post("/me/requests/{request_id}/submit")
def submit_request(request_id: str, user=WriteOps, conn=Depends(get_db)):
    if user["role"] != Role.FPS_OWNER.value:
        raise ApiError(403, "FORBIDDEN", "Only the FPS owner submits their requests.")
    return _move_request(conn, user, request_id, "SUBMITTED", None, True)


@router.post("/me/requests/{request_id}/receive")
def receive_request(request_id: str, user=WriteOps, conn=Depends(get_db)):
    if user["role"] != Role.FPS_OWNER.value:
        raise ApiError(403, "FORBIDDEN", "Only the FPS owner confirms receipt.")
    return _move_request(conn, user, request_id, "RECEIVED", "confirmed received at shop", True)


@router.delete("/me/requests/{request_id}")
def delete_request(request_id: str, user=WriteOps, conn=Depends(get_db)):
    if user["role"] != Role.FPS_OWNER.value:
        raise ApiError(403, "FORBIDDEN", "Only the FPS owner withdraws their requests.")
    shop = _shop(conn, user, None)
    r = one(conn, "SELECT status, fps_id FROM fps_stock_requests WHERE request_id = %s", (request_id,))
    if not r:
        raise ApiError(404, "REQUEST_NOT_FOUND", f"Request {request_id} does not exist.")
    if r["fps_id"] != shop["fps_id"]:
        raise ApiError(403, "FORBIDDEN", "This request belongs to another shop.")
    if r["status"] != "DRAFT":
        raise ApiError(422, "REQUEST_LOCKED", "Only draft requests can be withdrawn.")
    conn.execute("DELETE FROM fps_stock_requests WHERE request_id = %s", (request_id,))
    conn.commit()
    write_audit(user["user_id"], user["role"], "SUPPLY_REQUEST_WITHDRAWN", "SUCCESS", "",
                "SUPPLY_REQUEST", request_id)
    return {"request_id": request_id, "withdrawn": True}


@router.post("/requests/{request_id}/transition")
def dso_transition(request_id: str, req: TransitionRequest, user=ManageSupply, conn=Depends(get_db)):
    """DSO supply-chain action on any shop's request. Real state, audited; never faked."""
    return _move_request(conn, user, request_id, req.to, (req.note or "").strip() or None, False)


# ------------------------------------------------------------------ close day

def _close_readiness(conn, fps_id: str, cyc: str) -> dict:
    rec = _reconciliation(conn, fps_id, cyc)
    unreviewed = [r["commodity"] for r in rec
                  if r["has_ledger"] and ((r["distribution_variance_kg"] or 0) != 0
                                          or (r["receipt_variance_kg"] or 0) != 0) and not r["review"]]
    missing_ledger = [r["commodity"] for r in rec if not r["has_ledger"]]
    failed_today = one(conn, """SELECT count(*) AS n FROM epos_transactions
                                WHERE fps_id = %s AND transaction_time::date = CURRENT_DATE
                                AND status = 'FAILED'""", (fps_id,))["n"]
    already = one(conn, "SELECT closure_id, closed_at FROM fps_day_closures WHERE fps_id = %s AND business_date = CURRENT_DATE",
                  (fps_id,))
    blockers = []
    if unreviewed:
        blockers.append({"code": "VARIANCE_REVIEW_REQUIRED", "step": "RECONCILIATION",
                         "message": f"{', '.join(unreviewed)} variance requires review before closing."})
    if missing_ledger:
        blockers.append({"code": "MISSING_LEDGER", "step": "STOCK",
                         "message": f"No {cyc} ledger for {', '.join(missing_ledger)} — cannot verify the day."})
    if already:
        blockers.append({"code": "ALREADY_CLOSED", "step": "CLOSE_DAY",
                         "message": f"Today is already closed ({already['closure_id']})."})
    return {"blockers": blockers, "unreviewed_variance": unreviewed, "missing_ledger": missing_ledger,
            "failed_today": failed_today, "already_closed": bool(already),
            "ready": not blockers}


@router.get("/me/close-day")
def close_day_status(fps_id: str | None = None, cycle: str | None = None, user=ReadShop, conn=Depends(get_db)):
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, cycle)
    cyc = c["cycle"]
    counts = _cycle_counts(conn, shop["fps_id"], cyc)
    today = _today_counts(conn, shop["fps_id"])
    inv = _inv_map(conn, shop["fps_id"], cyc)
    rec = _reconciliation(conn, shop["fps_id"], cyc)
    pending_req = one(conn, """SELECT count(*) AS n FROM fps_stock_requests WHERE fps_id = %s
                               AND status IN ('SUBMITTED','UNDER_REVIEW','APPROVED','DISPATCHED')""",
                      (shop["fps_id"],))["n"]
    readiness = _close_readiness(conn, shop["fps_id"], cyc)
    per_commodity = {}
    for com in COMMODITIES:
        per_commodity[com] = {"distributed_kg": _epos_sums(conn, shop["fps_id"], cyc).get(com, 0),
                              "remaining_kg": (inv.get(com) or {}).get("closing_stock_kg")}
    return {"fps_id": shop["fps_id"], "cycle": cyc, "today": date.today().isoformat(),
            "summary": {"beneficiaries_served_cycle": counts["beneficiaries"],
                        "transactions_cycle": counts["txns"], "transactions_today": today["txns"],
                        "per_commodity": per_commodity,
                        "stock_remaining_kg": sum(((inv.get(k) or {}).get("closing_stock_kg") or 0)
                                                  for k in COMMODITIES),
                        "pending_requests": pending_req},
            "reconciliation": rec, "readiness": readiness}


@router.post("/me/close-day", status_code=201)
def close_day(fps_id: str | None = None, cycle: str | None = None, user=WriteOps, conn=Depends(get_db)):
    if user["role"] != Role.FPS_OWNER.value:
        raise ApiError(403, "FORBIDDEN", "Only the FPS owner closes the day.")
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, cycle)
    cyc = c["cycle"]
    readiness = _close_readiness(conn, shop["fps_id"], cyc)
    if not readiness["ready"]:
        raise ApiError(422, "DAY_NOT_READY",
                       "The day cannot be closed: " + "; ".join(b["message"] for b in readiness["blockers"]))
    counts = _cycle_counts(conn, shop["fps_id"], cyc)
    epos = _epos_sums(conn, shop["fps_id"], cyc)
    inv = _inv_map(conn, shop["fps_id"], cyc)
    pending_req = one(conn, """SELECT count(*) AS n FROM fps_stock_requests WHERE fps_id = %s
                               AND status IN ('SUBMITTED','UNDER_REVIEW','APPROVED','DISPATCHED')""",
                      (shop["fps_id"],))["n"]
    cid = f"CLS-{shop['fps_id']}-{date.today().isoformat()}"
    conn.execute("""INSERT INTO fps_day_closures (closure_id, fps_id, business_date, cycle, beneficiaries_served,
                       transactions, rice_distributed_kg, wheat_distributed_kg, stock_remaining_kg, variances,
                       pending_requests, checks, closed_by)
                    VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s)
                    ON CONFLICT (fps_id, business_date) DO NOTHING""",
                 (cid, shop["fps_id"], cyc, counts["beneficiaries"], counts["txns"],
                  epos.get("RICE", 0), epos.get("WHEAT", 0),
                  sum(((inv.get(k) or {}).get("closing_stock_kg") or 0) for k in COMMODITIES),
                  __import__("json").dumps(_reconciliation(conn, shop["fps_id"], cyc), default=str),
                  pending_req, __import__("json").dumps(readiness, default=str), user["user_id"]))
    row = one(conn, "SELECT * FROM fps_day_closures WHERE fps_id = %s AND business_date = CURRENT_DATE",
              (shop["fps_id"],))
    conn.commit()
    if row["closure_id"] != cid:
        raise ApiError(409, "ALREADY_CLOSED", "Today was already closed.")
    write_audit(user["user_id"], user["role"], "DAY_CLOSED", "SUCCESS",
                f"{shop['fps_id']} closed for {date.today().isoformat()}", "DAY_CLOSURE", cid, cyc)
    for k in ("closed_at",):
        row[k] = iso(row[k])
    return row


# ------------------------------------------------------------------ alerts & insights

@router.get("/me/alerts")
def alerts(fps_id: str | None = None, cycle: str | None = None, user=ReadShop, conn=Depends(get_db)):
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, cycle)
    return {"fps_id": shop["fps_id"], "cycle": c["cycle"], "alerts": _alerts(conn, shop["fps_id"], c["cycle"])}


@router.get("/me/insights")
def insights(fps_id: str | None = None, cycle: str | None = None, user=ReadShop, conn=Depends(get_db)):
    shop = _shop(conn, user, fps_id)
    c = _cycle(conn, cycle)
    return {"fps_id": shop["fps_id"], "cycle": c["cycle"], "advisory": True,
            "insights": _insights(conn, shop["fps_id"], c["cycle"]),
            "note": "Advisory only. Insights never adjust stock, approve requests, or close the day."}
