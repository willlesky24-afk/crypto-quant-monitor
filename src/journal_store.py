"""v5 personal journal: plans, closed trades, discipline rules and verifier state.

Why it exists: losses come mostly from behaviour (size, overtrading, skipping
the plan), and v4 never saw what the owner actually did. Everything lives in a
local SQLite file (data/diario.db, git-ignored); nothing leaves the computer.

Rules of the module:
- A missing figure is None, never 0 (an empty week has no mean R).
- R of a closed trade = net P&L / dollars risked in the plan. The plan's risk
  already includes costs (src/position_sizing.py), so a trade that hits its
  stop exactly is about -1 R.
- Discipline limits exist only if the owner sets them; there are no defaults.
- Verifier attempts and the one-time use of reserved data are stored here so a
  server restart cannot reset them.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "diario.db"
SIDES = ("LONG", "SHORT")
RULE_KEYS = (
    "capital",
    "max_daily_loss_pct",
    "max_weekly_loss_pct",
    "max_open_risk_pct",
    "pause_after_losses",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (client TEXT PRIMARY KEY, n INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS holdout (key TEXT PRIMARY KEY, used_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS eligible (key TEXT PRIMARY KEY, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rules (key TEXT PRIMARY KEY, value REAL NOT NULL);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL, side TEXT NOT NULL,
    entry REAL NOT NULL, stop REAL NOT NULL, units REAL NOT NULL,
    risk_usd REAL NOT NULL, costs_usd REAL NOT NULL,
    reason TEXT NOT NULL, outside_rules INTEGER NOT NULL,
    opened_at TEXT NOT NULL,
    exit REAL, closed_at TEXT, moved_stop INTEGER, size_respected INTEGER
);
"""


class JournalError(ValueError):
    """Invalid journal input, shown to the user as is."""


@dataclass(frozen=True)
class Trade:
    id: int
    symbol: str
    side: str
    entry: float
    stop: float
    units: float
    risk_usd: float
    costs_usd: float
    reason: str
    outside_rules: bool
    opened_at: str
    exit: float | None
    closed_at: str | None
    moved_stop: bool | None
    size_respected: bool | None

    @property
    def pnl_usd(self) -> float | None:
        if self.exit is None:
            return None
        direction = 1.0 if self.side == "LONG" else -1.0
        return direction * (self.exit - self.entry) * self.units - self.costs_usd

    @property
    def r(self) -> float | None:
        pnl = self.pnl_usd
        return None if pnl is None else pnl / self.risk_usd

    @property
    def followed_plan(self) -> bool | None:
        if self.exit is None:
            return None
        return bool(
            self.size_respected and not self.moved_stop and not self.outside_rules
        )


