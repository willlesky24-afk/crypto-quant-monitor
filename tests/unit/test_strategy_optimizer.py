from __future__ import annotations

import json

import pandas as pd
import pytest

from src.backtest_models import BacktestConfig, BacktestReport, TradeResult
from src.regime_classifier import MarketRegime
from src.strategy_optimizer import (
    MFEMAEDistribution,
    StrategyOptimizer,
)


def make_synthetic_trades(
    n_trades: int = 30,
    regime: str = MarketRegime.TRENDING_BULL.value,
    start_year: int = 2023,
    end_year: int = 2024,
    mfe_mean: float = 4.0,
    mae_mean: float = 1.5,
    seed: int = 42,
) -> list[TradeResult]:
    """Generates synthetic TradeResult items with specified regime and timestamp range."""
    import numpy as np

    rng = np.random.default_rng(seed)
    start_ts = pd.Timestamp(f"{start_year}-01-01 00:00:00+00:00")
    end_ts = pd.Timestamp(f"{end_year}-12-31 23:59:59+00:00")

    trades: list[TradeResult] = []
    for i in range(n_trades):
        rand_offset_hours = int(rng.uniform(0, (end_ts - start_ts).total_seconds() / 3600))
        entry_time = start_ts + pd.Timedelta(hours=rand_offset_hours)
        exit_time = entry_time + pd.Timedelta(hours=int(rng.integers(1, 24)))

        entry_price = float(rng.uniform(20_000, 60_000))
        # Excursions in percentage (e.g. 3-6% MFE, 1-2% MAE)
        mfe_pct = max(0.2, float(rng.normal(mfe_mean, 1.0)))
        mae_pct = max(0.1, float(rng.normal(mae_mean, 0.5)))

        is_win = bool(mfe_pct > mae_pct * 1.5)
        exit_price = entry_price * (1.0 + (mfe_pct if is_win else -mae_pct) / 100.0)

        # Mock TradeResult
        t = TradeResult(
            trade_id=f"trade-{i + 1}",
            symbol="BTCUSDT",
            timeframe="1h",
            direction="LONG",
            signal_timestamp=entry_time - pd.Timedelta(hours=1),
            entry_timestamp=entry_time,
            exit_timestamp=exit_time,
            entry_price=entry_price,
            exit_price=exit_price,
            size_units=1.0,
            notional_entry=entry_price,
            notional_exit=exit_price,
            gross_pnl=exit_price - entry_price,
            fee_entry=entry_price * 0.0005,
            fee_exit=exit_price * 0.0005,
            net_pnl=(exit_price - entry_price) * 0.999,
            net_return_pct=((exit_price - entry_price) / entry_price) * 100.0,
            r_multiple=2.0 if is_win else -1.0,
            bars_held=int(rng.integers(2, 20)),
            exit_reason="TAKE_PROFIT" if is_win else "STOP_LOSS",
            mfe_pct=mfe_pct,
            mae_pct=mae_pct,
            is_win=is_win,
        )
        # Attach regime attribute dynamically
        object.__setattr__(t, "regime", regime)
        # Entry ATR simulated around 1.5% of price
        object.__setattr__(t, "atr_entry", entry_price * 0.015)
        trades.append(t)

    return trades


def test_strategy_optimizer_empty_trades_and_distribution():
    optimizer = StrategyOptimizer()
    dist = optimizer.analyze_distribution([])

    assert isinstance(dist, MFEMAEDistribution)
    assert dist.sample_size == 0
    assert dist.mfe_median == 0.0
    assert dist.mae_median == 0.0
    assert dist.win_rate_pct == 0.0

    d = dist.to_dict()
    assert d["sample_size"] == 0


def test_strategy_optimizer_determinism():
    optimizer = StrategyOptimizer()
    train_trades = make_synthetic_trades(n_trades=25, seed=123)

    res1 = optimizer.optimize_regime(MarketRegime.TRENDING_BULL, train_trades)
    res2 = optimizer.optimize_regime(MarketRegime.TRENDING_BULL, train_trades)

    assert res1.atr_tp_multiplier == pytest.approx(res2.atr_tp_multiplier)
    assert res1.atr_sl_multiplier == pytest.approx(res2.atr_sl_multiplier)
    assert res1.expected_rr == pytest.approx(res2.expected_rr)
    assert res1.confidence == pytest.approx(res2.confidence)
    assert res1.sample_size == res2.sample_size
    assert res1.to_dict() == res2.to_dict()


