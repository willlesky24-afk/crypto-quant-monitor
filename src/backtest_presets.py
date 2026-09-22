from __future__ import annotations

from typing import Any

from src.backtest_models import BacktestConfig, TradeDirection

PROVEN_STRATEGIES: dict[str, dict[str, Any]] = {
    "capital_preservation": {
        "name": "🛡️ Preservación de Capital (Principiante Seguro)",
        "short_name": "Preservación de Capital",
        "description": "Filtro estricto que prioriza cuidar tu dinero. Solo entra cuando hay alta confluencia técnica a favor (Quant Score >= 75), exclusivamente en compras (LONG) y con Stop Loss ceñido.",
        "direction": TradeDirection.LONG.value,
        "min_quant_score": 75.0,
        "tp_atr_multiple": 2.2,
        "sl_atr_multiple": 1.0,
        "enable_trailing_stop": False,
    },
    "trend_following": {
        "name": "🏛️ Seguimiento de Tendencia Institucional (Trend Following)",
        "short_name": "Trend Following",
        "description": "El estándar de Wall Street: solo opera a favor de la tendencia mayor (sobre EMA 200 y POC), buscando grandes corridas alcistas con relación Riesgo:Beneficio superior a 1:2.",
        "direction": TradeDirection.LONG.value,
        "min_quant_score": 68.0,
        "tp_atr_multiple": 3.0,
        "sl_atr_multiple": 1.5,
        "enable_trailing_stop": True,
    },
    "mean_reversion": {
        "name": "🔄 Reversión a la Media en Rangos (Mean Reversion)",
        "short_name": "Reversión a la Media",
        "description": "Ideal para mercados laterales: compra en zonas de descuento institucional (VAL) y vende en el precio justo (POC) o resistencia (VAH).",
        "direction": TradeDirection.BOTH.value,
        "min_quant_score": 60.0,
        "tp_atr_multiple": 1.8,
        "sl_atr_multiple": 1.0,
        "enable_trailing_stop": False,
    },
    "volatility_breakout": {
        "name": "🚀 Ruptura de Volatilidad (Volatility Breakout)",
        "short_name": "Ruptura de Volatilidad",
        "description": "Espera compresiones de volatilidad y se monta en la ola del impulso con Stop Loss dinámico (Trailing Stop) para capturar movimientos explosivos rápidos.",
        "direction": TradeDirection.BOTH.value,
        "min_quant_score": 65.0,
        "tp_atr_multiple": 3.5,
        "sl_atr_multiple": 1.2,
        "enable_trailing_stop": True,
    },
    "dynamic_hybrid": {
        "name": "🧠 Modelo Cuantitativo Híbrido (Nativo de Antigravity)",
        "short_name": "Cuantitativo Híbrido",
        "description": "El sistema inteligente nativo: clasifica el régimen en tiempo real y cambia dinámicamente entre tendencia y rango según probabilidades predictivas.",
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
) -> BacktestConfig:
    """Build a deterministic BacktestConfig from a battle-tested strategy preset."""
    preset = PROVEN_STRATEGIES.get(strategy_key, PROVEN_STRATEGIES["capital_preservation"])
    return BacktestConfig(
        initial_capital=max(5.0, float(initial_capital)),
        taker_fee_pct=taker_fee_pct,
        slippage_pct=slippage_pct,
        direction=preset["direction"],
        min_quant_score=preset["min_quant_score"],
        tp_atr_multiple=preset["tp_atr_multiple"],
        sl_atr_multiple=preset["sl_atr_multiple"],
        enable_trailing_stop=preset["enable_trailing_stop"],
    )


def evaluate_backtest_verdict(metrics: dict[str, Any]) -> dict[str, str]:
    """Evaluates backtest metrics and produces a pedagogical traffic light verdict."""
    total_trades = int(metrics.get("total_trades", 0))
    win_rate = float(metrics.get("win_rate", 0.0))
    profit_factor = float(metrics.get("profit_factor", 0.0))
    max_dd = float(metrics.get("max_drawdown_pct", 0.0))
    net_pnl = float(metrics.get("net_pnl", 0.0))

    if total_trades < 5:
        return {
            "status": "NEUTRAL",
            "badge": "⚪ MUESTRA INSUFICIENTE",
            "title": "Pocas operaciones para emitir un veredicto definitivo",
            "description": f"Se registraron solo {total_trades} operaciones en este periodo histórico. Intenta aumentar la cantidad de velas en la barra lateral para evaluar una muestra estadística más amplia.",
            "color": "#00E5FF",
        }

    if net_pnl > 0 and profit_factor >= 1.45 and max_dd <= 20.0:
        return {
            "status": "APPROVED",
            "badge": "🟢 ESTRATEGIA APROBADA / SALUDABLE",
            "title": "Excelente solidez cuantitativa y riesgo bajo control",
            "description": (
                f"Esta estrategia superó la prueba con éxito. De cada 10 operaciones ganó aproximadamente "
                f"{int(win_rate * 10)}, y por cada dólar que perdió generó ${profit_factor:.2f} de beneficio. "
                f"La caída máxima fue controlada ({max_dd:.1f}%), por lo que tu capital estuvo protegido en todo momento."
            ),
            "color": "#00FF88",
        }
    elif net_pnl > 0 and (profit_factor >= 1.05 or max_dd > 20.0):
        return {
            "status": "WARNING",
            "badge": "🟡 ESTRATEGIA MODERADA / PRECAUCIÓN",
            "title": "Genera ganancias, pero presenta altibajos o caídas considerables",
            "description": (
                f"La estrategia terminó en positivo (+${net_pnl:,.2f}), pero sufrió una caída máxima temporal de "
                f"{max_dd:.1f}% y su factor de beneficio es de {profit_factor:.2f}. "
                f"Podrías pasar sustos psicológicos en las malas rachas. Se recomienda usar corte de pérdida más estricto o perfil conservador."
            ),
            "color": "#FFD600",
        }
    else:
        return {
            "status": "REJECTED",
            "badge": "🔴 ESTRATEGIA NO RECOMENDADA / DE RIESGO",
            "title": "Rendimiento deficiente o riesgo excesivo en este par",
            "description": (
                f"La estrategia finalizó con saldo negativo (${net_pnl:,.2f}) o un factor de beneficio por debajo de 1.05 ({profit_factor:.2f}). "
                f"No se recomienda arriesgar capital real bajo estos parámetros en las condiciones actuales de mercado."
            ),
            "color": "#FF2E63",
        }
