from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viza.commands import CommandMapping
from viza.config_paths import resolve_config_path, source_root
from viza.event_patterns import EventPattern
from viza.project_store import project_store_path


REPO_ROOT = source_root()
STRATEGY_PROFILE_TEMPLATE_PATH = REPO_ROOT / "config" / "viza_strategy_profile_templates.json"


PredicateOperator = Literal["lte", "gte", "lt", "gt", "eq", "between"]


class ObservationPredicate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attribute_key: str
    operator: PredicateOperator
    threshold: float | None = None
    range_min: float | None = None
    range_max: float | None = None

    @model_validator(mode="after")
    def validate_operands(self) -> ObservationPredicate:
        if self.operator == "between":
            if self.range_min is None or self.range_max is None:
                raise ValueError("between operator requires range_min and range_max")
            if self.range_min > self.range_max:
                raise ValueError("range_min cannot exceed range_max")
        else:
            if self.threshold is None:
                raise ValueError(f"{self.operator} operator requires threshold")
        return self


class DecisionTrigger(BaseModel):
    """A rule's trigger condition.

    Phase 27 supported only the structured `observation_predicates` list
    (single-attribute comparisons combined by implicit AND). Phase 29 adds
    `feel_expression` — an S-FEEL-compatible boolean expression — that takes
    precedence over `observation_predicates` when both are set. The two forms
    are kept in parallel so existing tooling (the predicate-editor UI, the
    dead-band/cooldown helpers that key off `attribute_key`) keeps working
    against legacy rules without forcing every author to switch syntaxes.

    Round-trip: a `feel_expression` is regenerated from
    `observation_predicates` on save when only structured predicates are
    present, so a rule authored in the structured editor still exports to a
    valid DMN expression (`viza/dmn_export.py`).
    """

    model_config = ConfigDict(extra="forbid")

    observation_predicates: list[ObservationPredicate] = Field(default_factory=list)
    feel_expression: str | None = None
    event_pattern: EventPattern | None = None

    def has_feel_expression(self) -> bool:
        return bool(self.feel_expression and self.feel_expression.strip())

    def has_event_pattern(self) -> bool:
        return self.event_pattern is not None

    def referenced_attribute_keys(self) -> list[str]:
        """Best-effort enumeration of the attribute keys this trigger touches.

        Used by cooldown / dead-band bookkeeping. For a pure-structured rule
        the answer is exact (the keys in `observation_predicates`). For a
        FEEL-only rule the answer is the union of identifiers that look like
        bare attribute keys (no dotted path), which covers the common case
        without parsing FEEL fully.
        """
        keys = [predicate.attribute_key for predicate in self.observation_predicates]
        if self.feel_expression:
            keys.extend(_extract_bare_identifiers(self.feel_expression))
        seen: set[str] = set()
        unique: list[str] = []
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            unique.append(key)
        return unique


def _extract_bare_identifiers(expression: str) -> list[str]:
    """Return identifiers that look like flat attribute keys (lowercase,
    underscores, digits). Skips dotted paths and FEEL built-ins."""
    import re

    builtins = {
        "min", "max", "abs", "clamp", "round", "sqrt",
        "date", "datetime", "duration", "days", "now",
        "and", "or", "not", "in", "true", "false", "null",
    }
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", expression)
    out: list[str] = []
    for token in tokens:
        if "." in token:
            continue
        if token.lower() in builtins:
            continue
        out.append(token)
    return out


class LiveModeOptIn(BaseModel):
    """Per-profile, one-time opt-in record for live mode.

    Phase C.2. Recorded when the user accepts the live-mode disclosure dialog
    in the desktop shell. ``accepted_disclosure_version`` is the version of
    the disclosure text the user actually saw; if VIZA updates the disclosure
    text (bumping the version), the opt-in is treated as stale and the user
    is re-prompted. ``accepted_by_user`` is a free-text identifier the user
    supplied (display name, email, or "self") for the audit trail.
    """

    model_config = ConfigDict(extra="forbid")

    accepted_at: datetime
    accepted_disclosure_version: str
    accepted_by_user: str = "self"


