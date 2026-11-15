from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def canonical_json_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", by_alias=True)
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        + "\n"
    ).encode("utf-8")


def normalize_section_payload(value: bytes | str | dict[str, Any] | list[Any] | BaseModel) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    return canonical_json_bytes(value)


def sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def checksum_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def manifest_checksum_payload(manifest_payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(manifest_payload)
    integrity = dict(payload.get("integrity") or {})
    integrity.pop("manifest_checksum", None)
    integrity.pop("container_checksum", None)
    payload["integrity"] = integrity
    return payload


def checksum_manifest_payload(manifest_payload: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(manifest_checksum_payload(manifest_payload)))
