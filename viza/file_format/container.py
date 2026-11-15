from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from pydantic import ValidationError

from viza.file_format.checksums import (
    canonical_json_bytes,
    checksum_file,
    checksum_manifest_payload,
    normalize_section_payload,
    sha256_bytes,
)
from viza.file_format.models import (
    CANONICAL_SECTION_NAMES,
    DEFAULT_SECTION_PATHS,
    LEGACY_DOCUMENT_SCHEMA_ALIASES,
    VIZA_DOCUMENT_SCHEMA_VERSION,
    SectionStatus,
    VizaChecksumError,
    VizaFileError,
    VizaFileManifest,
    VizaInspectionResult,
    VizaManifestError,
    VizaSectionReadResult,
    VizaSectionUnavailableError,
    VizaWriteResult,
)
from viza.file_format.security import (
    assert_no_credentials,
    normalize_zip_path,
    validate_zip_members,
)


def write_viza_container(
    target_path: str | Path,
    manifest: VizaFileManifest,
    sections: dict[str, bytes | str | dict[str, Any] | list[Any]],
) -> VizaWriteResult:
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    writable_manifest = manifest.model_copy(deep=True)
    warnings: list[str] = []
    section_payloads: dict[str, bytes] = {}
    section_checksums: dict[str, str] = {}

    for section_name, descriptor in writable_manifest.sections.items():
        if descriptor.status != SectionStatus.INCLUDED:
            if section_name in sections:
                warnings.append(f"Ignored payload for {descriptor.status.value} section: {section_name}")
            descriptor.path = None
            descriptor.checksum = None
            continue

        if section_name not in sections:
            raise VizaManifestError(f"included section is missing payload: {section_name}")
        path = normalize_zip_path(descriptor.path or DEFAULT_SECTION_PATHS.get(section_name, section_name))
        payload_value = sections[section_name]
        assert_no_credentials(payload_value, path=f"sections.{section_name}")
        payload = normalize_section_payload(payload_value)
        checksum = sha256_bytes(payload)
        descriptor.path = path
        descriptor.checksum = checksum
        section_payloads[path] = payload
        section_checksums[section_name] = checksum

    assert_no_credentials(
        writable_manifest.model_dump(mode="json", by_alias=True),
        path="manifest",
    )
    manifest_payload = writable_manifest.model_dump(mode="json", by_alias=True)
    manifest_checksum = checksum_manifest_payload(manifest_payload)
    writable_manifest.integrity = {
        **writable_manifest.integrity,
        "manifest_checksum": manifest_checksum,
    }
    manifest_bytes = canonical_json_bytes(
        writable_manifest.model_dump(mode="json", by_alias=True)
    )

    with ZipFile(target, mode="w", compression=ZIP_DEFLATED) as zip_file:
        zip_file.writestr("manifest.json", manifest_bytes)
        for section_path, payload in sorted(section_payloads.items()):
            zip_file.writestr(section_path, payload)

    container_checksum = checksum_file(target)
    return VizaWriteResult(
        path=str(target),
        file_id=writable_manifest.file_id,
        manifest_checksum=manifest_checksum,
        container_checksum=container_checksum,
        section_checksums=section_checksums,
        warnings=warnings,
    )


def read_viza_manifest(path: str | Path) -> VizaFileManifest:
    try:
        with ZipFile(Path(path), mode="r") as zip_file:
            validate_zip_members(zip_file)
            payload = _read_manifest_payload(zip_file)
    except BadZipFile as exc:
        raise VizaManifestError("VIZA container is not a readable ZIP file.") from exc
    try:
        return VizaFileManifest.model_validate(payload)
    except ValidationError as exc:
        raise VizaManifestError(f"VIZA manifest is invalid: {exc}") from exc