class CooldownPolicy(BaseModel):
    """Per-rule cooldown / debounce / dead-band policy.

    Phase C (see docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md). Defaults make the
    policy a no-op so existing rules remain backward-compatible.

    - ``max_fires_per_entity_per_window``: hard cap on emissions for the same
      (rule, entity) within ``window_seconds``. ``None`` disables the cap.
    - ``window_seconds``: rolling window measured from the candidate
      ``cutoff_timestamp`` backward. Must be ``> 0`` when the cap is set.
    - ``dead_band_threshold``: when a single numeric trigger fired before for
      the same entity, the executor suppresses the next fire unless the new
      observation value moved by at least this magnitude from the last
      triggering value. ``None`` disables dead-band suppression.
    """

    model_config = ConfigDict(extra="forbid")

    max_fires_per_entity_per_window: int | None = None
    window_seconds: int | None = None
    dead_band_threshold: float | None = None

    @model_validator(mode="after")
    def validate_consistency(self) -> CooldownPolicy:
        if self.max_fires_per_entity_per_window is not None:
            if self.max_fires_per_entity_per_window < 1:
                raise ValueError(
                    "max_fires_per_entity_per_window must be >= 1 when set"
                )
            if self.window_seconds is None or self.window_seconds <= 0:
                raise ValueError(
                    "window_seconds must be > 0 when max_fires_per_entity_per_window is set"
                )
        if self.dead_band_threshold is not None and self.dead_band_threshold < 0:
            raise ValueError("dead_band_threshold cannot be negative")
        return self


