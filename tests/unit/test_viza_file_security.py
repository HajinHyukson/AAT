from __future__ import annotations

import json
from datetime import datetime, timezone
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from viza.file_format import inspect_viza_container, read_viza_manifest, read_viza_section
from viza.file_format.container import write_viza_container
from viza.file_format.models import (
    SectionStatus,
    VisibilityMode,
    VizaFileManifest,
    VizaFileSecurityError,
    VizaManifestError,
    VizaSectionDescriptor,
    VizaSectionUnavailableError,
)


def test_missing_manifest_is_rejected(tmp_path) -> None:
    target = tmp_path / "missing-manifest.viza"
    with ZipFile(target, mode="w", compression=ZIP_DEFLATED) as zip_file:
        zip_file.writestr("graph/methodology.json", "{}")

    inspection = inspect_viza_container(target)

    assert inspection.status == "invalid"
    assert any("missing manifest.json" in error for error in inspection.errors)
    with pytest.raises(VizaManifestError, match="missing manifest"):
        read_viza_manifest(target)


def test_invalid_manifest_is_rejected(tmp_path) -> None:
    target = tmp_path / "invalid-manifest.viza"
    with ZipFile(target, mode="w", compression=ZIP_DEFLATED) as zip_file:
        zip_file.writestr("manifest.json", "{}")

    inspection = inspect_viza_container(target)

    assert inspection.status == "invalid"
    assert any("schema is missing" in error for error in inspection.errors)
    with pytest.raises(VizaManifestError, match="manifest is invalid"):
        read_viza_manifest(target)


def test_path_traversal_member_is_blocked(tmp_path) -> None:
    target = tmp_path / "traversal.viza"
    with ZipFile(target, mode="w", compression=ZIP_DEFLATED) as zip_file:
        zip_file.writestr("manifest.json", "{}")
        zip_file.writestr("../evil.json", "{}")

    inspection = inspect_viza_container(target)

    assert inspection.status == "invalid"
    assert any("unsafe" in error for error in inspection.errors)


def test_executable_payload_is_blocked(tmp_path) -> None:
    target = tmp_path / "script.viza"
    with ZipFile(target, mode="w", compression=ZIP_DEFLATED) as zip_file:
        zip_file.writestr("manifest.json", "{}")
        zip_file.writestr("scripts/run.py", "print('nope')")

    inspection = inspect_viza_container(target)

    assert inspection.status == "invalid"
    assert any("Executable payloads" in error for error in inspection.errors)


def test_redacted_and_entitlement_locked_sections_are_not_bundled(tmp_path) -> None:
    target = tmp_path / "redacted.viza"
    manifest = _manifest(
        {
            "signal_outputs": VizaSectionDescriptor(
                status=SectionStatus.REDACTED,
                reason="creator_black_box_permission",
            ),
            "validation_proof": VizaSectionDescriptor(
                status=SectionStatus.ENTITLEMENT_LOCKED,
                reason="subscription_required",
            ),
        }
    )

    result = write_viza_container(
        target,
        manifest,
        {
            "signal_outputs": {"hidden": "value"},
            "validation_proof": {"locked": True},
        },
    )

    with ZipFile(target, mode="r") as zip_file:
        names = set(zip_file.namelist())
    assert "signals/signal_outputs.json" not in names
    assert "proof/validation_manifest.json" not in names
    assert result.warnings
    with pytest.raises(VizaSectionUnavailableError, match="redacted"):
        read_viza_section(target, "signal_outputs")
    with pytest.raises(VizaSectionUnavailableError, match="entitlement_locked"):
        read_viza_section(target, "validation_proof")


def test_credential_like_keys_are_rejected(tmp_path) -> None:
    target = tmp_path / "credentials.viza"
    manifest = _manifest(
        {
            "rights": VizaSectionDescriptor(
                status=SectionStatus.INCLUDED,
                path="rights/license_and_entitlements.json",
                schema="viza_rights_v0",
            )
        }
    )

    with pytest.raises(VizaFileSecurityError, match="Credential-like key"):
        write_viza_container(
            target,
            manifest,
            {"rights": {"api_key": "should-not-be-exported"}},
        )


def _manifest(sections: dict[str, VizaSectionDescriptor]) -> VizaFileManifest:
    timestamp = datetime.now(timezone.utc)
    return VizaFileManifest(
        schema="viza.document.v1",
        file_id="test-file",
        display_name="Security Test",
        object_kind="methodology",
        primary_mode="methodology_graph",
        exchange_modes=["methodology_graph"],
        visibility=VisibilityMode.WHITE_BOX,
        created_at=timestamp,
        updated_at=timestamp,
        sections=sections,
        minimum_viza_version="0.2.0",
    )
