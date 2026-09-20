from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

import pandas as pd


class TradeExitReason(str, Enum):
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    TIME_HORIZON = "TIME_HORIZON"
    SIGNAL_INVALIDATION = "SIGNAL_INVALIDATION"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class MarketType(str, Enum):
    SPOT = "SPOT"
    PERP = "PERP"


class TradeDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


@dataclass(frozen=True)
class SignalEvent:
    """Represents a discrete trading signal generated upon a fully closed candle T."""

    signal_id: str
    symbol: str
    timeframe: str
    candle_timestamp: pd.Timestamp
    price_at_signal: float
    signal_state: str
    confidence: float
    decision: str
    quant_score: float
    risk_level: str
    atr: float
    poc: float
    vah: float
    val: float
    direction: str = TradeDirection.LONG.value

    def to_dict(self) -> dict:
        d = asdict(self)
        d["candle_timestamp"] = str(self.candle_timestamp)
        return d


@dataclass
class BacktestConfig:
    """Configuration parameters for deterministic, event-driven backtesting."""

    initial_capital: float = 10_000.0
    position_size_pct: float = 1.0  # 1.0 = 100% of available capital
    maker_fee_pct: float = 0.0002  # 0.02%
    taker_fee_pct: float = 0.0005  # 0.05%
    slippage_pct: float = 0.0005  # 0.05%
    tp_atr_multiple: float = 2.0  # Take profit ATR multiple
    sl_atr_multiple: float = 1.0  # Stop loss ATR multiple
    max_holding_bars: int = 24  # Max time horizon in bars (e.g. 24h on 1h candles)
    enable_trailing_stop: bool = False
    trailing_stop_activation_r: float = 1.0  # Move SL to break-even after +1R gain
    direction: str = TradeDirection.LONG.value  # "LONG", "SHORT", or "BOTH"
    market_type: str = MarketType.SPOT.value  # "SPOT" or "PERP"
    funding_rate_8h: float = 0.0001  # 0.01% per 8h funding cycle on PERP
    leverage: float = 1.0
    min_quant_score: float = 60.0
    require_favorable_decision: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Position:
    """Represents an open active trade during simulation."""

    position_id: str
    signal: SignalEvent
    entry_timestamp: pd.Timestamp
    entry_price: float
    size_units: float
    notional_entry: float
    tp_price: float
    sl_price: float
    fee_entry: float
    side: str = PositionSide.LONG.value
    funding_fees_accumulated: float = 0.0
    last_funding_time: pd.Timestamp | None = None
    bars_held: int = 0
    highest_price: float = field(default=0.0)
    lowest_price: float = field(default=0.0)
    is_active: bool = True

    def __post_init__(self):
        if self.highest_price == 0.0:
            self.highest_price = self.entry_price
        if self.lowest_price == 0.0:
            self.lowest_price = self.entry_price

    def update_excursions(self, high: float, low: float):
        """Updates highest and lowest prices experienced during trade lifetime."""
        if high > self.highest_price:
            self.highest_price = high
        if low < self.lowest_price:
            self.lowest_price = low


@dataclass(frozen=True)
class TradeResult:
    """Immutable record of a fully closed and evaluated trade."""

    trade_id: str
    symbol: str
    timeframe: str
    direction: str
    signal_timestamp: pd.Timestamp
    entry_timestamp: pd.Timestamp
    exit_timestamp: pd.Timestamp
    entry_price: float
    exit_price: float
    size_units: float
    notional_entry: float
    notional_exit: float
    gross_pnl: float
    fee_entry: float
    fee_exit: float
    net_pnl: float
    net_return_pct: float
    r_multiple: float
    bars_held: int
    exit_reason: str
    mfe_pct: float  # Max Favorable Excursion (% gain potential)
    mae_pct: float  # Max Adverse Excursion (% loss potential / trade drawdown)
    is_win: bool
    side: str = PositionSide.LONG.value
    funding_fees: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signal_timestamp"] = str(self.signal_timestamp)
        d["entry_timestamp"] = str(self.entry_timestamp)
        d["exit_timestamp"] = str(self.exit_timestamp)
        return d


@dataclass(frozen=True)
class EquityPoint:
    """Point in time recording capital balance and drawdown."""

    timestamp: pd.Timestamp
    equity: float
    cash: float
    drawdown_pct: float

    def to_dict(self) -> dict:
        return {
            "timestamp": str(self.timestamp),
            "equity": self.equity,
            "cash": self.cash,
            "drawdown_pct": self.drawdown_pct,
        }


@dataclass
class BacktestReport:
    """Comprehensive performance summary of a completed backtest execution."""

    config: BacktestConfig
    symbol: str
    timeframe: str
    start_time: str
    end_time: str
    total_candles: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    expectancy: float
    expectancy_r: float
    max_drawdown_pct: float
    max_drawdown_usd: float
    max_drawdown_duration_bars: int
    avg_mfe_pct: float
    avg_mae_pct: float
    avg_bars_held: float
    total_gross_pnl: float
    total_fees_paid: float
    total_net_pnl: float
    return_on_capital_pct: float
    total_funding_fees: float = 0.0
    sharpe_ratio: float | None = None
    calmar_ratio: float | None = None
    trades: list[TradeResult] = field(default_factory=list)
    equity_curve: list[EquityPoint] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["config"] = self.config.to_dict()
        d["trades"] = [t.to_dict() for t in self.trades]
        d["equity_curve"] = [p.to_dict() for p in self.equity_curve]
        return d
