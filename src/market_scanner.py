from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from src.constants import LIVE_HISTORY_BARS
from src.data_loader import BinanceDataLoader
from src.decision_engine import DecisionEngine
from src.engine import MarketEngine
from src.indicators import TechnicalIndicators
from src.market_intelligence import MarketIntelligence
from src.predictive_engine import PredictiveEngine
from src.quant_score import QuantScore
from src.regime_classifier import RegimeClassifier
from src.risk_engine import RiskEngine
from src.signal_engine import SignalEngine
from src.volume_profile import VolumeProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScannedPairResult:
    """Quantitative evaluation snapshot for a single scanned asset."""

    symbol: str
    price: float
    regime: str
    action: str
    direction: str
    quant_score: float
    predictive_score: float
    confidence: float
    risk_reward: float | None
    stop_loss: float | None
    take_profit: float | None
    primary_reason: str
    ranking_score: float
    timeframe: str = "1h"
    status: str = "NO DISPONIBLE"
    entry_price: float | None = None
    entry_confirmed: bool = False
    risk_distance: float | None = None
    reward_distance: float | None = None
    risk_reason: str | None = None
    risk_methodology: str | None = None

    def is_operable(self) -> bool:
        """A scanner candidate cannot be dispatched as an activated trade."""
        if (
            self.status != "ACTIVADA"
            or not self.entry_confirmed
            or not self.risk_methodology
        ):
            return False
        levels = RiskEngine().calculate_levels(
            self.entry_price, self.stop_loss, self.take_profit, self.direction
        )
        return (
            levels["reason"] is None
            and self.risk_reward is not None
            and self.risk_distance is not None
            and self.reward_distance is not None
            and math.isclose(
                self.risk_reward, levels["gross_risk_reward"], rel_tol=1e-9
            )
            and math.isclose(self.risk_distance, levels["risk_distance"], rel_tol=1e-9)
            and math.isclose(
                self.reward_distance, levels["reward_distance"], rel_tol=1e-9
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "price": self.price,
            "reference_price": self.price,
            "entry_price": self.entry_price,
            "entry_confirmed": self.entry_confirmed,
            "status": self.status,
            "regime": self.regime,
            "action": self.action,
            "direction": self.direction,
            "quant_score": round(self.quant_score, 1),
            "predictive_score": round(self.predictive_score, 2),
            "confidence": round(self.confidence * 100, 1),
            "risk_reward": self.risk_reward,
            "risk_reward_basis": "bruto_sin_costes"
            if self.risk_reward is not None
            else None,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_distance": self.risk_distance,
            "reward_distance": self.reward_distance,
            "risk_reason": self.risk_reason,
            "risk_methodology": self.risk_methodology,
            "primary_reason": self.primary_reason,
            "ranking_score": self.ranking_score,
        }


class MarketScanner:
    """Scans and ranks multiple crypto assets using the causal quantitative pipeline."""

    DEFAULT_PAIRS: tuple[str, ...] = (
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
        "BNBUSDT",
        "XRPUSDT",
        "DOGEUSDT",
        "ADAUSDT",
        "AVAXUSDT",
        "LINKUSDT",
    )

    def __init__(self, data_loader: BinanceDataLoader | None = None) -> None:
        self.loader = data_loader or BinanceDataLoader()
        self.indicators = TechnicalIndicators()
        self.volume_profile = VolumeProfile()
        self.market_engine = MarketEngine()
        self.signal_engine = SignalEngine()
        self.risk_engine = RiskEngine()
        self.intel_engine = MarketIntelligence()
        self.decision_engine = DecisionEngine()
        self.quant_score_engine = QuantScore()
        self.regime_classifier = RegimeClassifier()
        self.predictive_engine = PredictiveEngine()

    def scan_market(
        self,
        symbols: list[str] | tuple[str, ...] | None = None,
        timeframe: str = "1h",
        limit: int = LIVE_HISTORY_BARS,
    ) -> list[ScannedPairResult]:
        """Scan candidate symbols and rank descending by composite quantitative score."""
        symbols = symbols or self.DEFAULT_PAIRS
        results: list[ScannedPairResult] = []

        for sym in symbols:
            try:
                df_raw = self.loader.get_klines(
                    sym, interval=timeframe, limit=limit, include_open_candle=False
                )
                if df_raw.empty or len(df_raw) < 35:
                    continue
                df = self.indicators.calculate_all(df_raw)
                profile = self.volume_profile.calculate(df)
                analysis = self.market_engine.analyze(df, profile)
                signal = self.signal_engine.evaluate(analysis, profile)
                risk = self.risk_engine.evaluate(analysis, profile)
                intel = self.intel_engine.evaluate(analysis)
                score_dict = self.quant_score_engine.calculate(analysis, signal, risk)
                regime_res = self.regime_classifier.classify(df)
                pred_res = self.predictive_engine.evaluate(
                    df, current_regime_res=regime_res
                )

                q_score = float(score_dict.get("score", 50.0))
                decision = self.decision_engine.evaluate(
                    signal=signal,
                    risk=risk,
                    intelligence=intel,
                    predictive=pred_res,
                    regime=regime_res.regime,
                    technical_score=q_score,
                    predictive_mode=True,
                )

                price = float(df.iloc[-1]["close"])
                p_score = float(pred_res.predictive_score)
                plan = self.risk_engine.plan_from_decision(
                    decision=decision.decision,
                    direction=decision.direction,
                    reference_price=price,
                    atr=df.iloc[-1].get("atr"),
                    sl_multiplier=decision.sl_multiplier,
                    tp_multiplier=decision.tp_multiplier,
                )
                rr = plan["gross_risk_reward"]
                raw_conf = float(decision.confidence)
                conf = raw_conf if raw_conf <= 1.0 else raw_conf / 100.0

                # Missing R adds no reward component to the ranking.
                ranking_score = round(
                    (q_score * 0.50)
                    + (p_score * 100.0 * 0.30)
                    + ((min(rr, 4.0) * 10.0 * 0.20) if rr is not None else 0.0),
                    1,
                )

                pos_list = (
                    signal.get("positives", [])
                    if isinstance(signal, dict)
                    else getattr(signal, "positives", [])
                )
                pos = pos_list[0] if pos_list else f"Régimen {regime_res.regime.value}"

                results.append(
                    ScannedPairResult(
                        symbol=sym,
                        timeframe=timeframe,
                        price=price,
                        regime=regime_res.regime.value,
                        action=str(decision.decision),
                        direction=plan["direction"],
                        status=plan["status"],
                        quant_score=q_score,
                        predictive_score=p_score,
                        confidence=conf,
                        risk_reward=rr,
                        entry_price=plan["entry_price"],
                        entry_confirmed=plan["entry_confirmed"],
                        stop_loss=plan["stop_loss"],
                        take_profit=plan["take_profit"],
                        risk_distance=plan["risk_distance"],
                        reward_distance=plan["reward_distance"],
                        risk_reason=plan["reason"],
                        risk_methodology=plan["methodology"],
                        primary_reason=pos,
                        ranking_score=ranking_score,
                    )
                )
            except Exception as exc:
                logger.warning(f"Error scanning {sym}: {exc}")
                continue

        results.sort(
            key=lambda x: (x.status == "CANDIDATA", x.ranking_score), reverse=True
        )
        return results

    def format_scanner_summary_es(self, results: list[ScannedPairResult]) -> str:
        """Produce everyday Spanish narrative explaining the best trading scenario."""
        if not results:
            return "No se pudieron obtener datos suficientes para escanear el mercado en este momento."

        def price_text(value: float | None, symbol: str) -> str:
            if value is None:
                return "No disponible"
            decimals = 5 if "=X" in symbol else (6 if value < 1 else 2)
            return f"${value:,.{decimals}f}"

        top = next(
            (
                item
                for item in results
                if item.status == "CANDIDATA"
                and item.entry_price is not None
                and item.risk_distance is not None
                and item.reward_distance is not None
                and item.risk_reward is not None
            ),
            None,
        )
        if top is None:
            narrative = [
                "No hay oportunidades con niveles técnicos completos en este escaneo."
            ]
        else:
            narrative = [
                f"**Escenario técnico destacado: {top.symbol} ({top.timeframe}) — CANDIDATA, entrada no confirmada.**",
                f"- Dirección: {top.direction}; precio de referencia: {price_text(top.price, top.symbol)}.",
                f"- Entrada propuesta: {price_text(top.entry_price, top.symbol)}; SL: {price_text(top.stop_loss, top.symbol)}; TP: {price_text(top.take_profit, top.symbol)}.",
                f"- Distancia de riesgo: {top.risk_distance:.6g}; distancia de beneficio: {top.reward_distance:.6g}.",
                f"- R bruto indicativo: 1:{top.risk_reward:.2f}, calculado con esos niveles; no incluye spread, comisiones ni deslizamiento.",
                f"- Puntaje cuantitativo: {top.quant_score:.1f}/100; puntaje predictivo heurístico: {top.predictive_score:.2f}; confianza interna no calibrada: {top.confidence * 100:.1f}%.",
                f"- Método: {top.risk_methodology}. {top.risk_reason}",
            ]

        narrative.append("\n**Pares evaluados:**")
        for item in results[:5]:
            ratio = (
                f"1:{item.risk_reward:.2f} bruto"
                if item.risk_reward is not None
                else "No disponible"
            )
            narrative.append(
                f"- {item.symbol} ({item.timeframe}): {item.status}; dirección {item.direction}; R {ratio}. {item.risk_reason or item.primary_reason}"
            )
        narrative.append(
            "\n*Una candidata no confirma ejecución ni constituye una señal activada.*"
        )
        return "\n".join(narrative)
