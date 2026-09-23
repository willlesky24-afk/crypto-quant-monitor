from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

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
    risk_reward: float
    stop_loss: float | None
    take_profit: float | None
    primary_reason: str
    ranking_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "regime": self.regime,
            "action": self.action,
            "direction": self.direction,
            "quant_score": round(self.quant_score, 1),
            "predictive_score": round(self.predictive_score, 2),
            "confidence": round(self.confidence * 100, 1),
            "risk_reward": round(self.risk_reward, 2),
            "stop_loss": round(self.stop_loss, 2) if self.stop_loss else None,
            "take_profit": round(self.take_profit, 2) if self.take_profit else None,
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
        limit: int = 100,
    ) -> list[ScannedPairResult]:
        """Scan candidate symbols and rank descending by composite quantitative score."""
        symbols = symbols or self.DEFAULT_PAIRS
        results: list[ScannedPairResult] = []

        for sym in symbols:
            try:
                df_raw = self.loader.get_klines(sym, interval=timeframe, limit=limit, include_open_candle=False)
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
                pred_res = self.predictive_engine.evaluate(df, current_regime_res=regime_res)

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
                rr = float(risk.get("risk_ratio", 1.5))
                raw_conf = float(decision.confidence)
                conf = raw_conf if raw_conf <= 1.0 else raw_conf / 100.0

                # Composite score weighting: 50% technical score, 30% predictive, 20% risk-reward
                ranking_score = round(
                    (q_score * 0.50) + (p_score * 100.0 * 0.30) + (min(rr, 4.0) * 10.0 * 0.20),
                    1,
                )

                pos_list = signal.get("positives", []) if isinstance(signal, dict) else getattr(signal, "positives", [])
                pos = pos_list[0] if pos_list else f"Régimen {regime_res.regime.value}"

                results.append(
                    ScannedPairResult(
                        symbol=sym,
                        price=price,
                        regime=regime_res.regime.value,
                        action=str(decision.decision),
                        direction=str(decision.direction),
                        quant_score=q_score,
                        predictive_score=p_score,
                        confidence=conf,
                        risk_reward=rr,
                        stop_loss=risk.get("stop_loss"),
                        take_profit=risk.get("take_profit"),
                        primary_reason=pos,
                        ranking_score=ranking_score,
                    )
                )
            except Exception as exc:
                logger.warning(f"Error scanning {sym}: {exc}")
                continue

        results.sort(key=lambda x: x.ranking_score, reverse=True)
        return results

    def format_scanner_summary_es(self, results: list[ScannedPairResult]) -> str:
        """Produce everyday Spanish narrative explaining the best trading scenario."""
        if not results:
            return "No se pudieron obtener datos suficientes para escanear el mercado en este momento."

        top = results[0]
        direction_text = "al alza (compra)" if top.direction == "LONG" else ("a la baja (venta)" if top.direction == "SHORT" else "en consolidación neutral")

        narrative = [
            f"🏆 **El par que presenta el MEJOR escenario en este momento es {top.symbol}**.",
            "",
            f"📌 **¿Por qué {top.symbol} y qué significan estos números en lenguaje cotidiano?**",
            f"- **Puntaje Cuantitativo:** `{top.quant_score:.1f}/100`. En palabras simples, de cada 10 métricas analizadas (volumen, tendencia, liquidez), aproximadamente **{int(top.quant_score/10)} están totalmente a favor** de este movimiento.",
            f"- **Postura Sugerida:** `{top.action}` {direction_text} al precio de **${top.price:,.2f}**.",
            f"- **Probabilidad Predictiva:** `{top.predictive_score:.2f}` con una confianza del **{top.confidence*100:.1f}%** de que el impulso continúe según las velas pasadas.",
            f"- **Relación Riesgo / Beneficio:** `1:{top.risk_reward:.1f}`. Significa que por cada dólar que pones en riesgo (corte de pérdida), el sistema busca obtener al menos **${top.risk_reward:.1f}** de ganancia potencial.",
            "- **Nivel de Protección (Stop Loss):** " + (f"${top.stop_loss:,.2f}" if top.stop_loss else "Calculado dinámicamente por ATR"),
            "- **Objetivo (Take Profit):** " + (f"${top.take_profit:,.2f}" if top.take_profit else "Calculado dinámicamente por ATR"),
            "",
            "📊 **Ranking de Otros Pares Analizados:**",
        ]

        for idx, r in enumerate(results[:5], 1):
            badge = "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else f"{idx}."))
            narrative.append(
                f"- {badge} **{r.symbol}** (${r.price:,.2f}) — `{r.action} {r.direction}` | Score: **{r.quant_score:.1f} pts** | R:R: `1:{r.risk_reward:.1f}` ({r.primary_reason})"
            )

        narrative.append("\n*Nota: Esta es una evaluación matemática de soporte de decisiones para el operador humano, sin ejecución automática.*")
        return "\n".join(narrative)
