from __future__ import annotations

import pandas as pd

from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo
from src.market_reports.generator import MarketReportService
from src.market_reports.models import DailyBriefingReport, IntradayUpdateReport


def _create_sample_context(price: float = 60000.0, score: float = 75.0, regime: str = "TRENDING_BULL") -> MarketContext:
    return MarketContext(
        timestamp=pd.Timestamp("2026-09-20 12:00:00", tz="UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=price,
        market_regime=regime,
        predictive_score=0.75,
        quant_score=score,
        signal=SignalInfo(
            action="BUY",
            direction="LONG",
            confidence=0.85,
            reasoning="Strong trend momentum",
            positives=("Volume expansion",),
            warnings=(),
        ),
        risk=RiskMetrics(
            stop_loss=58500.0,
            take_profit=63000.0,
            risk_ratio=2.0,
            risk_category="LOW",
            atr=1100.0,
        ),
        technical_indicators={"rsi": 62.0},
        volume_profile={"poc": 59800.0, "vah": 60500.0, "val": 59200.0},
    )


def test_daily_briefing_report_generation():
    svc = MarketReportService()
    ctx = _create_sample_context()
    briefing = svc.generate_daily_briefing(ctx)

    assert isinstance(briefing, DailyBriefingReport)
    assert briefing.symbol == "BTCUSDT"
    assert briefing.current_regime == "TRENDING_BULL"
    assert briefing.quant_score == 75.0
    assert "Stop Loss" in briefing.important_levels
    assert "Value Area High" in briefing.important_levels
    assert len(briefing.strongest_signals) > 0
    assert "DECISION SUPPORT ONLY" in briefing.disclaimer

    d = briefing.to_dict()
    assert d["symbol"] == "BTCUSDT"
    assert isinstance(d["strongest_signals"], list)


def test_daily_briefing_with_warnings_and_no_risks():
    svc = MarketReportService()
    # Context with warnings
    ctx_warn = MarketContext(
        timestamp=pd.Timestamp("2026-09-20 12:00:00", tz="UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=60000.0,
        market_regime="TRENDING_BULL",
        predictive_score=0.75,
        quant_score=75.0,
        signal=SignalInfo(
            action="WAIT",
            direction="NEUTRAL",
            confidence=0.50,
            warnings=("Overbought RSI", "High Funding"),
        ),
        risk=RiskMetrics(risk_category=""),
    )
    b_warn = svc.generate_daily_briefing(ctx_warn)
    assert "Overbought RSI" in b_warn.main_risks

    # Context with no warnings and no risk category
    ctx_clean = MarketContext(
        timestamp=pd.Timestamp("2026-09-20 12:00:00", tz="UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=60000.0,
        market_regime="TRENDING_BULL",
        predictive_score=0.75,
        quant_score=75.0,
        signal=SignalInfo(
            action="WAIT",
            direction="NEUTRAL",
            confidence=0.50,
            warnings=(),
        ),
        risk=RiskMetrics(risk_category=""),
    )
    b_clean = svc.generate_daily_briefing(ctx_clean)
    assert "No adverse volatility spikes detected." in b_clean.main_risks



def test_intraday_update_initial_baseline():
    svc = MarketReportService()
    ctx = _create_sample_context()
    update = svc.generate_intraday_update(current_context=ctx, previous_context=None)

    assert isinstance(update, IntradayUpdateReport)
    assert "Baseline established" in update.what_changed
    assert update.price_delta_pct == 0.0
    assert update.score_delta == 0.0
    assert len(update.what_to_monitor) > 0


def test_intraday_update_delta_calculation():
    svc = MarketReportService()
    prev_ctx = _create_sample_context(price=60000.0, score=70.0, regime="CHOPPY_RANGE")
    curr_ctx = _create_sample_context(price=61200.0, score=80.0, regime="TRENDING_BULL")

    update = svc.generate_intraday_update(current_context=curr_ctx, previous_context=prev_ctx)

    assert update.price_delta_pct == 2.0  # +2.0%
    assert update.score_delta == 10.0  # +10 pts
    assert update.regime_shift is not None
    assert "Shifted from 'CHOPPY_RANGE' to 'TRENDING_BULL'" in update.regime_shift
    assert len(update.what_to_monitor) >= 2

    d = update.to_dict()
    assert d["price_delta_pct"] == 2.0