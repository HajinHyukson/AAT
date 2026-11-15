"""Pin-5 model release-date table for the live_historical_PIT gate.

Hand-curated, versioned. One entry per supported model_id+model_version pair.
The look-ahead audit test in tests/lookahead_audit/ uses this table to verify
that historical-PIT replays cannot silently use models that did not exist at
the requested cutoff timestamp.

Dates are the public release dates of the model artifact, not the publication
date of any paper. When a model_version is missing from this table, the
``live_historical_PIT`` mode MUST return status="block" with reason
``model_release_date_unknown``.
"""

from __future__ import annotations

from datetime import date


# (model_id, model_version) -> public release date.
#
# ProsusAI/finbert: the canonical FinBERT artifact on Hugging Face was first
# pushed in 2019; we record an intentionally conservative date that the
# look-ahead audit can rely on without overstating provenance certainty.
# Any cutoff_timestamp before this date with a "pinned" model_policy targeting
# ProsusAI/finbert MUST be blocked.
MODEL_RELEASE_DATES: dict[tuple[str, str], date] = {
    ("ProsusAI/finbert", "v1.0"): date(2019, 9, 30),
    # Future model_versions are added here explicitly. The audit test fails
    # closed if a request references a (model_id, model_version) not in this
    # table.
}


def model_released_by(*, model_id: str, model_version: str, cutoff: date) -> bool:
    """True iff (model_id, model_version) was released on or before cutoff.

    Raises ``ModelReleaseDateUnknown`` if the pair is absent from the table,
    so the caller can convert that to a blocking resolver response rather than
    silently treat-as-released.
    """
    key = (model_id, model_version)
    release = MODEL_RELEASE_DATES.get(key)
    if release is None:
        raise ModelReleaseDateUnknown(model_id=model_id, model_version=model_version)
    return release <= cutoff


class ModelReleaseDateUnknown(LookupError):
    """Raised when a (model_id, model_version) is not in the release table."""

    def __init__(self, *, model_id: str, model_version: str) -> None:
        super().__init__(
            f"model release date not recorded for ({model_id}, {model_version})"
        )
        self.model_id = model_id
        self.model_version = model_version
