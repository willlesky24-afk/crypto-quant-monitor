"""v3.1 perpetual funding rates, read from public endpoints.

Funding is what one side of a perpetual pays the other: extreme values mean many
traders are leveraged the same way. It describes crowding, not direction.

Provider is chosen with FUNDING_PROVIDER (okx by default, or binance). Binance
Futures is not offered in every country, so it is opt-in. There is deliberately
no automatic switch: a change of source changes the market being measured, and
a blocked location must be reported, never worked around.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import pandas as pd
import requests

OKX_URL = "https://www.okx.com/api/v5/public/funding-rate-history"
BINANCE_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
PROVIDERS = ("okx", "binance")
DEFAULT_RECORDS = 1000
TIMEOUT_SECONDS = 15


class FundingUnavailableError(RuntimeError):
    """Funding data could not be obtained; the reason is shown to the user."""


def provider_from_env() -> str:
    return os.getenv("FUNDING_PROVIDER", "okx").strip().lower()


def _http_get(url: str, params: dict[str, Any]) -> tuple[int, Any]:
    response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
    return response.status_code, response.json()


class FundingSource:
    def __init__(
        self,
        provider: str,
        get: Callable[[str, dict[str, Any]], tuple[int, Any]] = _http_get,
        page_size: int = 100,
    ) -> None:
        if provider not in PROVIDERS:
            raise FundingUnavailableError(f"Proveedor de funding invalido: {provider}")
        self.provider = provider
        self._get = get
        self.page_size = page_size

    def _checked(self, url: str, params: dict[str, Any]) -> Any:
        status, payload = self._get(url, params)
        if status == 451:
            raise FundingUnavailableError(
                f"{self.provider}: no disponible desde esta ubicacion (HTTP 451)."
            )
        if status != 200:
            raise FundingUnavailableError(f"{self.provider}: HTTP {status}.")
        return payload

    def _okx_rows(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        inst = f"{symbol.removesuffix('USDT')}-USDT-SWAP"
        rows: list[dict[str, Any]] = []
        after = None
        while len(rows) < limit:
            params: dict[str, Any] = {"instId": inst, "limit": self.page_size}
            if after is not None:
                params["after"] = after
            payload = self._checked(OKX_URL, params)
            if payload.get("code") != "0":
                raise FundingUnavailableError(f"okx: codigo {payload.get('code')}.")
            page = payload["data"]
            if not page:
                break
            rows.extend(page)
            after = page[-1]["fundingTime"]
        return rows

    def fetch(self, symbol: str, limit: int = DEFAULT_RECORDS) -> pd.Series:
        """Rates as fractions per funding period, oldest first, newest ``limit``."""
        if self.provider == "okx":
            rows = self._okx_rows(symbol, limit)
        else:
            rows = self._checked(BINANCE_URL, {"symbol": symbol, "limit": limit})
        if not rows:
            raise FundingUnavailableError(f"{self.provider}: sin datos de {symbol}.")
        series = pd.Series(
            [float(r["fundingRate"]) for r in rows],
            index=pd.to_datetime(
                [int(r["fundingTime"]) for r in rows], unit="ms", utc=True
            ),
        )
        return series[~series.index.duplicated()].sort_index().tail(limit)


def funding_snapshot(series: pd.Series) -> dict[str, float | int]:
    """Latest rate and how large it is against the available records.

    Informative only, and not a radar alert: OKX keeps about 3 months (under 300
    records), too few to reach the radar's multi-test bar. Size is compared by
    absolute value, because crowding can lean either way.
    """
    sizes = series.abs()
    prior, current = sizes.iloc[:-1], sizes.iloc[-1]
    return {
        "rate_pct": float(series.iloc[-1] * 100.0),
        "size_percentile": float((prior < current).mean() * 100.0),
        "records": len(series),
    }
