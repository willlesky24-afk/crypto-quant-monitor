"""v4 web interface API: the same screens as Streamlit, as JSON.

Every endpoint calls the engine modules the Streamlit app uses, so a number
cannot differ between interfaces. Errors become HTTP errors with a readable
reason; nothing is replaced by sample data. Attempts on the verifier are
counted on the server per client, so reloading the page does not reset them.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
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
    spec_key,
    verify_holdout,
    verify_idea,
)
from src.journal_store import (
    Journal,
    JournalError,
    Trade,
    breaches,
    summary,
    week_start,
)
from src.market_copilot import answer_or_facts, copilot_prompt, facts_from
from src.operator_api.dependencies import verify_security
from src.operator_api.security import get_client_identifier
from src.operator_api.web_auth import require_session
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
    dependencies=[Depends(verify_security), Depends(require_session)],
)


def journal() -> Journal:
    """The owner's local journal (path from CQM_JOURNAL_DB or data/diario.db)."""
    return Journal()


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
    risk_pct: float = Field(default=1.0, gt=0, le=100)


def _spec(body: VerifyRequest) -> IdeaSpec:
    return IdeaSpec(
        body.symbol,
        body.interval,
        body.entry,
        body.side,
        body.sl_atr,
        body.tp_atr,
        body.max_bars,
    )


def _public(result: dict[str, Any], source: str) -> dict[str, Any]:
    out = {
        k: (str(v) if k in ("first_entry", "last_entry") else v)
        for k, v in result.items()
    }
    out.pop("r_values", None)
    return {**out, "story": past_story(result), "data_source": source}


@router.post("/verificar")
def verificar(body: VerifyRequest, request: Request) -> dict[str, Any]:
    df = load_history(body.symbol, body.interval)
    source = "historia guardada"
    if df is None:
        df = _candles(body.symbol, body.interval)
        source = "datos en vivo (poca historia)"
    spec = _spec(body)
    store = journal()
    attempt = store.next_attempt(get_client_identifier(request))
    try:
        result = verify_idea(
            df, spec, attempt, capital=body.capital, risk_pct=body.risk_pct
        )
    except IdeaVerifierError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    key = spec_key(spec)
    if result["code"] == "MERECE_ESTUDIO" and source == "historia guardada":
        store.mark_eligible(key)
    available = store.is_eligible(key) and store.holdout_used_at(key) is None
    return {**_public(result, source), "holdout_available": available}


@router.post("/verificar/reservado")
def verificar_reservado(body: VerifyRequest) -> dict[str, Any]:
    """Spend the reserved 20 % once, only for a rule that deserved study."""
    spec = _spec(body)
    store = journal()
    key = spec_key(spec)
    if not store.is_eligible(key):
        raise HTTPException(
            409,
            "Los datos reservados solo se usan con una regla que salió "
            '"Merece más estudio" con historia guardada.',
        )
    df = load_history(body.symbol, body.interval)
    if df is None:
        raise HTTPException(409, "No hay historia guardada de este mercado.")
    try:
        store.use_holdout(key)
    except JournalError as exc:
        raise HTTPException(409, str(exc)) from exc
    try:
        result = verify_holdout(df, spec, capital=body.capital, risk_pct=body.risk_pct)
    except IdeaVerifierError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _public(result, "datos reservados (una sola vez)")


def _trade_json(t: Trade) -> dict[str, Any]:
    return {
        "id": t.id,
        "symbol": t.symbol,
        "side": t.side,
        "entry": t.entry,
        "stop": t.stop,
        "units": t.units,
        "risk_usd": t.risk_usd,
        "costs_usd": t.costs_usd,
        "reason": t.reason,
        "outside_rules": t.outside_rules,
        "opened_at": t.opened_at,
        "exit": t.exit,
        "closed_at": t.closed_at,
        "moved_stop": t.moved_stop,
        "size_respected": t.size_respected,
        "pnl_usd": t.pnl_usd,
        "r": t.r,
        "followed_plan": t.followed_plan,
        "status": "abierta" if t.exit is None else "cerrada",
    }


def _since(trades: list[Trade], start: datetime) -> list[Trade]:
    return [
        t
        for t in trades
        if t.closed_at and datetime.fromisoformat(t.closed_at) >= start
    ]


@router.get("/diario")
def diario() -> dict[str, Any]:
    store = journal()
    trades = store.trades()
    now = datetime.now(UTC)
    rules = store.rules()
    return {
        "trades": [_trade_json(t) for t in trades],
        "semana": summary(_since(trades, week_start(now))),
        "mes": summary(_since(trades, now - timedelta(days=30))),
        "total": summary(trades),
        "rules": rules,
        "breaches": breaches(trades, rules, now),
    }


class PlanRequest(BaseModel):
    symbol: str
    side: str
    entry: float
    stop: float
    units: float
    risk_usd: float
    costs_usd: float = 0.0
    reason: str
    acknowledged: bool = False


@router.post("/diario")
def guardar_plan(body: PlanRequest) -> dict[str, Any]:
    store = journal()
    crossed = breaches(store.trades(), store.rules())
    if crossed and not body.acknowledged:
        raise HTTPException(409, {"breaches": crossed})
    try:
        trade = store.open_trade(
            body.symbol,
            body.side,
            body.entry,
            body.stop,
            body.units,
            body.risk_usd,
            body.costs_usd,
            body.reason,
            outside_rules=bool(crossed),
        )
    except JournalError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _trade_json(trade)


class CloseRequest(BaseModel):
    exit: float
    moved_stop: bool
    size_respected: bool


@router.post("/diario/{trade_id}/cerrar")
def cerrar(trade_id: int, body: CloseRequest) -> dict[str, Any]:
    try:
        trade = journal().close_trade(
            trade_id, body.exit, body.moved_stop, body.size_respected
        )
    except JournalError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _trade_json(trade)


@router.put("/diario/reglas")
def reglas(body: dict[str, float | None]) -> dict[str, float]:
    """Only the keys sent change; null removes a rule. No defaults are filled."""
    try:
        return journal().set_rules(dict(body))
    except JournalError as exc:
        raise HTTPException(422, str(exc)) from exc


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


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(max_length=2000)


class CopilotRequest(BaseModel):
    symbol: str
    interval: str = "1h"
    question: str = Field(min_length=2, max_length=500)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


@router.post("/copiloto")
def copiloto(body: CopilotRequest) -> dict[str, Any]:
    """Plain-language answer about one market; numbers only from the engine."""
    facts = facts_from(hoy(body.symbol, body.interval))
    prompt = copilot_prompt(
        body.question, facts, [(t.role, t.text) for t in body.history]
    )
    try:
        raw = _ask_ai(prompt)
    except IdeaAgentError as exc:
        return {"text": facts.text, "used_ai": False, "ai_error": str(exc)}
    text, used_ai = answer_or_facts(raw, facts)
    return {"text": text, "used_ai": used_ai, "ai_error": None}
