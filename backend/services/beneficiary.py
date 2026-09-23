"""Beneficiary-facing data service. Every function takes the authenticated beneficiary_id; nothing here trusts
an id supplied by the client. All values come from the database; nothing is defaulted or invented."""
from __future__ import annotations

import calendar
import hashlib
from datetime import date
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

from backend.core.errors import ApiError

CYCLE_STATES = ["OPEN", "MONITOR", "LOCKED", "ALLOCATED", "OPTIMIZED", "AUTHORIZED", "TRACKING", "DELIVERING",
                "RECONCILING", "AUDITING", "CLOSED"]
COLLECTION_MODES = ("SELF", "AUTHORIZED_PERSON")
GRIEVANCE_CATEGORIES = ("SHORT_DELIVERY", "WRONG_QUANTITY", "FPS_ISSUE", "QUALITY", "TRANSACTION_FAILURE",
                        "ENTITLEMENT_QUERY", "COLLECTION_ISSUE", "OTHER")
JOURNEY = ["INTENT_SUBMITTED", "DEMAND_PLANNED", "ALLOCATED", "DISPATCHED", "IN_TRANSIT", "RECEIVED_AT_FPS",
           "AVAILABLE_FOR_COLLECTION", "COLLECTED"]


def state_index(state: str) -> int:
    return CYCLE_STATES.index(state)


def num(v: Any) -> Any:
    """Decimal -> int when whole, else float (kg values)."""
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    return v


def rows(conn: psycopg.Connection, sql: str, params: Any = ()) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return [{k: num(v) for k, v in r.items()} for r in cur.fetchall()]


def one(conn: psycopg.Connection, sql: str, params: Any = ()) -> dict | None:
    r = rows(conn, sql, params)
    return r[0] if r else None


def iso(v) -> str | None:
    return v.isoformat() if v is not None else None


# ------------------------------------------------------------------ profile, FPS, cycle

def fps_view(r: dict, prefix: str = "") -> dict:
    return {"fps_id": r[prefix + "fps_id"], "name": r[prefix + "fps_name"], "district": r[prefix + "district"],
            "taluk": r[prefix + "taluk"], "latitude": float(r[prefix + "latitude"]), "longitude": float(r[prefix + "longitude"]),
            "opening_hours": r[prefix + "opening_hours"], "status": r[prefix + "status"]}


def get_profile(conn, beneficiary_id: str) -> dict:
    r = one(conn, """
        SELECT b.beneficiary_id, b.ration_card_id, b.head_of_household, b.household_size, b.scheme_type,
               b.entitlement_kg, b.rice_entitlement_kg, b.wheat_entitlement_kg, b.district AS b_district,
               b.taluk AS b_taluk, b.status AS b_status,
               f.fps_id, f.fps_name, f.district, f.taluk, f.latitude, f.longitude, f.opening_hours, f.status
        FROM beneficiaries b JOIN fps f ON f.fps_id = b.current_fps_id WHERE b.beneficiary_id = %s""", (beneficiary_id,))
    if not r:
        raise ApiError(404, "BENEFICIARY_NOT_FOUND", "Beneficiary record not found.")
    return {
        "beneficiary": {"beneficiary_id": r["beneficiary_id"], "ration_card_id": r["ration_card_id"],
                        "name": r["head_of_household"], "household_size": r["household_size"], "scheme": r["scheme_type"],
                        "district": r["b_district"], "taluk": r["b_taluk"], "status": r["b_status"]},
        "entitlement_statutory": {"rice_kg": r["rice_entitlement_kg"], "wheat_kg": r["wheat_entitlement_kg"],
                                  "total_kg": r["entitlement_kg"]},
        "fps": fps_view(r),
    }


def cycle_view(c: dict) -> dict:
    y, m = int(c["cycle"][:4]), int(c["cycle"][5:7])
    return {"cycle": c["cycle"], "state": c["state"], "window_open": c["state"] == "OPEN",
            "period_start": date(y, m, 1).isoformat(), "period_end": date(y, m, calendar.monthrange(y, m)[1]).isoformat(),
            "choice_window_start": iso(c["choice_window_start"]), "choice_window_end": iso(c["choice_window_end"])}