def inspect_viza_container(path: str | Path) -> VizaInspectionResult:
    container_path = Path(path)
    warnings: list[str] = []
    errors: list[str] = []
    entries: list[str] = []
    manifest_payload: dict[str, Any] = {}
    manifest_checksum: str | None = None
    file_id: str | None = None
    section_statuses: dict[str, str] = {}
    visualization_manifest: VizaFileManifest | None = None

    try:
        with ZipFile(container_path, mode="r") as zip_file:
            validate_zip_members(zip_file)
            entries = sorted(
                normalize_zip_path(info.filename)
                for info in zip_file.infolist()
                if not info.is_dir()
            )
            manifest_payload = _read_manifest_payload(zip_file)
            file_id = _read_string(manifest_payload.get("file_id"))
            raw_schema = _read_string(manifest_payload.get("schema"))
            if raw_schema is None:
                errors.append("VIZA manifest schema is missing.")
                return _inspection_result(
                    container_path=container_path,
                    status="invalid",
                    manifest_payload=manifest_payload,
                    file_id=file_id,
                    entries=entries,
                    manifest_checksum=None,
                    warnings=warnings,
                    errors=errors,
                )
            if raw_schema not in {VIZA_DOCUMENT_SCHEMA_VERSION, *LEGACY_DOCUMENT_SCHEMA_ALIASES}:
                warnings.append(f"Unsupported VIZA file schema: {raw_schema or 'missing'}")
                return _inspection_result(
                    container_path=container_path,
                    status="warning",
                    manifest_payload=manifest_payload,
                    file_id=file_id,
                    entries=entries,
                    manifest_checksum=None,
                    warnings=warnings,
                    errors=errors,
                )

            manifest = VizaFileManifest.model_validate(manifest_payload)
            visualization_manifest = manifest
            manifest_payload = manifest.model_dump(mode="json", by_alias=True)
            file_id = manifest.file_id
            section_statuses = manifest.section_statuses()
            manifest_checksum = checksum_manifest_payload(manifest_payload)
            stored_manifest_checksum = _read_string(
                manifest.integrity.get("manifest_checksum")
            )
            if stored_manifest_checksum and stored_manifest_checksum != manifest_checksum:
                warnings.append("Manifest checksum does not match manifest content.")

            entry_set = set(entries)
            for section_name, descriptor in manifest.sections.items():
                if section_name not in CANONICAL_SECTION_NAMES:
                    warnings.append(f"Unknown section is preserved but not executable: {section_name}")
                if descriptor.status != SectionStatus.INCLUDED:
                    continue
                if not descriptor.path:
                    errors.append(f"Included section has no path: {section_name}")
                    continue
                section_path = normalize_zip_path(descriptor.path)
                if section_path not in entry_set:
                    errors.append(f"Included section is missing from container: {section_name}")
    except (BadZipFile, OSError, VizaFileError, ValidationError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    status = "invalid" if errors else "warning" if warnings else "ok"
    result = _inspection_result(
        container_path=container_path,
        status=status,
        manifest_payload=manifest_payload,
        file_id=file_id,
        entries=entries,
        manifest_checksum=manifest_checksum,
        warnings=warnings,
        errors=errors,
        section_statuses=section_statuses,
    )
    if visualization_manifest is not None:
        from viza.file_format.visualization import build_file_visualization

        result.visualization = build_file_visualization(visualization_manifest, result)
    return result


def read_viza_section(path: str | Path, section_name: str) -> VizaSectionReadResult:
    manifest = read_viza_manifest(path)
    descriptor = manifest.sections.get(section_name)
    if descriptor is None:
        raise VizaSectionUnavailableError(f"unknown VIZA section: {section_name}")
    if descriptor.status != SectionStatus.INCLUDED:
        raise VizaSectionUnavailableError(
            f"section {section_name} is {descriptor.status.value} and cannot be read"
        )
    if not descriptor.path:
        raise VizaSectionUnavailableError(f"section {section_name} has no path")

    section_path = normalize_zip_path(descriptor.path)
    try:
        with ZipFile(Path(path), mode="r") as zip_file:
            validate_zip_members(zip_file)
            try:
                payload = zip_file.read(section_path)
            except KeyError as exc:
                raise VizaSectionUnavailableError(
                    f"section {section_name} is missing from container"
                ) from exc
    except BadZipFile as exc:
        raise VizaManifestError("VIZA container is not a readable ZIP file.") from exc

    checksum = sha256_bytes(payload)
    if descriptor.checksum and descriptor.checksum != checksum:
        raise VizaChecksumError(f"checksum mismatch for section {section_name}")
    return VizaSectionReadResult(
        section_name=section_name,
        path=section_path,
        schema=descriptor.schema_name,
        checksum=checksum,
        content=payload,
    )


def _read_manifest_payload(zip_file: ZipFile) -> dict[str, Any]:
    names = {info.filename for info in zip_file.infolist() if not info.is_dir()}
    if "manifest.json" not in names:
        raise VizaManifestError("VIZA container is missing manifest.json.")
    raw = zip_file.read("manifest.json")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VizaManifestError("VIZA manifest is not valid UTF-8 JSON.") from exc
    if not isinstance(payload, dict):
        raise VizaManifestError("VIZA manifest must be a JSON object.")
    return payload


def _inspection_result(
    *,
    container_path: Path,
    status: str,
    manifest_payload: dict[str, Any],
    file_id: str | None,
    entries: list[str],
    manifest_checksum: str | None,
    warnings: list[str],
    errors: list[str],
    section_statuses: dict[str, str] | None = None,
) -> VizaInspectionResult:
    container_checksum = checksum_file(container_path) if container_path.exists() else None
    return VizaInspectionResult(
        path=str(container_path),
        file_id=file_id,
        status=status,
        manifest=manifest_payload,
        manifest_checksum=manifest_checksum,
        container_checksum=container_checksum,
        section_statuses=section_statuses or {},
        entries=entries,
        warnings=warnings,
        errors=errors,
    )


def _read_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
