from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from viza.equity.config import EquityRuntimeConfig


JsonTransport = Callable[[str, dict[str, str], float], dict[str, Any] | list[dict[str, Any]]]

SEC_DATA_BASE_URL = "https://data.sec.gov"
FMP_STABLE_BASE_URL = "https://financialmodelingprep.com/stable"
FRED_API_BASE_URL = "https://api.stlouisfed.org/fred"
DEFAULT_FRED_SERIES = ("DGS10", "DGS2", "FEDFUNDS", "CPIAUCSL", "T10Y2Y")


class EquityConnectorError(RuntimeError):
    """Connector error with credential-bearing request details intentionally omitted."""


@dataclass
class _CacheEntry:
    payload: dict[str, Any] | list[dict[str, Any]]
    expires_at: float


class TTLCache:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = max(1, ttl_seconds)
        self._entries: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> dict[str, Any] | list[dict[str, Any]] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.monotonic():
            self._entries.pop(key, None)
            return None
        return copy.deepcopy(entry.payload)

    def set(self, key: str, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
        self._entries[key] = _CacheEntry(
            payload=copy.deepcopy(payload),
            expires_at=time.monotonic() + self.ttl_seconds,
        )


class RequestPacer:
    def __init__(self, max_rps: int) -> None:
        self.min_interval = 1.0 / max(1, max_rps)
        self._lock = Lock()
        self._last_request_at = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait_seconds = self.min_interval - (now - self._last_request_at)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self._last_request_at = time.monotonic()


class SecPublicClient:
    def __init__(
        self,
        config: EquityRuntimeConfig,
        *,
        transport: JsonTransport | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.config = config
        self.transport = transport or _http_json_transport
        self.timeout_seconds = timeout_seconds
        self.cache = TTLCache(config.sec_cache_ttl_seconds)
        self.pacer = RequestPacer(min(config.sec_max_rps, 5))

    def fetch_submissions(self, cik: str | int) -> dict[str, Any]:
        normalized_cik = normalize_cik(cik)
        url = f"{SEC_DATA_BASE_URL}/submissions/CIK{normalized_cik}.json"
        payload = self._fetch_json(url)
        if not isinstance(payload, dict):
            raise EquityConnectorError("SEC submissions response was not an object")
        return payload

    def fetch_companyfacts(self, cik: str | int) -> dict[str, Any]:
        normalized_cik = normalize_cik(cik)
        url = f"{SEC_DATA_BASE_URL}/api/xbrl/companyfacts/CIK{normalized_cik}.json"
        payload = self._fetch_json(url)
        if not isinstance(payload, dict):
            raise EquityConnectorError("SEC companyfacts response was not an object")
        return payload

    def _fetch_json(self, url: str) -> dict[str, Any] | list[dict[str, Any]]:
        cached = self.cache.get(url)
        if cached is not None:
            return cached
        headers = {
            "User-Agent": self.config.sec_user_agent,
            "Accept": "application/json",
        }
        payload = _fetch_with_retries(
            url,
            headers=headers,
            timeout_seconds=self.timeout_seconds,
            transport=self.transport,
            pacer=self.pacer,
            source_name="SEC public data",
        )
        self.cache.set(url, payload)
        return payload


class FmpMarketClient:
    def __init__(
        self,
        config: EquityRuntimeConfig,
        *,
        transport: JsonTransport | None = None,
        base_url: str = FMP_STABLE_BASE_URL,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.config = config
        self.transport = transport or _http_json_transport
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.cache = TTLCache(config.fmp_cache_ttl_seconds)
        self.pacer = RequestPacer(config.fmp_max_rps)

    def fetch_market_snapshot(
        self,
        *,
        symbol: str | None,
        cik: str | None = None,
        retrieved_at: datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = _utc_now(retrieved_at)
        if not self.config.fmp_api_key:
            return {
                "source": "fmp",
                "connector_role": "licensed_market_data_connector",
                "symbol": symbol,
                "cik": cik,
                "status": "missing_credential",
                "observations": [],
                "retrieved_at": timestamp,
                "rights_policy": fmp_rights_policy(self.config),
                "PIT_policy": fmp_pit_policy(),
                "warnings": ["FMP_API_KEY is not configured; optional market snapshot unavailable."],
            }
        if not symbol and not cik:
            return {
                "source": "fmp",
                "connector_role": "licensed_market_data_connector",
                "symbol": symbol,
                "cik": cik,
                "status": "unavailable",
                "observations": [],
                "retrieved_at": timestamp,
                "rights_policy": fmp_rights_policy(self.config),
                "PIT_policy": fmp_pit_policy(),
                "warnings": ["FMP requires a symbol or CIK for this optional snapshot."],
            }

        observations: list[dict[str, Any]] = []
        warnings: list[str] = []
        resolved_cik = cik
        normalized_symbol = symbol.upper() if symbol else None

        if normalized_symbol:
            profile = self._request("profile", {"symbol": normalized_symbol})
            profile_row = _first_row(profile)
            if profile_row:
                raw_cik = profile_row.get("cik") or resolved_cik
                resolved_cik = str(raw_cik).zfill(10) if raw_cik else None
                _append_observation(
                    observations,
                    field="company_profile",
                    value={
                        "company_name": profile_row.get("companyName") or profile_row.get("company_name"),
                        "cik": resolved_cik,
                    },
                    observed_at=timestamp,
                    available_at=timestamp,
                    source_id=f"fmp:profile:{normalized_symbol}",
                )
        elif cik:
            profile = self._request("profile-cik", {"cik": cik})
            profile_row = _first_row(profile)
            if profile_row and profile_row.get("symbol"):
                normalized_symbol = str(profile_row.get("symbol")).upper()

        if normalized_symbol:
            quote = self._request("quote", {"symbol": normalized_symbol})
            quote_row = _first_row(quote)
            if quote_row:
                observed_at = _provider_timestamp(quote_row) or timestamp
                price = _first_present(quote_row, "price", "previousClose", "close")
                if price is not None:
                    _append_observation(
                        observations,
                        field="latest_price",
                        value=price,
                        observed_at=observed_at,
                        available_at=timestamp,
                        source_id=f"fmp:quote:{normalized_symbol}",
                        unit="USD",
                    )
                market_cap = _first_present(quote_row, "marketCap", "market_cap")
                if market_cap is not None:
                    _append_observation(
                        observations,
                        field="market_cap",
                        value=market_cap,
                        observed_at=observed_at,
                        available_at=timestamp,
                        source_id=f"fmp:quote:{normalized_symbol}",
                        unit="USD",
                    )

            market_cap_payload = self._request(
                "market-capitalization", {"symbol": normalized_symbol}
            )
            market_cap_row = _first_row(market_cap_payload)
            market_cap = _first_present(market_cap_row or {}, "marketCap", "market_cap")
            if market_cap is not None:
                observed_at = _date_observed_at(market_cap_row or {}) or timestamp
                _append_observation(
                    observations,
                    field="market_cap",
                    value=market_cap,
                    observed_at=observed_at,
                    available_at=timestamp,
                    source_id=f"fmp:market-capitalization:{normalized_symbol}",
                    unit="USD",
                )
        else:
            warnings.append("FMP did not resolve a symbol; quote and market-cap calls skipped.")

        if not self.config.fmp_production_license_confirmed:
            warnings.append(
                "FMP production license is unconfirmed; observations are dev-only and export-blocked."
            )

        return {
            "source": "fmp",
            "connector_role": "licensed_market_data_connector",
            "symbol": normalized_symbol,
            "cik": resolved_cik,
            "status": "available" if observations else "unavailable",
            "observations": observations,
            "retrieved_at": timestamp,
            "rights_policy": fmp_rights_policy(self.config),
            "PIT_policy": fmp_pit_policy(),
            "warnings": warnings,
        }

    def _request(self, endpoint: str, params: dict[str, str]) -> dict[str, Any] | list[dict[str, Any]]:
        query = urlencode({**params, "apikey": self.config.fmp_api_key or ""})
        url = f"{self.base_url}/{endpoint}?{query}"
        cached = self.cache.get(url)
        if cached is not None:
            return cached
        payload = _fetch_with_retries(
            url,
            headers={"User-Agent": "VIZA Equity FMP connector"},
            timeout_seconds=self.timeout_seconds,
            transport=self.transport,
            pacer=self.pacer,
            source_name="FMP",
        )
        self.cache.set(url, payload)
        return payload


class FredMacroClient:
    def __init__(
        self,
        config: EquityRuntimeConfig,
        *,
        transport: JsonTransport | None = None,
        base_url: str = FRED_API_BASE_URL,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.config = config
        self.transport = transport or _http_json_transport
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.cache = TTLCache(config.fred_cache_ttl_seconds)
        self.pacer = RequestPacer(config.fred_max_rps)

    def fetch_macro_context(
        self,
        *,
        series_ids: tuple[str, ...] = DEFAULT_FRED_SERIES,
        retrieved_at: datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = _utc_now(retrieved_at)
        if not self.config.fred_api_key:
            return {
                "source": "fred",
                "connector_role": "official_public_connector",
                "status": "missing_credential",
                "observations": [],
                "retrieved_at": timestamp,
                "rights_policy": fred_rights_policy(),
                "PIT_policy": fred_pit_policy(self.config),
                "warnings": ["FRED_API_KEY is not configured; optional macro context unavailable."],
            }

        observations: list[dict[str, Any]] = []
        warnings: list[str] = []
        for series_id in series_ids:
            payload = self._request(series_id)
            observation = _latest_fred_observation(payload)
            if observation is None:
                warnings.append(f"FRED series {series_id} returned no usable observations.")
                continue
            _append_observation(
                observations,
                field=series_id,
                value=observation["value"],
                observed_at=f"{observation['date']}T00:00:00+00:00",
                available_at=(
                    f"{observation.get('realtime_start')}T00:00:00+00:00"
                    if self.config.fred_use_alfred_vintages
                    and observation.get("realtime_start")
                    else timestamp
                ),
                source_id=f"fred:{series_id}",
                unit="series_native",
                extra={
                    "series_id": series_id,
                    "realtime_start": observation.get("realtime_start"),
                    "realtime_end": observation.get("realtime_end"),
                },
            )

        if not self.config.fred_use_alfred_vintages:
            warnings.append(
                "FRED macro context is latest-only/ingestion-timestamped and not true PIT for backtests."
            )

        return {
            "source": "fred",
            "connector_role": "official_public_connector",
            "status": "available" if observations else "unavailable",
            "observations": observations,
            "retrieved_at": timestamp,
            "rights_policy": fred_rights_policy(),
            "PIT_policy": fred_pit_policy(self.config),
            "warnings": warnings,
        }

    def _request(self, series_id: str) -> dict[str, Any] | list[dict[str, Any]]:
        params = {
            "series_id": series_id.upper(),
            "api_key": self.config.fred_api_key or "",
            "file_type": "json",
            "sort_order": "desc",
            "limit": "1",
        }
        if self.config.fred_use_alfred_vintages:
            today = datetime.now(timezone.utc).date().isoformat()
            params["realtime_start"] = today
            params["realtime_end"] = today
        url = f"{self.base_url}/series/observations?{urlencode(params)}"
        cached = self.cache.get(url)
        if cached is not None:
            return cached
        payload = _fetch_with_retries(
            url,
            headers={"User-Agent": "VIZA Equity FRED connector"},
            timeout_seconds=self.timeout_seconds,
            transport=self.transport,
            pacer=self.pacer,
            source_name="FRED",
        )
        self.cache.set(url, payload)
        return payload


def normalize_cik(cik: str | int) -> str:
    digits = "".join(ch for ch in str(cik) if ch.isdigit())
    if not digits:
        raise ValueError("CIK must contain digits")
    return digits.zfill(10)


def fmp_rights_policy(config: EquityRuntimeConfig) -> dict[str, Any]:
    if config.fmp_production_license_confirmed:
        return {
            "license_policy": "licensed_provider_confirmed",
            "display_policy": "allowed_if_entitled",
            "export_policy": "blocked_unless_license_terms_allow",
            "marketplace_policy": "redacted_unless_license_terms_allow",
            "production_scoring_eligible": True,
            "redaction_required": True,
        }
    return {
        "license_policy": "dev_only_unconfirmed",
        "display_policy": "dev_only",
        "export_policy": "blocked",
        "marketplace_policy": "redacted",
        "production_scoring_eligible": False,
        "redaction_required": True,
    }


def fmp_pit_policy() -> dict[str, Any]:
    return {
        "observed_at_policy": "provider_timestamp_or_market_date",
        "available_at_policy": "retrieved_at_if_no_provider_timestamp",
        "retrieved_at_policy": "runtime_now",
        "PIT_safe": False,
        "lookahead_risk": "provider_latest_or_non_vintaged_market_snapshot",
    }


def fred_rights_policy() -> dict[str, Any]:
    return {
        "license_policy": "public_official",
        "display_policy": "allowed_with_attribution",
        "export_policy": "metadata_and_derived_allowed",
        "marketplace_policy": "metadata_and_derived_allowed_with_attribution",
        "attribution_required": True,
        "redaction_required": False,
    }


def fred_pit_policy(config: EquityRuntimeConfig) -> dict[str, Any]:
    return {
        "observed_at_policy": "series_observation_date",
        "available_at_policy": (
            "realtime_period_if_vintage_enabled"
            if config.fred_use_alfred_vintages
            else "retrieved_at_latest_only"
        ),
        "retrieved_at_policy": "runtime_now",
        "vintage_required": True,
        "PIT_safe": False,
        "pit_status": (
            "vintage_metadata_requested_not_backtest_promoted"
            if config.fred_use_alfred_vintages
            else "latest_only_or_ingestion_timestamped"
        ),
        "lookahead_risk": (
            "macro_vintage_cutoff_not_enforced"
            if config.fred_use_alfred_vintages
            else "macro_revision_or_latest_only"
        ),
    }


def _fetch_with_retries(
    url: str,
    *,
    headers: dict[str, str],
    timeout_seconds: float,
    transport: JsonTransport,
    pacer: RequestPacer,
    source_name: str,
    attempts: int = 3,
) -> dict[str, Any] | list[dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        pacer.wait()
        try:
            payload = transport(url, headers, timeout_seconds)
            if isinstance(payload, (dict, list)):
                return payload
            raise EquityConnectorError(f"{source_name} response was not JSON-like")
        except Exception as exc:  # pragma: no cover - exercised only for live/network failures.
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.25 * (attempt + 1))
    raise EquityConnectorError(f"{source_name} request failed; request details redacted") from last_error


def _http_json_transport(
    url: str,
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any] | list[dict[str, Any]]:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _first_row(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any] | None:
    if isinstance(payload, list):
        return payload[0] if payload and isinstance(payload[0], dict) else None
    if isinstance(payload, dict):
        for key in ("data", "historical", "observations"):
            value = payload.get(key)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value[0]
        return payload
    return None


def _latest_fred_observation(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any] | None:
    observations = payload.get("observations") if isinstance(payload, dict) else payload
    if not isinstance(observations, list):
        return None
    for row in observations:
        if not isinstance(row, dict):
            continue
        if row.get("value") in {None, "", "."}:
            continue
        if row.get("date"):
            return row
    return None


def _append_observation(
    observations: list[dict[str, Any]],
    *,
    field: str,
    value: Any,
    observed_at: str,
    available_at: str,
    source_id: str,
    unit: str = "unknown",
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "field": field,
        "value": value,
        "unit": unit,
        "observed_at": observed_at,
        "available_at": available_at,
        "retrieved_at": available_at,
        "source_id": source_id,
    }
    if extra:
        payload.update(extra)
    observations.append(payload)


def _first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return None


def _provider_timestamp(row: dict[str, Any]) -> str | None:
    raw_timestamp = row.get("timestamp")
    if raw_timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(float(raw_timestamp), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _date_observed_at(row: dict[str, Any]) -> str | None:
    raw_date = row.get("date")
    if not raw_date:
        return None
    return f"{raw_date}T00:00:00+00:00"


def _utc_now(value: datetime | None = None) -> str:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat()
