"""Stage B model manager.

Locates a local FinBERT artifact on disk (weights + tokenizer files), computes
the four pin-1 hashes, and returns the ModelMetadata that an implementation
will record on every observation. The manager intentionally does NOT load
weights into memory — that's the implementation's job — so it can be used to
fingerprint a model without a transformers/torch dependency.

LOCATION POLICY
  1. If ``cache_dir`` is given and contains the model id subdirectory, use it.
  2. Else if the HuggingFace cache convention exists under
     ``$VIZA_FINBERT_CACHE_DIR`` or ``~/.cache/huggingface/hub``, use it.
  3. Else: model files are not local. Behavior depends on
     ``VIZA_EQUITY_FINBERT_MODEL_DOWNLOAD_ENABLED``. If enabled, the
     transformers implementation may download (Stage B); if not, we raise
     ``ModelArtifactsMissing`` so the resolver can fail closed.

SECRETS
  The manager never reads environment-variable API keys, never reads .env,
  never logs paths to anywhere except its own exceptions. It returns
  hashes, NOT raw bytes, to its caller.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from viza.equity.text.hashing import (
    InferenceConfig,
    hash_inference_config,
    hash_tokenizer_files,
    hash_weights_file,
)
from viza.equity.text.types import ModelMetadata


WEIGHTS_PRIORITY: tuple[str, ...] = ("model.safetensors", "pytorch_model.bin")
TOKENIZER_FILES = {
    "tokenizer_json": "tokenizer.json",
    "vocab_txt": "vocab.txt",
    "vocab_json": "vocab.json",
    "merges_txt": "merges.txt",
    "special_tokens_map": "special_tokens_map.json",
}


class ModelArtifactsMissing(RuntimeError):
    """Raised when no local FinBERT artifact directory can be located."""


@dataclass(frozen=True)
class LocatedArtifact:
    """A located on-disk FinBERT artifact + its computed hashes."""

    model_dir: Path
    weights_path: Path
    weights_filename: str
    model_hash: str
    tokenizer_hash: str

    def as_metadata(
        self,
        *,
        model_id: str,
        model_version: str,
        implementation_id: str,
        inference_config: InferenceConfig,
        tokenizer_version: str | None = None,
        runtime_version: str = "transformers",
    ) -> ModelMetadata:
        return ModelMetadata(
            model_provider="local",
            model_family="financial_text_sentiment",
            implementation_id=implementation_id,
            model_id=model_id,
            model_version=model_version,
            model_hash=self.model_hash,
            tokenizer_version=tokenizer_version,
            tokenizer_hash=self.tokenizer_hash,
            runtime=inference_config["runtime"],
            runtime_version=inference_config["runtime_version"],
            inference_config_hash=hash_inference_config(inference_config),
            max_tokens_policy=str(inference_config["max_seq_length"]),
            truncation_policy=inference_config["truncation"],
            created_at=datetime.now(timezone.utc),
        )


def locate_local_artifact(
    *,
    model_id: str,
    cache_dir: str | Path | None = None,
) -> LocatedArtifact:
    """Find a local FinBERT artifact and compute its pin-1 hashes.

    The directory layout is the standard HuggingFace cache (per-model
    subdirectories under the cache root). The lookup is intentionally narrow:
    we read a small enumerated file set, so the same model on two machines
    produces identical hashes if and only if the files are byte-identical.
    """
    model_dir = _resolve_model_dir(model_id=model_id, cache_dir=cache_dir)

    weights_path = _pick_weights_file(model_dir)
    model_hash = hash_weights_file(weights_path)

    tokenizer_hash = hash_tokenizer_files(
        tokenizer_json=_read_optional(model_dir / TOKENIZER_FILES["tokenizer_json"]),
        vocab=(
            _read_optional(model_dir / TOKENIZER_FILES["vocab_txt"])
            or _read_optional(model_dir / TOKENIZER_FILES["vocab_json"])
        ),
        merges=_read_optional(model_dir / TOKENIZER_FILES["merges_txt"]),
        special_tokens_map=_read_optional(
            model_dir / TOKENIZER_FILES["special_tokens_map"]
        ),
    )

    return LocatedArtifact(
        model_dir=model_dir,
        weights_path=weights_path,
        weights_filename=weights_path.name,
        model_hash=model_hash,
        tokenizer_hash=tokenizer_hash,
    )


def _resolve_model_dir(*, model_id: str, cache_dir: str | Path | None) -> Path:
    """Locate the model directory.

    Lookup precedence:
      1. ``cache_dir`` argument, if explicitly provided (caller wins).
      2. ``VIZA_FINBERT_CACHE_DIR`` env var, if set and ``cache_dir`` is None.
      3. The default HuggingFace cache (``~/.cache/huggingface/hub/...``),
         ONLY if neither (1) nor (2) is set.

    This precedence makes tests deterministic: pass a tmp_path cache_dir to
    isolate from any real local HF cache.
    """
    hf_subdir = f"models--{model_id.replace('/', '--')}"
    candidates: list[Path] = []
    if cache_dir is not None:
        root = Path(cache_dir)
        candidates.append(root / _safe_model_subdir(model_id))
        candidates.append(root / hf_subdir)  # HF cache nested layout
        candidates.append(root)
    else:
        env_dir = os.getenv("VIZA_FINBERT_CACHE_DIR")
        if env_dir:
            root = Path(env_dir)
            candidates.append(root / _safe_model_subdir(model_id))
            candidates.append(root / hf_subdir)
            candidates.append(root)
        else:
            candidates.append(
                Path.home() / ".cache" / "huggingface" / "hub" / hf_subdir
            )
    for candidate in candidates:
        if candidate.is_dir() and any(
            (candidate / name).exists() for name in WEIGHTS_PRIORITY
        ):
            return candidate
        # HF cache nested snapshot layout: models--<org>--<name>/snapshots/<sha>/
        snapshots = candidate / "snapshots"
        if snapshots.is_dir():
            for snapshot in sorted(snapshots.iterdir()):
                if snapshot.is_dir() and any(
                    (snapshot / name).exists() for name in WEIGHTS_PRIORITY
                ):
                    return snapshot
    raise ModelArtifactsMissing(
        f"no local FinBERT artifact found for model_id={model_id!r}; "
        "set VIZA_FINBERT_CACHE_DIR or enable VIZA_EQUITY_FINBERT_MODEL_DOWNLOAD_ENABLED"
    )


def _safe_model_subdir(model_id: str) -> str:
    # Translate "ProsusAI/finbert" -> "ProsusAI__finbert" so it's safe as a
    # single directory name on any OS.
    return model_id.replace("/", "__")


def _pick_weights_file(model_dir: Path) -> Path:
    for name in WEIGHTS_PRIORITY:
        candidate = model_dir / name
        if candidate.exists():
            return candidate
    raise ModelArtifactsMissing(
        f"no weights file (one of {WEIGHTS_PRIORITY}) in {model_dir}"
    )


def _read_optional(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()
