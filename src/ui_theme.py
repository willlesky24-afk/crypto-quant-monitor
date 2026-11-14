"""Visual system of Quant Monitor (docs/diseno/DEC-V01.md).

Swiss technical language in light: the market as a technical sheet where every
figure carries its unit, source and time. Every value below comes from a token
declared in DEC-V01. Data always comes from the engine: a missing value shows as
N/D, never as a placeholder or a zero. Text is escaped because some of it comes
from providers.

Streamlit controls (sidebar, selects, sliders, tabs) are only adjusted through
stable data-testid selectors; their structure is outside our control.
"""

from __future__ import annotations

from html import escape

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
:root {
  --font-text: 'IBM Plex Sans', sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
  --fs-xs: 0.8rem; --fs-s: 1rem; --fs-m: 1.25rem; --fs-l: 1.563rem;
  --fs-xl: 2.441rem; --fs-xxl: 3.052rem;
  --bg: #F2F1EE; --surface: #FAF9F7; --ink: #1C1E21; --ink-soft: #5E6166;
  --line: #D6D2CA; --accent: #86672E; --up: #2F6B4F; --down: #A23B3B;
  --radius: 2px; --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 24px; --s6: 40px;
  --t-fast: 150ms ease-out;
}

/* Base */
.stApp { background: var(--bg); color: var(--ink); }
.stApp, .stApp p, .stApp label, .stApp li, .stApp input, .stApp textarea,
.stApp button, .stApp div[data-testid="stMarkdownContainer"] {
  font-family: var(--font-text);
}
[data-testid="stIconMaterial"], .stApp span[class*="material"] {
  font-family: 'Material Symbols Rounded' !important;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--line); }
h1 { font-family: var(--font-text); font-weight: 600 !important; font-size: var(--fs-xl) !important;
  letter-spacing: -0.02em; color: var(--ink) !important; line-height: 1.05 !important; }
h2, h3 { font-family: var(--font-text); font-weight: 600 !important; letter-spacing: -0.01em;
  color: var(--ink) !important; line-height: 1.15 !important; }

/* Streamlit controls (limited by the environment) */
[data-testid="stTabs"] button[role="tab"] p { font-size: var(--fs-s); font-weight: 500; }
[data-baseweb="tab-highlight"] { background-color: var(--accent) !important; }
.stButton > button {
  background: var(--ink); color: var(--surface); border: 1px solid var(--ink);
  border-radius: var(--radius); font-weight: 500; min-height: 44px;
  transition: background var(--t-fast);
}
.stButton > button p { color: var(--surface); }
.stButton > button:hover { background: #3A3D42; border-color: #3A3D42; color: var(--surface); }
.stButton > button:focus-visible, a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
[data-testid="stMetric"] { background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); padding: var(--s3) var(--s4); }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
  font-family: var(--font-mono) !important; font-size: var(--fs-m) !important;
  color: var(--ink) !important; white-space: normal !important; }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
  color: var(--ink-soft) !important; font-size: var(--fs-xs) !important; white-space: normal !important; }

/* Market header */
.market-head { border-top: 2px solid var(--ink); padding-top: var(--s3); margin: var(--s4) 0 var(--s5); }
.market-head .name { font-size: var(--fs-m); font-weight: 600; }
.market-head .price { font-family: var(--font-mono); font-size: var(--fs-xxl); font-weight: 500;
  letter-spacing: -0.03em; line-height: 1; margin: var(--s2) 0; font-variant-numeric: tabular-nums; }
.market-head .change { font-family: var(--font-mono); font-size: var(--fs-m); margin-left: var(--s3); white-space: nowrap; display: inline-block; }
.up { color: var(--up); } .down { color: var(--down); }
.source { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--ink-soft); }

/* Technical sheet */
.sheet { border-top: 1px solid var(--ink); margin-bottom: var(--s5); }
.sheet-row { display: grid; grid-template-columns: 9rem 1fr; gap: var(--s4);
  padding: var(--s3) 0; border-bottom: 1px solid var(--line); transition: border-color var(--t-fast); }
.sheet-row:hover { border-bottom-color: var(--accent); }
.sheet-label { font-size: var(--fs-s); font-weight: 500; }
.sheet-value { white-space: nowrap; font-family: var(--font-mono); font-size: var(--fs-m); font-variant-numeric: tabular-nums; }
.sheet-status { font-size: var(--fs-xs); font-weight: 600; margin-left: var(--s2); color: var(--ink-soft); }
.sheet-status.bad { color: var(--down); } .sheet-status.warn { color: var(--accent); } .sheet-status.good { color: var(--up); }
.sheet-note { font-size: var(--fs-xs); color: var(--ink-soft); margin-top: var(--s1); }
.scale { position: relative; height: 2px; background: var(--line); margin: var(--s2) 0 var(--s1); max-width: 22rem; }
.scale-fill { position: absolute; left: 0; top: 0; bottom: 0; background: var(--accent); }
.scale-mark { position: absolute; top: -5px; width: 2px; height: 12px; background: var(--ink); }