class DecisionRule(BaseModel):
    """A user-authored, deterministic rule that fires inside the simulator frame.

    See docs/VIZA_OUTPUT_RADAR_DECISIONS_PLAN.md (Phase A + Phase C). The
    ``action_template`` is the user's own wording; the runtime quotes it
    verbatim and never generates investment-recommendation language.
    ``effective_from`` (optional) is the rule's release date — the executor
    refuses to fire the rule against observations cutoff earlier than
    ``effective_from`` so a sandbox replay cannot fabricate decisions that did
    not yet exist as rules at that time (pin-5 (C) analog). ``cooldown_policy``
    enforces per-entity firing caps and dead-band suppression (Phase C).

    Phase 27 (`docs/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`): the
    optional ``command_mapping`` binds a firing to a structured investment
    command (e.g. ``BUY_TO_OPEN`` with a target-weight sizing expression).
    When ``command_mapping`` is omitted, the rule still emits a DecisionFrame
    with the verbatim ``action_template`` and ``command=None``, preserving
    the pre-Phase-27 behavior.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.decision_rule.v1", alias="schema")
    rule_id: str
    label: str
    enabled: bool = True
    trigger: DecisionTrigger
    action_template: str
    cooldown_policy: CooldownPolicy = Field(default_factory=CooldownPolicy)
    evidence_requirements: list[str] = Field(default_factory=list)
    effective_from: datetime | None = None
    command_mapping: CommandMapping | None = None


class VizaStrategyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: str = Field(default="viza.strategy_profile.v1", alias="schema")
    strategy_profile_id: str
    display_name: str
    domain: str
    module_id: str
    entity_types: list[str] = Field(default_factory=list)
    universe_constraints: dict[str, Any] = Field(default_factory=dict)
    holding_period: dict[str, str] = Field(default_factory=dict)
    preferred_indicators: list[str] = Field(default_factory=list)
    catalyst_types: list[str] = Field(default_factory=list)
    required_confirmations: list[str] = Field(default_factory=list)
    risk_limits: dict[str, Any] = Field(default_factory=dict)
    output_preferences: dict[str, Any] = Field(default_factory=dict)
    action_thresholds: dict[str, float] = Field(default_factory=dict)
    evidence_requirements: dict[str, Any] = Field(default_factory=dict)
    decision_rules: list[DecisionRule] = Field(default_factory=list)
    live_mode_opt_in: LiveModeOptIn | None = None
    output_radar_config: dict[str, Any] = Field(default_factory=dict)
    # Phase 29: typed DMN decision table for action-threshold routing. When
    # set, supersedes the legacy `action_thresholds` dict on the same field.
    # Stored as a free-form dict (round-tripped via `viza.decision_tables`)
    # to avoid an import cycle and keep the persisted profile shape
    # JSON-compatible.
    action_thresholds_table: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class StrategyProfileCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_profile_id: str | None = None
    display_name: str
    domain: str = "finance.securities"
    module_id: str = "viza.finance.securities"
    entity_types: list[str] = Field(default_factory=lambda: ["security", "company"])
    universe_constraints: dict[str, Any] = Field(default_factory=dict)
    holding_period: dict[str, str] = Field(default_factory=dict)
    preferred_indicators: list[str] = Field(default_factory=list)
    catalyst_types: list[str] = Field(default_factory=list)
    required_confirmations: list[str] = Field(default_factory=list)
    risk_limits: dict[str, Any] = Field(default_factory=dict)
    output_preferences: dict[str, Any] = Field(default_factory=dict)
    action_thresholds: dict[str, float] = Field(default_factory=dict)
    evidence_requirements: dict[str, Any] = Field(default_factory=dict)
    decision_rules: list[DecisionRule] = Field(default_factory=list)
    live_mode_opt_in: LiveModeOptIn | None = None
    template_id: str | None = None
    label: str | None = None
    message: str | None = None


class StrategyProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    universe_constraints: dict[str, Any] | None = None
    holding_period: dict[str, str] | None = None
    preferred_indicators: list[str] | None = None
    catalyst_types: list[str] | None = None
    required_confirmations: list[str] | None = None
    risk_limits: dict[str, Any] | None = None
    output_preferences: dict[str, Any] | None = None
    action_thresholds: dict[str, float] | None = None
    evidence_requirements: dict[str, Any] | None = None
    decision_rules: list[DecisionRule] | None = None
    live_mode_opt_in: LiveModeOptIn | None = None
    label: str | None = None
    message: str | None = None


class StrategyProfileCloneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    label: str | None = None
    message: str | None = None


class StrategyProfileVersionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: str
    strategy_profile_id: str
    profile: VizaStrategyProfile
    profile_hash: str
    parent_version_id: str | None = None
    label: str | None = None
    message: str | None = None
    created_at: str


class StrategyProfileTemplateCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str = Field(default="viza.strategy_profile_templates.v1", alias="schema")
    template_version: str = "0.1.0"
    templates: list[StrategyProfileCreateRequest] = Field(default_factory=list)


class StrategyProfileStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else project_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def list_profiles(self) -> list[VizaStrategyProfile]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM strategy_profiles ORDER BY updated_at DESC"
            ).fetchall()
        return [_profile_from_row(row) for row in rows]

    def create_profile(self, request: StrategyProfileCreateRequest) -> VizaStrategyProfile:
        base = _profile_from_template(request.template_id) if request.template_id else None
        timestamp = _utc_now()
        profile = VizaStrategyProfile(
            strategy_profile_id=request.strategy_profile_id or f"profile-{uuid4()}",
            display_name=request.display_name or (base.display_name if base else "Strategy Profile"),
            domain=request.domain or (base.domain if base else "finance.securities"),
            module_id=request.module_id or (base.module_id if base else "viza.finance.securities"),
            entity_types=request.entity_types or (base.entity_types if base else []),
            universe_constraints=request.universe_constraints or (base.universe_constraints if base else {}),
            holding_period=request.holding_period or (base.holding_period if base else {}),
            preferred_indicators=request.preferred_indicators or (base.preferred_indicators if base else []),
            catalyst_types=request.catalyst_types or (base.catalyst_types if base else []),
            required_confirmations=(
                request.required_confirmations or (base.required_confirmations if base else [])
            ),
            risk_limits=request.risk_limits or (base.risk_limits if base else {}),
            output_preferences=request.output_preferences or (base.output_preferences if base else {}),
            action_thresholds=request.action_thresholds or (base.action_thresholds if base else {}),
            evidence_requirements=request.evidence_requirements or (base.evidence_requirements if base else {}),
            decision_rules=request.decision_rules or (base.decision_rules if base else []),
            # Live-mode opt-in is intentionally NOT inherited from the template
            # (`base.live_mode_opt_in`). Opt-in is always a per-user,
            # per-consent-moment action recorded by the desktop disclosure
            # dialog after the profile already exists. A caller-supplied
            # ``request.live_mode_opt_in`` is preserved (rare; primarily for
            # migration paths). See `viza.decisions._enforce_live_mode_preconditions`
            # and `viza.service:viza_profile_live_mode_opt_in` for the
            # canonical opt-in flow.
            live_mode_opt_in=request.live_mode_opt_in,
            created_at=timestamp,
            updated_at=timestamp,
        )
        return self.upsert_profile(profile, label=request.label, message=request.message)

    def upsert_profile(
        self,
        profile: VizaStrategyProfile,
        *,
        label: str | None = None,
        message: str | None = None,
        parent_version_id: str | None = None,
    ) -> VizaStrategyProfile:
        payload = profile.model_dump(mode="json", by_alias=True)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO strategy_profiles(
                    strategy_profile_id,
                    display_name,
                    domain,
                    module_id,
                    profile_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(strategy_profile_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    domain = excluded.domain,
                    module_id = excluded.module_id,
                    profile_json = excluded.profile_json,
                    updated_at = excluded.updated_at
                """,
                (
                    profile.strategy_profile_id,
                    profile.display_name,
                    profile.domain,
                    profile.module_id,
                    json.dumps(payload, sort_keys=True),
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                ),
            )
            self._insert_version(
                connection,
                profile,
                parent_version_id=parent_version_id,
                label=label,
                message=message,
            )
        return self.require_profile(profile.strategy_profile_id)

    def update_profile(
        self,
        profile_id: str,
        request: StrategyProfileUpdateRequest,
    ) -> VizaStrategyProfile:
        current = self.require_profile(profile_id)
        parent = self.latest_version(profile_id)
        updates = {
            key: value
            for key, value in request.model_dump(exclude_none=True).items()
            if key not in {"label", "message"}
        }
        profile = current.model_copy(
            update={
                **updates,
                "updated_at": _utc_now(),
            }
        )
        return self.upsert_profile(
            profile,
            label=request.label,
            message=request.message,
            parent_version_id=parent.version_id if parent else None,
        )

    def clone_profile(
        self,
        profile_id: str,
        request: StrategyProfileCloneRequest,
    ) -> VizaStrategyProfile:
        source = self.require_profile(profile_id)
        timestamp = _utc_now()
        clone = source.model_copy(
            update={
                "strategy_profile_id": f"profile-{uuid4()}",
                "display_name": request.display_name or f"{source.display_name} Copy",
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        return self.upsert_profile(clone, label=request.label, message=request.message)

    def require_profile(self, profile_id: str) -> VizaStrategyProfile:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM strategy_profiles WHERE strategy_profile_id = ?",
                (profile_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown VIZA strategy profile: {profile_id}")
        return _profile_from_row(row)

    def latest_version(self, profile_id: str) -> StrategyProfileVersionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM strategy_profile_versions
                WHERE strategy_profile_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (profile_id,),
            ).fetchone()
        return _version_from_row(row) if row is not None else None

    def _insert_version(
        self,
        connection: sqlite3.Connection,
        profile: VizaStrategyProfile,
        *,
        parent_version_id: str | None,
        label: str | None,
        message: str | None,
    ) -> None:
        payload = profile.model_dump(mode="json", by_alias=True)
        connection.execute(
            """
            INSERT INTO strategy_profile_versions(
                version_id,
                strategy_profile_id,
                profile_json,
                profile_hash,
                parent_version_id,
                label,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"profile-version-{uuid4()}",
                profile.strategy_profile_id,
                json.dumps(payload, sort_keys=True),
                strategy_profile_hash(profile),
                parent_version_id,
                label,
                message,
                _utc_now().isoformat(),
            ),
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(STRATEGY_PROFILE_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


STRATEGY_PROFILE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS strategy_profiles (
  strategy_profile_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  domain TEXT NOT NULL,
  module_id TEXT NOT NULL,
  profile_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_profile_versions (
  version_id TEXT PRIMARY KEY,
  strategy_profile_id TEXT NOT NULL,
  profile_json TEXT NOT NULL,
  profile_hash TEXT NOT NULL,
  parent_version_id TEXT,
  label TEXT,
  message TEXT,
  created_at TEXT NOT NULL
);
"""


def get_strategy_profile_store(path: str | Path | None = None) -> StrategyProfileStore:
    return StrategyProfileStore(path)


def load_strategy_profile_templates(path: str | Path | None = None) -> StrategyProfileTemplateCatalog:
    active_path = (
        Path(path)
        if path is not None
        else resolve_config_path("viza_strategy_profile_templates.json")
    )
    with active_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return StrategyProfileTemplateCatalog.model_validate(payload)


def strategy_profile_hash(profile: VizaStrategyProfile) -> str:
    payload = profile.model_dump(mode="json", by_alias=True)
    payload.pop("created_at", None)
    payload.pop("updated_at", None)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _profile_from_template(template_id: str | None) -> VizaStrategyProfile | None:
    if not template_id:
        return None
    timestamp = _utc_now()
    for template in load_strategy_profile_templates().templates:
        if template.strategy_profile_id == template_id or template.display_name == template_id:
            return VizaStrategyProfile(
                strategy_profile_id=template.strategy_profile_id or template_id,
                display_name=template.display_name,
                domain=template.domain,
                module_id=template.module_id,
                entity_types=template.entity_types,
                universe_constraints=template.universe_constraints,
                holding_period=template.holding_period,
                preferred_indicators=template.preferred_indicators,
                catalyst_types=template.catalyst_types,
                required_confirmations=template.required_confirmations,
                risk_limits=template.risk_limits,
                output_preferences=template.output_preferences,
                action_thresholds=template.action_thresholds,
                evidence_requirements=template.evidence_requirements,
                decision_rules=template.decision_rules,
                created_at=timestamp,
                updated_at=timestamp,
            )
    raise KeyError(f"unknown VIZA strategy profile template: {template_id}")


def _profile_from_row(row: sqlite3.Row) -> VizaStrategyProfile:
    return VizaStrategyProfile.model_validate(json.loads(row["profile_json"]))


def _version_from_row(row: sqlite3.Row) -> StrategyProfileVersionRecord:
    return StrategyProfileVersionRecord(
        version_id=row["version_id"],
        strategy_profile_id=row["strategy_profile_id"],
        profile=VizaStrategyProfile.model_validate(json.loads(row["profile_json"])),
        profile_hash=row["profile_hash"],
        parent_version_id=row["parent_version_id"],
        label=row["label"],
        message=row["message"],
        created_at=row["created_at"],
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
