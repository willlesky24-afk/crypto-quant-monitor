from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from src.operator_cli.client import OperatorCLI
from src.operator_service.service import OperatorService
from src.streaming.live_worker import LiveMarketWorker


def _generate_synthetic_candles(bars: int = 220) -> pd.DataFrame:
    dates = pd.date_range("2026-03-01", periods=bars, freq="1h", tz="UTC")
    base = 60000.0
    return pd.DataFrame({
        "timestamp": dates,
        "open": base + np.arange(bars) * 15,
        "high": base + np.arange(bars) * 15 + 80,
        "low": base + np.arange(bars) * 15 - 80,
        "close": base + np.arange(bars) * 15 + 40,
        "volume": np.random.uniform(500.0, 1500.0, size=bars),
    })


def test_phase10_full_e2e_live_deployment_pipeline(tmp_path: Path):
    """End-to-end integration test of Phase 10:

    LiveMarketWorker -> CandleAggregator -> LiveExecutionEngine -> LiveAIContextBridge
    -> SQLite Persistent Storage -> OperatorService -> OperatorAssistant -> OperatorCLI.
    """
    db_file = tmp_path / "e2e_market_contexts.db"

    # 1. Initialize LiveMarketWorker
    worker = LiveMarketWorker(
        symbols=["BTCUSDT"],
        interval="1h",
        db_path=db_file,
        warm_up_bars=200,
        dry_run=True,
    )

    # 2. Bootstrap warm-up bars
    mock_loader = MagicMock()
    mock_loader.get_klines.return_value = _generate_synthetic_candles(bars=210)
    boot_res = worker.bootstrap_warmup(loader=mock_loader)
    assert boot_res["BTCUSDT"] == 210

    worker.start(bootstrap=False)
    assert worker.is_running

    # 3. Simulate an incoming closed candle T kline event
    kline_payload = {
        "e": "kline",
        "E": 1772456400000,
        "s": "BTCUSDT",
        "k": {
            "t": 1773079200000,
            "T": 1773082799999,
            "s": "BTCUSDT",
            "i": "1h",
            "f": 100,
            "L": 200,
            "o": "63200.00",
            "c": "63450.00",
            "h": "63550.00",
            "l": "63150.00",
            "v": "1250.50",
            "n": 500,
            "x": True,  # Candle closed
            "q": "79312500.00",
            "V": "600.0",
            "Q": "38000000.0",
            "B": "0",
        },
    }

    # Ingest payload into client/aggregator
    client = worker.ws_clients["BTCUSDT"]
    client.simulate_message(kline_payload)

    # 4. Verify LiveExecutionEngine fired and created a SignalEvent
    engine = worker.engines["BTCUSDT"]
    assert len(engine.signal_history) >= 1
    latest_sig = engine.last_signal
    assert latest_sig is not None
    assert latest_sig.symbol == "BTCUSDT"
    assert latest_sig.timeframe == "1h"
    assert latest_sig.price == 63450.0

    # 5. Verify LiveAIContextBridge processed and persisted context into SQLite
    bridge = worker.bridges["BTCUSDT"]
    assert bridge.processed_count >= 1
    assert bridge.last_context is not None

    # Read directly from SQLite repository
    repo = worker.context_provider.repository
    saved_context = repo.get_latest_context("BTCUSDT", "1h")
    assert saved_context is not None
    assert saved_context.current_price == 63450.0
    assert saved_context.symbol == "BTCUSDT"

    # 6. Verify OperatorService queries
    service = OperatorService(context_provider=worker.context_provider)
    import asyncio
    health = asyncio.run(service.health_check())
    assert health.status.upper() == "HEALTHY"
    assert "BTCUSDT" in health.available_symbols

    # 7. Verify OperatorCLI can inspect status and query Copilot
    cli = OperatorCLI(db_path=db_file, provider_type="mock")

    # Status check
    status = cli.get_status("BTCUSDT", "1h")
    assert status["status"] == "ACTIVE"
    assert status["price"] == 63450.0
    formatted_status = cli.format_status_output(status)
    assert "MARKET STATUS: BTCUSDT [1H]" in formatted_status
    assert "$63,450.00" in formatted_status

    # Ask Copilot
    copilot_reply = cli.ask("What is the current regime and risk level?", "BTCUSDT", "1h")
    assert "COPILOT RESPONSE [BTCUSDT 1h]" in copilot_reply
    assert "DISCLAIMER" in copilot_reply

    # Generate Report
    report_output = cli.get_report("BTCUSDT", "1h")
    assert "BTCUSDT" in report_output
    assert "EXECUTIVE SUMMARY" in report_output
    assert "DECISION SUPPORT CONCLUSION" in report_output

    # 8. Clean shutdown
    worker.stop()
    assert not worker.is_running