.reading p { max-width: 40rem; }
.reading-title, .label-head { font-size: var(--fs-s); font-weight: 600; color: var(--ink);
  border-top: 2px solid var(--ink); padding-top: var(--s2); margin: var(--s4) 0 var(--s2); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] *,
.stRadio [data-testid="stWidgetLabel"] + div p, .stApp ::placeholder { color: var(--ink-soft) !important; opacity: 1; }
.reading p { font-size: 0.9rem; line-height: 1.6; color: var(--ink-soft); margin: 0 0 var(--s2); }
.side-state { border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
  padding: var(--s2) 0; margin-bottom: var(--s3); }
.side-state > div:first-child { color: var(--up) !important; font-weight: 600 !important; }
.state-line { display: flex; gap: var(--s2); align-items: baseline; font-size: var(--fs-s);
  padding: var(--s3) 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
  margin: var(--s4) 0; }
.state-dot { width: 10px; height: 10px; border-radius: var(--radius); flex: none; transform: translateY(1px); }
.footnote { font-size: var(--fs-xs); color: var(--ink-soft); }

/* Shared blocks on other screens */
.meter-grid { display: grid; gap: 0 var(--s5); margin: var(--s3) 0 var(--s4);
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); border-top: 1px solid var(--ink); }
.meter { padding: var(--s3) 0; border-bottom: 1px solid var(--line); display: flex;
  flex-direction: column; gap: var(--s1); }
.meter-head { display: flex; justify-content: space-between; gap: var(--s2); align-items: baseline; }
.meter-title { font-size: var(--fs-xs); font-weight: 600; color: var(--ink-soft); }
.meter-value { font-family: var(--font-mono); font-size: var(--fs-l); color: var(--ink);
  font-variant-numeric: tabular-nums; }
.meter-note { font-size: var(--fs-xs); color: var(--ink-soft); line-height: 1.4; }
.tag { font-size: var(--fs-xs); font-weight: 600; color: var(--ink-soft); }
.tag-good { color: var(--up); } .tag-bad { color: var(--down); } .tag-warn { color: var(--accent); }
.bar-track { position: relative; height: 2px; background: var(--line); margin: var(--s2) 0 var(--s1); }
.bar-fill { position: absolute; left: 0; top: 0; bottom: 0; background: var(--accent); }
.bar-dot { position: absolute; top: -5px; width: 2px; height: 12px; background: var(--ink); }
.panel { border-top: 1px solid var(--line); padding: var(--s3) 0; margin-bottom: var(--s3); }
.panel p { margin: 0 0 var(--s2); font-size: var(--fs-s); line-height: 1.6; max-width: 46rem; }
.alert-row { border-left: 2px solid var(--accent); padding: var(--s2) var(--s3); margin-bottom: var(--s2);
  background: var(--surface); }
.alert-row b { display: block; font-family: var(--font-mono); font-size: var(--fs-xs); font-weight: 500; }
.alert-row span { font-size: var(--fs-s); color: var(--ink); line-height: 1.5; }
.justification-card, .strategy-preset-card, .verdict-card { background: var(--surface);
  border: 1px solid var(--line); border-radius: var(--radius); padding: var(--s4); margin-bottom: var(--s3); }
.metric-pill { display: inline-block; font-size: var(--fs-xs); margin-right: var(--s3); color: var(--ink-soft); }

