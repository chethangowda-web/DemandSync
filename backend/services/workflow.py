"""Cross-role workflow event system.

Every significant cross-role action emits a persistent event here. These events
drive the "ACTION REQUIRED" queue in each portal and serve as the cross-portal
notification backbone. Events are never deleted; they move through
PENDING → ACKNOWLEDGED → COMPLETED (or DISMISSED).

This module is the single source of truth for cross-role workflow coordination.
It never modifies operational records (allocations, manifests, etc.) — it only
records that a transition happened and which role should act next.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from backend.services.beneficiary import iso, one, rows


def _next_id() -> str:
    return "WFE-" + uuid.uuid4().hex[:12].upper()


def emit(conn, *, cycle: str, event_type: str, source_role: str, target_role: str,
         entity_type: str, entity_id: str, created_by: str,
         payload: dict | None = None) -> str:
    """Persist a workflow event. Returns the event_id."""
    eid = _next_id()
    conn.execute(
        """INSERT INTO workflow_events
              (event_id, cycle, event_type, source_role, target_role, entity_type,
               entity_id, payload, status, created_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'PENDING', %s)""",
        (eid, cycle, event_type, source_role, target_role, entity_type,
         entity_id, __import__("json").dumps(payload or {}), created_by))
    return eid


def pending_actions(conn, role: str, district: str | None = None,
                    cycle: str | None = None, limit: int = 50) -> list[dict]:
    """Pending workflow events targeted at the given role — the ACTION REQUIRED queue.
    Only shows PENDING events. Each portal surfaces these as actionable items."""
    args: list = [role]
    q = """SELECT event_id, cycle, event_type, source_role, entity_type, entity_id,
                  payload, status, created_by, created_at
           FROM workflow_events WHERE target_role = %s AND status = 'PENDING'"""
    if cycle:
        q += " AND cycle = %s"
        args.append(cycle)
    q += " ORDER BY created_at DESC LIMIT %s"
    args.append(limit)
    out = rows(conn, q, tuple(args))
    for r in out:
        r["created_at"] = iso(r["created_at"])
    return out


def actions_summary(conn, role: str, cycle: str | None = None) -> dict:
    """Counts of pending events by type for a role."""
    args: list = [role]
    q = """SELECT event_type, count(*) AS n FROM workflow_events
           WHERE target_role = %s AND status = 'PENDING'"""
    if cycle:
        q += " AND cycle = %s"
        args.append(cycle)
    q += " GROUP BY event_type ORDER BY event_type"
    by_type = {r["event_type"]: r["n"] for r in rows(conn, q, tuple(args))}
    return {"role": role, "total_pending": sum(by_type.values()), "by_type": by_type}


def acknowledge(conn, event_id: str, user_id: str) -> dict:
    """Mark an event as acknowledged (the officer has seen it)."""
    ev = one(conn, "SELECT event_id, status FROM workflow_events WHERE event_id = %s", (event_id,))
    if not ev:
        from backend.core.errors import ApiError
        raise ApiError(404, "EVENT_NOT_FOUND", f"Workflow event {event_id} does not exist.")
    if ev["status"] != "PENDING":
        return {"event_id": event_id, "status": ev["status"], "changed": False}
    conn.execute("UPDATE workflow_events SET status = 'ACKNOWLEDGED' WHERE event_id = %s", (event_id,))
    return {"event_id": event_id, "status": "ACKNOWLEDGED", "changed": True}


def complete(conn, event_id: str, user_id: str) -> dict:
    """Mark an event as completed (the action has been taken)."""
    ev = one(conn, "SELECT event_id, status FROM workflow_events WHERE event_id = %s", (event_id,))
    if not ev:
        from backend.core.errors import ApiError
        raise ApiError(404, "EVENT_NOT_FOUND", f"Workflow event {event_id} does not exist.")
    if ev["status"] == "COMPLETED":
        return {"event_id": event_id, "status": "COMPLETED", "changed": False}
    now = datetime.now(timezone.utc)
    conn.execute(
        "UPDATE workflow_events SET status = 'COMPLETED', completed_at = %s, completed_by = %s WHERE event_id = %s",
        (now, user_id, event_id))
    return {"event_id": event_id, "status": "COMPLETED", "changed": True}


def complete_by_entity(conn, event_type: str, entity_type: str, entity_id: str,
                       user_id: str) -> int:
    """Complete all pending events matching the given type+entity. Returns the count."""
    now = datetime.now(timezone.utc)
    r = conn.execute(
        """UPDATE workflow_events SET status = 'COMPLETED', completed_at = %s, completed_by = %s
           WHERE event_type = %s AND entity_type = %s AND entity_id = %s AND status IN ('PENDING', 'ACKNOWLEDGED')""",
        (now, user_id, event_type, entity_type, entity_id))
    return r.rowcount


def events_for_entity(conn, entity_type: str, entity_id: str,
                      limit: int = 50) -> list[dict]:
    """All workflow events for a given entity, newest first."""
    out = rows(conn,
               """SELECT event_id, cycle, event_type, source_role, target_role, entity_type,
                         entity_id, payload, status, created_by, created_at, completed_at, completed_by
                  FROM workflow_events WHERE entity_type = %s AND entity_id = %s
                  ORDER BY created_at DESC LIMIT %s""",
               (entity_type, entity_id, limit))
    for r in out:
        r["created_at"] = iso(r["created_at"])
        r["completed_at"] = iso(r["completed_at"])
    return out
