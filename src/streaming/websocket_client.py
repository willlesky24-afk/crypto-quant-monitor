from __future__ import annotations

import asyncio
import json
import logging
import random
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws"


class BinanceWebSocketClient:
    """Resilient WebSocket client for Binance kline streaming.

    Features:
    - Automatic reconnection with exponential backoff and jitter.
    - Connection health monitoring (ping/pong heartbeat).
    - Callback-based dispatch for kline events, errors, and state changes.
    - Background thread management with clean shutdown.
    - Dry-run / mock simulation mode for deterministic offline operation.
    """

    def __init__(
        self,
        symbol: str,
        interval: str,
        base_url: str = DEFAULT_BINANCE_WS_BASE,
        base_backoff_sec: float = 1.0,
        max_backoff_sec: float = 60.0,
        jitter_sec: float = 0.5,
        ping_interval: float = 20.0,
        ping_timeout: float = 10.0,
        dry_run: bool = False,
    ) -> None:
        self.symbol = symbol.strip().upper()
        self.interval = interval.strip().lower()
        self.base_url = base_url
        self.base_backoff_sec = base_backoff_sec
        self.max_backoff_sec = max_backoff_sec
        self.jitter_sec = jitter_sec
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.dry_run = dry_run

        self._stream_name = f"{self.symbol.lower()}@kline_{self.interval}"
        self._url = f"{self.base_url}/{self._stream_name}"

        # State management
        self._is_running = False
        self._is_connected = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._reconnect_attempts = 0

        # Callbacks
        self._kline_callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._error_callbacks: list[Callable[[Exception], None]] = []
        self._connect_callbacks: list[Callable[[], None]] = []
        self._disconnect_callbacks: list[Callable[[], None]] = []

    @property
    def is_connected(self) -> bool:
        """Whether the WebSocket is actively connected."""
        return self._is_connected

    @property
    def is_running(self) -> bool:
        """Whether the client connection manager is running."""
        return self._is_running

    @property
    def reconnect_attempts(self) -> int:
        """Number of consecutive reconnection attempts."""
        return self._reconnect_attempts

    def on_kline(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback for incoming kline JSON payloads."""
        self._kline_callbacks.append(callback)

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register a callback for connection or parsing errors."""
        self._error_callbacks.append(callback)

    def on_connect(self, callback: Callable[[], None]) -> None:
        """Register a callback for successful connection events."""
        self._connect_callbacks.append(callback)

    def on_disconnect(self, callback: Callable[[], None]) -> None:
        """Register a callback for disconnection events."""
        self._disconnect_callbacks.append(callback)

    def simulate_message(self, data: str | dict[str, Any]) -> None:
        """Simulate an incoming WebSocket message for testing or offline replay."""
        try:
            payload = json.loads(data) if isinstance(data, str) else data
            self._dispatch_kline(payload)
        except Exception as exc:
            self._dispatch_error(exc)

    def connect(self, run_in_background: bool = True) -> None:
        """Start the WebSocket connection and reconnection loop."""
        if self._is_running:
            logger.warning(f"[{self.symbol}] Client is already running.")
            return

        self._is_running = True

        if self.dry_run:
            logger.info(f"[{self.symbol} {self.interval}] Dry-run mode: skipping actual WebSocket connection.")
            self._is_connected = True
            self._dispatch_connect()
            return

        if run_in_background:
            self._thread = threading.Thread(
                target=self._run_event_loop,
                name=f"ws-{self._stream_name}",
                daemon=True,
            )
            self._thread.start()
        else:
            self._run_event_loop()

    def disconnect(self) -> None:
        """Gracefully disconnect and stop the reconnection loop."""
        self._is_running = False
        self._is_connected = False

        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread is not None:
            if self._thread.is_alive():
                self._thread.join(timeout=2.0)
            self._thread = None


        self._dispatch_disconnect()
        logger.info(f"[{self.symbol} {self.interval}] WebSocket client stopped.")

    def _run_event_loop(self) -> None:
        """Dedicated thread target running the asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connection_supervisor())
        finally:
            self._loop.close()
            self._loop = None

    async def _connection_supervisor(self) -> None:
        """Supervisor loop managing connection attempts and exponential backoff."""
        while self._is_running:
            try:
                await self._listen_stream()
                self._reconnect_attempts = 0
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._is_connected = False
                self._dispatch_error(exc)
                if not self._is_running:
                    break

                self._reconnect_attempts += 1
                backoff = min(
                    self.max_backoff_sec,
                    self.base_backoff_sec * (2 ** (self._reconnect_attempts - 1))
                    + random.uniform(0, self.jitter_sec),
                )
                logger.warning(
                    f"[{self.symbol} {self.interval}] Disconnected ({exc}). Reconnecting in {backoff:.2f}s (attempt {self._reconnect_attempts})..."
                )
                await asyncio.sleep(backoff)

    async def _listen_stream(self) -> None:
        """Connect to WebSocket and listen for messages."""
        import websockets  # Imported here to avoid module-level overhead

        async with websockets.connect(
            self._url,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout,
        ) as ws:
            self._is_connected = True
            self._dispatch_connect()
            logger.info(f"[{self.symbol} {self.interval}] Connected to {self._url}")

            async for message in ws:
                if not self._is_running:
                    break
                try:
                    payload = json.loads(message)
                    self._dispatch_kline(payload)
                except Exception as parse_exc:
                    self._dispatch_error(parse_exc)

            self._is_connected = False
            self._dispatch_disconnect()

    def _dispatch_kline(self, data: dict[str, Any]) -> None:
        """Notify all registered kline listeners."""
        for cb in self._kline_callbacks:
            try:
                cb(data)
            except Exception as exc:
                logger.error(f"Error in on_kline callback: {exc}", exc_info=True)

    def _dispatch_error(self, exc: Exception) -> None:
        """Notify all registered error listeners."""
        for cb in self._error_callbacks:
            try:
                cb(exc)
            except Exception as e:
                logger.error(f"Error in on_error callback: {e}", exc_info=True)

    def _dispatch_connect(self) -> None:
        """Notify all registered connect listeners."""
        for cb in self._connect_callbacks:
            try:
                cb()
            except Exception as exc:
                logger.error(f"Error in on_connect callback: {exc}", exc_info=True)

    def _dispatch_disconnect(self) -> None:
        """Notify all registered disconnect listeners."""
        for cb in self._disconnect_callbacks:
            try:
                cb()
            except Exception as exc:
                logger.error(f"Error in on_disconnect callback: {exc}", exc_info=True)
