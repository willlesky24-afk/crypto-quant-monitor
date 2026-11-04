from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from streamlit.testing.v1 import AppTest

from src.data_loader import BinanceDataLoader
from src.market_scanner import MarketScanner
from src.notifications.channels.discord import DiscordWebhookChannel
from src.notifications.models import NotificationChannelType, NotificationResult
from src.notifications.tracker import AlertOutcomeTracker
from src.risk_engine import RiskEngine


def test_streamlit_risk_metrics_match_shared_plan(
    monkeypatch, tmp_path, synthetic_ohlcv
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "contexts.db"))
    monkeypatch.setattr(
        BinanceDataLoader,
        "get_klines",
        lambda self, *args, **kwargs: synthetic_ohlcv.copy(),
    )

    plans = []
    original_plan = RiskEngine.plan_from_decision

    def capture_plan(self, **kwargs):
        plan = original_plan(self, **kwargs)
        plans.append(plan)
        return plan

    monkeypatch.setattr(RiskEngine, "plan_from_decision", capture_plan)
    app_path = Path(__file__).resolve().parents[2] / "src" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()

    assert not app.exception
    assert plans
    plan = plans[0]
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Estado de señal"] == f"{plan['status']} ({plan['direction']})"
    expected_stop = (
        f"${plan['stop_loss']:,.2f}"
        if plan["stop_loss"] is not None
        else "No disponible"
    )
    expected_target = (
        f"${plan['take_profit']:,.2f}"
        if plan["take_profit"] is not None
        else "No disponible"
    )
    expected_r = (
        f"1 : {plan['gross_risk_reward']:.2f}"
        if plan["gross_risk_reward"] is not None
        else "No disponible"
    )
    assert metrics["Stop Loss"] == expected_stop
    assert metrics["Take Profit"] == expected_target
    assert metrics["R bruto indicativo"] == expected_r
    assert any(
        "OPEN indica seguimiento de mercado, no envío confirmado" in caption.value
        for caption in app.caption
    )
    assert any(
        "Historial de señales registradas" in markdown.value
        for markdown in app.markdown
    )


def test_streamlit_reports_registered_signal_when_every_channel_fails(
    monkeypatch, tmp_path, synthetic_ohlcv
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "contexts.db"))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://invalid.example/test-only")
    monkeypatch.setattr(
        BinanceDataLoader,
        "get_klines",
        lambda self, *args, **kwargs: synthetic_ohlcv.copy(),
    )
    candidate = SimpleNamespace(
        quant_score=90.0,
        is_operable=lambda: True,
        symbol="BTCUSDT",
        entry_price=60000.0,
        action="BUY",
        direction="LONG",
        confidence=0.9,
        predictive_score=0.8,
        regime="TRENDING_BULL",
        primary_reason="fixture local",
        stop_loss=59000.0,
        take_profit=62000.0,
        risk_reward=2.0,
        status="ACTIVADA",
        entry_confirmed=True,
    )
    monkeypatch.setattr(
        MarketScanner, "scan_market", lambda self, *args, **kwargs: [candidate]
    )
    send_mock = MagicMock(
        return_value=NotificationResult(
            success=False,
            channel=NotificationChannelType.DISCORD,
            error_message="simulated channel failure",
            event_id="test-only",
        )
    )
    monkeypatch.setattr(DiscordWebhookChannel, "send", send_mock)

    app_path = Path(__file__).resolve().parents[2] / "src" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    assert not app.exception
    next(
        button
        for button in app.button
        if button.label == "🚀 Escanear Mercado y Enviar Alertas Reales"
    ).click()
    app.run()

    assert not app.exception
    assert send_mock.called
    assert any(
        "pero ningún canal confirmó la aceptación del envío" in warning.value
        for warning in app.warning
    )
    alerts = AlertOutcomeTracker(
        tmp_path / "data" / "dispatched_alerts.db"
    ).get_all_alerts()
    assert len(alerts) == 1 and alerts[0]["status"] == "OPEN"
    assert any(
        "OPEN indica seguimiento de mercado, no envío confirmado" in caption.value
        for caption in app.caption
    )