def test_strategy_optimizer_respects_bounds():
    """Validates that parameters are strictly clipped to [min, max] ranges."""
    optimizer = StrategyOptimizer(
        min_atr_tp=2.0,
        max_atr_tp=6.0,
        min_atr_sl=1.0,
        max_atr_sl=3.5,
    )

    # Trades with huge excursions (would exceed max without clipping)
    huge_trades = make_synthetic_trades(n_trades=20, mfe_mean=20.0, mae_mean=10.0, seed=99)
    res_huge = optimizer.optimize_regime(MarketRegime.HIGH_VOLATILITY_EXPANSION, huge_trades)

    assert res_huge.atr_tp_multiplier <= 6.0
    assert res_huge.atr_sl_multiplier <= 3.5

    # Trades with tiny excursions (would fall below min without clipping)
    tiny_trades = make_synthetic_trades(n_trades=20, mfe_mean=0.2, mae_mean=0.1, seed=77)
    res_tiny = optimizer.optimize_regime(MarketRegime.RANGING_CONSOLIDATION, tiny_trades)

    assert res_tiny.atr_tp_multiplier >= 2.0
    assert res_tiny.atr_sl_multiplier >= 1.0


def test_strategy_optimizer_small_sample_penalty():
    """Validates small sample handling: confidence penalty and fallback to defaults."""
    optimizer = StrategyOptimizer(min_sample_size=15)
    few_trades = make_synthetic_trades(n_trades=4, seed=55)

    res = optimizer.optimize_regime(MarketRegime.TRENDING_BULL, few_trades)

    assert res.sample_size == 4
    assert res.confidence < 0.30
    assert res.validation_period["status"] == "insufficient_training_sample"
    assert res.validation_period["penalty_applied"] is True
    # Default for TRENDING_BULL is 3.5 / 1.5
    assert res.atr_tp_multiplier == 3.5
    assert res.atr_sl_multiplier == 1.5


def test_strategy_optimizer_separation_by_regime():
    """Validates that distributions are kept strictly separated by regime."""
    optimizer = StrategyOptimizer()

    bull_trades = make_synthetic_trades(n_trades=25, regime=MarketRegime.TRENDING_BULL.value, mfe_mean=6.0, seed=1)
    range_trades = make_synthetic_trades(n_trades=25, regime=MarketRegime.RANGING_CONSOLIDATION.value, mfe_mean=2.0, seed=2)

    all_trades = bull_trades + range_trades
    results = optimizer.optimize_all_regimes(all_trades)

    assert MarketRegime.TRENDING_BULL.value in results
    assert MarketRegime.RANGING_CONSOLIDATION.value in results

    bull_opt = results[MarketRegime.TRENDING_BULL.value]
    range_opt = results[MarketRegime.RANGING_CONSOLIDATION.value]

    assert bull_opt.sample_size == 25
    assert range_opt.sample_size == 25
    assert bull_opt.atr_tp_multiplier != range_opt.atr_tp_multiplier


def test_strategy_optimizer_walk_forward_division():
    """Validates TRAIN (2023-2024) vs. VALIDATION (2025) walk-forward split."""
    optimizer = StrategyOptimizer(train_end="2025-01-01 00:00:00+00:00")

    trades_2023_2024 = make_synthetic_trades(n_trades=20, start_year=2023, end_year=2024, seed=11)
    trades_2025 = make_synthetic_trades(n_trades=10, start_year=2025, end_year=2025, seed=22)

    train_set, val_set = optimizer.split_walk_forward(trades_2023_2024 + trades_2025)

    assert len(train_set) == 20
    assert len(val_set) == 10

    for t in train_set:
        assert t["entry_timestamp"] < pd.Timestamp("2025-01-01 00:00:00+00:00")
    for t in val_set:
        assert t["entry_timestamp"] >= pd.Timestamp("2025-01-01 00:00:00+00:00")

    res = optimizer.optimize_regime(MarketRegime.TRENDING_BULL, train_set, val_set)
    assert res.validation_period["train_sample_size"] == 20
    assert res.validation_period["validation_sample_size"] == 10
    assert "validation_simulated_win_rate_pct" in res.validation_period


def test_strategy_optimizer_no_temporal_leakage():
    """Mandatory causal test:

    Modifying, adding, or removing trades posterior to TRAIN period
    MUST NEVER alter the parameters calculated on TRAIN.
    """
    optimizer = StrategyOptimizer(train_end="2025-01-01 00:00:00+00:00")

    train_trades = make_synthetic_trades(n_trades=30, start_year=2023, end_year=2024, seed=101)
    val_trades_original = make_synthetic_trades(n_trades=15, start_year=2025, end_year=2025, mfe_mean=3.0, seed=202)
    val_trades_modified = make_synthetic_trades(n_trades=30, start_year=2025, end_year=2026, mfe_mean=15.0, seed=303)

    res_baseline = optimizer.optimize_regime(MarketRegime.TRENDING_BULL, train_trades, val_trades_original)
    res_tampered = optimizer.optimize_regime(MarketRegime.TRENDING_BULL, train_trades, val_trades_modified)

    # TRAIN parameters must be 100% invariant
    assert res_baseline.atr_tp_multiplier == res_tampered.atr_tp_multiplier
    assert res_baseline.atr_sl_multiplier == res_tampered.atr_sl_multiplier
    assert res_baseline.expected_rr == res_tampered.expected_rr
    assert res_baseline.sample_size == res_tampered.sample_size
    assert res_baseline.confidence == res_tampered.confidence


