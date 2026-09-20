from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from src.streaming.websocket_client import BinanceWebSocketClient


def test_websocket_client_init_and_callbacks():
    client = BinanceWebSocketClient(symbol="ETHUSDT", interval="4h", dry_run=True)
    assert client.symbol == "ETHUSDT"
    assert client.interval == "4h"
    assert client.is_connected is False
    assert client.is_running is False
    assert client.reconnect_attempts == 0

    kline_calls = []
    error_calls = []
    connect_calls = []
    disconnect_calls = []

    client.on_kline(lambda k: kline_calls.append(k))
    client.on_error(lambda e: error_calls.append(e))
    client.on_connect(lambda: connect_calls.append(True))
    client.on_disconnect(lambda: disconnect_calls.append(True))

    # Test connect in dry_run mode
    client.connect()
    assert client.is_connected is True
    assert client.is_running is True
    assert len(connect_calls) == 1

    # Calling connect again when already running
    client.connect()
    assert len(connect_calls) == 1

    # Test simulate_message with valid payload
    raw_payload = {"e": "kline", "s": "ETHUSDT", "k": {"c": "3500.0"}}
    client.simulate_message(raw_payload)
    assert len(kline_calls) == 1
    assert kline_calls[0]["s"] == "ETHUSDT"

    # Test simulate_message with JSON string
    client.simulate_message(json.dumps(raw_payload))
    assert len(kline_calls) == 2

    # Test simulate_message with invalid JSON triggers error callback
    client.simulate_message("{invalid_json: true")
    assert len(error_calls) == 1

    # Test disconnect in dry_run mode
    client.disconnect()
    assert client.is_connected is False
    assert client.is_running is False
    assert len(disconnect_calls) == 1


def test_websocket_client_callback_exception_isolation():
    client = BinanceWebSocketClient(symbol="BTCUSDT", interval="1h", dry_run=True)

    def crashing_callback(data):
        raise RuntimeError("Exploding kline callback!")

    surviving_calls = []

    client.on_kline(crashing_callback)
    client.on_kline(lambda d: surviving_calls.append(d))

    # Should not raise exception and should execute subsequent callback
    client.simulate_message({"e": "kline", "s": "BTCUSDT"})
    assert len(surviving_calls) == 1


def test_websocket_client_listen_stream_with_mock():
    client = BinanceWebSocketClient(
        symbol="BTCUSDT",
        interval="1h",
        base_backoff_sec=0.01,
        max_backoff_sec=0.05,
        jitter_sec=0.0,
        dry_run=False,
    )

    received_klines = []
    client.on_kline(lambda k: received_klines.append(k))

    mock_messages = [
        json.dumps({"e": "kline", "s": "BTCUSDT", "k": {"c": "65000.0", "x": False}}),
        json.dumps({"e": "kline", "s": "BTCUSDT", "k": {"c": "65100.0", "x": True}}),
    ]

    class AsyncMockWebSocket:
        def __init__(self, messages):
            self.messages = messages

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        def __aiter__(self):
            return self._iter()

        async def _iter(self):
            for msg in self.messages:
                yield msg

    client._is_running = True

    async def _test_coro():
        with patch("websockets.connect", return_value=AsyncMockWebSocket(mock_messages)):
            await client._listen_stream()

    asyncio.run(_test_coro())

    assert len(received_klines) == 2
    assert received_klines[0]["k"]["c"] == "65000.0"
    assert received_klines[1]["k"]["x"] is True


def test_websocket_client_listen_stream_parse_error():
    client = BinanceWebSocketClient(symbol="BTCUSDT", interval="1h", dry_run=False)
    errors = []
    client.on_error(lambda e: errors.append(e))

    class AsyncMockBadWebSocket:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        def __aiter__(self):
            return self._iter()

        async def _iter(self):
            yield "not-valid-json{"

    client._is_running = True

    async def _test_coro():
        with patch("websockets.connect", return_value=AsyncMockBadWebSocket()):
            await client._listen_stream()

    asyncio.run(_test_coro())
    assert len(errors) == 1


def test_websocket_client_connection_supervisor_retry_and_cancellation():
    client = BinanceWebSocketClient(
        symbol="BTCUSDT",
        interval="1h",
        base_backoff_sec=0.001,
        max_backoff_sec=0.002,
        jitter_sec=0.0,
        dry_run=False,
    )
    client._is_running = True

    attempts = 0

    async def mock_listen():
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise ConnectionResetError("Simulated network drop")
        client._is_running = False

    client._listen_stream = mock_listen  # type: ignore

    async def _run_supervisor():
        # Stop after 2 attempts
        asyncio.create_task(_delayed_stop(client))
        await client._connection_supervisor()

    async def _delayed_stop(c):
        while attempts < 2:
            await asyncio.sleep(0.001)
        c._is_running = False

    asyncio.run(_run_supervisor())
    assert attempts == 2
    assert client.reconnect_attempts >= 1


def test_websocket_client_run_event_loop_and_thread_lifecycle():
    client = BinanceWebSocketClient(symbol="BTCUSDT", interval="1h", dry_run=False)

    async def mock_supervisor():
        # Immediate return
        pass

    client._connection_supervisor = mock_supervisor  # type: ignore
    client._run_event_loop()
    assert client._loop is None


def test_websocket_client_background_thread_start_and_disconnect():
    client = BinanceWebSocketClient(symbol="BTCUSDT", interval="1h", dry_run=False)

    with patch.object(client, "_run_event_loop"):
        client.connect(run_in_background=True)
        assert client.is_running is True
        assert client._thread is not None
        client.disconnect()
        assert client.is_running is False
        assert client._thread is None



def test_websocket_client_callback_errors_in_connect_disconnect_error():
    client = BinanceWebSocketClient(symbol="BTCUSDT", interval="1h", dry_run=True)

    client.on_connect(lambda: (_ for _ in ()).throw(RuntimeError("Connect fail")))
    client.on_disconnect(lambda: (_ for _ in ()).throw(RuntimeError("Disconnect fail")))
    client.on_error(lambda e: (_ for _ in ()).throw(RuntimeError("Error fail")))

    # None of these should raise uncaught exceptions
    client._dispatch_connect()
    client._dispatch_disconnect()
    client._dispatch_error(ValueError("Original error"))


