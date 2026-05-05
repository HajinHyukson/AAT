from __future__ import annotations

from datetime import datetime

from engine.contracts import TimestampedRecord


def is_point_in_time_visible(record: TimestampedRecord, attribution_cutoff: datetime) -> bool:
    return record.timestamp_available <= attribution_cutoff
