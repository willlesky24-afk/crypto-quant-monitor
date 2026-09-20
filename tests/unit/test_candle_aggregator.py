from __future__ import annotations

import pandas as pd
import pytest

from src.streaming.candle_aggregator import CandleAggregator, KlineEvent


def _make_binance_kline_payload(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    open_time: int = 1672531200000,
    close_price: float = 65000.0,
    is_closed: bool = False,
) -> dict:
    return {
        "e": "kline",
        "E": open_time + 1000,
        "s": symbol,
        "k": {
            "t": open_time,
            "T": open_time + 3599999,
            "s": symbol,
            "i": interval,
            "o": "64500.0",
            "c": str(close_price),
            "h": "65200.0",
            "l": "64400.0",
            "v": "150.5",
            "x": is_closed,
        },
    }


def test_kline_event_parsing_and_dict():
    raw = _make_binance_kline_payload(is_closed=True)
    event = KlineEvent.from_binance_payload(raw)

    assert event.symbol == "BTCUSDT"
    assert event.interval == "1h"
    assert event.open == 64500.0
    assert event.close == 65000.0
    assert event.high == 65200.0
    assert event.low == 64400.0
    assert event.volume == 150.5
    assert event.is_closed is True
    assert isinstance(event.start_time, pd.Timestamp)

    d = event.to_dict()
    assert d["close"] == 65000.0
    assert d["timestamp"] == event.start_time


def test_candle_aggregator_initial_state_and_seeding():
    agg = CandleAggregator(symbol="BTCUSDT", interval="1h", max_bars=10)
    assert agg.symbol == "BTCUSDT"
    assert agg.interval == "1h"
    assert agg.current_candle is None
    assert agg.closed_count == 0
    assert agg.is_warmed_up(min_bars=5) is False

    # 1. Seeding empty df
    agg.seed(pd.DataFrame())
    assert len(agg.get_dataframe()) == 0

    # 2. Seeding with missing columns raises ValueError
    bad_df = pd.DataFrame({"timestamp": [pd.Timestamp.now("UTC")], "close": [65000.0]})
    with pytest.raises(ValueError, match="Missing required columns"):
        agg.seed(bad_df)

    # 3. Valid seeding exceeding max_bars (15 bars into max_bars=10)
    dates = pd.date_range("2026-01-01", periods=15, freq="1h", tz="UTC")
    seed_df = pd.DataFrame({
        "timestamp": dates,
        "open": 60000.0,
        "high": 61000.0,
        "low": 59000.0,
        "close": 60500.0,
        "volume": 100.0,
    })
    agg.seed(seed_df)

    df_buffer = agg.get_dataframe()
    assert len(df_buffer) == 10  # Truncated to max_bars
    assert agg.is_warmed_up(min_bars=10) is True
    assert df_buffer.iloc[-1]["timestamp"] == dates[-1]


def test_candle_aggregator_process_intra_bar_and_closed_kline():
    closed_events = []
    updated_events = []

    def on_close(df, event):
        closed_events.append((len(df), event))

    def on_update(event):
        updated_events.append(event)

    agg = CandleAggregator(
        symbol="BTCUSDT",
        interval="1h",
        max_bars=5,
        on_candle_close=on_close,
        on_candle_update=on_update,
    )

    t0 = 1672531200000  # Bar 1

    # 1. Intra-bar update (is_closed=False)
    k1_open = KlineEvent.from_binance_payload(_make_binance_kline_payload(open_time=t0, close_price=65100.0, is_closed=False))
    res1 = agg.process_kline(k1_open)

    assert res1 is False
    assert agg.closed_count == 0
    assert len(agg.get_dataframe()) == 0
    assert len(updated_events) == 1
    assert len(closed_events) == 0
    assert agg.current_candle == k1_open

    # 2. Bar close (is_closed=True)
    k1_close = KlineEvent.from_binance_payload(_make_binance_kline_payload(open_time=t0, close_price=65200.0, is_closed=True))
    res2 = agg.process_kline(k1_close)

    assert res2 is True
    assert agg.closed_count == 1
    assert len(agg.get_dataframe()) == 1
    assert len(closed_events) == 1
    assert closed_events[0][0] == 1
    assert closed_events[0][1].close == 65200.0

    # 3. Bar 2 close
    t1 = t0 + 3600000
    k2_close = KlineEvent.from_binance_payload(_make_binance_kline_payload(open_time=t1, close_price=65500.0, is_closed=True))
    agg.process_kline(k2_close)
    assert agg.closed_count == 2
    assert len(agg.get_dataframe()) == 2