def trade_r(
    side: str, entry: float, exit_price: float, units: float, costs: float, risk: float
) -> float:
    """R of a trade; kept as a function so the formula is tested on its own."""
    direction = 1.0 if side == "LONG" else -1.0
    return (direction * (exit_price - entry) * units - costs) / risk


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Journal:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or os.getenv("CQM_JOURNAL_DB") or DEFAULT_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    # Verifier state -------------------------------------------------------
    def next_attempt(self, client: str) -> int:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO attempts(client, n) VALUES(?, 1) "
                "ON CONFLICT(client) DO UPDATE SET n = n + 1",
                (client,),
            )
            return int(
                db.execute(
                    "SELECT n FROM attempts WHERE client=?", (client,)
                ).fetchone()[0]
            )

    def attempts(self, client: str) -> int:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT n FROM attempts WHERE client=?", (client,)
            ).fetchone()
        return int(row[0]) if row else 0

    def holdout_used_at(self, key: str) -> str | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT used_at FROM holdout WHERE key=?", (key,)
            ).fetchone()
        return row[0] if row else None

    def use_holdout(self, key: str) -> None:
        """Mark the reserved data as spent; a second use is an error, not a rerun."""
        with closing(self._connect()) as db, db:
            try:
                db.execute(
                    "INSERT INTO holdout(key, used_at) VALUES(?, ?)", (key, _now())
                )
            except sqlite3.IntegrityError as exc:
                raise JournalError(
                    "Los datos reservados de esta regla ya se usaron."
                ) from exc

    def mark_eligible(self, key: str) -> None:
        """A rule that came out "deserves study" may use its reserved data once."""
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO eligible(key, at) VALUES(?, ?)", (key, _now())
            )

    def is_eligible(self, key: str) -> bool:
        with closing(self._connect()) as db:
            return (
                db.execute("SELECT 1 FROM eligible WHERE key=?", (key,)).fetchone()
                is not None
            )

    # Rules ----------------------------------------------------------------
    def rules(self) -> dict[str, float]:
        with closing(self._connect()) as db:
            return {k: float(v) for k, v in db.execute("SELECT key, value FROM rules")}

    def set_rules(self, values: dict[str, float | None]) -> dict[str, float]:
        unknown = set(values) - set(RULE_KEYS)
        if unknown:
            raise JournalError(f"Regla desconocida: {', '.join(sorted(unknown))}")
        with closing(self._connect()) as db, db:
            for key, value in values.items():
                if value is None:
                    db.execute("DELETE FROM rules WHERE key=?", (key,))
                elif value <= 0:
                    raise JournalError(f"{key} debe ser mayor que cero.")
                else:
                    db.execute(
                        "INSERT INTO rules(key, value) VALUES(?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, float(value)),
                    )
        return self.rules()

    # Trades ---------------------------------------------------------------
    def open_trade(
        self,
        symbol: str,
        side: str,
        entry: float,
        stop: float,
        units: float,
        risk_usd: float,
        costs_usd: float,
        reason: str,
        outside_rules: bool = False,
    ) -> Trade:
        if side not in SIDES:
            raise JournalError("Lado inválido: usa LONG o SHORT.")
        if min(entry, stop, units, risk_usd) <= 0 or costs_usd < 0:
            raise JournalError("Entrada, stop, tamaño y riesgo deben ser positivos.")
        if (side == "LONG" and stop >= entry) or (side == "SHORT" and stop <= entry):
            raise JournalError("El stop debe estar del lado de la pérdida.")
        if not reason.strip():
            raise JournalError("Escribe el motivo: sin motivo no hay revisión posible.")
        with closing(self._connect()) as db, db:
            cur = db.execute(
                "INSERT INTO trades(symbol, side, entry, stop, units, risk_usd, costs_usd, "
                "reason, outside_rules, opened_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    symbol,
                    side,
                    entry,
                    stop,
                    units,
                    risk_usd,
                    costs_usd,
                    reason.strip(),
                    int(outside_rules),
                    _now(),
                ),
            )
            new_id = int(cur.lastrowid)
        return self.trade(new_id)  # read after the commit

    def close_trade(
        self, trade_id: int, exit_price: float, moved_stop: bool, size_respected: bool
    ) -> Trade:
        if exit_price <= 0:
            raise JournalError("El precio de salida debe ser positivo.")
        current = self.trade(trade_id)
        if current.exit is not None:
            raise JournalError("Esta operación ya está cerrada.")
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE trades SET exit=?, closed_at=?, moved_stop=?, size_respected=? WHERE id=?",
                (exit_price, _now(), int(moved_stop), int(size_respected), trade_id),
            )
        return self.trade(trade_id)

    def trade(self, trade_id: int) -> Trade:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        if row is None:
            raise JournalError(f"No existe la operación {trade_id}.")
        return _to_trade(row)

    def trades(self) -> list[Trade]:
        with closing(self._connect()) as db:
            return [
                _to_trade(r)
                for r in db.execute("SELECT * FROM trades ORDER BY id DESC")
            ]


