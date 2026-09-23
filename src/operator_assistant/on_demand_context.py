from __future__ import annotations

import logging
import re

import pandas as pd

from src.ai_agent.context_builder import ContextBuilder
from src.ai_agent.models import MarketContext
from src.data_loader import BinanceDataLoader
from src.decision_engine import DecisionEngine
from src.engine import MarketEngine
from src.forex_data_loader import ForexDataLoader
from src.indicators import TechnicalIndicators
from src.market_intelligence import MarketIntelligence
from src.notifications.models import SignalEvent
from src.predictive_engine import PredictiveEngine
from src.quant_score import QuantScore
from src.regime_classifier import RegimeClassifier
from src.risk_engine import RiskEngine
from src.signal_engine import SignalEngine
from src.volume_profile import VolumeProfile

logger = logging.getLogger(__name__)

FOREX_ALIAS_MAP: dict[str, str] = {
    "EURUSD": "EURUSD=X",
    "EUR/USD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "USD/JPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "AUD/USD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USD/CAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "USD/CHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    "NZD/USD": "NZDUSD=X",
    "EURGBP": "EURGBP=X",
    "EUR/GBP": "EURGBP=X",
}

CRYPTO_ALIAS_MAP: dict[str, str] = {
    "BITCOIN": "BTCUSDT",
    "BTC": "BTCUSDT",
    "BTCUSDT": "BTCUSDT",
    "ETHEREUM": "ETHUSDT",
    "ETH": "ETHUSDT",
    "ETHUSDT": "ETHUSDT",
    "SOLANA": "SOLUSDT",
    "SOL": "SOLUSDT",
    "SOLUSDT": "SOLUSDT",
    "BINANCE": "BNBUSDT",
    "BNB": "BNBUSDT",
    "BNBUSDT": "BNBUSDT",
    "RIPPLE": "XRPUSDT",
    "XRP": "XRPUSDT",
    "XRPUSDT": "XRPUSDT",
    "DOGECOIN": "DOGEUSDT",
    "DOGE": "DOGEUSDT",
    "DOGEUSDT": "DOGEUSDT",
    "CARDANO": "ADAUSDT",
    "ADA": "ADAUSDT",
    "ADAUSDT": "ADAUSDT",
    "AVALANCHE": "AVAXUSDT",
    "AVAX": "AVAXUSDT",
    "AVAXUSDT": "AVAXUSDT",
    "CHAINLINK": "LINKUSDT",
    "LINK": "LINKUSDT",
    "LINKUSDT": "LINKUSDT",
}


def resolve_mentioned_symbol(
    query_text: str,
    fallback_symbol: str = "BTCUSDT",
    fallback_tf: str = "1h",
) -> tuple[str, str, bool]:
    """Extract symbol, timeframe, and whether it is a Forex pair from user text.

    Returns:
    (symbol, timeframe, is_forex)
    """
    clean_text = query_text.upper()
    resolved_sym = fallback_symbol
    resolved_tf = fallback_tf
    is_forex = "=X" in fallback_symbol or "/" in fallback_symbol

    # 1. Check Forex exact aliases first
    for alias, f_sym in FOREX_ALIAS_MAP.items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, clean_text):
            resolved_sym = f_sym
            is_forex = True
            break

    # If not matched, check crypto aliases
    if not is_forex or resolved_sym == fallback_symbol:
        for alias, c_sym in CRYPTO_ALIAS_MAP.items():
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, clean_text):
                resolved_sym = c_sym
                is_forex = False
                break

    # If still not matched, check regex patterns for generic pairs
    if resolved_sym == fallback_symbol:
        match_crypto = re.search(r"\b([A-Z0-9]{2,10}(?:USDT|BUSD))\b", clean_text)
        if match_crypto:
            resolved_sym = match_crypto.group(1)
            is_forex = False
        else:
            match_forex = re.search(r"\b([A-Z]{3}/[A-Z]{3})\b", clean_text)
            if match_forex:
                raw_pair = match_forex.group(1)
                compact = raw_pair.replace("/", "")
                resolved_sym = f"{compact}=X"
                is_forex = True

    # 2. Extract Timeframe
    match_tf = re.search(r"\b(15[mM]|1[hH]|4[hH]|1[dD])\b", query_text)
    if match_tf:
        resolved_tf = match_tf.group(1).lower()

    return resolved_sym, resolved_tf, is_forex


