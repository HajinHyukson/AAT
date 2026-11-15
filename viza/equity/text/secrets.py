"""Stage B secret-safety utility.

The brief's §18 hard requirement: no API keys, tokens, or credentials may
appear in observations, runs, reports, proofs, fixtures, logs, API
responses, package previews, or UI payloads.

This module provides ``scan_for_secrets``, a depth-recursive substring scan
that flags any string in a structured payload (dict / list / primitive)
matching a configurable sentinel set. It is intentionally simple:
substring-match against the literal sentinel value. Tests pollute env vars
with sentinel placeholders and assert their absence from generated payloads.
"""

from __future__ import annotations

from typing import Any, Iterable


# Default sentinels used by the secret-safety tests. The brief defines these
# values verbatim; the scanner finds them as substrings so JSON encoding,
# escaping, and nesting cannot hide them.
DEFAULT_SECRET_SENTINELS: tuple[str, ...] = (
    "TEST_FMP_SECRET_SHOULD_NOT_APPEAR",
    "TEST_FRED_SECRET_SHOULD_NOT_APPEAR",
    "TEST_HF_SECRET_SHOULD_NOT_APPEAR",
)


class SecretLeakError(AssertionError):
    """Raised when a sentinel value is found in a payload."""

    def __init__(self, sentinel: str, location: str) -> None:
        super().__init__(
            f"secret sentinel {sentinel!r} found at {location}; "
            "credentials must never appear in generated artifacts"
        )
        self.sentinel = sentinel
        self.location = location


def scan_for_secrets(
    payload: Any,
    *,
    sentinels: Iterable[str] = DEFAULT_SECRET_SENTINELS,
    location: str = "$",
) -> None:
    """Recursively scan payload for any sentinel substring.

    Raises ``SecretLeakError`` on the first hit. On clean payloads, returns
    None. Walks dict values, list/tuple items, and stringifies primitives.
    """
    sentinel_list = tuple(sentinels)
    if isinstance(payload, str):
        for sentinel in sentinel_list:
            if sentinel in payload:
                raise SecretLeakError(sentinel=sentinel, location=location)
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_location = f"{location}.{key}" if not str(key).startswith("[") else f"{location}{key}"
            scan_for_secrets(value, sentinels=sentinel_list, location=child_location)
        return
    if isinstance(payload, (list, tuple)):
        for idx, item in enumerate(payload):
            scan_for_secrets(item, sentinels=sentinel_list, location=f"{location}[{idx}]")
        return
    # bools, ints, floats, None: stringify and scan defensively.
    text = repr(payload)
    for sentinel in sentinel_list:
        if sentinel in text:
            raise SecretLeakError(sentinel=sentinel, location=location)
