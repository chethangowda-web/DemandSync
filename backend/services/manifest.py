"""Manifest sealing and cycle authorization for the DSO: OPTIMIZED -> AUTHORIZED. See
docs/AI_ARCHITECTURE.md / the Phase 2 plan's Slice 4.

Every manifest this app creates is prefixed "MFO-" (routing.py) -- distinct from the seeded dataset's own
historical manifests ("MAN-NNNNNN"), which already exist for every cycle and are not this workflow's
concern. Every query here that scopes to "this workflow's manifests" filters on that prefix; the lesson
from Slices 1-3 (seeded historical data colliding with a naive "any row for this cycle" check) applies
here just as much as it did to demand_forecast, allocations, and dispatch_manifest_items.

manifest_status: DRAFT -> VALIDATED -> LOCKED. Once LOCKED, migration 0002's manifest_sealed trigger makes
the manifest's content immutable at the DB level -- this module's lock_manifest() is the one and only
place that transition happens, and it happens together with computing the seal (sha256_hash, qr_payload)
in the same UPDATE, matching the trigger's OLD-state check.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from datetime import datetime, timezone

import qrcode

from backend.core.errors import ApiError
from backend.services.beneficiary import num, one, rows

MY_MANIFEST_PREFIX = "MFO-"


def _canonical_manifest(conn, manifest_id: str) -> dict:
    m = one(conn, """SELECT manifest_id, cycle, warehouse_id, vehicle_id, total_kg
                     FROM dispatch_manifests WHERE manifest_id = %s""", (manifest_id,))
    items = rows(conn, """SELECT fps_id, commodity, planned_kg, sequence_number FROM dispatch_manifest_items
                          WHERE manifest_id = %s ORDER BY sequence_number, commodity""", (manifest_id,))
    route = rows(conn, """SELECT fps_id, stop_sequence, distance_from_previous_km, eta_minutes FROM vehicle_routes
                          WHERE manifest_id = %s ORDER BY stop_sequence""", (manifest_id,))
    return {"manifest_id": m["manifest_id"], "cycle": m["cycle"], "warehouse_id": m["warehouse_id"],
            "vehicle_id": m["vehicle_id"], "total_kg": m["total_kg"], "items": items, "route": route}


def manifest_hash(canonical: dict) -> str:
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _get_manifest(conn, manifest_id: str, for_update: bool = False) -> dict:
    suffix = " FOR UPDATE" if for_update else ""
    m = one(conn, f"""SELECT manifest_id, cycle, warehouse_id, vehicle_id, manifest_status, total_kg
                      FROM dispatch_manifests WHERE manifest_id = %s{suffix}""", (manifest_id,))
    if not m:
        raise ApiError(404, "MANIFEST_NOT_FOUND", f"No manifest {manifest_id}.")
    if not m["manifest_id"].startswith(MY_MANIFEST_PREFIX):
        raise ApiError(422, "NOT_A_LIVE_MANIFEST",
                       f"{manifest_id} is historical seed data, not a manifest this workflow produced; it cannot be validated or locked.")
    return m


def validate_manifest(conn, manifest_id: str, officer_id: str) -> dict:
    """DRAFT -> VALIDATED. Re-checks the manifest's own arithmetic and that it still matches the live
    allocations it was built from (an override could in principle have changed one since Slice 3 ran).
    Never advances a manifest whose numbers don't add up."""
    m = _get_manifest(conn, manifest_id, for_update=True)
    if m["manifest_status"] != "DRAFT":
        raise ApiError(409, "MANIFEST_NOT_DRAFT", f"Manifest {manifest_id} is {m['manifest_status']}, not DRAFT.",
                       {"manifest_status": m["manifest_status"]})

    items = rows(conn, "SELECT fps_id, commodity, planned_kg, allocation_id FROM dispatch_manifest_items WHERE manifest_id = %s", (manifest_id,))
    problems = []
    items_total = round(sum(num(i["planned_kg"]) for i in items), 1)
    if items_total != num(m["total_kg"]):
        problems.append(f"manifest total_kg {m['total_kg']} does not equal the sum of its items {items_total}")
    vehicle = one(conn, "SELECT capacity_kg FROM vehicles WHERE vehicle_id = %s", (m["vehicle_id"],))
    if vehicle and num(m["total_kg"]) > num(vehicle["capacity_kg"]):
        problems.append(f"manifest total_kg {m['total_kg']} exceeds vehicle {m['vehicle_id']}'s capacity {vehicle['capacity_kg']}kg")
    for it in items:
        a = one(conn, "SELECT allocated_kg, status FROM allocations WHERE allocation_id = %s", (it["allocation_id"],))
        if not a:
            problems.append(f"{it['fps_id']}/{it['commodity']}: its allocation {it['allocation_id']} no longer exists")
        elif num(a["allocated_kg"]) != num(it["planned_kg"]):
            problems.append(f"{it['fps_id']}/{it['commodity']}: planned {it['planned_kg']}kg no longer matches the "
                            f"current allocation of {a['allocated_kg']}kg (it was overridden after routing)")
        elif a["status"] != "APPROVED":
            problems.append(f"{it['fps_id']}/{it['commodity']}: its allocation is now {a['status']}, not APPROVED")

    if problems:
        raise ApiError(422, "VALIDATION_FAILED", "; ".join(problems), {"problems": problems})

    with conn.transaction():
        conn.execute("UPDATE dispatch_manifests SET manifest_status = 'VALIDATED' WHERE manifest_id = %s", (manifest_id,))
    return {"manifest_id": manifest_id, "manifest_status": "VALIDATED"}