def get_cycle(conn, cycle: str | None = None) -> dict | None:
    """The requested cycle, or the current one: the latest cycle that is not CLOSED."""
    if cycle:
        c = one(conn, "SELECT * FROM cycles WHERE cycle = %s", (cycle,))
        if not c:
            raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
    else:
        c = one(conn, "SELECT * FROM cycles WHERE state <> 'CLOSED' ORDER BY cycle DESC LIMIT 1")
    return cycle_view(c) if c else None


def list_cycles(conn) -> list[dict]:
    """All cycles ordered newest first — for the beneficiary month selector. Real rows only."""
    return [cycle_view(c) for c in rows(conn, "SELECT * FROM cycles ORDER BY cycle DESC")]


# ------------------------------------------------------------------ entitlement

def get_entitlement(conn, beneficiary_id: str, cycle: str) -> dict:
    """Statutory entitlement (read-only) minus what e-PoS has actually recorded as SUCCESS in the cycle."""
    b = one(conn, "SELECT rice_entitlement_kg, wheat_entitlement_kg, entitlement_kg, scheme_type, household_size "
                  "FROM beneficiaries WHERE beneficiary_id = %s", (beneficiary_id,))
    used = {r["commodity"]: r["kg"] for r in rows(conn, """
        SELECT commodity, COALESCE(sum(quantity_kg), 0) AS kg FROM epos_transactions
        WHERE beneficiary_id = %s AND cycle = %s AND status = 'SUCCESS' GROUP BY commodity""", (beneficiary_id, cycle))}
    used_rice, used_wheat = used.get("RICE", 0), used.get("WHEAT", 0)
    rem_rice, rem_wheat = max(b["rice_entitlement_kg"] - used_rice, 0), max(b["wheat_entitlement_kg"] - used_wheat, 0)
    return {"cycle": cycle, "scheme": b["scheme_type"], "household_size": b["household_size"],
            "rice_kg": b["rice_entitlement_kg"], "wheat_kg": b["wheat_entitlement_kg"], "total_kg": b["entitlement_kg"],
            "collected_rice_kg": used_rice, "collected_wheat_kg": used_wheat, "collected_total_kg": used_rice + used_wheat,
            "remaining_rice_kg": rem_rice, "remaining_wheat_kg": rem_wheat, "remaining_total_kg": rem_rice + rem_wheat,
            "source": "beneficiaries + epos_transactions (SUCCESS)"}


# ------------------------------------------------------------------ FPS choice

def eligible_fps(conn, beneficiary_id: str, limit: int = 25) -> list[dict]:
    """ACTIVE FPS in the beneficiary's own district, nearest first (distance from the registered home location)."""
    return rows(conn, """
        WITH me AS (SELECT district, latitude AS lat, longitude AS lon, current_fps_id FROM beneficiaries WHERE beneficiary_id = %s),
        d AS (
          SELECT f.*, me.current_fps_id,
                 CASE WHEN me.lat IS NULL THEN NULL ELSE 6371 * acos(LEAST(1, GREATEST(-1,
                      cos(radians(me.lat)) * cos(radians(f.latitude)) * cos(radians(f.longitude) - radians(me.lon))
                      + sin(radians(me.lat)) * sin(radians(f.latitude))))) END AS km
          FROM fps f JOIN me ON f.district = me.district
          WHERE f.status = 'ACTIVE' OR f.fps_id = me.current_fps_id)
        SELECT fps_id, fps_name AS name, district, taluk, latitude::float AS latitude, longitude::float AS longitude,
               opening_hours, status, (fps_id = current_fps_id) AS is_current, round(km::numeric, 1)::float AS distance_km
        FROM d ORDER BY (fps_id = current_fps_id) DESC, km NULLS LAST, fps_id LIMIT %s""", (beneficiary_id, limit))


