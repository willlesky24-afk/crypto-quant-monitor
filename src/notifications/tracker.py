from __future__ import annotations

import logging
import math
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from src.notifications.models import SignalEvent
from src.risk_engine import RiskEngine

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
            # New provenance is stored separately; existing alert rows are untouched.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS validated_alert_plans (
                    alert_id TEXT PRIMARY KEY,
                    recorded_at TEXT NOT NULL,
                    planned_r REAL NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def _now_utc() -> pd.Timestamp:
        return pd.Timestamp.now(tz="UTC")

    @staticmethod
    def _validated_plan(
        entry_price: Any, stop_loss: Any, take_profit: Any,
        direction: Any, reported_r: Any,
    ) -> dict[str, Any]:
        levels = RiskEngine().calculate_levels(entry_price, stop_loss, take_profit, direction)
        if levels["reason"] is not None:
            raise ValueError(f"Alerta no operable: {levels['reason']}")
        try:
            ratio = float(reported_r)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Alerta no operable: falta un R bruto válido.") from exc
        if not math.isfinite(ratio) or not math.isclose(
            ratio, levels["gross_risk_reward"], rel_tol=1e-6, abs_tol=0.005
        ):
            raise ValueError("Alerta no operable: el R reportado no coincide con los niveles.")
        return levels

    @classmethod
    def _classify_alert(cls, alert: dict[str, Any]) -> dict[str, Any]:
        if alert.get("risk_recorded_at") is None:
            alert["risk_integrity_status"] = "LEGACY_UNVERIFIED"
            alert["risk_integrity_reason"] = "No consta validación del plan al registrar la alerta."
            return alert
        try:
            levels = cls._validated_plan(
                alert["entry_price"], alert["stop_loss"], alert["take_profit"],
                alert["direction"], alert["risk_reward"],
            )
            cls._validated_plan(
                alert["entry_price"], alert["stop_loss"], alert["take_profit"],
                alert["direction"], alert["validated_planned_r"],
            )
        except ValueError as exc:
            alert["risk_integrity_status"] = "INVALID_PLAN"
            alert["risk_integrity_reason"] = str(exc)
        else:
            alert["risk_integrity_status"] = "VALIDATED"
            alert["risk_integrity_reason"] = None
            alert["risk_reward"] = levels["gross_risk_reward"]
        return alert

    def record_alert(
        self,
        signal: SignalEvent,
        is_forex: bool = False,
        risk_reward: float | None = None,
    ) -> dict[str, Any]:
        """Record only an activated alert with a validated, explicit gross R."""
        action_direction = (str(signal.action).upper(), str(signal.direction).upper())
        if action_direction not in {("BUY", "LONG"), ("SELL", "SHORT")}:
            raise ValueError("Alerta no operable: acción y dirección no coinciden.")
        if signal.metadata.get("signal_status") not in (None, "ACTIVADA") or signal.metadata.get("entry_confirmed") is False:
            raise ValueError("Alerta no operable: la entrada no está activada.")

        reported_r = risk_reward if risk_reward is not None else signal.metadata.get("risk_reward_ratio")
        levels = self._validated_plan(
            signal.price, signal.stop_loss, signal.take_profit, signal.direction, reported_r
        )
        if signal.metadata.get("risk_reward_ratio") is not None:
            self._validated_plan(
                signal.price, signal.stop_loss, signal.take_profit,
                signal.direction, signal.metadata["risk_reward_ratio"],
            )

        alert_id = signal.signal_id
        entry_price = levels["entry_price"]
        recorded_at = self._now_utc().isoformat()

        record = {
            "id": alert_id,
            "timestamp": str(signal.timestamp)[:19],
            "symbol": signal.symbol,
            "direction": signal.direction.upper(),
            "timeframe": signal.timeframe,
            "entry_price": entry_price,
            "stop_loss": levels["stop_loss"],
            "take_profit": levels["take_profit"],
            "quant_score": float(signal.quant_score),
            "risk_reward": levels["gross_risk_reward"],
            "status": "OPEN",
            "current_or_exit_price": entry_price,
            "exit_time": None,
            "pnl_percent": 0.0,
            "r_multiple": 0.0,
            "is_forex": 1 if is_forex else 0,
        }

        with self._get_connection() as conn:
            inserted = conn.execute(
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
            if inserted.rowcount:
                conn.execute(
                    "INSERT INTO validated_alert_plans (alert_id, recorded_at, planned_r) VALUES (?, ?, ?)",
                    (alert_id, recorded_at, levels["gross_risk_reward"]),
                )
            else:
                existing = conn.execute(
                    """SELECT a.*, v.recorded_at AS risk_recorded_at,
                              v.planned_r AS validated_planned_r
                       FROM dispatched_alerts a
                       LEFT JOIN validated_alert_plans v ON v.alert_id = a.id
                       WHERE a.id = ?""",
                    (alert_id,),
                ).fetchone()
                return self._classify_alert(dict(existing))

        return self._classify_alert({
            **record,
            "risk_recorded_at": recorded_at,
            "validated_planned_r": levels["gross_risk_reward"],
        })

    def get_all_alerts(self, limit: int = 300) -> list[dict[str, Any]]:
        """Retrieve all recorded alerts ordered from newest to oldest."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT a.*, v.recorded_at AS risk_recorded_at,
                       v.planned_r AS validated_planned_r
                FROM dispatched_alerts a
                LEFT JOIN validated_alert_plans v ON v.alert_id = a.id
                ORDER BY a.timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [self._classify_alert(dict(row)) for row in cursor.fetchall()]

    def update_alert_outcomes(
        self,
        forex_loader: Any = None,
        crypto_loader: Any = None,
    ) -> int:
        """Evaluate only validated alerts against candles after their recording time."""
        open_alerts = []
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT a.*, v.recorded_at AS risk_recorded_at,
                          v.planned_r AS validated_planned_r
                   FROM dispatched_alerts a
                   JOIN validated_alert_plans v ON v.alert_id = a.id
                   WHERE a.status = 'OPEN'"""
            )
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
            if self._classify_alert(alert)["risk_integrity_status"] != "VALIDATED":
                logger.warning("Skipping alert %s with an invalid persisted risk plan", alert["id"])
                continue
            is_fx = bool(alert["is_forex"]) or "=X" in alert["symbol"]
            sym = alert["symbol"]
            tf = alert["timeframe"]
            signal_time = pd.to_datetime(alert["timestamp"], utc=True, errors="coerce")
            recorded_time = pd.to_datetime(alert["risk_recorded_at"], utc=True, errors="coerce")
            if pd.isna(signal_time) or pd.isna(recorded_time):
                logger.warning("Skipping alert %s with an invalid event or recording timestamp", alert["id"])
                continue
            cutoff_time = max(signal_time, recorded_time)
            direction = alert["direction"]
            entry_p = alert["entry_price"]
            sl = alert["stop_loss"]
            tp = alert["take_profit"]
            plan = self._validated_plan(entry_p, sl, tp, direction, alert["risk_reward"])
            planned_r = plan["gross_risk_reward"]

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

            if "timestamp" not in candles_df.columns:
                logger.warning("Skipping alert %s: outcome candles have no timestamp", alert["id"])
                continue
            post_candles = candles_df.copy()
            post_candles["timestamp"] = pd.to_datetime(
                post_candles["timestamp"], utc=True, errors="coerce"
            )
            post_candles = post_candles[
                post_candles["timestamp"].notna() & (post_candles["timestamp"] > cutoff_time)
            ].sort_values("timestamp")
            if post_candles.empty:
                continue

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
                        r_mult = planned_r
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
                        r_mult = planned_r
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
                r_mult = (
                    (latest_close - entry_p) if direction == "LONG" else (entry_p - latest_close)
                ) / plan["risk_distance"]

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
        """Calculate performance only from alerts validated when first recorded."""
        recorded_alerts = self.get_all_alerts(limit=1000)
        alerts = [a for a in recorded_alerts if a["risk_integrity_status"] == "VALIDATED"]
        unverified_count = len(recorded_alerts) - len(alerts)
        if not alerts:
            return {
                "total_alerts": 0,
                "all_recorded_alerts": len(recorded_alerts),
                "excluded_unverified_alerts": unverified_count,
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
            "all_recorded_alerts": len(recorded_alerts),
            "excluded_unverified_alerts": unverified_count,
            "closed_alerts": closed_cnt,
            "wins": wins,
            "losses": losses,
            "open_alerts": open_cnt,
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "total_r": round(total_r, 2),
            "total_pnl_percent": round(total_pnl, 2),
        }