@media (max-width: 640px) {
  .source span { display: block; }
  .source .sep { display: none; }
  .sheet-row { grid-template-columns: 1fr; gap: var(--s1); }
  .market-head .price { font-size: var(--fs-xl); }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
"""


def value_area_position(price: float, val: float, vah: float) -> float | None:
    """Percent of the way from VAL to VAH; outside 0-100 means outside the zone."""
    if vah <= val:
        return None
    return 100.0 * (price - val) / (vah - val)


def bar_position(value: float | None) -> float | None:
    return None if value is None else max(0.0, min(100.0, value))


def gauge_html(value: float | None) -> str:
    """Half-circle gauge for a 0-100 value; no arc is drawn when it is missing."""
    arc = "M 8 50 A 42 42 0 0 1 92 50"
    track = f'<path d="{arc}" fill="none" stroke="#D6D2CA" stroke-width="3"/>'
    indicator = ""
    if value is not None:
        shown = bar_position(value)
        indicator = (
            f'<path d="{arc}" fill="none" stroke="#86672E" stroke-width="3" '
            f'pathLength="100" stroke-dasharray="{shown:.1f} 100"/>'
        )
    return f'<svg viewBox="0 0 100 56" width="110" height="62">{track}{indicator}</svg>'


def market_header(
    name: str, price: str, change_pct: float | None, source: tuple[str, str]
) -> str:
    """The one figure that leads the screen, with its source and time."""
    change = ""
    if change_pct is not None:
        tone = "up" if change_pct > 0 else "down" if change_pct < 0 else ""
        change = f'<span class="change {tone}">{change_pct:+.2f} % 24 h</span>'
    return (
        f'<div class="market-head"><div class="name">{escape(name)}</div>'
        f'<div><span class="price">{escape(price)}</span>{change}</div>'
        f'<div class="source"><span>{escape(source[0])}</span>'
        f'<span class="sep"> · </span><span>{escape(source[1])}</span></div></div>'
    )


def zone_scale(
    price: float, val: float, vah: float
) -> tuple[tuple[float, float] | None, float | None]:
    """Value area as a stretch on a scale wide enough to contain the price.

    Returns the area's start and end and the price, all as 0-100 positions, so a
    price outside the area still sits inside the drawing instead of at an edge.
    """
    if vah <= val:
        return None, None
    low, high = min(val, price), max(vah, price)
    width = high - low
    pad = 0.08 * width
    low, high = low - pad, high + pad

    def place(x: float) -> float:
        return 100.0 * (x - low) / (high - low)

    return (place(val), place(vah)), place(price)


def sheet_row(
    label: str,
    value: str | None,
    status: str,
    note: str,
    *,
    tone: str = "",
    fill: float | None = None,
    mark: float | None = None,
    span: tuple[float, float] | None = None,
    show_value: bool = True,
) -> str:
    """One line of the technical sheet; a missing value reads N/D, never zero."""
    scale = ""
    if fill is not None or mark is not None or span is not None:
        inner = ""
        if fill is not None:
            inner += f'<div class="scale-fill" style="width:{bar_position(fill):.1f}%"></div>'
        if span is not None:
            start, end = bar_position(span[0]), bar_position(span[1])
            inner += (
                f'<div class="scale-fill" style="left:{start:.1f}%;'
                f'width:{end - start:.1f}%"></div>'
            )
        if mark is not None:
            inner += (
                f'<div class="scale-mark" style="left:{bar_position(mark):.1f}%"></div>'
            )
        scale = f'<div class="scale">{inner}</div>'
    shown = escape(value) if value is not None else "N/D"
    value_html = f'<span class="sheet-value">{shown}</span>' if show_value else ""
    status_html = (
        f'<span class="sheet-status {tone}">{escape(status)}</span>' if status else ""
    )
    return (
        '<div class="sheet-row">'
        f'<div class="sheet-label">{escape(label)}</div><div>'
        f"{value_html}{status_html}"
        f'{scale}<div class="sheet-note">{escape(note)}</div></div></div>'
    )


def state_line(level: str, text: str) -> str:
    color = {
        "VERDE": "var(--up)",
        "AMARILLO": "var(--accent)",
        "ROJO": "var(--down)",
    }.get(level, "var(--line)")
    return (
        f'<div class="state-line"><span class="state-dot" style="background:{color}">'
        f"</span><span>{escape(text)}</span></div>"
    )


def meter_card(
    title: str,
    value: str | None,
    status: str,
    note: str,
    *,
    tone: str = "",
    bar: float | None = None,
    dot: float | None = None,
    gauge: str = "",
) -> str:
    tag = f"tag tag-{tone}" if tone else "tag"
    visual = gauge
    if bar is not None:
        visual += (
            '<div class="bar-track">'
            f'<div class="bar-fill" style="width:{bar_position(bar):.1f}%"></div></div>'
        )
    if dot is not None:
        visual += (
            '<div class="bar-track">'
            f'<div class="bar-dot" style="left:{bar_position(dot):.1f}%"></div></div>'
        )
    return (
        '<div class="meter"><div class="meter-head">'
        f'<span class="meter-title">{escape(title)}</span>'
        f'<span class="{tag}">{escape(status)}</span></div>'
        f'<div class="meter-value">{escape(value) if value is not None else "N/D"}</div>'
        f'{visual}<div class="meter-note">{escape(note)}</div></div>'
    )


def alert_row(market: str, text: str) -> str:
    return (
        f'<div class="alert-row"><b>{escape(market)}</b>'
        f"<span>{escape(text)}</span></div>"
    )


def method_card(name: str, idea: str, suffers: str) -> str:
    return (
        f'<div class="meter"><span class="meter-title">{escape(name)}</span>'
        f'<div class="meter-note">{escape(idea)}</div>'
        f'<div class="meter-note"><b>Sufre cuando:</b> {escape(suffers)}</div></div>'
    )