# ------------------------------------------------------------------ intents

def receipt_view(conn, r: dict, window_open: bool) -> dict:
    f = one(conn, "SELECT fps_id, fps_name, district, taluk, latitude, longitude, opening_hours, status FROM fps WHERE fps_id = %s",
            (r["fps_id"],))
    return {"reference": r["intent_id"], "cycle": r["cycle"], "status": "RECORDED" if r["status"] == "SUBMITTED" else "CANCELLED",
            "fps": fps_view(f), "rice_kg": r["rice_quantity_kg"], "wheat_kg": r["wheat_quantity_kg"],
            "total_kg": r["total_quantity_kg"], "collection_mode": r["collection_mode"], "submitted_at": iso(r["submitted_at"]),
            "can_cancel": r["status"] == "SUBMITTED" and window_open}


def live_intent(conn, beneficiary_id: str, cycle: str) -> dict | None:
    return one(conn, "SELECT * FROM intent_signals WHERE beneficiary_id = %s AND cycle = %s AND status = 'SUBMITTED'",
               (beneficiary_id, cycle))


def submit_intent(conn, beneficiary_id: str, fps_id: str, rice: int, wheat: int, mode: str, cycle: str | None) -> dict:
    """Validate against backend truth and create the one live intent for this beneficiary + cycle."""
    cyc = get_cycle(conn, cycle)
    if cyc is None:
        raise ApiError(409, "NO_ACTIVE_CYCLE", "There is no active cycle right now.")
    if not cyc["window_open"]:
        raise ApiError(409, "CHOICE_WINDOW_CLOSED", "The choice window for this cycle is closed.", {"cycle": cyc["cycle"]})
    if mode not in COLLECTION_MODES:
        raise ApiError(422, "INVALID_COLLECTION_MODE", "Invalid collection option.")
    if rice < 0 or wheat < 0 or rice + wheat <= 0:
        raise ApiError(422, "INVALID_QUANTITY", "Enter a quantity greater than zero. Negative quantities are not allowed.")

    existing = live_intent(conn, beneficiary_id, cyc["cycle"])
    if existing:
        raise ApiError(409, "INTENT_DUPLICATE", "Your collection preference has already been submitted for this cycle.",
                       {"reference": existing["intent_id"]})

    fps = one(conn, "SELECT f.fps_id, f.status, f.district, b.district AS b_district FROM fps f, beneficiaries b "
                    "WHERE f.fps_id = %s AND b.beneficiary_id = %s", (fps_id, beneficiary_id))
    if not fps:
        raise ApiError(422, "FPS_NOT_FOUND", "This fair price shop does not exist.")
    if fps["status"] != "ACTIVE" or fps["district"] != fps["b_district"]:
        raise ApiError(422, "FPS_NOT_ELIGIBLE", "You can only choose an active fair price shop in your own district.")

    ent = get_entitlement(conn, beneficiary_id, cyc["cycle"])
    problems = {}
    if rice > ent["remaining_rice_kg"]:
        problems["rice"] = {"requested_kg": rice, "remaining_kg": ent["remaining_rice_kg"]}
    if wheat > ent["remaining_wheat_kg"]:
        problems["wheat"] = {"requested_kg": wheat, "remaining_kg": ent["remaining_wheat_kg"]}
    if problems:
        raise ApiError(422, "EXCEEDS_REMAINING",
                       f"Requested quantity exceeds your remaining entitlement (rice {ent['remaining_rice_kg']} kg, "
                       f"wheat {ent['remaining_wheat_kg']} kg).", problems)

    year = cyc["cycle"][:4]
    try:
        with conn.transaction():
            seq = conn.execute("SELECT nextval('intent_reference_seq')").fetchone()[0]
            ref = f"INT-{year}-{seq:06d}"
            conn.execute(
                """INSERT INTO intent_signals (intent_id, beneficiary_id, fps_id, cycle, rice_quantity_kg, wheat_quantity_kg,
                       total_quantity_kg, collection_mode, submitted_at, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), 'SUBMITTED')""",
                (ref, beneficiary_id, fps_id, cyc["cycle"], rice, wheat, rice + wheat, mode))
    except psycopg.errors.UniqueViolation:  # a concurrent submit won the race
        raise ApiError(409, "INTENT_DUPLICATE", "Your collection preference has already been submitted for this cycle.")
    return receipt_view(conn, one(conn, "SELECT * FROM intent_signals WHERE intent_id = %s", (ref,)), True)


