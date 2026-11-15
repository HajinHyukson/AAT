from __future__ import annotations

import zipfile
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from viza.attribute_registry import load_attribute_registry
from viza.execution import run_methodology
from viza.file_format.container import write_viza_container
from viza.file_format.models import SectionStatus, VisibilityMode, VizaFileManifest, VizaSectionDescriptor
from viza.graph_schema import load_methodology_graph
from viza.sample_data import SAMPLE_METHODOLOGY_GRAPH_PATH
from viza.service import app
from viza.strategy_profiles import VizaStrategyProfile
from viza.translation import (
    TranslationBatchRequest,
    TranslationRequest,
    default_strategy_profile,
    get_translation_store,
    translate_batch,
    translate_insight,
    translation_for_export,
)


client = TestClient(app)


def _sample_insight():
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    return run_methodology(graph, load_attribute_registry()).insights[0]


def _alternate_profile() -> VizaStrategyProfile:
    profile = default_strategy_profile()
    return profile.model_copy(
        update={
            "strategy_profile_id": "profile-alt-risk",
            "display_name": "Risk Only Profile",
            "catalyst_types": ["regulatory_action"],
            "preferred_indicators": ["realized_volatility"],
            "required_confirmations": ["regulatory_confirmation"],
            "action_thresholds": {"review": 0.7, "watchlist": 0.85, "high_conviction": 0.95},
        }
    )


def test_same_insight_translates_differently_for_two_profiles() -> None:
    insight = _sample_insight()

    default_translation = translate_insight(insight, default_strategy_profile())
    alternate_translation = translate_insight(insight, _alternate_profile())

    assert default_translation.fit_score != alternate_translation.fit_score
    assert default_translation.suggested_research_action != alternate_translation.suggested_research_action
    assert default_translation.translated_summary != alternate_translation.translated_summary


def test_missing_confirmations_and_weak_evidence_reduce_score() -> None:
    insight = _sample_insight()
    profile = default_strategy_profile()
    strong = translate_insight(insight, profile)
    weak_insight = insight.model_copy(
        update={
            "evidence_refs": [],
            "confidence": 0.25,
            "magnitude": {"technical_confirmation": None},
        }
    )
    weak = translate_insight(weak_insight, profile)

    assert strong.fit_score > weak.fit_score
    assert weak.missing_confirmations
    assert "weak_evidence" in weak.risk_factors


def test_invalidation_conditions_and_advice_flag_propagate() -> None:
    translation = translate_insight(_sample_insight(), default_strategy_profile())

    assert translation.invalidation_conditions
    assert translation.not_investment_advice is True
    assert translation.translated_summary


def test_translation_endpoints_and_store_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIZA_PROJECT_STORE_PATH", str(tmp_path / "viza_projects.sqlite3"))
    insight = _sample_insight()
    profile = default_strategy_profile()

    response = client.post(
        "/viza/translate",
        json={
            "insight": insight.model_dump(mode="json", by_alias=True),
            "strategy_profile": profile.model_dump(mode="json", by_alias=True),
        },
    )
    assert response.status_code == 200
    translation_id = response.json()["translation_id"]

    get_response = client.get(f"/viza/translations/{translation_id}")
    batch_response = client.post(
        "/viza/translate/batch",
        json={
            "insights": [insight.model_dump(mode="json", by_alias=True)],
            "strategy_profile": profile.model_dump(mode="json", by_alias=True),
        },
    )

    assert get_response.status_code == 200
    assert get_response.json()["translation_id"] == translation_id
    assert batch_response.status_code == 200
    assert get_translation_store().require_translation(translation_id).fit_score >= 0


def test_translate_request_helpers() -> None:
    insight = _sample_insight()
    profile = default_strategy_profile()

    single = TranslationRequest(insight=insight, strategy_profile=profile, persist=False)
    batch = TranslationBatchRequest(insights=[insight], strategy_profile=profile, persist=False)

    assert single.insight is not None
    assert single.insight.insight_id == insight.insight_id
    assert translate_batch(batch)[0].insight_id == insight.insight_id


def test_radar_row_includes_translated_fields() -> None:
    graph = load_methodology_graph(SAMPLE_METHODOLOGY_GRAPH_PATH)
    result = run_methodology(graph, load_attribute_registry())
    row = next(row for row in result.rows if row.strategy_fit_score is not None)

    assert result.translations
    assert row.primary_insight_type
    assert row.translated_summary
    assert row.strategy_fit_score is not None
    assert row.evidence_count > 0


def test_translation_exports_with_rights_policy_flag(tmp_path) -> None:
    translation = translate_insight(_sample_insight(), default_strategy_profile())
    manifest = VizaFileManifest(
        schema="viza.document.v1",
        file_id="file-translations-test",
        display_name="Translations Test",
        object_kind="strategy_package",
        visibility=VisibilityMode.WHITE_BOX,
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        sections={"translations": VizaSectionDescriptor(status=SectionStatus.INCLUDED)},
    )
    target = tmp_path / "translations.viza"

    write_viza_container(
        target,
        manifest,
        {"translations": {"translations": [translation_for_export(translation)]}},
    )

    with zipfile.ZipFile(target) as archive:
        payload = archive.read("translations/translations.json").decode("utf-8")

    assert "not_investment_advice" in payload
