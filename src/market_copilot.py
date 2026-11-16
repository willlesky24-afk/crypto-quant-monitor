"""Web copilot: plain-language answers about one market, with engine numbers only.

Why it is built like this:
- The AI never calculates. It receives the facts of the "Hoy" screen as text
  and may only repeat those numbers. Any other number (a price target, an
  invented probability) discards the answer and the engine facts are shown.
- It never advises. Answers with action or promise words are discarded too,
  even without numbers ("te recomiendo comprar").
- A missing value is written as "sin dato", never as zero.
- Images are not accepted: the active provider (DeepSeek) does not read them,
  and numbers read from a picture could not pass this control anyway.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_FORBIDDEN = (
    "compra",
    "compre",
    "vende",
    "venda",
    "rentable",
    "garantiz",
    "recomiend",
    "deberías",
    "deberias",
    "buen momento",
    "entrar en largo",
    "entrar en corto",
)
_THOUSANDS = re.compile(r"\b[1-9]\d{0,2}(?:,\d{3})+\b")
_NUMBER = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
# Fixed context numbers the facts themselves use (24 h change, 70 % value area,
# 0-100 percentile scale, 300-bar window).
_CONTEXT = (24.0, 70.0, 100.0, 300.0, 0.0)


@dataclass
class Facts:
    text: str
    allowed: set[float] = field(default_factory=set)


def _fmt(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}"


def facts_from(hoy: dict[str, Any]) -> Facts:
    """Facts text and the set of numbers the AI is allowed to use."""
    lines: list[str] = []
    values: list[float] = []

    def add(label: str, value: float | None, text: str | None = None) -> None:
        if value is None:
            lines.append(f"{label}: sin dato.")
            return
        values.append(float(value))
        lines.append(f"{label}: {text if text is not None else _fmt(value)}.")

    lines.append(f"Mercado: {hoy['symbol']}, velas de {hoy['interval']}.")
    add("Precio", hoy.get("price"))
    change = hoy.get("change_24h_pct")
    add("Cambio en 24 h (%)", change, None if change is None else f"{change:+.2f} %")
    # The regime code is internal English; the Spanish summary below describes it.
    vol = hoy.get("volatility") or {}
    add(
        "Volatilidad, percentil frente a su historia (0 a 100)",
        vol.get("percentile"),
        None
        if vol.get("percentile") is None
        else f"{vol['percentile']:.0f} ({vol.get('status', '')})",
    )
    add("Movimiento típico por vela, ATR (% del precio)", vol.get("atr_pct"))
    cost = hoy.get("cost") or {}
    add(
        "Costo de operar",
        cost.get("spread_pct"),
        None
        if cost.get("spread_pct") is None
        else f"spread {cost['spread_pct']:.3f} %",
    )
    zone = hoy.get("zone") or {}
    if zone.get("val") is not None and zone.get("vah") is not None:
        values += [float(zone["val"]), float(zone["vah"])]
        lines.append(
            f"Zona de valor (70 % del volumen de las últimas 300 velas): de {_fmt(zone['val'])} "
            f"a {_fmt(zone['vah'])}; el precio está {str(zone.get('status', '')).lower()}."
        )
    else:
        lines.append("Zona de valor: sin dato.")
    funding = hoy.get("funding")
    if funding and not funding.get("error"):
        add(
            "Funding (%)",
            funding.get("rate_pct"),
            None
            if funding.get("rate_pct") is None
            else f"{funding['rate_pct']:+.4f} %",
        )
        add(
            "Tamaño del funding, percentil",
            funding.get("size_percentile"),
            None
            if funding.get("size_percentile") is None
            else f"{funding['size_percentile']:.0f}",
        )
        if funding.get("records") is not None:
            values.append(float(funding["records"]))
    for line in hoy.get("summary") or []:
        lines.append(line)

    allowed: set[float] = set(_CONTEXT)
    digits = re.findall(r"\d+", str(hoy.get("interval", "")))
    allowed.update(float(d) for d in digits)
    for value in values:
        for d in (0, 1, 2, 3, 4):
            allowed.add(round(value, d))
            allowed.add(round(abs(value), d))
    return Facts("\n".join(lines), allowed)


def copilot_prompt(question: str, facts: Facts, history: list[tuple[str, str]]) -> str:
    talk = "\n".join(
        f"{'Usuario' if role == 'user' else 'Copiloto'}: {text}"
        for role, text in history[-6:]
    )
    return (
        "Eres el copiloto de Quant Monitor. Respondes en español claro a un ingeniero que no es "
        "trader profesional.\n"
        "Reglas:\n"
        "- Usa solo las cifras de los DATOS, copiadas tal cual con su signo y separador de miles. "
        "No calcules ni inventes cifras, objetivos de precio ni probabilidades.\n"
        "- No recomiendes comprar, vender ni entrar; no digas si es buen momento. Si te lo piden, "
        "explica qué describen los datos y que la decisión es del usuario.\n"
        "- Si un dato dice 'sin dato', dilo así.\n"
        "- Máximo 120 palabras. Termina con punto.\n\n"
        f"DATOS:\n{facts.text}\n\n"
        f"CONVERSACIÓN PREVIA:\n{talk or '(ninguna)'}\n\n"
        f"PREGUNTA: {question}\n"
    )


def answer_or_facts(text: str, facts: Facts) -> tuple[str, bool]:
    """Return the AI answer if it passes the controls, else the engine facts."""
    lowered = text.lower()
    grouped = _THOUSANDS.sub(lambda m: m.group(0).replace(",", ""), text)
    numbers = [float(n.replace(",", ".")) for n in _NUMBER.findall(grouped)]
    valid = (
        text.rstrip().endswith((".", "!", "?"))
        and not any(word in lowered for word in _FORBIDDEN)
        and all(n in facts.allowed or abs(n) in facts.allowed for n in numbers)
    )
    return (text, True) if valid else (facts.text, False)