def build_on_demand_context(
    symbol: str,
    timeframe: str = "1h",
    is_forex: bool | None = None,
) -> MarketContext | None:
    """Fetch live data and generate complete causal MarketContext for any symbol on demand."""
    try:
        is_fx = is_forex if is_forex is not None else ("=X" in symbol or "/" in symbol)
        if is_fx:
            f_loader = ForexDataLoader()
            raw_df = f_loader.get_forex_klines(symbol=symbol, interval=timeframe, limit=200)
        else:
            b_loader = BinanceDataLoader()
            raw_df = b_loader.get_klines(symbol=symbol, interval=timeframe, limit=200, include_open_candle=False)

        if raw_df.empty or len(raw_df) < 35:
            logger.warning("Datos insuficientes para contexto on-demand de %s", symbol)
            return None

        ind_svc = TechnicalIndicators()
        enr_df = ind_svc.calculate_all(raw_df)
        vp_svc = VolumeProfile()
        prof = vp_svc.calculate(enr_df)
        m_eng = MarketEngine()
        ana = m_eng.analyze(enr_df, prof)
        s_eng = SignalEngine()
        sig = s_eng.evaluate(ana, prof)
        r_eng = RiskEngine()
        rsk = r_eng.evaluate(ana, prof)
        i_eng = MarketIntelligence()
        intl = i_eng.evaluate(ana)
        q_eng = QuantScore()
        sc = q_eng.calculate(ana, sig, rsk)
        rc_eng = RegimeClassifier()
        reg_res = rc_eng.classify(enr_df)
        pe_eng = PredictiveEngine()
        prd_res = pe_eng.evaluate(enr_df, current_regime_res=reg_res)
        dec_eng = DecisionEngine()
        dec = dec_eng.evaluate(
            signal=sig,
            risk=rsk,
            intelligence=intl,
            predictive=prd_res,
            regime=reg_res.regime,
            technical_score=sc["score"],
            predictive_mode=True,
        )

        last_row = enr_df.iloc[-1]
        live_sig = SignalEvent(
            timestamp=pd.Timestamp(last_row["timestamp"]),
            symbol=symbol,
            timeframe=timeframe,
            action=dec.decision,
            direction=dec.direction,
            confidence=dec.confidence if dec.confidence <= 1.0 else dec.confidence / 100.0,
            predictive_score=prd_res.predictive_score,
            regime=reg_res.regime.value,
            reasoning=dec.reasoning,
            price=float(last_row["close"]),
            quant_score=sc["score"],
            stop_loss=rsk.get("stop_loss"),
            take_profit=rsk.get("take_profit"),
            signal_id=f"on_demand-{symbol}-{timeframe}",
            metadata={
                "risk_reward_ratio": rsk.get("risk_ratio"),
                "atr": rsk.get("atr"),
                "positives": dec.positives,
                "warnings": dec.warnings,
            },
        )
        ctx_b = ContextBuilder()
        return ctx_b.build_context(
            signal_event=live_sig,
            technical_indicators={
                "rsi": float(last_row.get("rsi", 50.0)),
                "adx": float(last_row.get("adx", 20.0)),
                "volume": float(last_row.get("volume", 0.0)),
            },
            volume_profile=prof,
            metadata={"source": "On-demand Live Copilot Query"},
        )
    except Exception as exc:
        logger.error("Error generando contexto on-demand para %s: %s", symbol, exc)
        return None
