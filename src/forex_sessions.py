from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ForexSessionStatus:
    """Real-time status and active financial trading sessions in the Forex market."""

    is_market_open: bool
    status_headline: str
    active_sessions: list[str]
    session_details: dict[str, str]
    current_utc_time: str
    weekend_reopen_info: str


def get_forex_session_status(dt: datetime | None = None) -> ForexSessionStatus:
    """Evaluates current global Forex trading sessions and market status.

    Standard global financial center hours (UTC):
    - Sydney: 21:00 to 06:00 UTC
    - Tokyo: 00:00 to 09:00 UTC
    - London: 07:00 to 16:00 UTC
    - New York: 12:00 to 21:00 UTC

    Market closed: Friday 21:00 UTC until Sunday 21:00 UTC.
    """
    now = dt or datetime.now(timezone.utc)
    weekday = now.weekday()  # 0=Monday, ..., 4=Friday, 5=Saturday, 6=Sunday
    hour = now.hour
    minute = now.minute
    time_float = hour + (minute / 60.0)

    # Check if market is closed for weekend (Friday 21:00 UTC to Sunday 21:00 UTC)
    is_weekend_closed = False
    if weekday == 4 and time_float >= 21.0:
        is_weekend_closed = True
    elif weekday == 5:
        is_weekend_closed = True
    elif weekday == 6 and time_float < 21.0:
        is_weekend_closed = True

    active_sessions: list[str] = []
    session_details: dict[str, str] = {
        "🇬🇧 Londres": "07:00 - 16:00 UTC (Mayor volumen mundial)",
        "🇺🇸 Nueva York": "12:00 - 21:00 UTC (Alta liquidez y noticias Fed)",
        "🇯🇵 Tokio / Asia": "00:00 - 09:00 UTC (Yen, Banco de Japón)",
        "🇦🇺 Sídney": "21:00 - 06:00 UTC (Apertura de la semana)",
    }

    if not is_weekend_closed:
        if 7.0 <= time_float < 16.0:
            active_sessions.append("🇬🇧 Sesión Londres")
        if 12.0 <= time_float < 21.0:
            active_sessions.append("🇺🇸 Sesión Nueva York")
        if 0.0 <= time_float < 9.0:
            active_sessions.append("🇯🇵 Sesión Tokio")
        if time_float >= 21.0 or time_float < 6.0:
            active_sessions.append("🇦🇺 Sesión Sídney")

    if is_weekend_closed:
        status_headline = "🔴 Mercado Forex Cerrado (Fin de Semana)"
        reopen_info = "Reapertura: Domingo a las 21:00 UTC (17:00 EST / 23:00 España)"
    else:
        # Check overlap
        if "🇬🇧 Sesión Londres" in active_sessions and "🇺🇸 Sesión Nueva York" in active_sessions:
            status_headline = "🟢 Solapamiento Londres - Nueva York (Máxima Liquidez Mundial)"
        elif active_sessions:
            status_headline = f"🟢 Mercado Abierto: {' + '.join(active_sessions)}"
        else:
            status_headline = "🟢 Mercado Abierto (Transición Interbancaria)"
        reopen_info = "Abierto 24/5 continuo hasta el viernes 21:00 UTC"

    return ForexSessionStatus(
        is_market_open=not is_weekend_closed,
        status_headline=status_headline,
        active_sessions=active_sessions,
        session_details=session_details,
        current_utc_time=now.strftime("%H:%M UTC (%A)"),
        weekend_reopen_info=reopen_info,
    )
