"""SKOS-shaped concept registry for VIZA taxonomies.

Phase 26 of `docs/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`. Backs the
migration from bare-string `family` fields on registries and relationship edges
to IRIs that can be navigated via skos:broader / skos:narrower. The compliance
report's cross-cutting principle (`docs/VIZA_KR_COMPLIANCE_REPORT.md` §10.2)
says every taxonomy field should carry an IRI; this module supplies the
resolution layer those IRIs need.

Back-compat: every concept declares `skos_alt_labels` that include the legacy
bare-string family value. The `resolve_family` helper accepts either an IRI or
a legacy string and returns the canonical IRI.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from viza.config_paths import resolve_config_path


CONCEPTS_FILE_NAME = "viza_concepts.json"

ConceptDomain = Literal["event", "insight", "relationship", "command", "attribute"]


class Concept(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    iri: str
    skos_pref_label: str
    skos_alt_labels: list[str] = Field(default_factory=list)
    skos_broader: list[str] = Field(default_factory=list)
    skos_narrower: list[str] = Field(default_factory=list)
    domain: ConceptDomain | None = None
    description: str | None = None


class ConceptScheme(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.concepts.v1", alias="schema")
    registry_version: str = "0.1.0"
    concept_scheme: str
    description: str | None = None
    concepts: list[Concept] = Field(default_factory=list)

    def get(self, iri: str) -> Concept | None:
        return next((concept for concept in self.concepts if concept.iri == iri), None)

    def resolve(self, value: str, *, domain: ConceptDomain | None = None) -> str:
        """Return a canonical IRI for the given value.

        Accepts either an IRI (returned unchanged after existence check) or a
        bare-string family value that matches a concept's `skos_pref_label` or
        `skos_alt_labels`. Optional `domain` narrows the search.

        Raises KeyError when no concept matches — callers that want the
        permissive behavior should use `resolve_or_none`.
        """
        resolved = self.resolve_or_none(value, domain=domain)
        if resolved is None:
            raise KeyError(f"no concept resolves {value!r} (domain={domain!r})")
        return resolved

    def resolve_or_none(
        self, value: str, *, domain: ConceptDomain | None = None
    ) -> str | None:
        candidate = self.get(value)
        if candidate is not None:
            if domain is None or candidate.domain == domain or candidate.domain is None:
                return candidate.iri
        for concept in self.concepts:
            if domain is not None and concept.domain not in (domain, None):
                continue
            if concept.skos_pref_label == value or value in concept.skos_alt_labels:
                return concept.iri
        return None

    def broader_closure(self, iri: str) -> list[str]:
        """Walk skos:broader transitively, returning every ancestor IRI."""
        seen: list[str] = []
        frontier = list(self.get(iri).skos_broader) if self.get(iri) else []
        while frontier:
            parent = frontier.pop(0)
            if parent in seen:
                continue
            seen.append(parent)
            parent_concept = self.get(parent)
            if parent_concept is not None:
                frontier.extend(parent_concept.skos_broader)
        return seen

    def narrower_closure(self, iri: str) -> list[str]:
        """Walk skos:narrower transitively (and broader-inverse), returning every descendant IRI."""
        descendants: set[str] = set()
        frontier: list[str] = []
        root = self.get(iri)
        if root is None:
            return []
        frontier.extend(root.skos_narrower)
        for concept in self.concepts:
            if iri in concept.skos_broader:
                frontier.append(concept.iri)
        while frontier:
            child_iri = frontier.pop(0)
            if child_iri in descendants:
                continue
            descendants.add(child_iri)
            child = self.get(child_iri)
            if child is None:
                continue
            frontier.extend(child.skos_narrower)
            for concept in self.concepts:
                if child_iri in concept.skos_broader and concept.iri not in descendants:
                    frontier.append(concept.iri)
        return sorted(descendants)

    def family_expansion(self, value: str, *, domain: ConceptDomain) -> set[str]:
        """Back-compat shim for relationship/event family alias expansion.

        Returns the set of bare-string labels (legacy alt labels + pref label)
        for the resolved concept and every descendant. Used by
        `viza/relationships.py` to keep existing API consumers working while
        the rest of the system migrates to IRI-keyed lookups.
        """
        iri = self.resolve_or_none(value, domain=domain)
        if iri is None:
            return {value}
        relevant = [iri, *self.narrower_closure(iri)]
        labels: set[str] = set()
        for member_iri in relevant:
            concept = self.get(member_iri)
            if concept is None:
                continue
            labels.add(concept.skos_pref_label)
            labels.update(concept.skos_alt_labels)
            labels.add(member_iri)
        labels.add(value)
        return labels


def load_concept_scheme(path: str | Path | None = None) -> ConceptScheme:
    """Load and validate the concept scheme. Path defaults to the bundled config."""
    target = Path(path) if path is not None else resolve_config_path(CONCEPTS_FILE_NAME)
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return ConceptScheme.model_validate(payload)


@lru_cache(maxsize=1)
def get_concept_scheme() -> ConceptScheme:
    """Process-wide cached accessor for the default concept scheme.

    The cache is invalidated by calling `reset_concept_scheme_cache()`, which
    tests use after writing a custom scheme.
    """
    return load_concept_scheme()


def reset_concept_scheme_cache() -> None:
    get_concept_scheme.cache_clear()
