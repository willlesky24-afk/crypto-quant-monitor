from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any

from src.data_loader import BinanceDataLoader
from src.notifications.dispatcher import NotificationDispatcher
from src.operator_service.live_bridge import LiveAIContextBridge
from src.operator_service.storage.sqlite_provider import SQLiteMarketContextProvider
from src.streaming.candle_aggregator import CandleAggregator, KlineEvent
from src.streaming.live_engine import LiveExecutionEngine
from src.streaming.websocket_client import BinanceWebSocketClient

logger = logging.getLogger(__name__)


class LiveMarketWorker:
    """Production live worker service orchestrating real-time market data streaming,

    quantitative pipeline execution, AI context building, and persistent state management.

    Architecture Flow:
    Binance WebSocket (kline)
          │
          ▼
    CandleAggregator (closed candle T buffer)
          │
          ▼
    LiveExecutionEngine (QuantScore + Regime + PredictiveScore + DecisionEngine)
          │
          ▼
    LiveAIContextBridge (Transforms SignalEvent -> MarketContext)
          │
          ▼
    SQLiteMarketContextProvider (Persistent market_contexts.db)
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        interval: str = "1h",
        db_path: str | Path | None = None,
        warm_up_bars: int = 200,
        dispatcher: NotificationDispatcher | None = None,
        dry_run: bool = False,
    ) -> None:
        self.symbols = [s.strip().upper() for s in (symbols or ["BTCUSDT"])]
        self.interval = interval.strip().lower()
        self.db_path = Path(db_path or os.getenv("DATABASE_PATH", "data/market_contexts.db"))
        self.warm_up_bars = warm_up_bars
        self.dispatcher = dispatcher
        self.dry_run = dry_run

        # Persistent context layer
        self.context_provider = SQLiteMarketContextProvider(db_path=self.db_path)

        # Worker state per symbol
        self._aggregators: dict[str, CandleAggregator] = {}
        self._engines: dict[str, LiveExecutionEngine] = {}
        self._bridges: dict[str, LiveAIContextBridge] = {}
        self._ws_clients: dict[str, BinanceWebSocketClient] = {}

        self._is_running = False
        self._stop_event = threading.Event()
        self._setup_pipelines()

    @property
    def is_running(self) -> bool:
        """Whether the worker is actively running."""
        return self._is_running

    @property
    def engines(self) -> dict[str, LiveExecutionEngine]:
        """Map of symbol to LiveExecutionEngine instance."""
        return self._engines

    @property
    def bridges(self) -> dict[str, LiveAIContextBridge]:
        """Map of symbol to LiveAIContextBridge instance."""
        return self._bridges

    @property
    def ws_clients(self) -> dict[str, BinanceWebSocketClient]:
        """Map of symbol to BinanceWebSocketClient instance."""
        return self._ws_clients

    def _setup_pipelines(self) -> None:
        """Initialize pipeline components for each tracked symbol."""
        for symbol in self.symbols:
            aggregator = CandleAggregator(
                symbol=symbol,
                interval=self.interval,
                max_bars=max(self.warm_up_bars + 50, 300),
            )
            engine = LiveExecutionEngine(
                symbol=symbol,
                interval=self.interval,
                dispatcher=self.dispatcher,
                warm_up_bars=self.warm_up_bars,
            )
            bridge = LiveAIContextBridge(context_provider=self.context_provider)

            # Chain components together
            engine.attach_aggregator(aggregator)
            bridge.attach_to_live_engine(engine)

            ws_client = BinanceWebSocketClient(
                symbol=symbol,
                interval=self.interval,
                dry_run=self.dry_run,
            )

            def _handle_kline(payload: dict[str, Any], agg: CandleAggregator = aggregator) -> None:
                agg.process_kline(KlineEvent.from_binance_payload(payload))

            ws_client.on_kline(_handle_kline)

            self._aggregators[symbol] = aggregator
            self._engines[symbol] = engine
            self._bridges[symbol] = bridge
            self._ws_clients[symbol] = ws_client

    def bootstrap_warmup(self, loader: BinanceDataLoader | None = None) -> dict[str, int]:
        """Pre-fetch closed historical candles to warm up technical indicators from bar 0."""
        results: dict[str, int] = {}
        data_loader = loader or BinanceDataLoader()

        for symbol in self.symbols:
            logger.info(f"[{symbol} {self.interval}] Fetching {self.warm_up_bars} warm-up bars...")
            try:
                df = data_loader.get_klines(
                    symbol=symbol,
                    interval=self.interval,
                    limit=self.warm_up_bars + 10,
                    include_open_candle=False,
                )
                if df is not None and not df.empty:
                    self._aggregators[symbol].seed(df)
                    loaded = len(self._aggregators[symbol].get_dataframe())
                    results[symbol] = loaded
                    logger.info(f"[{symbol} {self.interval}] Successfully bootstrapped {loaded} warm-up bars.")
                else:
                    results[symbol] = 0
                    logger.warning(f"[{symbol} {self.interval}] No warm-up bars received from data loader.")

            except Exception as exc:
                results[symbol] = 0
                logger.error(f"[{symbol} {self.interval}] Failed to bootstrap warm-up bars: {exc}")

        return results

    def start(self, bootstrap: bool = True) -> None:
        """Start the worker daemon."""
        if self._is_running:
            logger.warning("LiveMarketWorker is already running.")
            return

        logger.info(f"Starting LiveMarketWorker for symbols={self.symbols} interval={self.interval} db={self.db_path}...")
        if bootstrap:
            self.bootstrap_warmup()

        for symbol, client in self._ws_clients.items():
            logger.info(f"[{symbol}] Starting WebSocket connection...")
            client.connect()

        self._is_running = True
        self._stop_event.clear()
        logger.info("LiveMarketWorker successfully started.")

    def stop(self) -> None:
        """Stop the worker daemon and disconnect all stream clients cleanly."""
        if not self._is_running:
            return

        logger.info("Stopping LiveMarketWorker...")
        for symbol, client in self._ws_clients.items():
            try:
                client.disconnect()
                logger.info(f"[{symbol}] WebSocket disconnected.")
            except Exception as exc:
                logger.error(f"[{symbol}] Error disconnecting WebSocket: {exc}")

        self._is_running = False
        self._stop_event.set()

        try:
            self.context_provider.repository.close()
        except Exception as exc:
            logger.error(f"Error closing context repository: {exc}")

        logger.info("LiveMarketWorker stopped cleanly.")

    def run_forever(self, bootstrap: bool = True) -> None:
        """Run the worker in a blocking loop until a termination signal is received."""
        self.start(bootstrap=bootstrap)

        def _signal_handler(sig: int, _frame: Any) -> None:
            logger.info(f"Received termination signal ({sig}). Initiating graceful shutdown...")
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, _signal_handler)
            signal.signal(signal.SIGTERM, _signal_handler)
        except (ValueError, AttributeError):
            # Not supported in some environments (e.g. non-main thread)
            pass

        try:
            while not self._stop_event.is_set():
                time.sleep(0.1)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self.stop()

