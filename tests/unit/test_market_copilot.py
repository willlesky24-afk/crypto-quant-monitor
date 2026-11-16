"""Web copilot: the AI may only talk with numbers the engine already produced."""

from __future__ import annotations

from src.market_copilot import answer_or_facts, copilot_prompt, facts_from

HOY = {
    "symbol": "BTCUSDT",
    "interval": "1h",
    "price": 64924.01,
    "change_24h_pct": 2.36,
    "regime": "tendencia bajista",
    "volatility": {"status": "Agitado", "percentile": 91.0, "atr_pct": 1.0},
    "cost": {"status": "Sin dato", "spread_pct": None, "percentile": None},
    "zone": {"val": 67385.14, "vah": 80657.95, "poc": 70000.0, "status": "Debajo"},
    "funding": {
        "provider": "OKX",
        "rate_pct": -0.0013,
        "size_percentile": 9.0,
        "records": 293,
    },
    "summary": ["BTCUSDT está en 64,924.01 y viene en tendencia bajista."],
}


def test_facts_list_engine_values_and_mark_missing_ones():
    facts = facts_from(HOY)
    assert "64,924.01" in facts.text and "91" in facts.text
    assert (
        "costo de operar: sin dato" in facts.text.lower()
    )  # None is said, not invented
    assert 64924.01 in facts.allowed and 91.0 in facts.allowed


def test_answer_with_engine_numbers_passes():
    facts = facts_from(HOY)
    text = "El precio está en 64,924.01 y la volatilidad en el percentil 91: el mercado está agitado."
    assert answer_or_facts(text, facts) == (text, True)


def test_invented_number_is_rejected():
    facts = facts_from(HOY)
    text = "El precio podría llegar a 70,500 pronto."
    shown, used_ai = answer_or_facts(text, facts)
    assert used_ai is False and shown == facts.text


def test_advice_words_are_rejected_even_without_numbers():
    facts = facts_from(HOY)
    for text in (
        "Te recomiendo comprar ahora.",
        "Es buen momento para vender.",
        "Deberías entrar en largo.",
    ):
        assert answer_or_facts(text, facts)[1] is False


def test_cut_off_answer_is_rejected():
    facts = facts_from(HOY)
    assert answer_or_facts("El mercado está agitado y", facts)[1] is False


def test_prompt_carries_facts_question_and_rules():
    facts = facts_from(HOY)
    p = copilot_prompt(
        "¿Está caro operar ahora?",
        facts,
        history=[("user", "hola"), ("assistant", "Hola.")],
    )
    assert facts.text in p and "¿Está caro operar ahora?" in p
    assert "no recomiendes" in p.lower() and "solo las cifras" in p.lower()
    assert "hola" in p