def lock_manifest(conn, manifest_id: str, officer_id: str) -> dict:
    """VALIDATED -> LOCKED. Seals the manifest: SHA256 over its canonical content, a QR payload carrying
    that hash for a field scan to verify against. This is the one write that makes it immutable."""
    m = _get_manifest(conn, manifest_id, for_update=True)
    if m["manifest_status"] != "VALIDATED":
        raise ApiError(409, "MANIFEST_NOT_VALIDATED", f"Manifest {manifest_id} is {m['manifest_status']}, not VALIDATED.",
                       {"manifest_status": m["manifest_status"]})

    canonical = _canonical_manifest(conn, manifest_id)
    sha = manifest_hash(canonical)
    now = datetime.now(timezone.utc)
    qr_payload = json.dumps({"manifest_id": manifest_id, "cycle": m["cycle"], "vehicle_id": m["vehicle_id"],
                             "sha256_hash": sha}, sort_keys=True, separators=(",", ":"))
    with conn.transaction():
        conn.execute("""UPDATE dispatch_manifests SET manifest_status = 'LOCKED', sha256_hash = %s, qr_payload = %s,
                            locked_by = %s, locked_at = %s WHERE manifest_id = %s""",
                    (sha, qr_payload, officer_id, now, manifest_id))
    return {"manifest_id": manifest_id, "manifest_status": "LOCKED", "sha256_hash": sha, "qr_payload": qr_payload}


def manifest_qr_png_base64(conn, manifest_id: str) -> str:
    m = one(conn, "SELECT qr_payload FROM dispatch_manifests WHERE manifest_id = %s", (manifest_id,))
    if not m:
        raise ApiError(404, "MANIFEST_NOT_FOUND", f"No manifest {manifest_id}.")
    if not m["qr_payload"]:
        raise ApiError(409, "MANIFEST_NOT_LOCKED", f"Manifest {manifest_id} has no QR payload yet; lock it first.")
    img = qrcode.make(m["qr_payload"])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def get_lock_verification(conn, manifest_id: str) -> dict:
    """Recomputes the manifest's hash from its current DB content and compares to the sealed value --
    the same tamper-evidence pattern as demand_locks (demand.py:get_lock)."""
    m = one(conn, "SELECT manifest_status, sha256_hash FROM dispatch_manifests WHERE manifest_id = %s", (manifest_id,))
    if not m:
        raise ApiError(404, "MANIFEST_NOT_FOUND", f"No manifest {manifest_id}.")
    if m["manifest_status"] not in ("LOCKED", "DISPATCHED", "DELIVERED", "RECONCILED"):
        raise ApiError(409, "MANIFEST_NOT_LOCKED", f"Manifest {manifest_id} is {m['manifest_status']}, not yet sealed.")
    recomputed = manifest_hash(_canonical_manifest(conn, manifest_id))
    return {"manifest_id": manifest_id, "sha256_hash": m["sha256_hash"], "hash_verified": recomputed == m["sha256_hash"]}


# ------------------------------------------------------------------ cycle authorization

def authorize_cycle(conn, cycle: str, officer_id: str) -> dict:
    """OPTIMIZED -> AUTHORIZED. The DSO's final human sign-off: every manifest this workflow produced for
    the cycle must be sealed (LOCKED) first. The seeded dataset's own historical manifests for this same
    cycle (a different id prefix entirely) are not this workflow's concern and are never checked here."""
    c = one(conn, "SELECT state FROM cycles WHERE cycle = %s FOR UPDATE", (cycle,))
    if not c:
        raise ApiError(404, "CYCLE_NOT_FOUND", f"Cycle {cycle} does not exist.")
    if c["state"] == "AUTHORIZED":
        raise ApiError(409, "CYCLE_ALREADY_AUTHORIZED", f"Cycle {cycle} has already been authorized.")
    if c["state"] != "OPTIMIZED":
        raise ApiError(409, "CYCLE_NOT_OPTIMIZED", f"Cycle {cycle} is {c['state']}, not OPTIMIZED. It cannot be authorized.",
                       {"state": c["state"]})

    mine = rows(conn, f"""SELECT manifest_id, manifest_status FROM dispatch_manifests
                          WHERE cycle = %s AND manifest_id LIKE '{MY_MANIFEST_PREFIX}%%'""", (cycle,))
    not_locked = [m["manifest_id"] for m in mine if m["manifest_status"] != "LOCKED"]
    if not_locked:
        raise ApiError(409, "MANIFESTS_NOT_LOCKED",
                       f"{len(not_locked)} manifest(s) are not yet LOCKED; validate and lock every manifest before authorizing.",
                       {"unlocked_manifest_ids": not_locked})

    now = datetime.now(timezone.utc)
    with conn.transaction():
        conn.execute("UPDATE cycles SET state = 'AUTHORIZED' WHERE cycle = %s", (cycle,))
    return {"cycle": cycle, "state": "AUTHORIZED", "manifests_authorized": len(mine)}
