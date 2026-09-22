from __future__ import annotations

from src.backtest_presets import (
    PROVEN_STRATEGIES,
    build_strategy_config,
    evaluate_backtest_verdict,
)


def test_proven_strategies_dict():
    assert "capital_preservation" in PROVEN_STRATEGIES
    assert "trend_following" in PROVEN_STRATEGIES
    assert "mean_reversion" in PROVEN_STRATEGIES
    assert "volatility_breakout" in PROVEN_STRATEGIES
    assert "dynamic_hybrid" in PROVEN_STRATEGIES


def test_build_strategy_config():
    cfg = build_strategy_config("capital_preservation", initial_capital=50.0)
    assert cfg.initial_capital == 50.0
    assert cfg.direction == "LONG"
    assert cfg.min_quant_score == 75.0

    # Minimum threshold protection
    cfg_low = build_strategy_config("trend_following", initial_capital=2.0)
    assert cfg_low.initial_capital == 5.0


def test_evaluate_backtest_verdict():
    # Low sample
    v_empty = evaluate_backtest_verdict({"total_trades": 2})
    assert v_empty["status"] == "NEUTRAL"
    assert "INSUFICIENTE" in v_empty["badge"]

    # Solid winning strategy
    v_approved = evaluate_backtest_verdict({
        "total_trades": 25,
        "win_rate": 0.65,
        "profit_factor": 2.10,
        "max_drawdown_pct": 8.5,
        "net_pnl": 150.0,
    })
    assert v_approved["status"] == "APPROVED"
    assert "APROBADA" in v_approved["badge"]

    # Losing strategy
    v_rejected = evaluate_backtest_verdict({
        "total_trades": 25,
        "win_rate": 0.35,
        "profit_factor": 0.75,
        "max_drawdown_pct": 25.0,
        "net_pnl": -80.0,
    })
    assert v_rejected["status"] == "REJECTED"
    assert "NO RECOMENDADA" in v_rejected["badge"]
