"""v3.2 agent guards: the AI proposes and narrates, but cannot add a number."""

from __future__ import annotations

import pytest

from src.idea_agent import (
    IdeaAgentError,
    explanation_or_facts,
    facts_text,
    parse_translation,
    translate_prompt,
)

RESULT = {
    "code": "NO_SE_DISTINGUE",
    "text": "No se distingue del azar con estos datos.",
    "ci": (-0.166, 0.431),
    "trades": 139,
    "mean_r": 0.129,
    "win_pct": 28.8,
    "random_best": 0.114,
    "attempts": 2,
    "reserved_bars": 1545,
}


def test_prompt_lists_only_allowed_entries_and_keeps_user_text():
    prompt = translate_prompt("compro rupturas")
    assert "donchian_20" in prompt and "compro rupturas" in prompt
    assert "control_random" not in prompt


def test_valid_translation():
    raw = (
        '{"entry":"donchian_20","side":"LONG","sl_atr":2,'
        '"tp_atr":6,"max_bars":120,"note":"ruptura"}'
    )
    p = parse_translation(raw)
    assert p["entry"] == "donchian_20" and p["sl_atr"] == 2.0 and p["max_bars"] == 120


def test_code_fences_are_accepted():
    raw = '```json\n{"no_cabe":"usa noticias"}\n```'
    assert parse_translation(raw) == {"no_cabe": "usa noticias"}


@pytest.mark.parametrize(
    "raw",
    [
        "no es json",
        '{"entry":"magia","side":"LONG","sl_atr":2,"tp_atr":6,"max_bars":120}',
        '{"entry":"donchian_20","side":"X","sl_atr":2,"tp_atr":6,"max_bars":120}',
        '{"entry":"donchian_20","side":"LONG","sl_atr":0,"tp_atr":6,"max_bars":120}',
        '{"entry":"donchian_20","side":"LONG","sl_atr":2,"tp_atr":6}',
        '{"entry":"donchian_20","side":"LONG","sl_atr":2,"tp_atr":6,"max_bars":0}',
        "[1,2]",
    ],
)
def test_bad_translations_are_rejected(raw):
    with pytest.raises(IdeaAgentError):
        parse_translation(raw)


def test_explanation_with_engine_numbers_passes():
    text = "Con 139 operaciones la media fue +0.129 R, cerca del azar (0.114)."
    assert explanation_or_facts(text, RESULT) == (text, True)


def test_rounded_engine_number_passes():
    text = "La media fue 0.13 R y ganó 29 % de las veces."
    assert explanation_or_facts(text, RESULT)[1] is True


def test_invented_number_falls_back_to_facts():
    text = "Con 139 operaciones tendrías 72 % de acierto."
    out, used_ai = explanation_or_facts(text, RESULT)
    assert used_ai is False
    assert out == facts_text(RESULT)


@pytest.mark.parametrize("word", ["compra", "rentable", "garantizado", "vende"])
def test_action_or_promise_words_fall_back(word):
    assert explanation_or_facts(f"Esto es {word}.", RESULT)[1] is False


def test_empty_or_negative_mismatch_falls_back():
    assert explanation_or_facts("", RESULT)[1] is False
    assert explanation_or_facts("La media fue -0.129 R.", RESULT)[1] is False


def test_cut_off_explanation_falls_back_to_facts():
    text = "Tus resultados con 139 operaciones muestran una media de"
    assert explanation_or_facts(text, RESULT)[1] is False


def test_thousands_separator_is_one_number():
    result = dict(
        RESULT, final_capital=1799.0, capital=1000.0, worst_streak=4, hold_final=1031.0
    )
    assert (
        explanation_or_facts("Terminaste con $1,799 desde $1,000.", result)[1] is True
    )
    assert explanation_or_facts("Terminaste con $1,800.", result)[1] is False


def test_decimal_comma_is_not_a_thousands_separator():
    assert explanation_or_facts("La media fue +0,129 R.", RESULT)[1] is True
