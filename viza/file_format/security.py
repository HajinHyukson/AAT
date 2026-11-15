from __future__ import annotations

import re
import stat
from pathlib import PurePosixPath
from typing import Any
from zipfile import ZipFile, ZipInfo

from viza.file_format.models import VizaFileSecurityError


MAX_FILE_COUNT = 256
MAX_MANIFEST_SIZE = 1_000_000
MAX_SECTION_SIZE = 25_000_000

BLOCKED_SUFFIXES = frozenset(
    {
        ".bat",
        ".cmd",
        ".dll",
        ".dylib",
        ".exe",
        ".js",
        ".ps1",
        ".py",
        ".sh",
        ".so",
        ".ts",
    }
)

CREDENTIAL_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "auth_token",
    "client_secret",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)


def normalize_zip_path(path: str) -> str:
    value = str(path or "").strip().replace("\\", "/")
    if not value:
        raise VizaFileSecurityError("ZIP member path is empty.")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise VizaFileSecurityError(f"ZIP member path is absolute: {path}")
    pure_path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in pure_path.parts):
        raise VizaFileSecurityError(f"ZIP member path is unsafe: {path}")
    normalized = str(pure_path)
    if PurePosixPath(normalized).suffix.lower() in BLOCKED_SUFFIXES:
        raise VizaFileSecurityError(f"Executable payloads are not allowed: {path}")
    return normalized


def validate_zip_members(zip_file: ZipFile) -> None:
    infos = zip_file.infolist()
    if len(infos) > MAX_FILE_COUNT:
        raise VizaFileSecurityError("VIZA container has too many files.")

    seen: set[str] = set()
    for info in infos:
        normalized = normalize_zip_path(info.filename.rstrip("/") if info.is_dir() else info.filename)
        if normalized in seen and not info.is_dir():
            raise VizaFileSecurityError(f"Duplicate ZIP member path: {normalized}")
        seen.add(normalized)
        validate_zip_info(info)


def validate_zip_info(info: ZipInfo) -> None:
    normalize_zip_path(info.filename.rstrip("/") if info.is_dir() else info.filename)
    file_type = (info.external_attr >> 16) & 0o170000
    if file_type == stat.S_IFLNK:
        raise VizaFileSecurityError(f"ZIP symlinks are not allowed: {info.filename}")
    if info.filename == "manifest.json" and info.file_size > MAX_MANIFEST_SIZE:
        raise VizaFileSecurityError("VIZA manifest is too large.")
    if not info.is_dir() and info.file_size > MAX_SECTION_SIZE:
        raise VizaFileSecurityError(f"VIZA section is too large: {info.filename}")


def assert_no_credentials(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            key_text = str(key).lower()
            if any(fragment in key_text for fragment in CREDENTIAL_KEY_FRAGMENTS):
                raise VizaFileSecurityError(f"Credential-like key is not allowed at {path}.{key}")
            assert_no_credentials(nested_value, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            assert_no_credentials(item, f"{path}[{index}]")
