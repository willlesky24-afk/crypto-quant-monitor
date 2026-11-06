"""v3.2 agent: turns a sentence into a rule and narrates the engine's result.

The AI never decides or calculates. Its rule proposal is parsed against a closed
list and the user confirms it on screen. Its explanation is shown only if every
number already came from the engine and no action or promise word appears;
otherwise the plain engine facts are shown.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .idea_verifier import ENTRIES, SIDES

_FORBIDDEN = ("compra", "compre", "vende", "venda", "rentable", "garantiz")
_THOUSANDS = re.compile(r"\b[1-9]\d{0,2}(?:,\d{3})+\b")
_NUMBER = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


class IdeaAgentError(ValueError):
    """The AI output could not be used."""


def translate_prompt(text: str) -> str:
    return (
        "Traduce la idea de trading a JSON. Responde solo el JSON, sin comentarios.\n"
        f'Claves: "entry" (una de {list(ENTRIES)}), "side" (una de {list(SIDES)}), '
        '"sl_atr", "tp_atr" (numeros > 0), "max_bars" (entero > 0), "note" (breve).\n'
        "Significados: trend_ema tendencia; momentum_rsi momentum; volume_direction "
        "volumen con vela a favor; profile_value_area fuera de zona de valor; "
        "donchian_20 ruptura; tsmom_180 direccion reciente; bollinger_20_2 y "
        "reversion_rsi reversion.\n"
        'Si la idea no cabe en estas reglas responde {"no_cabe": "motivo"}. No '
        "inventes una aproximacion.\n"
        f"Idea: {text}"
    )


def parse_translation(raw: str) -> dict[str, Any]:
    clean = re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip()
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as exc:
        raise IdeaAgentError("La IA no devolvio una regla legible.") from exc
    if not isinstance(data, dict):
        raise IdeaAgentError("La IA no devolvio una regla legible.")
    if "no_cabe" in data:
        return {"no_cabe": str(data["no_cabe"])}
    if data.get("entry") not in ENTRIES or data.get("side") not in SIDES:
        raise IdeaAgentError("La IA propuso una regla fuera de la lista.")
    try:
        sl, tp, bars = (
            float(data["sl_atr"]),
            float(data["tp_atr"]),
            int(data["max_bars"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise IdeaAgentError("A la regla le faltan valores.") from exc
    if sl <= 0 or tp <= 0 or bars <= 0:
        raise IdeaAgentError("La regla tiene valores no positivos.")
    return {
        "entry": data["entry"],
        "side": data["side"],
        "sl_atr": sl,
        "tp_atr": tp,
        "max_bars": bars,
        "note": str(data.get("note", "")),
    }


def facts_text(result: dict[str, Any]) -> str:
    parts = [result["text"], f"Operaciones: {result['trades']}."]
    if "final_capital" in result:
        parts.append(
            f"Capital inicial: {result['capital']:.0f}. "
            f"Capital final en el pasado: {result['final_capital']:.0f}. "
            f"Peor racha: {result['worst_streak']} perdidas. "
            f"Solo mantener desde el inicio: {result['hold_final']:.0f}."
        )
    if result.get("mean_r") is not None:
        parts.append(f"R neta media: {result['mean_r']:+.3f}.")
    if result.get("random_best") is not None:
        parts.append(f"Mejor corrida al azar: {result['random_best']:+.3f}.")
    return " ".join(parts)


def explain_prompt(result: dict[str, Any]) -> str:
    return (
        "Explica este resultado a un principiante en 3 frases en espanol. Usa solo "
        "estas cifras, sin calcular otras. No recomiendes operar ni prometas nada.\n"
        f"{facts_text(result)}"
    )


def _allowed(result: dict[str, Any]) -> set[float]:
    values = [
        result.get(k)
        for k in (
            "trades",
            "mean_r",
            "win_pct",
            "random_best",
            "attempts",
            "reserved_bars",
            "capital",
            "final_capital",
            "worst_streak",
            "max_drawdown_pct",
            "hold_final",
        )
    ]
    values += list(result.get("ci") or ())
    allowed: set[float] = set()
    for value in values:
        if value is None:
            continue
        allowed.update(round(float(value), d) for d in (0, 1, 2, 3))
    return allowed


def explanation_or_facts(text: str, result: dict[str, Any]) -> tuple[str, bool]:
    """Return the AI text if it passes the guards, else the engine facts."""
    lowered = text.lower()
    allowed = _allowed(result)
    grouped = _THOUSANDS.sub(lambda m: m.group(0).replace(",", ""), text)
    numbers = [float(n.replace(",", ".")) for n in _NUMBER.findall(grouped)]
    valid = (
        text.rstrip().endswith((".", "!", "?"))  # a cut-off answer is not shown
        and not any(word in lowered for word in _FORBIDDEN)
        and all(n in allowed for n in numbers)
    )
    return (text, True) if valid else (facts_text(result), False)