def get_receipt(conn, beneficiary_id: str, reference: str) -> dict:
    r = one(conn, "SELECT * FROM intent_signals WHERE intent_id = %s AND beneficiary_id = %s", (reference, beneficiary_id))
    if not r:  # someone else's reference looks exactly like a missing one
        raise ApiError(404, "RECEIPT_NOT_FOUND", "Receipt not found.")
    cyc = one(conn, "SELECT state FROM cycles WHERE cycle = %s", (r["cycle"],))
    return receipt_view(conn, r, cyc["state"] == "OPEN")


def cancel_intent(conn, beneficiary_id: str, reference: str) -> dict:
    r = one(conn, "SELECT * FROM intent_signals WHERE intent_id = %s AND beneficiary_id = %s", (reference, beneficiary_id))
    if not r:
        raise ApiError(404, "RECEIPT_NOT_FOUND", "Receipt not found.")
    cyc = one(conn, "SELECT state FROM cycles WHERE cycle = %s", (r["cycle"],))
    if cyc["state"] != "OPEN":
        raise ApiError(409, "CHOICE_WINDOW_CLOSED", "The choice window is closed; this plan can no longer be changed.")
    if r["status"] != "SUBMITTED":
        raise ApiError(409, "INTENT_NOT_ACTIVE", "This plan is already cancelled.")
    conn.execute("UPDATE intent_signals SET status = 'CANCELLED' WHERE intent_id = %s", (reference,))
    return get_receipt(conn, beneficiary_id, reference)


# ------------------------------------------------------------------ tracking

_DELIVERED_MANIFEST = ("DISPATCHED", "DELIVERED", "RECONCILED")


