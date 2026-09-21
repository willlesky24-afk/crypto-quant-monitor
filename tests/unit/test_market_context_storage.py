from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo
from src.notifications.models import SignalEvent
from src.operator_service.live_bridge import LiveAIContextBridge
from src.operator_service.service import OperatorService
from src.operator_service.storage.models import (
    MarketContextRecord,
    market_context_from_dict,
)
from src.operator_service.storage.sqlite_provider import (
    SQLiteMarketContextProvider,
    SQLiteMarketContextRepository,
)


def make_test_context(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    timestamp_str: str = "2026-03-30 12:00:00",
    price: float = 65000.0,
    action: str = "BUY",
    direction: str = "LONG",
    quant_score: float = 85.0,
    predictive_score: float = 0.75,
) -> MarketContext:
    return MarketContext(
        timestamp=pd.Timestamp(timestamp_str),
        symbol=symbol,
        timeframe=timeframe,
        current_price=price,
        market_regime="BULL_TREND",
        predictive_score=predictive_score,
        quant_score=quant_score,
        signal=SignalInfo(
            action=action,
            direction=direction,
            confidence=0.85,
            reasoning="Strong multi-factor alignment.",
            positives=("RSI oversold rebound", "Volume surge"),
            warnings=("Approaching major resistance",),
        ),
        risk=RiskMetrics(
            stop_loss=63500.0,
            take_profit=68000.0,
            risk_ratio=2.0,
            risk_category="LOW_RISK",
            atr=500.0,
            tp_multiplier=3.0,
            sl_multiplier=1.5,
        ),
        technical_indicators={"rsi": 32.5, "adx": 28.0},
        volume_profile={"poc": 64800.0, "vah": 65500.0, "val": 64200.0},
        metadata={"cycle_id": "test-1"},
    )


class TestStorageModels:
    def test_market_context_record_dataclass(self):
        rec = MarketContextRecord(
            id=1,
            symbol="BTCUSDT",
            timeframe="1h",
            candle_timestamp="2026-03-30 12:00:00",
            price=65000.0,
            regime="BULL_TREND",
            action="BUY",
            direction="LONG",
            quant_score=85.0,
            predictive_score=0.75,
            payload_json="{}",
            created_at="2026-03-30T12:00:00Z",
        )
        assert rec.id == 1
        assert rec.symbol == "BTCUSDT"
        assert rec.price == 65000.0

    def test_serialization_and_reconstruction(self):
        ctx = make_test_context()
        d = ctx.to_dict()
        reconstructed = market_context_from_dict(d)

        assert reconstructed.symbol == ctx.symbol
        assert reconstructed.timeframe == ctx.timeframe
        assert reconstructed.current_price == ctx.current_price
        assert reconstructed.timestamp == ctx.timestamp
        assert reconstructed.signal.action == "BUY"
        assert reconstructed.signal.positives == ("RSI oversold rebound", "Volume surge")
        assert reconstructed.signal.warnings == ("Approaching major resistance",)
        assert reconstructed.risk.stop_loss == 63500.0
        assert reconstructed.risk.take_profit == 68000.0
        assert reconstructed.technical_indicators["rsi"] == 32.5

    def test_deserialization_from_json_string(self):
        ctx = make_test_context()
        json_str = json.dumps(ctx.to_dict())
        reconstructed = market_context_from_dict(json_str)
        assert reconstructed.symbol == "BTCUSDT"

    def test_deserialization_invalid_input(self):
        with pytest.raises(ValueError, match="Expected dict or JSON string"):
            market_context_from_dict(12345)  # type: ignore

        with pytest.raises(ValueError, match="Failed to parse JSON payload"):
            market_context_from_dict("invalid-json{")

        with pytest.raises(ValueError, match="Invalid MarketContext payload structure"):
            market_context_from_dict({"symbol": "BTC"})  # missing required fields


