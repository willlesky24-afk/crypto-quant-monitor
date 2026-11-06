"""v3.2 visual system: a calm light theme and the meter cards of the Hoy screen.

Style adapted from the supervisor's reference (Atelier Telemetry). Only the
look is taken from it: every value comes from the engine, and a missing value
shows as N/D rather than as a placeholder or a zero. All text is escaped because
some of it comes from providers.
"""

from __future__ import annotations

from html import escape

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;500;600;700&display=swap');
:root {
  --ink: #191D23; --muted: #717782; --line: rgba(25, 29, 35, 0.08);
  --bronze: #8A7A56; --emerald: #036340; --rose: #BD5B5B; --canvas: #F6F8F9;
  --track: rgba(25, 29, 35, 0.07);
}
.stApp, .stApp p, .stApp label, .stApp li, .stApp span, .stApp div, .stApp input,
.stApp button, .stApp textarea {
  font-family: 'Open Sans', sans-serif;
}
[data-testid="stIconMaterial"], .material-symbols-rounded,
.stApp span[class*="material"] { font-family: 'Material Symbols Rounded' !important; }
.stApp { background: var(--canvas); color: var(--ink); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid var(--line); }
h1 { font-weight: 600 !important; letter-spacing: -0.03em; color: var(--ink) !important; }
h2, h3 { font-weight: 600 !important; letter-spacing: -0.02em; color: var(--ink) !important; }

[data-testid="stTabs"] button[role="tab"] p { font-size: 0.86rem; font-weight: 500; }
[data-testid="stTabs"] button[aria-selected="true"] p { color: var(--ink); font-weight: 600; }
[data-baseweb="tab-highlight"] { background-color: var(--ink) !important; }

.stButton > button {
  background: var(--ink); color: #FFFFFF; border: 1px solid var(--ink);
  border-radius: 999px; font-weight: 600; font-size: 0.8rem; padding: 0.35rem 1.1rem;
}
.stButton > button p { color: #FFFFFF; }
.stButton > button:hover { background: #2B313A; color: #FFFFFF; border-color: #2B313A; }

[data-testid="stMetric"] {
  background: #FFFFFF; border: 1px solid var(--line); border-radius: 16px;
  padding: 12px 14px; height: 100%;
}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
  color: var(--muted) !important; font-size: 0.68rem !important; font-weight: 600 !important;
  letter-spacing: 0.06em; text-transform: uppercase; white-space: normal !important;
}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
  color: var(--ink) !important; font-size: 1.05rem !important; font-weight: 600 !important;
  line-height: 1.25 !important; white-space: normal !important;
  overflow-wrap: break-word; text-overflow: clip !important;
}

.eyebrow { font-size: 0.66rem; font-weight: 600; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--muted); margin-bottom: 2px; }
.eyebrow b { color: var(--bronze); font-weight: 600; }
.meter-grid { display: grid; gap: 12px; margin: 12px 0 16px;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }
.meter { background: #FFFFFF; border: 1px solid var(--line); border-radius: 18px;
  padding: 14px 16px; display: flex; flex-direction: column; gap: 6px; }
.meter-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.meter-title { font-size: 0.66rem; font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--muted); }
.meter-value { font-size: 1.55rem; font-weight: 500; letter-spacing: -0.03em;
  color: var(--ink); line-height: 1.2; }
.meter-note { font-size: 0.74rem; color: var(--muted); line-height: 1.35; }
.tag { font-size: 0.62rem; font-weight: 600; letter-spacing: 0.03em; padding: 2px 8px;
  border-radius: 999px; background: var(--track); color: #45474B; white-space: nowrap; }
.tag-good { background: rgba(3, 99, 64, 0.08); color: #024A30; }
.tag-warn { background: rgba(138, 122, 86, 0.14); color: #5B4E30; }
.tag-bad { background: rgba(189, 91, 91, 0.10); color: #9B4343; }
.bar-track { position: relative; height: 5px; border-radius: 999px; background: var(--track);
  margin: 4px 0 2px; }
.bar-fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 999px;
  background: var(--bronze); }
.bar-dot { position: absolute; top: -3px; width: 11px; height: 11px; margin-left: -5px;
  border-radius: 50%; background: var(--ink); border: 2px solid #FFFFFF; }
.panel { background: #FFFFFF; border: 1px solid var(--line); border-radius: 18px;
  padding: 14px 18px; margin-bottom: 14px; }
.panel p { margin: 0 0 6px; font-size: 0.92rem; line-height: 1.5; color: var(--ink); }
.alert-row { background: #FFFFFF; border: 1px solid var(--line); border-left: 3px solid var(--bronze);
  border-radius: 12px; padding: 10px 14px; margin-bottom: 8px; }
.alert-row b { display: block; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.05em;
  color: var(--ink); }
.alert-row span { font-size: 0.82rem; color: #45474B; line-height: 1.4; }

.justification-card, .strategy-preset-card, .verdict-card {
  background: #FFFFFF; border: 1px solid var(--line); border-radius: 16px; padding: 16px;
  margin-bottom: 12px; color: var(--ink);
}
.justification-header { display: flex; justify-content: space-between; gap: 8px;
  align-items: center; margin-bottom: 8px; }
.justification-title { font-weight: 600; color: var(--ink); }
.justification-text { color: #45474B; font-size: 0.88rem; line-height: 1.5; }
.metric-pill { display: inline-block; padding: 2px 10px; margin: 2px 4px 2px 0; border-radius: 999px;
  font-size: 0.72rem; font-weight: 600; background: var(--track); color: #45474B; }
.metric-pill-green { background: rgba(3, 99, 64, 0.08); color: #024A30; }
.metric-pill-coral { background: rgba(189, 91, 91, 0.10); color: #9B4343; }
.metric-pill-gold, .metric-pill-cyan { background: rgba(138, 122, 86, 0.14); color: #5B4E30; }
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
    track = f'<path d="{arc}" fill="none" stroke="rgba(25,29,35,0.07)" stroke-width="6" stroke-linecap="round"/>'
    indicator = ""
    if value is not None:
        shown = bar_position(value)
        indicator = (
            f'<path d="{arc}" fill="none" stroke="#8A7A56" stroke-width="6" '
            f'stroke-linecap="round" pathLength="100" '
            f'stroke-dasharray="{shown:.1f} 100"/>'
        )
    return f'<svg viewBox="0 0 100 56" width="110" height="62">{track}{indicator}</svg>'


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
