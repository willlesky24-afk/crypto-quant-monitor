from __future__ import annotations

import pandas as pd
import pytest

from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo
from src.anomaly_detection.detector import MarketAnomalyDetector
from src.anomaly_detection.models import AlertSeverity, AnomalyType
from src.market_reports.generator import MarketReportService
from src.operator_assistant.assistant import OperatorAssistant
from src.operator_assistant.models import OperatorQuery
from src.operator_memory.sqlite_memory import SQLiteOperatorMemory
from src.operator_service.interfaces import InMemoryMarketContextProvider


def _create_context(symbol: str = "BTCUSDT", price: float = 65000.0, score: float = 80.0, pred: float = 0.8) -> MarketContext:
    return MarketContext(
        timestamp=pd.Timestamp("2026-09-20 12:00:00", tz="UTC"),
        symbol=symbol,
        timeframe="1h",
        current_price=price,
        market_regime="TRENDING_BULL",
        predictive_score=pred,
        quant_score=score,
        signal=SignalInfo(
            action="BUY",
            direction="LONG",
            confidence=0.85,
            reasoning="Trend continuation",
            positives=("Momentum",),
            warnings=(),
        ),
        risk=RiskMetrics(stop_loss=63000.0, take_profit=69000.0, atr=1200.0),
        technical_indicators={"rsi": 65.0, "volume": 40000.0},
        volume_profile={"poc": 64500.0, "vah": 65500.0, "val": 63500.0},
    )


@pytest.mark.anyio
async def test_copilot_multi_asset_inquiries():
    provider = InMemoryMarketContextProvider()
    btc_ctx = _create_context(symbol="BTCUSDT", price=65000.0)
    eth_ctx = _create_context(symbol="ETHUSDT", price=3400.0, score=70.0, pred=0.7)
    sol_ctx = _create_context(symbol="SOLUSDT", price=150.0, score=60.0, pred=0.6)

    provider.update_context(btc_ctx)
    provider.update_context(eth_ctx)
    provider.update_context(sol_ctx)

    assistant = OperatorAssistant(context_provider=provider)

    res_btc = await assistant.ask(OperatorQuery(query="Analyze BTC", symbol="BTCUSDT"))
    res_eth = await assistant.ask(OperatorQuery(query="What about ETH?", symbol="ETHUSDT"))
    res_sol = await assistant.ask(OperatorQuery(query="Status of SOLUSDT", symbol="SOLUSDT"))

    assert res_btc.symbol == "BTCUSDT"
    assert res_eth.symbol == "ETHUSDT"
    assert res_sol.symbol == "SOLUSDT"


@pytest.mark.anyio
async def test_memory_multi_operator_isolation():
    mem = SQLiteOperatorMemory(db_path=":memory:")

    await mem.add_entry(entry_type="note", symbol="BTCUSDT", content="Operator A Note", operator_id="op_A")
    await mem.add_entry(entry_type="note", symbol="BTCUSDT", content="Operator B Note", operator_id="op_B")

    a_notes = await mem.get_recent_entries(operator_id="op_A")
    b_notes = await mem.get_recent_entries(operator_id="op_B")

    assert len(a_notes) == 1
    assert a_notes[0].content == "Operator A Note"
    assert len(b_notes) == 1
    assert b_notes[0].content == "Operator B Note"


def test_anomaly_detector_critical_regime_shift():
    detector = MarketAnomalyDetector()
    prev = _create_context(symbol="BTCUSDT")
    curr = MarketContext(
        timestamp=pd.Timestamp("2026-09-20 13:00:00", tz="UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=61000.0,
        market_regime="HIGH_VOLATILITY_EXPANSION_BEAR",
        predictive_score=0.2,
        quant_score=30.0,
        signal=SignalInfo(action="SELL", direction="SHORT", confidence=0.9),
        risk=RiskMetrics(atr=2500.0),
        technical_indicators={"volume": 90000.0},
        volume_profile={},
    )

    alerts = detector.evaluate(curr, prev)
    assert any(a.severity == AlertSeverity.CRITICAL for a in alerts)
    assert any(a.anomaly_type == AnomalyType.VOLATILITY_EXPANSION for a in alerts)


def test_market_report_service_levels_parsing():
    svc = MarketReportService()
    ctx = _create_context()
    briefing = svc.generate_daily_briefing(ctx)

    assert "Volume POC" in briefing.important_levels
    assert briefing.important_levels["Volume POC"] == 64500.0
    assert "Stop Loss" in briefing.important_levels