class TestSQLiteMarketContextRepository:
    def test_in_memory_creation_and_schema(self):
        repo = SQLiteMarketContextRepository(":memory:")
        assert repo.count_records() == 0
        repo.close()

    def test_wal_mode_and_file_creation(self, tmp_path: Path):
        db_file = tmp_path / "test_contexts.db"
        repo = SQLiteMarketContextRepository(db_file)

        cursor = repo._conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        row = cursor.fetchone()
        assert row[0].lower() == "wal"

        repo.close()
        assert db_file.exists()

    def test_save_and_get_latest_context(self):
        repo = SQLiteMarketContextRepository(":memory:")
        ctx1 = make_test_context(timestamp_str="2026-03-30 10:00:00", price=64000.0)
        ctx2 = make_test_context(timestamp_str="2026-03-30 11:00:00", price=65000.0)

        repo.save_context(ctx1)
        repo.save_context(ctx2)

        latest = repo.get_latest_context("BTCUSDT", "1h")
        assert latest is not None
        assert latest.current_price == 65000.0
        assert str(latest.timestamp) == "2026-03-30 11:00:00"
        repo.close()

    def test_upsert_replaces_duplicate_timestamp(self):
        repo = SQLiteMarketContextRepository(":memory:")
        ctx1 = make_test_context(timestamp_str="2026-03-30 12:00:00", price=60000.0, action="WAIT")
        ctx2 = make_test_context(timestamp_str="2026-03-30 12:00:00", price=61000.0, action="BUY")

        repo.save_context(ctx1)
        assert repo.count_records() == 1

        repo.save_context(ctx2)
        assert repo.count_records() == 1

        latest = repo.get_latest_context("BTCUSDT", "1h")
        assert latest is not None
        assert latest.current_price == 61000.0
        assert latest.signal.action == "BUY"
        repo.close()

    def test_get_context_history(self):
        repo = SQLiteMarketContextRepository(":memory:")
        for hour in range(10, 15):
            ctx = make_test_context(
                timestamp_str=f"2026-03-30 {hour:02d}:00:00",
                price=60000.0 + hour * 100,
            )
            repo.save_context(ctx)

        history = repo.get_context_history("BTCUSDT", "1h", limit=3)
        assert len(history) == 3
        assert str(history[0].timestamp) == "2026-03-30 14:00:00"
        assert str(history[1].timestamp) == "2026-03-30 13:00:00"
        assert str(history[2].timestamp) == "2026-03-30 12:00:00"
        repo.close()

    def test_available_symbols_and_timeframes(self):
        repo = SQLiteMarketContextRepository(":memory:")
        repo.save_context(make_test_context(symbol="BTCUSDT", timeframe="1h"))
        repo.save_context(make_test_context(symbol="BTCUSDT", timeframe="4h"))
        repo.save_context(make_test_context(symbol="ETHUSDT", timeframe="1h"))

        symbols = repo.get_available_symbols()
        assert symbols == ["BTCUSDT", "ETHUSDT"]

        btc_tf = repo.get_available_timeframes("BTCUSDT")
        assert btc_tf == ["1h", "4h"]

        eth_tf = repo.get_available_timeframes("ETHUSDT")
        assert eth_tf == ["1h"]

        assert repo.count_records() == 3
        assert repo.count_records(symbol="BTCUSDT") == 2
        assert repo.count_records(timeframe="1h") == 2
        assert repo.count_records(symbol="BTCUSDT", timeframe="1h") == 1
        repo.close()

    def test_get_latest_not_found(self):
        repo = SQLiteMarketContextRepository(":memory:")
        assert repo.get_latest_context("NONEXISTENT", "1h") is None
        assert repo.get_context_history("NONEXISTENT", "1h") == []
        repo.close()

    def test_operations_after_close_raise(self):
        repo = SQLiteMarketContextRepository(":memory:")
        repo.close()
        ctx = make_test_context()

        with pytest.raises(RuntimeError, match="closed repository"):
            repo.save_context(ctx)

        with pytest.raises(RuntimeError, match="closed repository"):
            repo.get_latest_context("BTCUSDT", "1h")

        with pytest.raises(RuntimeError, match="closed repository"):
            repo.get_context_history("BTCUSDT", "1h")

        with pytest.raises(RuntimeError, match="closed repository"):
            repo.get_available_symbols()

        with pytest.raises(RuntimeError, match="closed repository"):
            repo.get_available_timeframes("BTCUSDT")

        with pytest.raises(RuntimeError, match="closed repository"):
            repo.count_records()

    def test_corrupted_payload_handling(self):
        repo = SQLiteMarketContextRepository(":memory:")
        cursor = repo._conn.cursor()
        cursor.execute(
            """
            INSERT INTO market_contexts (
                symbol, timeframe, candle_timestamp, price, regime,
                action, direction, quant_score, predictive_score,
                payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("CORRUPT", "1h", "2026-03-30 12:00:00", 100.0, "UNKNOWN", "WAIT", "NEUTRAL", 50.0, 0.5, "{broken_json", "2026-03-30T12:00:00Z"),
        )
        assert repo.get_latest_context("CORRUPT", "1h") is None
        assert repo.get_context_history("CORRUPT", "1h") == []
        repo.close()


class TestSQLiteMarketContextProvider:
    @pytest.mark.anyio
    async def test_provider_conformance_and_operations(self):
        provider = SQLiteMarketContextProvider()
        ctx = make_test_context(symbol="SOLUSDT", timeframe="15m", price=180.0)

        provider.update_context(ctx)

        retrieved = await provider.get_latest_context("SOLUSDT", "15m")
        assert retrieved is not None
        assert retrieved.symbol == "SOLUSDT"
        assert retrieved.current_price == 180.0

        symbols = await provider.get_available_symbols()
        assert symbols == ["SOLUSDT"]

        timeframes = await provider.get_available_timeframes("SOLUSDT")
        assert timeframes == ["15m"]

        history = await provider.get_context_history("SOLUSDT", "15m", limit=10)
        assert len(history) == 1
        assert history[0].symbol == "SOLUSDT"

        provider.close()

    @pytest.mark.anyio
    async def test_persistence_across_reconnect(self, tmp_path: Path):
        db_file = tmp_path / "persist_test.db"

        provider1 = SQLiteMarketContextProvider(db_path=db_file)
        ctx = make_test_context(symbol="ETHUSDT", timeframe="1h", price=3500.0)
        provider1.update_context(ctx)
        provider1.close()

        provider2 = SQLiteMarketContextProvider(db_path=db_file)
        retrieved = await provider2.get_latest_context("ETHUSDT", "1h")
        assert retrieved is not None
        assert retrieved.symbol == "ETHUSDT"
        assert retrieved.current_price == 3500.0
        provider2.close()

    @pytest.mark.anyio
    async def test_integration_with_operator_service(self):
        provider = SQLiteMarketContextProvider()
        service = OperatorService(context_provider=provider)

        ctx = make_test_context(symbol="BTCUSDT", timeframe="1h", price=67000.0)
        provider.update_context(ctx)

        from src.operator_service.models import (
            MarketSummaryRequest,
            SignalExplanationRequest,
        )

        exp_res = await service.get_signal_explanation(
            SignalExplanationRequest(symbol="BTCUSDT", timeframe="1h")
        )
        assert exp_res.symbol == "BTCUSDT"
        assert exp_res.explanation.confidence == 0.85

        sum_res = await service.get_market_summary(
            MarketSummaryRequest(symbol="BTCUSDT", timeframe="1h")
        )
        assert sum_res.symbol == "BTCUSDT"
        assert "BTCUSDT" in sum_res.summary.title

        provider.close()

    def test_integration_with_live_ai_context_bridge(self):
        provider = SQLiteMarketContextProvider()
        bridge = LiveAIContextBridge(context_provider=provider)

        signal_event = SignalEvent(
            timestamp=pd.Timestamp("2026-03-30 14:00:00"),
            symbol="BTCUSDT",
            timeframe="1h",
            action="BUY",
            direction="LONG",
            price=66200.0,
            confidence=0.88,
            quant_score=86.5,
            predictive_score=0.78,
            regime="BULL_TREND",
            stop_loss=64800.0,
            take_profit=69000.0,
            reasoning="Multi-engine alignment.",
            metadata={"positives": ["Trend aligned"], "warnings": []},
        )

        ctx = bridge.on_signal_event(signal_event)
        assert ctx.symbol == "BTCUSDT"

        assert provider.repository.count_records() == 1
        stored = provider.repository.get_latest_context("BTCUSDT", "1h")
        assert stored is not None
        assert stored.current_price == 66200.0
        assert stored.signal.action == "BUY"

        provider.close()
