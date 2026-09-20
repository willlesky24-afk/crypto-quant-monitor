from src.alert_engine import AlertEngine
from src.analyzer import MarketAnalyzer
from src.market_intelligence import MarketIntelligence


def test_alert_engine_emits_breakout_rsi_and_volume(analysis_factory, profile):
    analysis = analysis_factory(price=110, rsi=75, volume="Superior al promedio")
    result = AlertEngine().check(analysis, profile)
    assert [alert["type"] for alert in result] == [
        "BREAKOUT_VAH",
        "RSI_OVERBOUGHT",
        "VOLUME_CONFIRMATION",
    ]


def test_alert_engine_emits_breakdown_and_oversold(analysis_factory, profile):
    analysis = analysis_factory(
        price=90,
        rsi=25,
        volume="Inferior al promedio",
    )
    result = AlertEngine().check(analysis, profile)
    assert [alert["type"] for alert in result] == [
        "BREAKDOWN_VAL",
        "RSI_OVERSOLD",
    ]


def test_analyzer_preserves_summary_contract(analysis_factory):
    result = MarketAnalyzer().generate_summary(analysis_factory())
    assert set(result) == {"summary", "conclusion"}
    assert "estructura alcista" in result["summary"]


def test_market_intelligence_preserves_public_contract(analysis_factory):
    result = MarketIntelligence().evaluate(analysis_factory())
    assert set(result) == {
        "state",
        "risk",
        "risk_reason",
        "trend_analysis",
        "momentum",
        "volume",
        "profile",
    }
    assert result["state"] == "🟢 Alta confluencia"
    assert result["risk"] == "Bajo"


def test_analyzer_covers_bearish_extended_medium_score(analysis_factory):
    analysis = analysis_factory(
        trend="Bajista",
        momentum="Fuerte pero extendido",
        volume="Inferior al promedio",
        score=2,
    )
    result = MarketAnalyzer().generate_summary(analysis)
    assert "estructura bajista" in result["summary"]
    assert "señales de extensión" in result["summary"]
    assert "debajo del promedio" in result["summary"]
    assert "faltan confirmaciones" in result["conclusion"]


def test_analyzer_covers_lateral_weak_context(analysis_factory):
    analysis = analysis_factory(
        trend="Lateral",
        momentum="Débil",
        score=0,
    )
    result = MarketAnalyzer().generate_summary(analysis)
    assert "sin una tendencia clara" in result["summary"]
    assert "no presenta suficiente confluencia" in result["conclusion"]


def test_market_intelligence_covers_medium_bearish_state(analysis_factory):
    analysis = analysis_factory(
        trend="Bajista",
        volume="Inferior al promedio",
        score=3,
    )
    result = MarketIntelligence().evaluate(analysis)
    assert result["state"] == "🟡 Contexto interesante"
    assert result["risk"] == "Medio"
    assert "presión vendedora" in result["trend_analysis"]


def test_market_intelligence_covers_weak_lateral_state(analysis_factory):
    result = MarketIntelligence().evaluate(
        analysis_factory(trend="Lateral", score=0)
    )
    assert result["state"] == "🔴 Contexto débil"
    assert result["risk"] == "Bajo"
    assert "tendencia dominante" in result["trend_analysis"]