def get_journey(conn, beneficiary_id: str, cycle: str) -> dict:
    """Eight-stage ration journey built from real records. A pipeline stage only counts once the cycle's state has
    reached it, so an OPEN cycle can never show 'dispatched' even if stray downstream rows exist."""
    cyc = get_cycle(conn, cycle)
    idx = state_index(cyc["state"])
    intent = live_intent(conn, beneficiary_id, cycle)
    fps_id = intent["fps_id"] if intent else one(conn, "SELECT current_fps_id FROM beneficiaries WHERE beneficiary_id = %s",
                                                (beneficiary_id,))["current_fps_id"]

    lock = one(conn, "SELECT locked_at FROM demand_locks WHERE cycle = %s", (cycle,))
    alloc = one(conn, """SELECT count(*) AS n, count(*) FILTER (WHERE status = 'APPROVED') AS approved, max(approved_at) AS at
                         FROM allocations WHERE cycle = %s AND fps_id = %s""", (cycle, fps_id))
    manifests = rows(conn, """
        SELECT DISTINCT m.manifest_id, m.manifest_status, m.vehicle_id, m.locked_at
        FROM dispatch_manifest_items i JOIN dispatch_manifests m USING (manifest_id)
        WHERE m.cycle = %s AND i.fps_id = %s""", (cycle, fps_id))
    mids = [m["manifest_id"] for m in manifests]
    deliveries = rows(conn, "SELECT manifest_id, status, delivery_date FROM delivery_history "
                            "WHERE fps_id = %s AND manifest_id = ANY(%s) ORDER BY delivery_date", (fps_id, mids)) if mids else []
    if idx < state_index("TRACKING"):  # a delivery cannot count before the cycle has reached tracking
        deliveries = []
    received = [d for d in deliveries if d["status"] in ("VERIFIED", "VARIANCE")]
    rejected = [d for d in deliveries if d["status"] == "REJECTED"]
    collected = rows(conn, """SELECT commodity, sum(quantity_kg) AS kg, max(transaction_time) AS at FROM epos_transactions
                              WHERE beneficiary_id = %s AND cycle = %s AND status = 'SUCCESS' GROUP BY commodity""",
                     (beneficiary_id, cycle))

    dispatched = idx >= state_index("AUTHORIZED") and (
        any(m["manifest_status"] in _DELIVERED_MANIFEST for m in manifests) or bool(deliveries))
    in_transit_phase = dispatched and not received
    steps: dict[str, dict] = {}

    def step(key: str, status: str, at=None, detail: str | None = None) -> None:
        steps[key] = {"key": key, "status": status, "at": iso(at), "detail": detail}

    if intent:
        step("INTENT_SUBMITTED", "DONE", intent["submitted_at"], intent["intent_id"])
    else:
        step("INTENT_SUBMITTED", "PENDING" if cyc["window_open"] else "UNAVAILABLE",
             detail=None if cyc["window_open"] else "NO_INTENT_SUBMITTED")
    step("DEMAND_PLANNED", "DONE" if idx >= state_index("LOCKED") else "PENDING", lock["locked_at"] if lock else None)
    if idx >= state_index("ALLOCATED") and alloc["n"] and not alloc["approved"]:
        step("ALLOCATED", "DELAYED", detail="ALLOCATION_ON_HOLD")
    else:
        done = idx >= state_index("ALLOCATED") and alloc["approved"] > 0
        step("ALLOCATED", "DONE" if done else "PENDING", alloc["at"] if done else None)
    step("DISPATCHED", "DONE" if dispatched else "PENDING", None,
         "INFERRED_FROM_DELIVERY" if dispatched and not any(m["manifest_status"] in _DELIVERED_MANIFEST for m in manifests) else None)
    step("IN_TRANSIT", "DONE" if received else ("ACTIVE" if in_transit_phase else "PENDING"))
    if received:
        step("RECEIVED_AT_FPS", "DONE", received[0]["delivery_date"], received[0]["status"])
    elif rejected and idx >= state_index("DELIVERING"):
        step("RECEIVED_AT_FPS", "DELAYED", rejected[0]["delivery_date"], "DELIVERY_REJECTED")
    else:
        step("RECEIVED_AT_FPS", "PENDING")
    step("AVAILABLE_FOR_COLLECTION", "DONE" if received else "PENDING", received[0]["delivery_date"] if received else None)
    if collected:
        step("COLLECTED", "DONE", max(c["at"] for c in collected),
             ", ".join(f"{c['commodity']}:{num(c['kg'])}" for c in collected))
    else:
        step("COLLECTED", "PENDING")

    ordered = [steps[k] for k in JOURNEY]
    # Progress is the unbroken run of DONE stages from the start. A later stage with a record (for example an e-PoS
    # collection in a cycle that has not even locked) is still shown as recorded, but it does not advance the headline.
    prefix = 0
    while prefix < len(ordered) and ordered[prefix]["status"] == "DONE":
        prefix += 1
    if prefix < len(ordered) and ordered[prefix]["status"] == "PENDING":
        ordered[prefix]["status"] = "ACTIVE"  # the stage currently in motion

    telemetry, route = None, None
    if in_transit_phase and manifests:
        t = one(conn, """SELECT v.vehicle_number, t.latitude::float AS latitude, t.longitude::float AS longitude, t.speed_kmph,
                                t.status, t.timestamp, t.manifest_id
                         FROM vehicle_telemetry t JOIN vehicles v USING (vehicle_id)
                         WHERE t.manifest_id = ANY(%s) AND t.latitude IS NOT NULL AND t.longitude IS NOT NULL
                         ORDER BY t.timestamp DESC LIMIT 1""", (mids,))
        if t:
            telemetry = {"vehicle_number": t["vehicle_number"], "latitude": t["latitude"], "longitude": t["longitude"],
                         "speed_kmph": t["speed_kmph"], "status": t["status"], "last_update": iso(t["timestamp"])}
        rt = rows(conn, "SELECT fps_id, stop_sequence, eta_minutes FROM vehicle_routes WHERE manifest_id = ANY(%s) "
                        "ORDER BY manifest_id, stop_sequence", (mids,))
        mine = next((r for r in rt if r["fps_id"] == fps_id), None)
        if mine:
            route = {"stops_total": len(rt), "your_stop": mine["stop_sequence"], "planned_eta_minutes": mine["eta_minutes"]}

    return {"cycle": cycle, "cycle_state": cyc["state"], "fps_id": fps_id, "steps": ordered,
            "headline": ordered[prefix - 1]["key"] if prefix else (None if cyc["window_open"] else "CHOICE_WINDOW_CLOSED"),
            "telemetry": telemetry, "route": route,
            "telemetry_note": None if telemetry else ("LIVE_LOCATION_UNAVAILABLE" if in_transit_phase else None)}


