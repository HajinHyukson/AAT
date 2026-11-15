from __future__ import annotations

import json
import zipfile

import pytest

from viza.file_format.container import read_viza_manifest, read_viza_section
from viza.file_format.export import export_methodology_graph_to_viza
from viza.file_format.models import VisibilityMode
from viza.graph_schema import MethodologyGraph, load_methodology_graph
from viza.marketplace import MARKETPLACE_DRAFT_PURPOSE
from viza.project_store import CreatorRecordRequest, get_project_store
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH
from viza.service import app


def _graph() -> MethodologyGraph:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    payload = graph.model_dump(mode="json")
    payload["metadata"]["performance_claim"] = "Prototype backtest claim for review only."
    score_node = next(node for node in payload["nodes"] if node["id"] == "score-1")
    score_node["config"]["weights"] = {"proprietary_alpha": 0.12345}
    return MethodologyGraph.model_validate(payload)


def test_marketplace_draft_export_contains_review_metadata_only(tmp_path) -> None:
    target = tmp_path / "marketplace-draft.viza"

    export_methodology_graph_to_viza(
        _graph(),
        target,
        purpose=MARKETPLACE_DRAFT_PURPOSE,
        visibility=VisibilityMode.GRAY_BOX,
        creator_display_name="Research Creator",
        not_investment_advice_acknowledged=True,
    )

    manifest = read_viza_manifest(target)
    metadata = json.loads(read_viza_section(target, "marketplace_metadata").content)
    rights = json.loads(read_viza_section(target, "rights").content)

    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())

    assert manifest.purpose == MARKETPLACE_DRAFT_PURPOSE
    assert manifest.object_kind == "marketplace_draft"
    assert manifest.permissions["marketplace_publish_allowed"] is False
    assert manifest.marketplace["monetization_enabled"] is False
    assert manifest.sections["methodology_graph"].status.value == "redacted"
    assert "graph/methodology.json" not in names
    assert "marketplace/metadata.json" in names
    assert "rights/license_and_entitlements.json" in names
    assert metadata["allowed_summary"]["full_graph_included"] is False
    assert metadata["creator"]["display_name"] == "Research Creator"
    assert metadata["monetization"]["enabled"] is False
    assert rights["schema"] == "viza.rights_summary.v1"
    assert "performance_claim_unverified" in {
        warning["code"] for warning in manifest.compliance_warnings
    }


def test_marketplace_draft_blocks_restricted_source_rights(tmp_path) -> None:
    payload = _graph().model_dump(mode="json")
    payload["nodes"][1]["config"]["rights_policy"] = {
        "connector_id": "local_csv",
        "source_id": "unit_test_source",
        "license_policy": "user_provided",
        "redistribution_policy": "restricted",
    }
    graph = MethodologyGraph.model_validate(payload)

    with pytest.raises(ValueError, match="source_data_redistribution_forbidden"):
        export_methodology_graph_to_viza(
            graph,
            tmp_path / "blocked-marketplace-draft.viza",
            purpose=MARKETPLACE_DRAFT_PURPOSE,
            visibility=VisibilityMode.WHITE_BOX,
        )


def test_marketplace_draft_blocks_restricted_run_source_rights(tmp_path) -> None:
    with pytest.raises(ValueError, match="source_data_redistribution_forbidden"):
        export_methodology_graph_to_viza(
            _graph(),
            tmp_path / "blocked-run-rights-marketplace-draft.viza",
            purpose=MARKETPLACE_DRAFT_PURPOSE,
            visibility=VisibilityMode.GRAY_BOX,
            source_rights=[
                {
                    "connector_id": "local_csv",
                    "source_id": "local_csv",
                    "redistribution_allowed": False,
                }
            ],
        )


def test_marketplace_draft_allows_internal_workspace_source_rights(tmp_path) -> None:
    target = tmp_path / "internal-run-rights-marketplace-draft.viza"

    export_methodology_graph_to_viza(
        _graph(),
        target,
        purpose=MARKETPLACE_DRAFT_PURPOSE,
        visibility=VisibilityMode.GRAY_BOX,
        source_rights=[
            {
                "connector_id": "local_viza_workspace",
                "source_id": "local_viza_workspace",
                "license_policy": "internal_aat",
                "redistribution_allowed": False,
            }
        ],
    )

    manifest = read_viza_manifest(target)
    assert manifest.object_kind == "marketplace_draft"


def test_black_box_marketplace_draft_without_proof_gets_warning(tmp_path) -> None:
    target = tmp_path / "black-box-marketplace-draft.viza"

    export_methodology_graph_to_viza(
        _graph(),
        target,
        purpose=MARKETPLACE_DRAFT_PURPOSE,
        visibility=VisibilityMode.BLACK_BOX,
        not_investment_advice_acknowledged=True,
    )

    manifest = read_viza_manifest(target)
    metadata = json.loads(read_viza_section(target, "marketplace_metadata").content)
    warning_codes = {warning["code"] for warning in manifest.compliance_warnings}

    assert "black_box_without_proof" in warning_codes
    assert "insufficient_out_of_sample_history" in warning_codes
    assert "black_box_without_proof" in manifest.integrity["compliance_warning_labels"]
    assert "black_box_without_proof" in metadata["compliance_warning_labels"]


def test_creator_records_persist_in_project_store(tmp_path) -> None:
    store = get_project_store(tmp_path / "viza_projects.sqlite3")

    saved = store.save_creator_record(
        CreatorRecordRequest(
            creator_id="creator-local-review",
            display_name="Local Review Creator",
            metadata={"source": "unit_test"},
        )
    )
    loaded = store.require_creator_record(saved.creator_id)

    assert loaded.creator_id == "creator-local-review"
    assert loaded.display_name == "Local Review Creator"
    assert loaded.verification_status == "unverified"
    assert store.list_creator_records()[0].metadata["source"] == "unit_test"


def test_no_monetized_marketplace_endpoint_exists() -> None:
    monetization_tokens = {"buy", "sell", "checkout", "payment", "subscription"}
    route_paths = {route.path.lower() for route in app.routes}

    assert not any(
        token in route_path
        for route_path in route_paths
        for token in monetization_tokens
    )