def _to_trade(row: tuple[Any, ...]) -> Trade:
    (
        id_,
        symbol,
        side,
        entry,
        stop,
        units,
        risk,
        costs,
        reason,
        outside,
        opened,
        exit_,
        closed,
        moved,
        size,
    ) = row
    return Trade(
        id_,
        symbol,
        side,
        entry,
        stop,
        units,
        risk,
        costs,
        reason,
        bool(outside),
        opened,
        exit_,
        closed,
        None if moved is None else bool(moved),
        None if size is None else bool(size),
    )


def _streak(trades: list[Trade]) -> int:
    worst = current = 0
    for t in sorted(trades, key=lambda t: t.closed_at or ""):
        current = current + 1 if (t.pnl_usd or 0.0) < 0 else 0
        worst = max(worst, current)
    return worst


def summary(trades: list[Trade]) -> dict[str, Any]:
    """Figures for a set of closed trades. Empty sets give None, not zero."""
    closed = [t for t in trades if t.exit is not None]
    if not closed:
        return {
            "closed": 0,
            "mean_r": None,
            "plan_pct": None,
            "costs_usd": None,
            "pnl_usd": None,
            "worst_streak": None,
            "r_in_plan": None,
            "r_off_plan": None,
        }
    in_plan = [t.r for t in closed if t.followed_plan]
    off_plan = [t.r for t in closed if not t.followed_plan]
    return {
        "closed": len(closed),
        "mean_r": sum(t.r for t in closed) / len(closed),
        "plan_pct": 100.0 * len(in_plan) / len(closed),
        "costs_usd": sum(t.costs_usd for t in closed),
        "pnl_usd": sum(t.pnl_usd for t in closed),
        "worst_streak": _streak(closed),
        "r_in_plan": sum(in_plan) / len(in_plan) if in_plan else None,
        "r_off_plan": sum(off_plan) / len(off_plan) if off_plan else None,
    }


def _closed_since(trades: list[Trade], since: datetime) -> list[Trade]:
    return [
        t
        for t in trades
        if t.closed_at and datetime.fromisoformat(t.closed_at) >= since
    ]


def week_start(now: datetime) -> datetime:
    day = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return day - timedelta(days=day.weekday())


def breaches(
    trades: list[Trade], rules: dict[str, float], now: datetime | None = None
) -> list[str]:
    """Which of the owner's own limits are crossed right now, in plain words."""
    now = now or datetime.now(UTC)
    out: list[str] = []
    capital = rules.get("capital")
    day = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    pct_rules = (
        ("max_daily_loss_pct", _closed_since(trades, day), "del día"),
        ("max_weekly_loss_pct", _closed_since(trades, week_start(now)), "de la semana"),
    )
    for key, window, label in pct_rules:
        if key in rules and capital:
            loss = -sum(t.pnl_usd for t in window)
            if loss >= capital * rules[key] / 100.0:
                out.append(
                    f"Llegaste a tu pérdida máxima {label}: −${loss:,.2f} (límite {rules[key]:g} %)."
                )
    if "max_open_risk_pct" in rules and capital:
        open_risk = sum(t.risk_usd for t in trades if t.exit is None)
        if open_risk >= capital * rules["max_open_risk_pct"] / 100.0:
            out.append(
                f"Tu riesgo abierto es ${open_risk:,.2f}, en o sobre tu límite de {rules['max_open_risk_pct']:g} %."
            )
    if "pause_after_losses" in rules:
        run = 0
        for t in sorted(
            (t for t in trades if t.exit is not None),
            key=lambda t: t.closed_at or "",
            reverse=True,
        ):
            if (t.pnl_usd or 0.0) >= 0:
                break
            run += 1
        if run >= rules["pause_after_losses"]:
            out.append(
                f"Llevas {run} {'pérdida seguida' if run == 1 else 'pérdidas seguidas'}: "
                "tu regla dice hacer una pausa."
            )
    return out
