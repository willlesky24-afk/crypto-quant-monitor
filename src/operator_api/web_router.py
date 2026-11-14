"""v4 web interface API: the same screens as Streamlit, as JSON.

Every endpoint calls the engine modules the Streamlit app uses, so a number
cannot differ between interfaces. Errors become HTTP errors with a readable
reason; nothing is replaced by sample data. Attempts on the verifier are
counted on the server per client, so reloading the page does not reset them.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src import market_service
from src.idea_agent import (
    IdeaAgentError,
    explain_prompt,
    explanation_or_facts,
    parse_translation,
    translate_prompt,
)
from src.idea_verifier import (
    ENTRIES,
    METHODS,
    IdeaSpec,
    IdeaVerifierError,
    load_history,
    past_story,
    verify_idea,
)
from src.operator_api.dependencies import verify_security
from src.operator_api.security import get_client_identifier
from src.position_sizing import (
    PositionSizingError,
    compute_position_plan,
    quote_to_usd,
    stop_from_atr,
)
from src.unusual_radar import build_markets, run_radar

router = APIRouter(
    prefix="/api/v1",
    tags=["Interfaz web"],
    dependencies=[Depends(verify_security)],
)

_attempts: dict[str, int] = defaultdict(int)


def reset_attempts() -> None:
    _attempts.clear()


def _candles(symbol: str, interval: str):
    try:
        return market_service.load_candles(symbol, interval)
    except market_service.MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/mercados")
def mercados() -> dict[str, Any]:
    return market_service.markets()


@router.get("/hoy")
def hoy(symbol: str = "BTCUSDT", interval: str = "1h") -> dict[str, Any]:
    df = _candles(symbol, interval)
    return market_service.today_payload(
        df, symbol, interval, market_service.funding_for(symbol)
    )


class RiskRequest(BaseModel):
    symbol: str
    interval: str = "1h"
    capital: float = Field(gt=0)
    risk_pct: float = Field(gt=0, le=100)
    side: str = "LONG"
    entry_price: float | None = None
    atr_multiple: float = Field(default=2.0, gt=0)
    fee_pct: float | None = None


@router.post("/riesgo")
def riesgo(body: RiskRequest) -> dict[str, Any]:
    df = _candles(body.symbol, body.interval)
    last = df.iloc[-1]
    entry = body.entry_price or float(last["close"])
    spread = float(last["spread"]) if "spread" in df.columns else 0.0
    fee = body.fee_pct
    if fee is None:
        fee = 0.0 if body.symbol.endswith("=X") else 0.05
    try:
        stop = stop_from_atr(entry, float(last["atr"]), body.atr_multiple, body.side)
        plan = compute_position_plan(
            capital=body.capital,
            risk_pct=body.risk_pct,
            entry_price=entry,
            stop_price=stop,
            side=body.side,
            spread=spread,
            fee_pct=fee,
            quote_to_account=quote_to_usd(body.symbol, entry),
        )
    except PositionSizingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "entry_price": entry,
        "stop_price": stop,
        "spread_included": "spread" in df.columns,
        "fee_pct": fee,
        **plan.__dict__,
    }


@router.get("/metodos")
def metodos() -> dict[str, Any]:
    return {"methods": list(METHODS), "entries": list(ENTRIES)}


class VerifyRequest(BaseModel):
    symbol: str
    interval: str = "4h"
    entry: str
    side: str = "LONG"
    sl_atr: float = Field(gt=0)
    tp_atr: float = Field(gt=0)
    max_bars: int = Field(gt=0)
    capital: float = Field(default=1000.0, gt=0)


@router.post("/verificar")
def verificar(body: VerifyRequest, request: Request) -> dict[str, Any]:
    df = load_history(body.symbol, body.interval)
    source = "historia guardada"
    if df is None:
        df = _candles(body.symbol, body.interval)
        source = "datos en vivo (poca historia)"
    client = get_client_identifier(request)
    _attempts[client] += 1
    spec = IdeaSpec(
        body.symbol,
        body.interval,
        body.entry,
        body.side,
        body.sl_atr,
        body.tp_atr,
        body.max_bars,
    )
    try:
        result = verify_idea(df, spec, _attempts[client], capital=body.capital)
    except IdeaVerifierError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        **{k: (str(v) if k == "last_entry" else v) for k, v in result.items()},
        "story": past_story(result),
        "data_source": source,
    }


def _ask_ai(prompt: str) -> str:
    from src.ai_providers.factory import ProviderFactory

    provider = ProviderFactory.create_provider()
    if not hasattr(provider, "generate_response"):
        raise IdeaAgentError("No hay un proveedor de IA configurado.")
    response = asyncio.run(provider.generate_response(prompt))
    if response.metadata.get("status") == "fallback":
        raise IdeaAgentError(response.content)
    return response.content


class InterpretRequest(BaseModel):
    text: str = Field(min_length=3, max_length=500)


@router.post("/interpretar")
def interpretar(body: InterpretRequest) -> dict[str, Any]:
    try:
        return parse_translation(_ask_ai(translate_prompt(body.text)))
    except IdeaAgentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class ExplainRequest(BaseModel):
    result: dict[str, Any]


@router.post("/explicar")
def explicar(body: ExplainRequest) -> dict[str, Any]:
    try:
        raw = _ask_ai(explain_prompt(body.result))
    except IdeaAgentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=422, detail=f"Resultado incompleto: {exc}"
        ) from exc
    text, used_ai = explanation_or_facts(raw, body.result)
    return {"text": text, "used_ai": used_ai}


RADAR_PAIRS = [
    ("BTCUSDT", "ETHUSDT"),
    ("XAUUSD=X", "XAGUSD=X"),
    ("AUDUSD=X", "NZDUSD=X"),
    ("EURUSD=X", "GBPUSD=X"),
    ("SPX500=X", "NAS100=X"),
]
RADAR_INDICES = ["SPX500=X", "NAS100=X", "US30=X"]


@router.get("/radar")
def radar(interval: str = "1h") -> dict[str, Any]:
    """Scan every market against its own history; failures are listed, not hidden."""
    listed = market_service.markets()
    crypto = [m["symbol"] for m in listed["crypto"]]
    other = [m["symbol"] for m in listed["other"]]
    # Downloads run in parallel; a market that fails is listed, never dropped.
    # OANDA refused several parallel requests in live scans, so forex, metals and
    # indices are fetched two at a time; Binance takes the full parallel load.
    loaded, failed = build_markets(
        lambda s: market_service.load_candles(s, interval), crypto
    )
    other_loaded, other_failed = build_markets(
        lambda s: market_service.load_candles(s, interval), other, max_workers=2
    )
    loaded.update(other_loaded)
    failed.update(other_failed)
    if listed["other_error"]:
        failed["Forex"] = listed["other_error"]
    groups = [
        crypto,
        [s for s in other if s not in RADAR_INDICES],
        [s for s in other if s in RADAR_INDICES],
    ]
    result = run_radar(loaded, groups, RADAR_PAIRS, failed)
    return {
        "interval": interval,
        "tests": result.tests,
        "alpha": result.alpha,
        "alerts": [alert.__dict__ for alert in result.alerts],
        "failed": result.failed,
    }