# ------------------------------------------------------------------ history & receipts

def history(conn, beneficiary_id: str, kind: str, limit: int, offset: int) -> list[dict]:
    if kind == "intents":
        return rows(conn, """SELECT i.intent_id AS reference, i.cycle, i.submitted_at AS at, f.fps_id, f.fps_name AS fps_name,
                                    i.rice_quantity_kg AS rice_kg, i.wheat_quantity_kg AS wheat_kg, i.total_quantity_kg AS total_kg,
                                    CASE i.status WHEN 'SUBMITTED' THEN 'RECORDED' ELSE i.status END AS status
                             FROM intent_signals i JOIN fps f USING (fps_id) WHERE i.beneficiary_id = %s
                             ORDER BY i.submitted_at DESC, i.intent_id LIMIT %s OFFSET %s""", (beneficiary_id, limit, offset))
    if kind == "transactions":
        return rows(conn, """SELECT t.transaction_id AS reference, t.cycle, t.transaction_time AS at, f.fps_id, f.fps_name AS fps_name,
                                    t.commodity, t.quantity_kg, t.status, t.receipt_number
                             FROM epos_transactions t JOIN fps f USING (fps_id) WHERE t.beneficiary_id = %s
                             ORDER BY t.transaction_time DESC, t.transaction_id LIMIT %s OFFSET %s""", (beneficiary_id, limit, offset))
    if kind == "collections":
        return rows(conn, """SELECT t.cycle, t.fps_id, f.fps_name AS fps_name, max(t.transaction_time) AS at,
                                    COALESCE(sum(t.quantity_kg) FILTER (WHERE t.commodity = 'RICE'), 0) AS rice_kg,
                                    COALESCE(sum(t.quantity_kg) FILTER (WHERE t.commodity = 'WHEAT'), 0) AS wheat_kg,
                                    sum(t.quantity_kg) AS total_kg, count(*) AS transactions,
                                    array_agg(t.transaction_id ORDER BY t.transaction_id) AS transaction_ids
                             FROM epos_transactions t JOIN fps f USING (fps_id)
                             WHERE t.beneficiary_id = %s AND t.status = 'SUCCESS'
                             GROUP BY t.cycle, t.fps_id, f.fps_name ORDER BY max(t.transaction_time) DESC LIMIT %s OFFSET %s""",
                    (beneficiary_id, limit, offset))
    raise ApiError(422, "INVALID_HISTORY_KIND", "kind must be intents, transactions or collections")


