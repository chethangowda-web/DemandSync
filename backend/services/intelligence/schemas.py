"""Phase 8 intelligence contracts.

Every insight follows the AI grounding contract: WHAT / WHY / EVIDENCE /
WHAT CAN I DO, plus model/dataset versioning and an explicit ADVISORY status.
Confidence is None unless a real statistical/model value exists — the API and
UI must render that as "Confidence unavailable", never a fabricated number.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


ADVISORY = "ADVISORY"
DATA_UNAVAILABLE = "DATA UNAVAILABLE"
CONFIDENCE_UNAVAILABLE = "Confidence unavailable"
STALE_AFTER_HOURS = 48


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Insight(dict):
    """A single grounded insight. A dict subclass so it serialises directly."""

    def __init__(self, *, insight_id: str, type: str, severity: str, title: str,
                 summary: str, recommendation: str | None = None,
                 entity_type: str | None = None, entity_id: str | None = None,
                 evidence: list[dict] | None = None,
                 calculation: dict | None = None,
                 source_records: list[str] | None = None,
                 model_type: str = "deterministic",
                 model_version: str | None = None,
                 dataset_version: str | None = None,
                 confidence: float | int | None = None,
                 stale: bool = False,
                 data_timestamp: str | None = None):
        super().__init__(
            insight_id=insight_id, type=type, severity=severity, title=title,
            summary=summary, recommendation=recommendation,
            entity_type=entity_type, entity_id=entity_id,
            evidence=evidence or [], calculation=calculation or {},
            source_records=source_records or [],
            model_type=model_type, model_version=model_version,
            dataset_version=dataset_version,
            generated_at=utcnow_iso(), confidence=confidence,
            confidence_display=(confidence if confidence is not None else CONFIDENCE_UNAVAILABLE),
            stale=stale, data_timestamp=data_timestamp,
            status=ADVISORY,
        )


GroundingContract = Insight


def evidence_item(*, record: str, field: str | None = None, value: Any = None,
                  detail: str | None = None) -> dict:
    item: dict = {"record": record}
    if field is not None:
        item["field"] = field
    if value is not None:
        item["value"] = value
    if detail is not None:
        item["detail"] = detail
    return item


def brief_section(title: str, lines: list[str]) -> dict:
    return {"title": title, "lines": lines}
