from __future__ import annotations

import hashlib


def advisory_lock_key(name: str) -> int:
    """Return a deterministic signed int64 key for PostgreSQL advisory locks."""
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)
