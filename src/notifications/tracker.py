from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from src.notifications.models import SignalEvent

logger = logging.getLogger(__name__)

DEFAULT_ALERTS_DB = Path("data/dispatched_alerts.db")


class AlertOutcomeTracker:
    """Tracks dispatched signals, monitors subsequent market price action,
    and determines whether Take Profit or Stop Loss was reached to audit Win Rate.
    """

    def __init__(self, db_path: Path | str = DEFAULT_ALERTS_DB) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dispatched_alerts (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    quant_score REAL NOT NULL,
                    risk_reward REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    current_or_exit_price REAL,
                    exit_time TEXT,
                    pnl_percent REAL DEFAULT 0.0,
                    r_multiple REAL DEFAULT 0.0,
                    is_forex INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    def record_alert(
        self,
        signal: SignalEvent,
        is_forex: bool = False,
        risk_reward: float = 2.0,
    ) -> dict[str, Any]:
        """Record an outbound alert in the persistent audit database."""
        alert_id = signal.signal_id
        entry_price = float(signal.price)
        sl = float(signal.stop_loss) if signal.stop_loss is not None else entry_price * 0.98
        tp = float(signal.take_profit) if signal.take_profit is not None else entry_price * 1.04

        record = {
            "id": alert_id,
            "timestamp": str(signal.timestamp)[:19],
            "symbol": signal.symbol,
            "direction": signal.direction.upper(),
            "timeframe": signal.timeframe,
            "entry_price": entry_price,
            "stop_loss": sl,
            "take_profit": tp,
            "quant_score": float(signal.quant_score),
            "risk_reward": float(risk_reward),
            "status": "OPEN",
            "current_or_exit_price": entry_price,
            "exit_time": None,
            "pnl_percent": 0.0,
            "r_multiple": 0.0,
            "is_forex": 1 if is_forex else 0,
        }

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO dispatched_alerts (
                    id, timestamp, symbol, direction, timeframe,
                    entry_price, stop_loss, take_profit, quant_score,
                    risk_reward, status, current_or_exit_price, exit_time,
                    pnl_percent, r_multiple, is_forex
                ) VALUES (
                    :id, :timestamp, :symbol, :direction, :timeframe,
                    :entry_price, :stop_loss, :take_profit, :quant_score,
                    :risk_reward, :status, :current_or_exit_price, :exit_time,
                    :pnl_percent, :r_multiple, :is_forex
                )
                """,
                record,
            )
            conn.commit()

        return record

    def get_all_alerts(self, limit: int = 300) -> list[dict[str, Any]]:
        """Retrieve all recorded alerts ordered from newest to oldest."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM dispatched_alerts
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_alert_outcomes(
        self,
        forex_loader: Any = None,
        crypto_loader: Any = None,
    ) -> int:
        """Fetch subsequent candles for all OPEN alerts and evaluate TP/SL hits."""
        open_alerts = []
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM dispatched_alerts WHERE status = 'OPEN'")
            open_alerts = [dict(r) for r in cursor.fetchall()]

        if not open_alerts:
            return 0

        updated_count = 0

        # Lazy import loaders if not provided
        if forex_loader is None:
            try:
                from src.forex_data_loader import ForexDataLoader
                forex_loader = ForexDataLoader()
            except Exception as e:
                logger.warning(f"Could not initialize ForexDataLoader: {e}")
        if crypto_loader is None:
            try:
                from src.data_loader import BinanceDataLoader
                crypto_loader = BinanceDataLoader()
            except Exception as e:
                logger.warning(f"Could not initialize BinanceDataLoader: {e}")

        for alert in open_alerts:
            is_fx = bool(alert["is_forex"]) or "=X" in alert["symbol"]
            sym = alert["symbol"]
            tf = alert["timeframe"]
            entry_time = pd.to_datetime(alert["timestamp"], utc=True)
            direction = alert["direction"]
            entry_p = alert["entry_price"]
            sl = alert["stop_loss"]
            tp = alert["take_profit"]
            rr = alert["risk_reward"]

            candles_df = None
            try:
                if is_fx and forex_loader is not None:
                    candles_df = forex_loader.get_klines(symbol=sym, interval=tf, limit=200)
                elif crypto_loader is not None:
                    candles_df = crypto_loader.get_klines(symbol=sym, interval=tf, limit=200)
            except Exception as exc:
                logger.warning(f"Failed to fetch outcome candles for {sym}: {exc}")
                continue

            if candles_df is None or candles_df.empty:
                continue

            # Ensure timestamp is datetime with utc
            if "timestamp" in candles_df.columns:
                candles_df["timestamp"] = pd.to_datetime(candles_df["timestamp"], utc=True)
                post_candles = candles_df[candles_df["timestamp"] >= entry_time]
            else:
                post_candles = candles_df

            if post_candles.empty:
                post_candles = candles_df.iloc[-5:]

            new_status = "OPEN"
            exit_price = None
            exit_time = None
            pnl_pct = 0.0
            r_mult = 0.0

            for _, candle in post_candles.iterrows():
                high = float(candle["high"])
                low = float(candle["low"])
                c_time = str(candle.get("timestamp", ""))[:19]

                if direction == "LONG":
                    # Check both hit scenario
                    if low <= sl and high >= tp:
                        # Conservative: stop loss hit
                        new_status = "LOSS"
                        exit_price = sl
                        exit_time = c_time
                        pnl_pct = ((sl - entry_p) / entry_p) * 100
                        r_mult = -1.0
                        break
                    elif high >= tp:
                        new_status = "WIN"
                        exit_price = tp
                        exit_time = c_time
                        pnl_pct = ((tp - entry_p) / entry_p) * 100
                        r_mult = rr
                        break
                    elif low <= sl:
                        new_status = "LOSS"
                        exit_price = sl
                        exit_time = c_time
                        pnl_pct = ((sl - entry_p) / entry_p) * 100
                        r_mult = -1.0
                        break
                elif direction == "SHORT":
                    if high >= sl and low <= tp:
                        new_status = "LOSS"
                        exit_price = sl
                        exit_time = c_time
                        pnl_pct = ((entry_p - sl) / entry_p) * 100
                        r_mult = -1.0
                        break
                    elif low <= tp:
                        new_status = "WIN"
                        exit_price = tp
                        exit_time = c_time
                        pnl_pct = ((entry_p - tp) / entry_p) * 100
                        r_mult = rr
                        break
                    elif high >= sl:
                        new_status = "LOSS"
                        exit_price = sl
                        exit_time = c_time
                        pnl_pct = ((entry_p - sl) / entry_p) * 100
                        r_mult = -1.0
                        break

            # If still open, calculate floating PnL with latest candle close
            if new_status == "OPEN" and not post_candles.empty:
                latest_close = float(post_candles.iloc[-1]["close"])
                exit_price = latest_close
                if direction == "LONG":
                    pnl_pct = ((latest_close - entry_p) / entry_p) * 100
                else:
                    pnl_pct = ((entry_p - latest_close) / entry_p) * 100
                r_mult = pnl_pct / (abs(entry_p - sl) / entry_p * 100) if abs(entry_p - sl) > 0 else 0.0

            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE dispatched_alerts
                    SET status = :status,
                        current_or_exit_price = :exit_price,
                        exit_time = :exit_time,
                        pnl_percent = :pnl_pct,
                        r_multiple = :r_mult
                    WHERE id = :id
                    """,
                    {
                        "status": new_status,
                        "exit_price": exit_price,
                        "exit_time": exit_time,
                        "pnl_pct": pnl_pct,
                        "r_mult": r_mult,
                        "id": alert["id"],
                    },
                )
                conn.commit()
                updated_count += 1

        return updated_count

    def compute_statistics(self) -> dict[str, Any]:
        """Calculate high-level performance metrics across all tracked alerts."""
        alerts = self.get_all_alerts(limit=1000)
        if not alerts:
            return {
                "total_alerts": 0,
                "closed_alerts": 0,
                "wins": 0,
                "losses": 0,
                "open_alerts": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_r": 0.0,
                "total_pnl_percent": 0.0,
            }

        wins = sum(1 for a in alerts if a["status"] == "WIN")
        losses = sum(1 for a in alerts if a["status"] == "LOSS")
        open_cnt = sum(1 for a in alerts if a["status"] == "OPEN")
        closed_cnt = wins + losses

        win_rate = (wins / closed_cnt * 100.0) if closed_cnt > 0 else 0.0

        total_gain_r = sum(a["r_multiple"] for a in alerts if a["status"] == "WIN")
        total_loss_r = abs(sum(a["r_multiple"] for a in alerts if a["status"] == "LOSS"))
        profit_factor = (total_gain_r / total_loss_r) if total_loss_r > 0 else (total_gain_r if total_gain_r > 0 else 0.0)

        total_r = sum(a["r_multiple"] for a in alerts if a["status"] in ("WIN", "LOSS"))
        total_pnl = sum(a["pnl_percent"] for a in alerts if a["status"] in ("WIN", "LOSS"))

        return {
            "total_alerts": len(alerts),
            "closed_alerts": closed_cnt,
            "wins": wins,
            "losses": losses,
            "open_alerts": open_cnt,
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "total_r": round(total_r, 2),
            "total_pnl_percent": round(total_pnl, 2),
        }
