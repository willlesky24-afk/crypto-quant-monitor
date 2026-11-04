from __future__ import annotations

from typing import Any

from src.backtest_models import BacktestConfig, TradeDirection

PROVEN_STRATEGIES: dict[str, dict[str, Any]] = {
    "capital_preservation": {
        "name": "🛡️ Spot 1x — Sin apalancamiento (filtro estricto)",
        "short_name": "Spot 1x — Sin apalancamiento",
        "description": "Preset con filtro de confluencia técnica (Quant Score >= 75), dirección LONG y stop configurado. No impide pérdidas.",
        "direction": TradeDirection.LONG.value,
        "min_quant_score": 75.0,
        "tp_atr_multiple": 2.2,
        "sl_atr_multiple": 1.0,
        "enable_trailing_stop": False,
    },
    "trend_following": {
        "name": "🏛️ Seguimiento de Tendencia Institucional (Trend Following)",
        "short_name": "Trend Following",
        "description": "Preset que simula compras a favor de la tendencia mayor (sobre EMA 200 y POC) con niveles derivados de sus parámetros configurados.",
        "direction": TradeDirection.LONG.value,
        "min_quant_score": 68.0,
        "tp_atr_multiple": 3.0,
        "sl_atr_multiple": 1.5,
        "enable_trailing_stop": True,
    },
    "mean_reversion": {
        "name": "🔄 Reversión a la Media en Rangos (Mean Reversion)",
        "short_name": "Reversión a la Media",
        "description": "Preset de investigación para rangos que utiliza referencias VAL, POC y VAH. Su dirección BOTH no está disponible en la contabilidad SPOT actual.",
        "direction": TradeDirection.BOTH.value,
        "min_quant_score": 60.0,
        "tp_atr_multiple": 1.8,
        "sl_atr_multiple": 1.0,
        "enable_trailing_stop": False,
    },
    "volatility_breakout": {
        "name": "🚀 Ruptura de Volatilidad (Volatility Breakout)",
        "short_name": "Ruptura de Volatilidad",
        "description": "Preset de investigación para rupturas de volatilidad con trailing stop. Su dirección BOTH no está disponible en la contabilidad SPOT actual.",
        "direction": TradeDirection.BOTH.value,
        "min_quant_score": 65.0,
        "tp_atr_multiple": 3.5,
        "sl_atr_multiple": 1.2,
        "enable_trailing_stop": True,
    },
    "dynamic_hybrid": {
        "name": "🧠 Modelo Cuantitativo Híbrido (Nativo de Antigravity)",
        "short_name": "Cuantitativo Híbrido",
        "description": "Preset que combina clasificación de régimen y señales predictivas. Su dirección BOTH no está disponible en la contabilidad SPOT actual.",
        "direction": TradeDirection.BOTH.value,
        "min_quant_score": 60.0,
        "tp_atr_multiple": 2.5,
        "sl_atr_multiple": 1.25,
        "enable_trailing_stop": False,
    },
}


def build_strategy_config(
    strategy_key: str,
    initial_capital: float = 100.0,
    taker_fee_pct: float = 0.0005,
    slippage_pct: float = 0.0005,
    leverage: float = 1.0,
    **kwargs: Any,
) -> BacktestConfig:
    """Build a deterministic BacktestConfig from a configured strategy preset."""
    preset = PROVEN_STRATEGIES.get(
        strategy_key, PROVEN_STRATEGIES["capital_preservation"]
    )
    return BacktestConfig(
        initial_capital=max(5.0, float(initial_capital)),
        taker_fee_pct=taker_fee_pct,
        slippage_pct=slippage_pct,
        leverage=max(1.0, float(leverage)),
        direction=preset["direction"],
        min_quant_score=preset["min_quant_score"],
        tp_atr_multiple=preset["tp_atr_multiple"],
        sl_atr_multiple=preset["sl_atr_multiple"],
        enable_trailing_stop=preset["enable_trailing_stop"],
        require_favorable_decision=preset.get("require_favorable_decision", False),
    )


def evaluate_backtest_verdict(metrics: dict[str, Any]) -> dict[str, str]:
    """Classify simulated metrics with the existing pedagogical thresholds."""
    total_trades = int(metrics.get("total_trades", 0))
    win_rate = float(metrics.get("win_rate", 0.0))
    profit_factor = float(metrics.get("profit_factor", 0.0))
    max_dd = float(metrics.get("max_drawdown_pct", 0.0))
    net_pnl = float(metrics.get("net_pnl", 0.0))

    if total_trades < 5:
        return {
            "status": "NEUTRAL",
            "badge": "⚪ MUESTRA INSUFICIENTE",
            "title": "Pocas operaciones para evaluar los criterios de esta simulación",
            "description": f"Se registraron solo {total_trades} operaciones en este periodo histórico. Intenta aumentar la cantidad de velas en la barra lateral para evaluar una muestra estadística más amplia.",
            "color": "#00E5FF",
        }

    if net_pnl > 0 and profit_factor >= 1.45 and max_dd <= 20.0:
        return {
            "status": "APPROVED",
            "badge": "🟢 CUMPLE CRITERIOS DE ESTA SIMULACIÓN",
            "title": "Resultado histórico dentro de los umbrales configurados",
            "description": (
                f"En esta simulación, la tasa de acierto fue {win_rate * 100:.1f}% y el factor de beneficio "
                f"fue {profit_factor:.2f}. El drawdown máximo observado fue {max_dd:.1f}%. "
                "Estos resultados no acreditan desempeño prospectivo ni protección del capital."
            ),
            "color": "#00FF88",
        }
    elif net_pnl > 0 and (profit_factor >= 1.05 or max_dd > 20.0):
        return {
            "status": "WARNING",
            "badge": "🟡 RESULTADO MIXTO EN ESTA SIMULACIÓN",
            "title": "Resultado positivo con riesgo observado",
            "description": (
                f"El PnL neto simulado fue +${net_pnl:,.2f}; el drawdown máximo observado fue "
                f"{max_dd:.1f}% y el factor de beneficio fue {profit_factor:.2f}. "
                "La muestra histórica no permite inferir resultados futuros."
            ),
            "color": "#FFD600",
        }
    else:
        return {
            "status": "REJECTED",
            "badge": "🔴 NO CUMPLE CRITERIOS DE ESTA SIMULACIÓN",
            "title": "Resultado fuera de los umbrales configurados",
            "description": (
                f"El PnL neto simulado fue ${net_pnl:,.2f} y el factor de beneficio fue {profit_factor:.2f}. "
                "La clasificación describe esta muestra histórica; no es una recomendación operativa."
            ),
            "color": "#FF2E63",
        }
