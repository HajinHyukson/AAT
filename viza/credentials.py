from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


SERVICE_NAME = "viza-local-engine"
DEV_ENV_PREFIX = "VIZA_CREDENTIAL"


class CredentialRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    key: str
    storage: str
    reference: str
    created_at: str


class CredentialStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    key: str
    configured: bool
    storage: str
    credential_mode: str
    reference: str | None = None
    env_var: str | None = None
    warning: str | None = None
    updated_at: str | None = None


class CredentialSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    value: str = Field(min_length=1)


class CredentialStore:
    def __init__(self, *, force_mode: str | None = None) -> None:
        self._keyring: Any | None = None
        self._keyring_available = False
        self._mode = force_mode or os.getenv("VIZA_CREDENTIAL_MODE") or "auto"
        if self._mode != "env_var_dev":
            try:
                import keyring  # type: ignore[import-not-found]

                self._keyring = keyring
                self._keyring_available = True
            except Exception:
                self._keyring = None
                self._keyring_available = False

    @property
    def mode(self) -> str:
        if self._mode == "env_var_dev":
            return "env_var_dev"
        return "os_keyring" if self._keyring_available else "env_var_dev"

    def set_secret(self, connector_id: str, key: str, value: str) -> CredentialRef:
        if self.mode == "os_keyring":
            reference = _reference(connector_id, key)
            assert self._keyring is not None
            try:
                self._keyring.set_password(SERVICE_NAME, reference, value)
                return CredentialRef(
                    connector_id=connector_id,
                    key=key,
                    storage="os_keyring",
                    reference=reference,
                    created_at=_utc_now(),
                )
            except Exception:
                self._keyring_available = False

        env_var = dev_env_var(connector_id, key)
        os.environ[env_var] = value
        return CredentialRef(
            connector_id=connector_id,
            key=key,
            storage="env_var_dev",
            reference=env_var,
            created_at=_utc_now(),
        )

    def has_secret(
        self,
        connector_id: str,
        key: str,
        *,
        env_var: str | None = None,
    ) -> bool:
        return self._secret_value(connector_id, key, env_var=env_var) is not None

    def get_secret_for_runtime(
        self,
        connector_id: str,
        key: str,
        *,
        env_var: str | None = None,
    ) -> str:
        value = self._secret_value(connector_id, key, env_var=env_var)
        if value is None:
            raise KeyError(f"credential is not configured: {connector_id}:{key}")
        return value

    def delete_secret(self, connector_id: str, key: str) -> None:
        env_var = dev_env_var(connector_id, key)
        os.environ.pop(env_var, None)
        if self._keyring_available and self._keyring is not None:
            try:
                self._keyring.delete_password(SERVICE_NAME, _reference(connector_id, key))
            except Exception:
                pass

    def status_for_secret(
        self,
        connector_id: str,
        key: str,
        *,
        env_var: str | None = None,
        required: bool = False,
    ) -> CredentialStatus:
        configured = self.has_secret(connector_id, key, env_var=env_var)
        storage = "none"
        reference: str | None = None
        credential_mode = self.mode
        if env_var and os.getenv(env_var):
            storage = "environment"
            reference = env_var
            credential_mode = "environment"
        elif configured and self.mode == "os_keyring":
            storage = "os_keyring"
            reference = _reference(connector_id, key)
        elif configured:
            storage = "env_var_dev"
            reference = dev_env_var(connector_id, key)

        warning = (
            "dev_only_env_var_storage"
            if storage == "env_var_dev"
            else "credential_required"
            if required and not configured
            else None
        )
        return CredentialStatus(
            connector_id=connector_id,
            key=key,
            configured=configured,
            storage=storage,
            credential_mode=credential_mode,
            reference=reference,
            env_var=env_var,
            warning=warning,
            updated_at=_utc_now(),
        )

    def list_secret_status(self, connector_id: str) -> list[CredentialStatus]:
        prefix = f"{DEV_ENV_PREFIX}_{_env_token(connector_id)}_"
        statuses = [
            CredentialStatus(
                connector_id=connector_id,
                key=key_from_dev_env_var(name, connector_id),
                configured=True,
                storage="env_var_dev",
                credential_mode="env_var_dev",
                reference=name,
                warning="dev_only_env_var_storage",
                updated_at=_utc_now(),
            )
            for name in sorted(os.environ)
            if name.startswith(prefix)
        ]
        return statuses

    def _secret_value(
        self,
        connector_id: str,
        key: str,
        *,
        env_var: str | None = None,
    ) -> str | None:
        if env_var and os.getenv(env_var):
            return os.getenv(env_var)
        if self._keyring_available and self._keyring is not None:
            try:
                value = self._keyring.get_password(SERVICE_NAME, _reference(connector_id, key))
                if value:
                    return value
            except Exception:
                self._keyring_available = False
        return os.getenv(dev_env_var(connector_id, key))


def dev_env_var(connector_id: str, key: str) -> str:
    return f"{DEV_ENV_PREFIX}_{_env_token(connector_id)}_{_env_token(key)}"


def key_from_dev_env_var(env_var: str, connector_id: str) -> str:
    prefix = f"{DEV_ENV_PREFIX}_{_env_token(connector_id)}_"
    if not env_var.startswith(prefix):
        return env_var.lower()
    return env_var.removeprefix(prefix).lower()


def _reference(connector_id: str, key: str) -> str:
    return f"{connector_id}:{key}"


def _env_token(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value.upper())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
