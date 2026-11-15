from __future__ import annotations

from typing import Any

from viza.modules.models import UnknownModuleNodePlaceholder


def create_unknown_node_placeholder(
    module_id: str,
    node_type: str,
    raw_config: dict[str, Any] | None = None,
) -> UnknownModuleNodePlaceholder:
    return UnknownModuleNodePlaceholder(
        module_id=module_id,
        node_type=node_type,
        raw_config=dict(raw_config or {}),
    )