def test_candle_aggregator_symbol_mismatch_and_callback_error_handling():
    def exploding_callback(df, event):
        raise RuntimeError("Callback explosion!")

    agg = CandleAggregator(
        symbol="BTCUSDT",
        interval="1h",
        on_candle_close=exploding_callback,
        on_candle_update=lambda e: (_ for _ in ()).throw(ValueError("Update explosion!")),
    )

    # Mismatched symbol ignored
    mismatched = KlineEvent.from_binance_payload(_make_binance_kline_payload(symbol="ETHUSDT", is_closed=True))
    assert agg.process_kline(mismatched) is False
    assert agg.closed_count == 0

    # Mismatched interval ignored
    mismatched_inv = KlineEvent.from_binance_payload(_make_binance_kline_payload(interval="15m", is_closed=True))
    assert agg.process_kline(mismatched_inv) is False

    # Matching symbol with exploding callbacks does not crash the aggregator
    matching = KlineEvent.from_binance_payload(_make_binance_kline_payload(is_closed=True))
    assert agg.process_kline(matching) is True
    assert agg.closed_count == 1


def test_candle_aggregator_clear():
    agg = CandleAggregator(symbol="BTCUSDT", interval="1h")
    event = KlineEvent.from_binance_payload(_make_binance_kline_payload(is_closed=True))
    agg.process_kline(event)
    assert agg.closed_count == 1
    assert len(agg.get_dataframe()) == 1

    agg.clear()
    assert agg.closed_count == 0
    assert len(agg.get_dataframe()) == 0
    assert agg.current_candle is None


def test_candle_aggregator_seeding_string_timestamps_and_row_replacement():
    agg = CandleAggregator(symbol="BTCUSDT", interval="1h", max_bars=3)

    # 1. Seed with string timestamps (covers line 116)
    seed_df = pd.DataFrame({
        "timestamp": ["2026-01-01 00:00:00", "2026-01-01 01:00:00"],
        "open": [60000.0, 61000.0],
        "high": [60500.0, 61500.0],
        "low": [59500.0, 60500.0],
        "close": [60200.0, 61200.0],
        "volume": [10.0, 20.0],
    })
    agg.seed(seed_df)
    assert len(agg.get_dataframe()) == 2
    assert pd.api.types.is_datetime64_any_dtype(agg.get_dataframe()["timestamp"])

    # 2. Add closed bar with existing timestamp to test replacement (covers line 155-156)
    t1_ms = int(pd.Timestamp("2026-01-01 01:00:00", tz="UTC").timestamp() * 1000)
    replaced_kline = KlineEvent.from_binance_payload(
        _make_binance_kline_payload(open_time=t1_ms, close_price=61999.0, is_closed=True)
    )
    agg.process_kline(replaced_kline)
    df = agg.get_dataframe()
    assert len(df) == 2
    assert df.iloc[-1]["close"] == 61999.0

    # 3. Add closed bars exceeding max_bars to test rolling window truncation (covers line 162)
    t2_ms = t1_ms + 3600000
    t3_ms = t2_ms + 3600000
    agg.process_kline(KlineEvent.from_binance_payload(_make_binance_kline_payload(open_time=t2_ms, is_closed=True)))
    agg.process_kline(KlineEvent.from_binance_payload(_make_binance_kline_payload(open_time=t3_ms, is_closed=True)))
    df_trunc = agg.get_dataframe()
    assert len(df_trunc) == 3

