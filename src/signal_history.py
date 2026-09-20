from __future__ import annotations

from datetime import datetime

try:
    from .database import Database
except ImportError:
    from database import Database


class SignalHistory:
    def __init__(self, database=None, database_name=None):
        if database is not None and database_name is not None:
            raise ValueError("Use database or database_name, not both.")

        if isinstance(database, Database):
            self.db = database
        else:
            path = database if database is not None else database_name
            self.db = Database(path) if path is not None else Database()

    def save(
        self,
        symbol,
        analysis,
        decision,
        quant_score,
        risk,
        signal=None,
        timeframe="1h",
        candle_timestamp=None,
        open=None,
        high=None,
        low=None,
        close=None,
        volume=None,
        is_legacy=0,
    ):
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if candle_timestamp is None:
            candle_timestamp = analysis.get("candle_timestamp", created_at)

        price = analysis["price"]

        data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "candle_timestamp": str(candle_timestamp),
            "price": price,
            "open": open if open is not None else price,
            "high": high if high is not None else price,
            "low": low if low is not None else price,
            "close": close if close is not None else price,
            "volume": volume if volume is not None else float(analysis.get("volume_raw", 0.0)),
            "trend": analysis["trend"],
            "signal": (
                signal["state"]
                if signal is not None
                else decision["decision"]
            ),
            "decision": decision["decision"],
            "quant_score": quant_score["score"],
            "risk": risk["level"],
            "created_at": created_at,
            "is_legacy": is_legacy,
            "timestamp": str(candle_timestamp),  # for backwards compatibility with v1.6 dict consumers
        }

        inserted = self.db.insert_signal(data)
        data["inserted"] = inserted

        return data

    def get_history(self, limit=10):
        return self.db.get_recent_signals(limit)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
