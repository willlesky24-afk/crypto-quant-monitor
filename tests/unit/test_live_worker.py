from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.streaming.live_worker import LiveMarketWorker


def _generate_mock_df(bars: int = 250) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=bars, freq="1h", tz="UTC")
    base = 50000.0
    return pd.DataFrame({
        "timestamp": dates,
        "open": base + np.arange(bars) * 10,
        "high": base + np.arange(bars) * 10 + 50,
        "low": base + np.arange(bars) * 10 - 50,
        "close": base + np.arange(bars) * 10 + 20,
        "volume": np.full(bars, 100.0),
    })


def test_live_worker_initialization():
    worker = LiveMarketWorker(
        symbols=["BTCUSDT", "ETHUSDT"],
        interval="1h",
        db_path=":memory:",
        warm_up_bars=100,
        dry_run=True,
    )

    assert worker.symbols == ["BTCUSDT", "ETHUSDT"]
    assert worker.interval == "1h"
    assert not worker.is_running
    assert len(worker.engines) == 2
    assert "BTCUSDT" in worker.engines
    assert "ETHUSDT" in worker.engines
    assert len(worker.bridges) == 2
    assert len(worker.ws_clients) == 2


def test_live_worker_bootstrap_warmup_success():
    worker = LiveMarketWorker(
        symbols=["BTCUSDT"],
        interval="1h",
        db_path=":memory:",
        warm_up_bars=150,
        dry_run=True,
    )

    mock_loader = MagicMock()
    mock_df = _generate_mock_df(bars=160)
    mock_loader.get_klines.return_value = mock_df

    res = worker.bootstrap_warmup(loader=mock_loader)
    assert res["BTCUSDT"] == 160
    assert len(worker._aggregators["BTCUSDT"].get_dataframe()) == 160



def test_live_worker_bootstrap_warmup_empty_or_failure():
    worker = LiveMarketWorker(
        symbols=["BTCUSDT"],
        interval="1h",
        db_path=":memory:",
        warm_up_bars=150,
        dry_run=True,
    )

    # Empty return
    mock_loader = MagicMock()
    mock_loader.get_klines.return_value = pd.DataFrame()
    res = worker.bootstrap_warmup(loader=mock_loader)
    assert res["BTCUSDT"] == 0

    # Exception
    mock_loader.get_klines.side_effect = RuntimeError("Network timeout")
    res_err = worker.bootstrap_warmup(loader=mock_loader)
    assert res_err["BTCUSDT"] == 0


def test_live_worker_start_stop_lifecycle():
    worker = LiveMarketWorker(
        symbols=["BTCUSDT"],
        interval="1h",
        db_path=":memory:",
        warm_up_bars=50,
        dry_run=True,
    )

    mock_loader = MagicMock()
    mock_loader.get_klines.return_value = _generate_mock_df(bars=60)

    with patch.object(worker, "bootstrap_warmup") as mock_boot:
        worker.start(bootstrap=True)
        assert worker.is_running
        mock_boot.assert_called_once()

        # Calling start again when already running logs warning and returns
        worker.start()
        assert worker.is_running

        # Stop worker
        worker.stop()
        assert not worker.is_running

        # Stopping again is idempotent
        worker.stop()
        assert not worker.is_running


def test_live_worker_stop_handles_exceptions():
    worker = LiveMarketWorker(
        symbols=["BTCUSDT"],
        interval="1h",
        db_path=":memory:",
        dry_run=True,
    )
    worker.start(bootstrap=False)
    assert worker.is_running

    # Inject exceptions into client disconnect and repo close
    with patch.object(worker._ws_clients["BTCUSDT"], "disconnect", side_effect=RuntimeError("WS error")):
        with patch.object(worker.context_provider.repository, "close", side_effect=RuntimeError("DB close error")):
            worker.stop()
            assert not worker.is_running


def test_live_worker_run_forever_signals():
    worker = LiveMarketWorker(
        symbols=["BTCUSDT"],
        interval="1h",
        db_path=":memory:",
        dry_run=True,
    )

    # Trigger stop immediately after start
    def _mock_start(*args, **kwargs):
        worker._is_running = True
        worker._stop_event.set()

    with patch.object(worker, "start", side_effect=_mock_start):
        worker.run_forever(bootstrap=False)
        assert not worker.is_running

    # Test signal handler execution
    worker_sig = LiveMarketWorker(symbols=["BTCUSDT"], interval="1h", db_path=":memory:", dry_run=True)
    with patch("signal.signal") as mock_signal:
        with patch.object(worker_sig, "start"):
            worker_sig._stop_event.set()
            worker_sig.run_forever(bootstrap=False)
            assert mock_signal.call_count >= 1
            # Retrieve registered handler and test it
            handler = mock_signal.call_args_list[0][0][1]
            with pytest.raises(SystemExit):
                handler(2, None)

