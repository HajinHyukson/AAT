from __future__ import annotations

from datetime import datetime


def evidence_payload_is_visible(*, evidence_payload: dict | None, attribution_cutoff: datetime) -> bool:
    if not evidence_payload:
        return True
    raw_timestamp = evidence_payload.get("timestamp_available")
    if raw_timestamp is None:
        return True
    timestamp = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
    return timestamp <= attribution_cutoff