def transaction_receipt(conn, beneficiary_id: str, transaction_id: str) -> dict:
    t = one(conn, """SELECT t.*, f.fps_name, f.district, f.taluk, b.head_of_household, b.ration_card_id
                     FROM epos_transactions t JOIN fps f USING (fps_id) JOIN beneficiaries b USING (beneficiary_id)
                     WHERE t.transaction_id = %s AND t.beneficiary_id = %s""", (transaction_id, beneficiary_id))
    if not t:
        raise ApiError(404, "TRANSACTION_NOT_FOUND", "Transaction not found.")
    if t["status"] != "SUCCESS":
        raise ApiError(404, "RECEIPT_NOT_AVAILABLE", "A receipt is only issued for successful collections.")
    ref = hashlib.sha256(f"{t['transaction_id']}|{t['receipt_number']}|{t['beneficiary_id']}|{t['commodity']}|"
                         f"{t['quantity_kg']}|{t['transaction_time'].isoformat()}".encode()).hexdigest()[:16].upper()
    return {"transaction_id": t["transaction_id"], "receipt_number": t["receipt_number"], "cycle": t["cycle"],
            "beneficiary_name": t["head_of_household"], "ration_card_id": t["ration_card_id"],
            "fps": {"fps_id": t["fps_id"], "name": t["fps_name"], "district": t["district"], "taluk": t["taluk"]},
            "commodity": t["commodity"], "quantity_kg": num(t["quantity_kg"]), "transaction_time": iso(t["transaction_time"]),
            "status": t["status"], "verification_ref": ref, "qr_payload": f"DSYNC|{t['transaction_id']}|{ref}"}


# ------------------------------------------------------------------ grievances

def create_grievance(conn, beneficiary_id: str, category: str, description: str, fps_id: str | None,
                     cycle: str | None, related_transaction_id: str | None) -> dict:
    if category not in GRIEVANCE_CATEGORIES:
        raise ApiError(422, "INVALID_CATEGORY", "Choose one of the listed issue types.")
    description = description.strip()
    if not 10 <= len(description) <= 500:
        raise ApiError(422, "INVALID_DESCRIPTION", "Please describe the issue in 10 to 500 characters.")
    if related_transaction_id and not one(conn, "SELECT 1 AS x FROM epos_transactions WHERE transaction_id = %s AND beneficiary_id = %s",
                                          (related_transaction_id, beneficiary_id)):
        raise ApiError(422, "INVALID_TRANSACTION", "That transaction does not belong to you.")
    if cycle and not one(conn, "SELECT 1 AS x FROM cycles WHERE cycle = %s", (cycle,)):
        raise ApiError(422, "CYCLE_NOT_FOUND", "Unknown cycle.")
    fps_id = fps_id or one(conn, "SELECT current_fps_id FROM beneficiaries WHERE beneficiary_id = %s", (beneficiary_id,))["current_fps_id"]
    if not one(conn, "SELECT 1 AS x FROM fps WHERE fps_id = %s", (fps_id,)):
        raise ApiError(422, "FPS_NOT_FOUND", "This fair price shop does not exist.")
    seq = conn.execute("SELECT nextval('grievance_reference_seq')").fetchone()[0]
    gid = f"GRV-{seq:06d}"
    conn.execute(
        """INSERT INTO grievances (grievance_id, beneficiary_id, fps_id, category, description, created_at, status, cycle,
                                   related_transaction_id) VALUES (%s, %s, %s, %s, %s, now(), 'OPEN', %s, %s)""",
        (gid, beneficiary_id, fps_id, category, description, cycle, related_transaction_id))
    return one(conn, "SELECT grievance_id, category, description, status, resolution, created_at, resolved_at, fps_id, cycle, "
                     "related_transaction_id FROM grievances WHERE grievance_id = %s", (gid,))


def list_grievances(conn, beneficiary_id: str) -> list[dict]:
    return rows(conn, """SELECT grievance_id, category, description, status, resolution, created_at, resolved_at, fps_id,
                                cycle, related_transaction_id
                         FROM grievances WHERE beneficiary_id = %s ORDER BY created_at DESC, grievance_id DESC LIMIT 100""",
                (beneficiary_id,))
