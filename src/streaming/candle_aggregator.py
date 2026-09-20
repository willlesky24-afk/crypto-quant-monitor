from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KlineEvent:
    """Represents a standardized kline update event from a streaming market feed."""

    symbol: str
    interval: str
    start_time: pd.Timestamp
    close_time: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool

    @classmethod
    def from_binance_payload(cls, data: dict[str, Any]) -> KlineEvent:
        """Parse raw Binance WebSocket kline event payload."""
        k = data.get("k", data)
        sym = str(k.get("s", data.get("s", ""))).strip().upper()
        inv = str(k.get("i", "1h")).strip().lower()

        t_val = k.get("t", 0)
        t_close = k.get("T", t_val)

        start_ts = pd.to_datetime(t_val, unit="ms", utc=True) if isinstance(t_val, (int, float)) else pd.to_datetime(t_val)
        close_ts = pd.to_datetime(t_close, unit="ms", utc=True) if isinstance(t_close, (int, float)) else pd.to_datetime(t_close)

        return cls(
            symbol=sym,
            interval=inv,
            start_time=start_ts,
            close_time=close_ts,
            open=float(k["o"]),
            high=float(k["h"]),
            low=float(k["l"]),
            close=float(k["c"]),
            volume=float(k["v"]),
            is_closed=bool(k.get("x", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary matching DataFrame schema."""
        return {
            "timestamp": self.start_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class CandleAggregator:
    """Maintains a bounded in-memory sliding buffer of OHLCV candles and detects bar close events."""

    REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

    def __init__(
        self,
        symbol: str,
        interval: str,
        max_bars: int = 300,
        on_candle_close: Callable[[pd.DataFrame, KlineEvent], None] | None = None,
        on_candle_update: Callable[[KlineEvent], None] | None = None,
    ) -> None:
        self.symbol = symbol.strip().upper()
        self.interval = interval.strip().lower()
        self.max_bars = max_bars
        self._on_candle_close = on_candle_close
        self._on_candle_update = on_candle_update

        # In-memory sliding DataFrame buffer
        self._df = pd.DataFrame(columns=self.REQUIRED_COLUMNS)
        self._current_kline: KlineEvent | None = None
        self._closed_count: int = 0

    @property
    def current_candle(self) -> KlineEvent | None:
        """Current in-progress or most recently closed candle."""
        return self._current_kline

    @property
    def closed_count(self) -> int:
        """Total number of closed candle events processed."""
        return self._closed_count

    def is_warmed_up(self, min_bars: int = 200) -> bool:
        """Check if the aggregator has accumulated enough closed candles for technical indicator warm-up."""
        return len(self._df) >= min_bars

    def seed(self, df: pd.DataFrame) -> None:
        """Pre-populate the rolling buffer with historical candles to fulfill warm-up immediately."""
        if df.empty:
            logger.warning(f"[{self.symbol}] Cannot seed empty DataFrame.")
            return

        missing = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns for seeding: {missing}")

        clean_df = df[self.REQUIRED_COLUMNS].copy()
        if not pd.api.types.is_datetime64_any_dtype(clean_df["timestamp"]):
            clean_df["timestamp"] = pd.to_datetime(clean_df["timestamp"], utc=True)

        clean_df = clean_df.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)

        if len(clean_df) > self.max_bars:
            clean_df = clean_df.iloc[-self.max_bars :].reset_index(drop=True)

        self._df = clean_df
        logger.info(f"[{self.symbol} {self.interval}] Seeded {len(self._df)} historical bars into rolling buffer.")

    def process_kline(self, event: KlineEvent) -> bool:
        """Process an incoming kline event.

        Updates the current intra-bar state and emits a closed-candle event
        strictly when is_closed is True.

        Returns:
            True if a candle closed and was appended to the buffer; False otherwise.
        """
        if event.symbol != self.symbol or event.interval != self.interval:
            logger.warning(
                f"Ignored kline event: mismatch ({event.symbol} {event.interval}) vs expected ({self.symbol} {self.interval})"
            )
            return False

        self._current_kline = event

        if self._on_candle_update is not None:
            try:
                self._on_candle_update(event)
            except Exception as exc:
                logger.error(f"Error in on_candle_update callback: {exc}", exc_info=True)

        # If the candle has closed, integrate into buffer
        if event.is_closed:
            new_row = pd.DataFrame([event.to_dict()])

            if not self._df.empty and (self._df["timestamp"] == event.start_time).any():
                # Replace existing row if timestamp matches exactly
                idx = self._df.index[self._df["timestamp"] == event.start_time].tolist()[0]
                self._df.iloc[idx] = new_row.iloc[0]
            else:
                self._df = pd.concat([self._df, new_row], ignore_index=True)

            # Enforce bounded memory
            if len(self._df) > self.max_bars:
                self._df = self._df.iloc[-self.max_bars :].reset_index(drop=True)

            self._closed_count += 1

            if self._on_candle_close is not None:
                try:
                    self._on_candle_close(self.get_dataframe(), event)
                except Exception as exc:
                    logger.error(f"Error in on_candle_close callback: {exc}", exc_info=True)

            return True

        return False

    def get_dataframe(self) -> pd.DataFrame:
        """Return a copy of the current in-memory rolling OHLCV DataFrame."""
        return self._df.copy()

    def clear(self) -> None:
        """Reset the internal DataFrame buffer and state."""
        self._df = pd.DataFrame(columns=self.REQUIRED_COLUMNS)
        self._current_kline = None
        self._closed_count = 0