def test_strategy_optimizer_serialization():
    optimizer = StrategyOptimizer()
    trades = make_synthetic_trades(n_trades=15, seed=555)
    res = optimizer.optimize_regime(MarketRegime.TRENDING_BULL, trades)

    d = res.to_dict()
    assert isinstance(d, dict)
    assert "regime" in d
    assert "atr_tp_multiplier" in d
    assert "atr_sl_multiplier" in d
    assert "expected_rr" in d
    assert "confidence" in d
    assert "validation_period" in d

    json_str = json.dumps(d)
    assert isinstance(json_str, str)


def test_strategy_optimizer_optimize_from_report():
    optimizer = StrategyOptimizer()
    trades = make_synthetic_trades(n_trades=20, regime=MarketRegime.TRENDING_BULL.value, seed=777)

    mock_report = BacktestReport(
        config=BacktestConfig(),
        symbol="BTCUSDT",
        timeframe="1h",
        start_time="2023-01-01 00:00:00+00:00",
        end_time="2024-12-31 00:00:00+00:00",
        total_candles=1000,
        total_trades=20,
        winning_trades=12,
        losing_trades=8,
        win_rate_pct=60.0,
        profit_factor=1.8,
        expectancy=100.0,
        expectancy_r=1.5,
        max_drawdown_pct=5.0,
        max_drawdown_usd=500.0,
        max_drawdown_duration_bars=10,
        avg_mfe_pct=4.0,
        avg_mae_pct=1.5,
        avg_bars_held=8.0,
        total_gross_pnl=2200.0,
        total_fees_paid=200.0,
        total_net_pnl=2000.0,
        return_on_capital_pct=20.0,
        trades=trades,
    )

    results = optimizer.optimize_from_report(mock_report)
    assert isinstance(results, dict)
    assert MarketRegime.TRENDING_BULL.value in results
    bull_res = results[MarketRegime.TRENDING_BULL.value]
    assert bull_res.sample_size == 20


def test_strategy_optimizer_with_candles():
    """Validates that supplying candles automatically annotates unclassified trades."""
    from tests.unit.test_predictive_engine import make_predictive_candles

    candles = make_predictive_candles(n_candles=80, pattern="bull")

    optimizer = StrategyOptimizer()
    # Trades without explicit regime
    trades = make_synthetic_trades(n_trades=10, regime="", seed=888)
    # Assign entry_timestamp to match candles
    for i, t in enumerate(trades):
        object.__setattr__(t, "signal_timestamp", candles["timestamp"].iloc[55 + i])
        object.__setattr__(t, "entry_timestamp", candles["timestamp"].iloc[56 + i])

    results = optimizer.optimize_all_regimes(trades, candles=candles)
    assert isinstance(results, dict)
    assert any(res.sample_size > 0 for res in results.values())


def test_strategy_optimizer_edge_cases_and_fallbacks():
    optimizer = StrategyOptimizer(min_sample_size=10)

    # 1. Trade without to_dict or dict (custom object)
    class RawTrade:
        entry_price = 0.0
        mfe_pct = 2.0
        mae_pct = 1.0
        is_win = True
        regime = "TRENDING_BULL"
        atr_entry = 0.0

    raw = RawTrade()
    res = optimizer.analyze_distribution([raw])
    assert res.sample_size == 1

    # 2. Trade without timestamps
    train_set, val_set = optimizer.split_walk_forward([{"trade_id": "no_ts"}])
    assert len(train_set) == 0
    assert len(val_set) == 0

    # 3. Few winning trades (< 3 wins) in training set
    losing_trades = make_synthetic_trades(n_trades=12, seed=12)
    for t in losing_trades:
        object.__setattr__(t, "is_win", False)
    # Give just 1 win
    object.__setattr__(losing_trades[0], "is_win", True)
    res_fallback = optimizer.optimize_regime(MarketRegime.TRENDING_BULL, losing_trades)
    assert res_fallback.sample_size == 12
    assert res_fallback.atr_sl_multiplier >= 1.0

    # 4. Report with closed_trades attribute instead of trades
    class LegacyReport:
        closed_trades = losing_trades

    res_report = optimizer.optimize_from_report(LegacyReport())
    assert MarketRegime.TRENDING_BULL.value in res_report


