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


def test_evaluate_backtest_verdict_with_backtest_report_metrics():
    from src.backtest_models import BacktestConfig, BacktestReport

    report = BacktestReport(
        config=BacktestConfig(),
        symbol="BTCUSDT",
        timeframe="1h",
        start_time="2024-01-01",
        end_time="2024-01-10",
        total_candles=100,
        total_trades=20,
        winning_trades=14,
        losing_trades=6,
        win_rate_pct=70.0,
        profit_factor=2.2,
        expectancy=50.0,
        expectancy_r=1.2,
        max_drawdown_pct=5.0,
        max_drawdown_usd=25.0,
        max_drawdown_duration_bars=4,
        avg_mfe_pct=2.5,
        avg_mae_pct=0.8,
        avg_bars_held=5.0,
        total_gross_pnl=500.0,
        total_fees_paid=20.0,
        total_net_pnl=480.0,
        return_on_capital_pct=48.0,
    )

    verdict = evaluate_backtest_verdict(report.metrics)
    assert verdict["status"] == "APPROVED"
    assert "APROBADA" in verdict["badge"]
