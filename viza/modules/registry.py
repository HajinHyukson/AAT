from __future__ import annotations

import os
from functools import lru_cache

from viza.file_format.models import VizaModuleRequirement
from viza.graph_schema import MethodologyGraph
from viza.modules.core_strategy import CORE_MODULE_ID, build_core_strategy_module
from viza.equity.config import equity_runtime_enabled_from_env
from viza.modules.finance_securities import (
    FINANCE_MODULE_ID,
    finance_module_type_for_legacy,
    legacy_type_for_finance_module,
    build_finance_securities_module,
)
from viza.modules.equity_investment import build_equity_investment_module
from viza.modules.real_estate_acquisition import build_real_estate_acquisition_module
from viza.modules.models import (
    ModuleCompatibilityResult,
    ResolvedNodeType,
    VizaModuleManifest,
)
from viza.modules.placeholders import create_unknown_node_placeholder


class ModuleRegistry:
    def __init__(self, modules: list[VizaModuleManifest] | None = None) -> None:
        loaded_modules = modules or [
            build_core_strategy_module(),
            build_finance_securities_module(),
        ]
        if modules is None and equity_runtime_enabled_from_env():
            loaded_modules.append(build_equity_investment_module())
        if modules is None and _non_finance_modules_enabled():
            loaded_modules.append(build_real_estate_acquisition_module())
        self._modules = {module.module_id: module for module in loaded_modules}
        self._node_type_index = {
            node_type.type_id: (module.module_id, node_type)
            for module in loaded_modules
            for node_type in module.node_types.values()
        }

    def list_modules(self) -> list[VizaModuleManifest]:
        return sorted(self._modules.values(), key=lambda module: module.module_id)

    def get_module(self, module_id: str) -> VizaModuleManifest:
        if module_id not in self._modules:
            raise KeyError(f"unknown VIZA module: {module_id}")
        return self._modules[module_id]

    def resolve_node_type(self, type_id: str) -> ResolvedNodeType:
        if type_id in self._node_type_index:
            module_id, node_type = self._node_type_index[type_id]
            return ResolvedNodeType(
                requested_type_id=type_id,
                status="resolved",
                module_id=module_id,
                module_installed=True,
                node_type=node_type,
                legacy_type=node_type.legacy_type,
            )
        try:
            module_type = self.legacy_to_module_type(type_id)
            return self.resolve_node_type(module_type)
        except KeyError:
            module_id = _module_id_from_type(type_id)
            placeholder = create_unknown_node_placeholder(
                module_id=module_id,
                node_type=type_id,
            )
            return ResolvedNodeType(
                requested_type_id=type_id,
                status="missing_module",
                module_id=module_id,
                module_installed=False,
                placeholder=placeholder.model_dump(mode="json"),
                message="Module is not installed; node is preserved as a locked placeholder.",
            )

    def legacy_to_module_type(self, legacy_type: str) -> str:
        return finance_module_type_for_legacy(legacy_type)

    def module_to_legacy_type(self, module_type: str) -> str:
        return legacy_type_for_finance_module(module_type)

    def required_modules_for_graph(self, graph: MethodologyGraph) -> list[VizaModuleRequirement]:
        domain = graph.metadata.get("domain") if isinstance(graph.metadata, dict) else None
        if domain == "real_estate.acquisition":
            return [
                VizaModuleRequirement(
                    module_id=CORE_MODULE_ID,
                    version_range=">=0.1.0",
                    required=True,
                ),
                VizaModuleRequirement(
                    module_id="viza.real_estate.acquisition",
                    version_range=">=0.1.0",
                    required=True,
                ),
            ]
        if graph.nodes:
            return [
                VizaModuleRequirement(
                    module_id=FINANCE_MODULE_ID,
                    version_range=">=0.1.0",
                    required=True,
                )
            ]
        return []

    def check_compatibility(
        self,
        required_modules: list[VizaModuleRequirement],
    ) -> list[ModuleCompatibilityResult]:
        results: list[ModuleCompatibilityResult] = []
        for requirement in required_modules:
            module = self._modules.get(requirement.module_id)
            if module is None:
                results.append(
                    ModuleCompatibilityResult(
                        module_id=requirement.module_id,
                        required=requirement.required,
                        version_range=requirement.version_range,
                        installed=False,
                        status="missing_required" if requirement.required else "missing_optional",
                        message="Module is not installed.",
                    )
                )
                continue
            results.append(
                ModuleCompatibilityResult(
                    module_id=requirement.module_id,
                    required=requirement.required,
                    version_range=requirement.version_range,
                    installed=True,
                    installed_version=module.module_version,
                    status="installed",
                    message="Module is installed.",
                )
            )
        return results


@lru_cache(maxsize=1)
def get_module_registry() -> ModuleRegistry:
    return ModuleRegistry()


def _module_id_from_type(type_id: str) -> str:
    parts = type_id.split(".")
    if len(parts) <= 1:
        return "unknown"
    return ".".join(parts[:-1])


def _non_finance_modules_enabled() -> bool:
    return os.getenv("VIZA_ENABLE_NON_FINANCE_MODULES", "").lower() in {"1", "true", "yes", "on"}
