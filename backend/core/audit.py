"""Append-only, hash-chained audit trail written to audit_events.

Each event's hash covers its own content plus the previous event's hash, so editing or removing history
is detectable (verify_chain). Events are written on their own connection so a failed login is still
recorded even if the request's transaction rolls back. Never pass passwords, OTPs or tokens in here.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from backend.db.conn import connect

_CHAIN_LOCK_KEY = 72_657_001  # pg_advisory_xact_lock key serialising chain appends


def _digest(prev_hash: str, e: dict) -> str:
    body = json.dumps(
        {k: e[k] for k in ("audit_event_id", "cycle", "actor_user_id", "actor_role", "action", "entity_type",
                           "entity_id", "reason", "result", "timestamp", "before_state", "after_state")},
        sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()


def write_audit(actor: str, role: str, action: str, result: str, reason: str = "",
                entity_type: str = "USER", entity_id: str | None = None, cycle: str | None = None,
                before: str | None = None, after: str | None = None, url: str | None = None) -> str:
    """Append one event and return its id. Raises on failure: an action that cannot be audited should not proceed."""
    event = {
        "audit_event_id": "AUD-" + uuid.uuid4().hex[:12].upper(),
        "cycle": cycle, "actor_user_id": actor or "unknown", "actor_role": role or "unknown",
        "action": action, "entity_type": entity_type, "entity_id": entity_id or actor or "unknown",
        "reason": reason or None, "result": result,
        "before_state": before, "after_state": after,
    }
    with connect(url) as conn, conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_CHAIN_LOCK_KEY,))
        # timestamp is taken while holding the lock so chain order always equals time order
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        row = conn.execute("SELECT hash FROM audit_events ORDER BY timestamp DESC, audit_event_id DESC LIMIT 1").fetchone()
        event["hash"] = _digest(row[0] if row and row[0] else "", event)
        conn.execute(
            """INSERT INTO audit_events (audit_event_id, cycle, actor_user_id, actor_role, action, entity_type,
                   entity_id, reason, result, timestamp, before_state, after_state, hash)
               VALUES (%(audit_event_id)s, %(cycle)s, %(actor_user_id)s, %(actor_role)s, %(action)s, %(entity_type)s,
                   %(entity_id)s, %(reason)s, %(result)s, %(timestamp)s, %(before_state)s, %(after_state)s, %(hash)s)""",
            event)
    return event["audit_event_id"]


_CHAINED_ID_LEN = 16  # "AUD-" + 12 hex chars; seeded dataset ids ("AUD-0000001") are shorter


def verify_chain(url: str | None = None) -> dict:
    """Recompute the hash chain over events written by write_audit (identified by their 16-char id).

    Seeded dataset events predate the chain and are only used as its starting anchor."""
    with connect(url) as conn:
        rows = conn.execute(
            """SELECT audit_event_id, cycle, actor_user_id, actor_role, action, entity_type, entity_id, reason, result,
                      timestamp, before_state, after_state, hash
               FROM audit_events ORDER BY timestamp, audit_event_id""").fetchall()
    cols = ("audit_event_id", "cycle", "actor_user_id", "actor_role", "action", "entity_type", "entity_id",
            "reason", "result", "timestamp", "before_state", "after_state", "hash")
    prev, checked, broken = "", 0, []
    for r in rows:
        e = dict(zip(cols, r))
        if len(e["audit_event_id"]) == _CHAINED_ID_LEN:
            e["timestamp"] = e["timestamp"].isoformat()
            if _digest(prev, e) != e["hash"]:
                broken.append(e["audit_event_id"])
            checked += 1
        prev = r[-1] or prev
    return {"checked": checked, "broken": broken, "intact": not broken}
