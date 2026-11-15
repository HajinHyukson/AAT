from __future__ import annotations

from pathlib import Path

from viza.file_format.container import read_viza_manifest, write_viza_container
from viza.file_format.legacy import legacy_graph_json_to_viza_manifest
from viza.file_format.models import VisibilityMode, VizaWriteResult
from viza.file_format.packaging import VizaPackagingRequest, export_packaged_viza
from viza.graph_schema import MethodologyGraph
from viza.marketplace import MARKETPLACE_DRAFT_PURPOSE
from viza.validation_ledger import VizaValidationRecord


def export_methodology_graph_to_viza(
    graph: MethodologyGraph,
    target_path: str | Path,
    *,
    display_name: str | None = None,
    purpose: str = "methodology_graph",
    visibility: VisibilityMode = VisibilityMode.WHITE_BOX,
    include_validation_proof: bool = False,
    validation_record: VizaValidationRecord | None = None,
    include_signal_outputs: bool = False,
    include_sample_outputs: bool = False,
    redact_parameters: bool = False,
    lock_sections: list[str] | None = None,
    creator_id: str | None = None,
    creator_display_name: str | None = None,
    source_rights: list[dict] | None = None,
    not_investment_advice_acknowledged: bool = False,
) -> tuple[VizaWriteResult, dict]:
    if purpose == MARKETPLACE_DRAFT_PURPOSE or visibility != VisibilityMode.WHITE_BOX or any(
        [
            include_validation_proof,
            include_signal_outputs,
            include_sample_outputs,
            redact_parameters,
            lock_sections,
        ]
    ):
        return export_packaged_viza(
            VizaPackagingRequest(
                graph=graph,
                target_path=target_path,
                purpose=purpose,
                visibility=visibility,
                display_name=display_name,
                include_validation_proof=include_validation_proof,
                validation_record=validation_record,
                include_signal_outputs=include_signal_outputs,
                include_sample_outputs=include_sample_outputs,
                redact_parameters=redact_parameters,
                lock_sections=lock_sections or [],
                creator_id=creator_id,
                creator_display_name=creator_display_name,
                source_rights=source_rights or [],
                not_investment_advice_acknowledged=not_investment_advice_acknowledged,
            )
        )
    manifest = legacy_graph_json_to_viza_manifest(graph.model_dump(mode="json"))
    if display_name is not None:
        manifest.display_name = display_name
    manifest.purpose = purpose
    result = write_viza_container(
        target_path,
        manifest,
        {"methodology_graph": graph.model_dump(mode="json")},
    )
    written_manifest = read_viza_manifest(target_path)
    return result, written_manifest.model_dump(mode="json", by_alias=True)
