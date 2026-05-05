from __future__ import annotations

import pytest

from adapters.config import AdapterConfig, validate_adapter_config


def test_public_adapter_does_not_require_credentials_in_production() -> None:
    validate_adapter_config(
        AdapterConfig(name="sec_edgar", license_tier="public"),
        env="production",
    )


def test_licensed_adapter_fails_closed_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FMP_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="missing credentials"):
        validate_adapter_config(
            AdapterConfig(
                name="fmp",
                license_tier="licensed",
                credential_env_vars=("FMP_API_KEY",),
            ),
            env="production",
        )
