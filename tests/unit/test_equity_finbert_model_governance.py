"""Stage B model governance tests.

These tests exercise the file-discovery + hash-computation behavior of
``viza.equity.text.model_manager`` and the lazy-import contract of
``LocalFinbertTransformers``. They do NOT require transformers or torch to
be installed; the transformers path is exercised behind a flag and falls
back to ``FinbertDependencyMissing`` when the library is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from viza.equity.text.config import EquityTextConfig
from viza.equity.text.model_manager import (
    LocatedArtifact,
    ModelArtifactsMissing,
    locate_local_artifact,
)
from viza.equity.text.models.local_finbert_onnx import (
    LocalFinbertOnnx,
    OnnxDeferred,
)
from viza.equity.text.models.local_finbert_transformers import (
    FinbertDependencyMissing,
    LocalFinbertTransformers,
    register_transformers_finbert_if_enabled,
)


def _seed_fake_finbert(model_dir: Path) -> None:
    """Populate a directory with the minimum file set the manager expects."""
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model.safetensors").write_bytes(b"FAKE_WEIGHTS_v1_0")
    (model_dir / "tokenizer.json").write_bytes(b'{"fake_tokenizer":"v1"}')
    (model_dir / "vocab.txt").write_bytes(b"[PAD]\n[CLS]\n[SEP]\n[UNK]\n")
    (model_dir / "special_tokens_map.json").write_bytes(b'{"pad_token":"[PAD]"}')


def test_locate_local_artifact_returns_pin1_hashes(tmp_path: Path) -> None:
    cache_dir = tmp_path / "hf_cache"
    model_dir = cache_dir / "ProsusAI__finbert"
    _seed_fake_finbert(model_dir)
    artifact = locate_local_artifact(
        model_id="ProsusAI/finbert",
        cache_dir=cache_dir,
    )
    assert isinstance(artifact, LocatedArtifact)
    assert artifact.weights_filename == "model.safetensors"
    assert len(artifact.model_hash) == 64
    assert len(artifact.tokenizer_hash) == 64


def test_locate_local_artifact_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactsMissing):
        locate_local_artifact(
            model_id="ProsusAI/finbert",
            cache_dir=tmp_path / "empty",
        )


def test_locate_local_artifact_hash_changes_when_weights_change(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "hf_cache"
    model_dir = cache_dir / "ProsusAI__finbert"
    _seed_fake_finbert(model_dir)
    before = locate_local_artifact(
        model_id="ProsusAI/finbert", cache_dir=cache_dir
    )
    (model_dir / "model.safetensors").write_bytes(b"FAKE_WEIGHTS_v2_0_changed")
    after = locate_local_artifact(
        model_id="ProsusAI/finbert", cache_dir=cache_dir
    )
    assert before.model_hash != after.model_hash, (
        "model_hash must change when weights bytes change"
    )


def test_locate_local_artifact_hash_changes_when_tokenizer_changes(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "hf_cache"
    model_dir = cache_dir / "ProsusAI__finbert"
    _seed_fake_finbert(model_dir)
    before = locate_local_artifact(
        model_id="ProsusAI/finbert", cache_dir=cache_dir
    )
    (model_dir / "tokenizer.json").write_bytes(b'{"fake_tokenizer":"v2"}')
    after = locate_local_artifact(
        model_id="ProsusAI/finbert", cache_dir=cache_dir
    )
    assert before.tokenizer_hash != after.tokenizer_hash


def test_locate_local_artifact_finds_hf_snapshot_layout(tmp_path: Path) -> None:
    """The HF cache nests weights under snapshots/<sha>/; the manager must
    walk into the snapshot dir."""
    cache_dir = tmp_path / "hf_cache"
    snapshot_dir = (
        cache_dir
        / "models--ProsusAI--finbert"
        / "snapshots"
        / "deadbeef1234"
    )
    _seed_fake_finbert(snapshot_dir)
    artifact = locate_local_artifact(
        model_id="ProsusAI/finbert",
        cache_dir=cache_dir,
    )
    assert artifact.weights_path == snapshot_dir / "model.safetensors"


def test_transformers_implementation_lazy_imports(tmp_path: Path) -> None:
    """Importing the transformers implementation must not require
    transformers to be installed."""
    # If this test passes, it means the module imported successfully without
    # the transformers library. The actual import happens inside classify().
    config = EquityTextConfig(finbert_enabled=True)
    impl = LocalFinbertTransformers(config=config)
    assert impl.implementation_id == "local_finbert_transformers"


def test_transformers_implementation_missing_artifact_raises(tmp_path: Path) -> None:
    config = EquityTextConfig(
        finbert_enabled=True,
        finbert_cache_dir=str(tmp_path / "empty"),
        finbert_model_download_enabled=False,
    )
    impl = LocalFinbertTransformers(config=config)
    with pytest.raises(ModelArtifactsMissing):
        impl.metadata()


def test_transformers_implementation_reports_metadata_with_local_artifact(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "hf_cache"
    model_dir = cache_dir / "ProsusAI__finbert"
    _seed_fake_finbert(model_dir)
    config = EquityTextConfig(
        finbert_enabled=True,
        finbert_cache_dir=str(cache_dir),
    )
    impl = LocalFinbertTransformers(config=config)
    metadata = impl.metadata()
    assert metadata.model_id == "ProsusAI/finbert"
    assert metadata.model_version == "v1.0"
    assert metadata.implementation_id == "local_finbert_transformers"
    assert len(metadata.model_hash) == 64
    assert len(metadata.tokenizer_hash) == 64
    assert len(metadata.inference_config_hash) == 64


def test_transformers_classify_without_library_raises_dependency_missing(
    tmp_path: Path,
) -> None:
    """If transformers isn't installed, classify raises FinbertDependencyMissing
    (so the resolver can convert it to status=missing_model)."""
    cache_dir = tmp_path / "hf_cache"
    model_dir = cache_dir / "ProsusAI__finbert"
    _seed_fake_finbert(model_dir)
    config = EquityTextConfig(
        finbert_enabled=True,
        finbert_cache_dir=str(cache_dir),
    )
    impl = LocalFinbertTransformers(config=config)
    try:
        import transformers  # noqa: F401
    except ImportError:
        with pytest.raises(FinbertDependencyMissing):
            impl.classify([])
    else:
        pytest.skip("transformers is installed; lazy-import behavior tested in env without it")


def test_register_transformers_finbert_respects_flag_off() -> None:
    config = EquityTextConfig(finbert_enabled=False)
    assert register_transformers_finbert_if_enabled(config=config) is False


def test_onnx_implementation_is_deferred() -> None:
    impl = LocalFinbertOnnx()
    with pytest.raises(OnnxDeferred):
        impl.metadata()
    with pytest.raises(OnnxDeferred):
        impl.classify([])


def test_inference_config_hash_changes_with_runtime(tmp_path: Path) -> None:
    """Pin 1: changing runtime must change inference_config_hash and therefore
    cache_key."""
    cache_dir = tmp_path / "hf_cache"
    model_dir = cache_dir / "ProsusAI__finbert"
    _seed_fake_finbert(model_dir)
    artifact = locate_local_artifact(
        model_id="ProsusAI/finbert", cache_dir=cache_dir
    )
    cpu_meta = artifact.as_metadata(
        model_id="ProsusAI/finbert",
        model_version="v1.0",
        implementation_id="x",
        inference_config={
            "runtime": "transformers",
            "runtime_version": "transformers==4.46.0",
            "max_seq_length": 256,
            "truncation": "longest_first",
            "fp_precision": "fp32",
            "batch_size": 32,
            "device": "cpu",
            "seed": 0,
        },
    )
    gpu_meta = artifact.as_metadata(
        model_id="ProsusAI/finbert",
        model_version="v1.0",
        implementation_id="x",
        inference_config={
            "runtime": "transformers",
            "runtime_version": "transformers==4.46.0",
            "max_seq_length": 256,
            "truncation": "longest_first",
            "fp_precision": "fp16",
            "batch_size": 32,
            "device": "cuda:0",
            "seed": 0,
        },
    )
    assert cpu_meta.inference_config_hash != gpu_meta.inference_config_hash
