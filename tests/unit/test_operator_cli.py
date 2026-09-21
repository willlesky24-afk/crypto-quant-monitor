from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from src.ai_agent.context_builder import ContextBuilder
from src.ai_agent.models import MarketContext
from src.notifications.models import SignalEvent
from src.operator_cli.client import OperatorCLI


def _create_sample_context(symbol: str = "BTCUSDT", timeframe: str = "1h") -> MarketContext:
    sig = SignalEvent(
        timestamp=pd.Timestamp("2026-03-01 12:00:00", tz="UTC"),
        symbol=symbol,
        timeframe=timeframe,
        action="BUY",
        direction="LONG",
        confidence=0.85,
        predictive_score=0.82,
        regime="TRENDING_BULL",
        reasoning="Strong momentum and volume breakout",
        price=65400.0,
        quant_score=85.0,
        stop_loss=64000.0,
        take_profit=68000.0,
        signal_id=f"test-{symbol}-{timeframe}",
        metadata={"risk_reward_ratio": 1.85, "atr": 250.0},
    )
    return ContextBuilder.build_from_signal_event(
        signal_event=sig,
        extra_metadata={"source": "test", "poc": 65000.0, "vah": 66000.0, "val": 64500.0},
    )




def test_operator_cli_status_no_data():
    cli = OperatorCLI(db_path=":memory:", provider_type="mock")
    status = cli.get_status("BTCUSDT", "1h")

    assert status["status"] == "NO_DATA"
    formatted = cli.format_status_output(status)
    assert "No persisted context found" in formatted


def test_operator_cli_status_and_formatting_active():
    cli = OperatorCLI(db_path=":memory:", provider_type="mock")
    ctx = _create_sample_context("BTCUSDT", "1h")
    cli.context_provider.update_context(ctx)

    status = cli.get_status("BTCUSDT", "1h")
    assert status["status"] == "ACTIVE"
    assert status["price"] == 65400.0
    assert status["regime"] == "TRENDING_BULL"
    assert status["quant_score"] == 85.0

    formatted = cli.format_status_output(status)
    assert "MARKET STATUS: BTCUSDT [1H]" in formatted
    assert "$65,400.00" in formatted
    assert "TRENDING_BULL" in formatted
    assert "85.00" in formatted


def test_operator_cli_ask():
    cli = OperatorCLI(db_path=":memory:", provider_type="mock")
    ctx = _create_sample_context("BTCUSDT", "1h")
    cli.context_provider.update_context(ctx)

    response_text = cli.ask("What is the current regime?", "BTCUSDT", "1h")
    assert "COPILOT RESPONSE [BTCUSDT 1h]" in response_text
    assert "DISCLAIMER" in response_text


def test_operator_cli_report_generation():
    cli = OperatorCLI(db_path=":memory:", provider_type="mock")

    # Empty context
    empty_rep = cli.get_report("ETHUSDT", "1h")
    assert "Cannot generate report" in empty_rep

    # Populated context
    ctx = _create_sample_context("ETHUSDT", "1h")
    cli.context_provider.update_context(ctx)
    rep = cli.get_report("ETHUSDT", "1h")

    assert "ETHUSDT" in rep
    assert "EXECUTIVE SUMMARY" in rep
    assert "TECHNICAL & PREDICTIVE ASSESSMENT" in rep
    assert "DECISION SUPPORT CONCLUSION" in rep
    assert "DISCLAIMER" in rep


def test_operator_cli_report_with_anomalies():
    cli = OperatorCLI(db_path=":memory:", provider_type="mock")
    ctx = _create_sample_context("ETHUSDT", "1h")
    cli.context_provider.update_context(ctx)

    from src.anomaly_detection.models import AlertSeverity, AnomalyType, MarketAlert

    mock_alert = MarketAlert(
        alert_id="alt-1",
        anomaly_type=AnomalyType.SCORE_DIVERGENCE,
        severity=AlertSeverity.WARNING,
        symbol="ETHUSDT",
        timeframe="1h",
        headline="Predictive Divergence",
        reason="Divergence between quantitative and predictive score",
        current_value=85.0,
        reference_value=50.0,
    )

    with patch.object(cli.anomaly_detector, "evaluate", return_value=[mock_alert]):
        rep = cli.get_report("ETHUSDT", "1h")
        assert "DETECTED ANOMALIES" in rep
        assert "Predictive Divergence" in rep


def test_operator_cli_run_repl_interactive():
    cli = OperatorCLI(db_path=":memory:", provider_type="mock")
    ctx = _create_sample_context("BTCUSDT", "1h")
    cli.context_provider.update_context(ctx)

    # Sequence of user commands: status -> report -> switch -> query -> exit
    inputs = [
        "",
        "   ",
        "status",
        "report",
        "switch ETHUSDT 15m",
        "How is volatility?",
        "exit",
    ]

    with patch("builtins.input", side_effect=inputs):
        cli.run_repl(default_symbol="BTCUSDT", default_timeframe="1h")

    # Test EOFError
    with patch("builtins.input", side_effect=EOFError):
        cli.run_repl(default_symbol="BTCUSDT", default_timeframe="1h")


def test_scripts_operator_cli_main_dispatch():
    from scripts.operator_cli import main as cli_main

    with patch("sys.argv", ["operator_cli.py", "--db-path", ":memory:", "status", "--symbol", "BTCUSDT"]):
        rc = cli_main()
        assert rc == 0

    with patch("sys.argv", ["operator_cli.py", "--db-path", ":memory:", "ask", "Explain risks", "--symbol", "BTCUSDT"]):
        rc = cli_main()
        assert rc == 0

    with patch("sys.argv", ["operator_cli.py", "--db-path", ":memory:", "report", "--symbol", "BTCUSDT"]):
        rc = cli_main()
        assert rc == 0

    with patch("sys.argv", ["operator_cli.py", "--db-path", ":memory:", "repl", "--symbol", "BTCUSDT"]):
        with patch.object(OperatorCLI, "run_repl") as mock_repl:
            rc = cli_main()
            assert rc == 0
            mock_repl.assert_called_once()

