"""Phase 8 — AI + Cross-Portal Intelligence.

Advisory-only intelligence layer. It READS persisted records, runs deterministic
statistics over them, reuses the XGBoost forecast envelope, and explains what it
found with evidence. It NEVER writes to authoritative tables (allocations,
manifests, inventory, intent, cycle state, entitlements, inspections, e-POS).

The only write this package ever performs is an advisory row in ai_predictions
(service='intelligence', status ADVISORY) for auditability — done by the API
layer, never inside a signal computation.

Pipeline per request:
    AUTHENTICATE -> AUTHORIZE (RBAC, server-side scoping) -> READ real rows
    -> DETERMINISTIC signals -> EXPLAIN with evidence -> RESPOND + audit log
"""
from backend.services.intelligence.schemas import Insight, GroundingContract

__all__ = ["Insight", "GroundingContract"]
