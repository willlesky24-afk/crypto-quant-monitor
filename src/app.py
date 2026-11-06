from __future__ import annotations

import asyncio
import math
import os
import sys
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv

# Ensure project root directory is on sys.path for cloud deployment (Streamlit Cloud, Render, etc.)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Synchronize Streamlit Cloud secrets into os.environ
try:
    if hasattr(st, "secrets"):
        for sec_k, sec_v in st.secrets.items():
            if isinstance(sec_v, str) and not os.getenv(sec_k):
                os.environ[sec_k] = sec_v
except Exception:
    pass

# Local credentials: .env decides here. It runs after the secrets, because reading
# secrets.toml makes Streamlit overwrite the environment with its own values.
if not os.getenv("CQM_SKIP_DOTENV"):  # tests must never read real credentials
    load_dotenv(_ROOT / ".env", override=True)

try:
    from src.ai_agent.context_builder import ContextBuilder
    from src.ai_providers.factory import ProviderFactory
    from src.constants import LIVE_HISTORY_BARS
    from src.daily_summary import (
        AGITATED_PERCENTILE,
        CALM_PERCENTILE,
        build_market_summary,
        format_price,
        market_conditions,
    )
    from src.data_loader import BinanceDataLoader
    from src.decision_engine import DecisionEngine
    from src.engine import MarketEngine
    from src.forex_data_loader import ForexDataError, ForexDataLoader
    from src.forex_sessions import get_forex_session_status
    from src.funding_rates import (
        FundingSource,
        FundingUnavailableError,
        funding_snapshot,
        provider_from_env,
    )
    from src.idea_agent import (
        IdeaAgentError,
        explain_prompt,
        explanation_or_facts,
        parse_translation,
        translate_prompt,
    )
    from src.idea_verifier import (
        ENTRIES,
        METHODS,
        MIN_TRADES,
        IdeaSpec,
        IdeaVerifierError,
        load_history,
        past_story,
        verify_idea,
    )
    from src.indicators import TechnicalIndicators
    from src.market_intelligence import MarketIntelligence
    from src.notifications.channels.discord import DiscordWebhookChannel
    from src.notifications.channels.telegram import TelegramChannel
    from src.notifications.channels.webhook import WebhookChannel
    from src.notifications.dispatcher import NotificationDispatcher
    from src.notifications.models import NotificationPriority, SignalEvent
    from src.operator_assistant.assistant import OperatorAssistant
    from src.operator_assistant.models import OperatorQuery
    from src.operator_assistant.on_demand_context import (
        build_on_demand_context,
        resolve_mentioned_symbol,
    )
    from src.operator_service.interfaces import InMemoryMarketContextProvider
    from src.operator_service.storage.sqlite_provider import SQLiteMarketContextProvider
    from src.position_sizing import (
        PositionSizingError,
        compute_position_plan,
        quote_to_usd,
        stop_from_atr,
    )
    from src.predictive_engine import PredictiveEngine
    from src.quant_score import QuantScore
    from src.regime_classifier import RegimeClassifier
    from src.risk_engine import RiskEngine
    from src.signal_engine import SignalEngine
    from src.ui_theme import (
        THEME_CSS,
        alert_row,
        gauge_html,
        meter_card,
        method_card,
        value_area_position,
    )
    from src.unusual_radar import build_markets, run_radar
    from src.volume_profile import VolumeProfile
except ImportError:
    from ai_agent.context_builder import ContextBuilder
    from ai_providers.factory import ProviderFactory
    from constants import LIVE_HISTORY_BARS
    from daily_summary import (
        AGITATED_PERCENTILE,
        CALM_PERCENTILE,
        build_market_summary,
        format_price,
        market_conditions,
    )
    from data_loader import BinanceDataLoader
    from decision_engine import DecisionEngine
    from engine import MarketEngine
    from forex_data_loader import ForexDataError, ForexDataLoader
    from forex_sessions import get_forex_session_status
    from funding_rates import (
        FundingSource,
        FundingUnavailableError,
        funding_snapshot,
        provider_from_env,
    )
    from idea_agent import (
        IdeaAgentError,
        explain_prompt,
        explanation_or_facts,
        parse_translation,
        translate_prompt,
    )
    from idea_verifier import (
        ENTRIES,
        METHODS,
        MIN_TRADES,
        IdeaSpec,
        IdeaVerifierError,
        load_history,
        past_story,
        verify_idea,
    )
    from indicators import TechnicalIndicators
    from market_intelligence import MarketIntelligence
    from notifications.channels.discord import DiscordWebhookChannel
    from notifications.channels.telegram import TelegramChannel
    from notifications.channels.webhook import WebhookChannel
    from notifications.dispatcher import NotificationDispatcher
    from notifications.models import NotificationPriority, SignalEvent
    from operator_assistant.assistant import OperatorAssistant
    from operator_assistant.models import OperatorQuery
    from operator_assistant.on_demand_context import (
        build_on_demand_context,
        resolve_mentioned_symbol,
    )
    from operator_service.interfaces import InMemoryMarketContextProvider
    from operator_service.storage.sqlite_provider import SQLiteMarketContextProvider
    from position_sizing import (
        PositionSizingError,
        compute_position_plan,
        quote_to_usd,
        stop_from_atr,
    )
    from predictive_engine import PredictiveEngine
    from quant_score import QuantScore
    from regime_classifier import RegimeClassifier
    from risk_engine import RiskEngine
    from signal_engine import SignalEngine
    from ui_theme import (
        THEME_CSS,
        alert_row,
        gauge_html,
        meter_card,
        value_area_position,
    )
    from unusual_radar import build_markets, run_radar
    from volume_profile import VolumeProfile


st.set_page_config(
    page_title="Quant Monitor",
    page_icon="📊",
    layout="wide",
)

# =====================================================================
# CUSTOM NEON CYBER FINANCE THEME & STYLING
# =====================================================================
st.markdown(THEME_CSS, unsafe_allow_html=True)

st.title("Quant Monitor")

# =====================================================================
# SIDEBAR: MASTER MARKET SELECTOR (CRYPTO VS FOREX)
# =====================================================================
st.sidebar.subheader("Mercado Activo")
market_choice = st.sidebar.radio(
    "Selecciona el Mercado:",
    ["🪙 Criptomonedas (24/7)", "💱 Divisas Forex (Lun - Vie)"],
    index=0,
)

is_forex = "Forex" in market_choice

# Live Market Status & Session Schedule
if is_forex:
    forex_status = get_forex_session_status()
    status_color = "#036340" if forex_status.is_market_open else "#BD5B5B"
    st.sidebar.markdown(
        f"""
        <div style="background: #FFFFFF; border: 1px solid rgba(25, 29, 35, 0.35); border-radius: 14px; padding: 12px 14px; margin-bottom: 12px;">
            <div style="font-weight: 700; font-size: 0.84rem; color: {status_color};">{forex_status.status_headline}</div>
            <div style="font-size: 0.76rem; color: #717782; margin-top: 4px;">🕒 {forex_status.current_utc_time}</div>
            <div style="font-size: 0.74rem; color: #8A7A56; margin-top: 3px;">📌 {forex_status.weekend_reopen_info}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.sidebar.expander("🕒 Horarios de Sesiones Bancarias (UTC)", expanded=False):
        for s_name, s_time in forex_status.session_details.items():
            st.caption(f"**{s_name}:** {s_time}")
else:
    st.sidebar.markdown(
        """
        <div style="background: #FFFFFF; border: 1px solid rgba(3, 99, 64, 0.35); border-radius: 14px; padding: 12px 14px; margin-bottom: 12px;">
            <div style="font-weight: 700; font-size: 0.84rem; color: #036340;">🟢 Mercado Cripto Abierto 24/7</div>
            <div style="font-size: 0.76rem; color: #717782; margin-top: 4px;">Operaciones continuas los 365 días del año sin cierres</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.sidebar.header("Parámetros de Selección")

POPULAR_PAIRS = {
    "🥇 BTC / USDT (Bitcoin)": "BTCUSDT",
    "🥈 ETH / USDT (Ethereum)": "ETHUSDT",
    "⚡ SOL / USDT (Solana)": "SOLUSDT",
    "🪙 BNB / USDT (Binance Coin)": "BNBUSDT",
    "💧 XRP / USDT (Ripple)": "XRPUSDT",
    "🐕 DOGE / USDT (Dogecoin)": "DOGEUSDT",
    "🔷 ADA / USDT (Cardano)": "ADAUSDT",
    "🔺 AVAX / USDT (Avalanche)": "AVAXUSDT",
    "🔗 LINK / USDT (Chainlink)": "LINKUSDT",
    "💶 EUR / USDT (Euro / Dólar)": "EURUSDT",
    "✍️ Escribir otro par personalizado...": "CUSTOM",
}

if is_forex:
    try:
        forex_pairs = ForexDataLoader().available_pairs()
    except ForexDataError as exc:
        st.sidebar.error(f"Proveedor forex no disponible: {exc}")
        st.stop()
    selected_label = st.sidebar.selectbox(
        "Forex, metales e índices",
        options=list(forex_pairs.keys()),
        index=0,
    )
    symbol = forex_pairs[selected_label]
else:
    selected_label = st.sidebar.selectbox(
        "Par de Criptomoneda",
        options=list(POPULAR_PAIRS.keys()),
        index=0,
    )
    if POPULAR_PAIRS[selected_label] == "CUSTOM":
        symbol = (
            st.sidebar.text_input("Ingresa el símbolo (ej. SUIUSDT)", "BTCUSDT")
            .strip()
            .upper()
        )
    else:
        symbol = POPULAR_PAIRS[selected_label]

interval = st.sidebar.selectbox("Temporalidad", ["15m", "1h", "4h", "1d"], index=1)
limit = st.sidebar.slider(
    "Velas en el gráfico", min_value=150, max_value=1000, value=300, step=50
)

# Caption under title
st.caption("Antes de arriesgar tu dinero, compruébalo.")

# =====================================================================
# SIDEBAR: MODO DE ANÁLISIS (AUTOMÁTICO VS MANUAL / WHAT-IF)
# =====================================================================
advanced_options = st.sidebar.expander("Opciones avanzadas", expanded=False)
sim_mode = advanced_options.radio(
    "Fuente de Parámetros",
    ["🕹️ Manual (Simulador de Escenarios)", "🟢 Automático (En Vivo)"],
    index=1,
)

is_manual_mode = "Manual" in sim_mode

if is_manual_mode:
    advanced_options.markdown("##### Parámetros Forzados")
    from src.regime_classifier import MarketRegime
    from src.strategy_optimizer import OptimizedParameters

    regime_options = [r.value for r in MarketRegime]
    manual_regime_str = advanced_options.selectbox(
        "Régimen de Mercado", regime_options, index=0
    )
    manual_regime = MarketRegime(manual_regime_str)

    manual_pred_score = advanced_options.slider(
        "Predictive Score", 0.0, 1.0, 0.65, 0.05
    )
    manual_prob_cont = advanced_options.slider("P(Continuación)", 0.0, 1.0, 0.60, 0.05)
    manual_tp_mult = advanced_options.slider("Target TP (x ATR)", 1.0, 6.0, 3.0, 0.25)
    manual_sl_mult = advanced_options.slider(
        "Stop Loss SL (x ATR)", 0.5, 4.0, 1.5, 0.25
    )
    manual_tech_weight = advanced_options.slider(
        "Peso Análisis Técnico", 0.1, 0.9, 0.60, 0.05
    )


# Fetch Market Data (Crypto vs Forex)
@st.cache_data(ttl=60, show_spinner="Cargando mercado...")
def _load_candles(market_symbol, market_interval, bars, forex_market):
    """Streamlit reruns the script on every click; a minute-old closed candle is
    still valid, and re-downloading took about 8 s each time. Errors are not cached.
    """
    if forex_market:
        return ForexDataLoader().get_forex_klines(
            symbol=market_symbol, interval=market_interval, limit=bars
        )
    return BinanceDataLoader().get_klines(
        symbol=market_symbol,
        interval=market_interval,
        limit=bars,
        include_open_candle=False,
    )


try:
    # Analysis always uses the shared history (v3.0); the slider only sets how
    # many candles the chart displays.
    df_raw = _load_candles(symbol, interval, max(limit, LIVE_HISTORY_BARS), is_forex)
except Exception as exc:
    st.error(f"Error cargando datos de mercado para {symbol}: {exc}")
    st.stop()

if df_raw.empty or len(df_raw) < 35:
    st.warning("Datos de mercado insuficientes para ejecutar el análisis cuantitativo.")
    st.stop()

# Enrich technical indicators & volume profile via validated services
indicators_service = TechnicalIndicators()
df = indicators_service.calculate_all(df_raw)

vp_service = VolumeProfile()
profile = vp_service.calculate(df)

# =====================================================================
# MAIN MULTI-TAB INTERFACE
# =====================================================================
tab_today, tab_risk, tab_verifier, tab_advanced = st.tabs(
    ["Hoy", "Mi riesgo", "Probar mi idea", "Avanzado"]
)
tab_radar = tab_today
with tab_today:
    today_summary = st.container()
with tab_advanced:
    st.caption("Herramientas de apoyo. Ninguna sugiere qué operar.")
    tab_live, tab_copilot, tab_settings, tab_guide = st.tabs(
        ["Gráfico", "Copiloto IA", "Notificaciones", "Guía y glosario"]
    )


# =====================================================================
# TAB: CALCULADORA DE RIESGO (v3.1)
# =====================================================================
REGIME_LABELS = {
    "TRENDING_BULL": "Tendencia alcista",
    "TRENDING_BEAR": "Tendencia bajista",
    "RANGING_CONSOLIDATION": "Sin tendencia",
    "HIGH_VOLATILITY_EXPANSION": "Expansión de volatilidad",
}


@st.cache_data(ttl=300, show_spinner=False)
def _load_funding(funding_symbol):
    """Latest funding for the header card, or the reason it is not available."""
    try:
        series = FundingSource(provider_from_env()).fetch(funding_symbol, limit=300)
    except (FundingUnavailableError, requests.RequestException) as exc:
        return {"error": str(exc)}
    return funding_snapshot(series)


def _level_tag(percentile, high_label, low_label):
    if percentile is None:
        return "Sin dato", ""
    if percentile >= AGITATED_PERCENTILE:
        return high_label, "bad"
    if percentile <= CALM_PERCENTILE:
        return low_label, "good"
    return "Normal", ""


def _today_cards(figures, conditions):
    """Four meters built only from engine figures; a gap stays visible as N/D."""
    volatility = conditions.get("volatility_percentile")
    v_status, v_tone = _level_tag(volatility, "Agitado", "Tranquilo")
    cards = [
        meter_card(
            "Volatilidad",
            None if volatility is None else f"{volatility:.0f}",
            v_status,
            f"Percentil frente a su historia. ATR {figures['atr_pct']:.2f} % del precio.",
            tone=v_tone,
            gauge=gauge_html(volatility),
        )
    ]

    cost = conditions.get("spread_percentile")
    c_status, c_tone = _level_tag(cost, "Caro", "Barato")
    spread = figures["spread_pct"]
    cards.append(
        meter_card(
            "Costo de operar",
            None if spread is None else f"{spread:.3f} %",
            c_status,
            "Spread frente al movimiento típico."
            if spread is not None
            else "Este proveedor no da spread.",
            tone=c_tone,
            bar=cost,
        )
    )

    position = value_area_position(figures["price"], figures["val"], figures["vah"])
    if position is None:
        z_status = "Sin dato"
    elif position > 100:
        z_status = "Encima"
    elif position < 0:
        z_status = "Debajo"
    else:
        z_status = "Dentro"
    cards.append(
        meter_card(
            "Zona de valor",
            format_price(figures["price"]),
            z_status,
            f"Entre {format_price(figures['val'])} y {format_price(figures['vah'])}.",
            dot=position,
        )
    )

    if symbol.endswith("=X"):
        change = figures["change_24h_pct"]
        cards.append(
            meter_card(
                "Cambio 24 h",
                None if change is None else f"{change:+.2f} %",
                "Sin dato" if change is None else "Precio",
                "Respecto al cierre de hace 24 horas.",
            )
        )
    else:
        funding = _load_funding(symbol)
        if "error" in funding:
            cards.append(
                meter_card("Apalancamiento", None, "Sin dato", funding["error"])
            )
        else:
            f_status, f_tone = _level_tag(funding["size_percentile"], "Alto", "Bajo")
            cards.append(
                meter_card(
                    "Apalancamiento",
                    f"{funding['rate_pct']:+.4f} %",
                    f_status,
                    f"Funding frente a {funding['records']} registros recientes.",
                    tone=f_tone,
                    bar=funding["size_percentile"],
                )
            )
    return '<div class="meter-grid">' + "".join(cards) + "</div>"


with tab_risk:
    st.subheader("¿Cuánto puedo operar sin arriesgar de más?")
    st.caption(
        f"{symbol}: elige cuánto aceptas perder y calculamos el tamaño. Es información "
        "de tamaño, no una recomendación de entrar. Cuenta en USD y sin apalancamiento."
    )
    last_bar = df.iloc[-1]
    last_close = float(last_bar["close"])
    last_atr = float(last_bar["atr"])
    is_forex_symbol = symbol.endswith("=X")

    r_col1, r_col2 = st.columns(2)
    with r_col1:
        risk_capital = st.number_input(
            "Capital de tu cuenta (USD)", min_value=0.0, value=1000.0, step=100.0
        )
        risk_pct = st.number_input(
            "¿Qué % del capital aceptas perder si sale mal?",
            min_value=0.0,
            max_value=100.0,
            value=1.0,
            step=0.25,
        )
        risk_side_label = st.radio(
            "Tu idea",
            ["Comprar", "Vender (corto)"],
            horizontal=True,
        )
        risk_side = "SHORT" if "corto" in risk_side_label else "LONG"
    with r_col2:
        risk_entry = st.number_input(
            "Precio de entrada", min_value=0.0, value=last_close, format="%.5f"
        )
        risk_atr_mult = st.number_input(
            f"Distancia del stop en ATR (ATR actual: {last_atr:.5f})",
            min_value=0.0,
            value=2.0,
            step=0.25,
        )
        risk_fee = st.number_input(
            "Comisión por lado (%)",
            min_value=0.0,
            value=0.0 if is_forex_symbol else 0.05,
            step=0.01,
            format="%.3f",
        )

    if "spread" in df.columns and math.isfinite(float(last_bar["spread"])):
        risk_spread = float(last_bar["spread"])
        spread_note = f"Spread real de la última vela: {risk_spread:.5f}."
    else:
        risk_spread = 0.0
        spread_note = "Este proveedor no da spread: el cálculo no lo incluye."

    try:
        risk_stop = stop_from_atr(risk_entry, last_atr, risk_atr_mult, risk_side)
        risk_plan = compute_position_plan(
            capital=risk_capital,
            risk_pct=risk_pct,
            entry_price=risk_entry,
            stop_price=risk_stop,
            side=risk_side,
            spread=risk_spread,
            fee_pct=risk_fee,
            quote_to_account=quote_to_usd(symbol, risk_entry),
        )
    except PositionSizingError as exc:
        st.error(f"No se puede calcular: {exc}")
    else:
        st.markdown(
            '<div class="meter-grid">'
            + meter_card(
                "Tamaño",
                f"{risk_plan.units:,.4f}",
                "Unidades",
                "Cantidad del activo para ese riesgo.",
            )
            + meter_card(
                "Valor de la posición",
                f"${risk_plan.notional:,.2f}",
                "Sin apalancamiento",
                f"De un capital de ${risk_capital:,.2f}.",
            )
            + meter_card(
                "Pérdida si toca el stop",
                f"${risk_plan.max_loss:,.2f}",
                "Máximo previsto",
                "Incluye los costos.",
                tone="warn",
            )
            + meter_card(
                "Costos incluidos",
                f"${risk_plan.costs:,.2f}",
                "Spread y comisión",
                "Entrada y salida.",
            )
            + "</div>",
            unsafe_allow_html=True,
        )
        st.write(
            f"Stop en **{risk_stop:.5f}**, a {risk_plan.stop_distance_pct:.2f} % de la "
            f"entrada. {spread_note}"
        )
        if risk_plan.limited_by_capital:
            st.warning(
                "Tu capital no alcanza para arriesgar ese %, porque no usamos "
                "apalancamiento. El tamaño se limitó a tu capital y arriesgas menos."
            )
        st.info(
            "El stop no es una garantía: con un salto de precio la pérdida puede ser mayor."
        )


# =====================================================================
# TAB: RADAR DE COSAS INUSUALES (v3.1)
# =====================================================================
RADAR_CRYPTO = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "LINKUSDT",
]
RADAR_PAIRS = [
    ("BTCUSDT", "ETHUSDT"),
    ("XAUUSD=X", "XAGUSD=X"),
    ("AUDUSD=X", "NZDUSD=X"),
    ("EURUSD=X", "GBPUSD=X"),
    ("SPX500=X", "NAS100=X"),
]
RADAR_INDICES = ["SPX500=X", "NAS100=X", "US30=X"]


def _radar_fetch(radar_symbol):
    if radar_symbol.endswith("=X"):
        raw = ForexDataLoader().get_forex_klines(
            symbol=radar_symbol, interval=interval, limit=LIVE_HISTORY_BARS
        )
    else:
        raw = BinanceDataLoader().get_klines(
            symbol=radar_symbol,
            interval=interval,
            limit=LIVE_HISTORY_BARS,
            include_open_candle=False,
        )
    return TechnicalIndicators().add_atr(raw)


with tab_radar:
    st.subheader("¿Qué está fuera de lo normal?")
    st.caption(
        f"Compara {len(RADAR_CRYPTO)} criptos, forex y metales con su propia historia "
        f"en {interval}. Un aviso dice que algo es raro, no qué hacer. Mientras más "
        "mercados se revisan, más exigente es el listón."
    )
    if st.button("Escanear mercados"):
        try:
            radar_forex = list(ForexDataLoader().available_pairs().values())
            radar_forex_error = {}
        except ForexDataError as exc:
            radar_forex = []
            radar_forex_error = {"Forex": str(exc)}
        with st.spinner("Revisando mercados..."):
            radar_markets, radar_failed = build_markets(
                _radar_fetch, RADAR_CRYPTO + radar_forex
            )
            try:
                radar_source = FundingSource(provider_from_env())
                radar_funding, radar_funding_failed = build_markets(
                    radar_source.fetch, RADAR_CRYPTO
                )
            except FundingUnavailableError as exc:
                radar_funding, radar_funding_failed = {}, {"Funding": str(exc)}
            st.session_state["radar_funding"] = (
                {k: funding_snapshot(v) for k, v in radar_funding.items()},
                radar_funding_failed,
            )
            st.session_state["radar_result"] = run_radar(
                radar_markets,
                [
                    RADAR_CRYPTO,
                    [m for m in radar_forex if m not in RADAR_INDICES],
                    [m for m in radar_forex if m in RADAR_INDICES],
                ],
                RADAR_PAIRS,
                {**radar_forex_error, **radar_failed},
            )

    radar_result = st.session_state.get("radar_result")
    if radar_result is not None:
        if radar_result.alpha is None:
            st.warning("Ningún mercado tiene historia suficiente para medir.")
        else:
            st.write(
                f"Se hicieron {radar_result.tests} mediciones; solo avisa lo que "
                f"esté en el {radar_result.alpha * 100:.2f} % más extremo."
            )
        for radar_alert in radar_result.alerts:
            st.markdown(
                alert_row(radar_alert.market, radar_alert.text),
                unsafe_allow_html=True,
            )
        if radar_result.alpha is not None and not radar_result.alerts:
            st.success("Nada fuera de lo normal en este momento.")
        for radar_market, radar_reason in radar_result.failed.items():
            st.error(f"{radar_market} no se pudo revisar: {radar_reason}")

    if "radar_funding" in st.session_state:
        funding_rows, funding_failed = st.session_state["radar_funding"]
        st.markdown(f"##### Apalancamiento en cripto ({provider_from_env().upper()})")
        st.caption(
            "Funding: lo que paga un lado de los contratos perpetuos al otro. Valores "
            "grandes indican mucha gente apalancada igual. Compara solo con los "
            "registros disponibles (unos 3 meses en OKX), así que no genera avisos."
        )
        if funding_rows:
            st.dataframe(
                [
                    {
                        "Mercado": k,
                        "Funding (%)": round(v["rate_pct"], 4),
                        "Mayor que el % de registros": round(v["size_percentile"]),
                        "Registros": v["records"],
                    }
                    for k, v in funding_rows.items()
                ],
                hide_index=True,
            )
        for funding_market, funding_reason in funding_failed.items():
            st.error(f"Funding de {funding_market}: {funding_reason}")


# =====================================================================
# TAB: VERIFICADOR DE IDEAS (v3.2)
# =====================================================================
ENTRY_LABELS = {
    "trend_ema": "Tendencia (precio y medias 50/200 alineados)",
    "momentum_rsi": "Momentum RSI (50 a 70 sube, bajo 30 baja)",
    "volume_direction": "Volumen alto con vela a favor",
    "profile_value_area": "Precio fuera de la zona de valor",
    "donchian_20": "Ruptura del canal de 20 velas",
    "tsmom_180": "Dirección de las últimas 180 velas",
    "bollinger_20_2": "Reversión desde bandas de Bollinger",
    "reversion_rsi": "Reversión RSI (bajo 30 sube, sobre 70 baja)",
}

with tab_verifier:
    st.subheader("¿Tu regla resiste los datos?")
    st.caption(
        f"Prueba una regla en {symbol} {interval} con costos reales. Reservamos el "
        "último 20 % de los datos y cada intento sube el listón, para que probar "
        "variantes hasta que una gane no cuente como evidencia."
    )
    v_sides = ["AMBOS", "LONG", "SHORT"] if symbol.endswith("=X") else ["LONG"]

    def _ask_ai(prompt):
        provider = ProviderFactory.create_provider()
        if not hasattr(provider, "generate_response"):
            raise IdeaAgentError("No hay un proveedor de IA configurado.")
        response = asyncio.run(provider.generate_response(prompt))
        if response.metadata.get("status") == "fallback":
            raise IdeaAgentError(response.content)
        return response.content

    st.markdown("##### Elige un método")
    st.caption("Métodos conocidos entre traders. Elegir uno no significa que funcione.")
    gallery_cols = st.columns(2)
    for gallery_index, gallery_method in enumerate(METHODS):
        with gallery_cols[gallery_index % 2]:
            st.markdown(
                method_card(
                    gallery_method["name"],
                    gallery_method["idea"],
                    gallery_method["suffers"],
                ),
                unsafe_allow_html=True,
            )
            if st.button("Usar este método", key=f"use_{gallery_method['entry']}"):
                st.session_state.update(
                    v_entry=gallery_method["entry"],
                    v_side="LONG",
                    v_sl=gallery_method["sl_atr"],
                    v_tp=gallery_method["tp_atr"],
                    v_bars=gallery_method["max_bars"],
                )
                st.rerun()

    st.markdown("##### O escribe tu propia regla")
    v_text = st.text_area(
        "Describe tu idea (opcional)",
        placeholder="Quiero entrar cuando rompa el máximo de 20 velas, con stop amplio",
    )
    if st.button("Interpretar con IA") and v_text.strip():
        try:
            v_rule = parse_translation(_ask_ai(translate_prompt(v_text)))
        except IdeaAgentError as exc:
            st.error(f"No se pudo interpretar: {exc}")
        else:
            if "no_cabe" in v_rule:
                st.warning(f"Esa idea no cabe en las reglas: {v_rule['no_cabe']}")
            elif v_rule["side"] not in v_sides:
                st.warning("En cripto spot solo se puede probar en largo.")
            else:
                st.session_state.update(
                    v_entry=v_rule["entry"],
                    v_side=v_rule["side"],
                    v_sl=v_rule["sl_atr"],
                    v_tp=v_rule["tp_atr"],
                    v_bars=v_rule["max_bars"],
                )
                st.info("Revisa abajo la regla propuesta antes de verificar.")

    v_col1, v_col2 = st.columns(2)
    with v_col1:
        v_entry = st.selectbox(
            "Regla de entrada",
            list(ENTRIES),
            format_func=ENTRY_LABELS.get,
            key="v_entry",
        )
        v_side = st.radio(
            "Lado",
            v_sides,
            horizontal=True,
            key="v_side",
            format_func={
                "AMBOS": "Ambos lados",
                "LONG": "Solo compras",
                "SHORT": "Solo ventas",
            }.get,
        )
    with v_col2:
        st.session_state.setdefault("v_sl", 2.0)
        st.session_state.setdefault("v_tp", 6.0)
        st.session_state.setdefault("v_bars", 120)
        v_sl = st.number_input("Stop (ATR)", min_value=0.5, step=0.5, key="v_sl")
        v_tp = st.number_input("Objetivo (ATR)", min_value=0.5, step=0.5, key="v_tp")
        v_bars = st.number_input("Máximo de velas", min_value=1, step=10, key="v_bars")

    v_capital = st.number_input(
        "Capital de ejemplo (USD)", min_value=10.0, value=1000.0, step=100.0
    )
    if st.button("Verificar idea"):
        st.session_state["verifier_attempts"] = (
            st.session_state.get("verifier_attempts", 0) + 1
        )
        v_spec = IdeaSpec(symbol, interval, v_entry, v_side, v_sl, v_tp, int(v_bars))
        try:
            with st.spinner("Probando contra el azar..."):
                v_history = load_history(symbol, interval)
                st.session_state["verifier_source"] = (
                    "datos en vivo de la sesión (poca historia)"
                    if v_history is None
                    else f"{len(v_history):,} velas guardadas"
                )
                st.session_state["verifier_result"] = verify_idea(
                    df if v_history is None else v_history,
                    v_spec,
                    st.session_state["verifier_attempts"],
                    capital=v_capital,
                )
        except IdeaVerifierError as exc:
            st.session_state.pop("verifier_result", None)
            st.error(f"No se puede probar: {exc}")

    v_result = st.session_state.get("verifier_result")
    if v_result is not None:
        v_box = st.info if v_result["code"] == "MERECE_ESTUDIO" else st.warning
        v_box(v_result["text"])
        st.markdown(
            f'<div class="panel"><p>{escape(past_story(v_result))}</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="meter-grid">'
            + meter_card(
                "Operaciones",
                str(v_result["trades"]),
                "En datos explorados",
                f"Mínimo para concluir: {MIN_TRADES}.",
            )
            + meter_card(
                "R neta media",
                None if v_result["mean_r"] is None else f"{v_result['mean_r']:+.3f}",
                "Después de costos",
                "Ganancia media por unidad de riesgo.",
            )
            + meter_card(
                "Mejor azar (R)",
                None
                if v_result["random_best"] is None
                else f"{v_result['random_best']:+.3f}",
                "Referencia",
                "Mejor resultado de entradas al azar.",
            )
            + meter_card(
                "Intento",
                str(v_result["attempts"]),
                "Sube el listón",
                "Cada intento exige más.",
            )
            + "</div>",
            unsafe_allow_html=True,
        )
        if v_result["ci"] is not None:
            st.write(
                f"Intervalo de la R media: {v_result['ci'][0]:+.3f} a "
                f"{v_result['ci'][1]:+.3f}. Quedaron {v_result['reserved_bars']} velas "
                "sin usar."
            )
        if st.button("Explicar con IA"):
            try:
                v_text_out, v_used_ai = explanation_or_facts(
                    _ask_ai(explain_prompt(v_result)), v_result
                )
            except IdeaAgentError as exc:
                st.error(f"La IA no está disponible: {exc}")
            else:
                st.write(v_text_out)
                if not v_used_ai:
                    st.caption(
                        "Se muestran los datos del motor: la IA no pasó el control."
                    )
        st.caption(
            f"Datos: {st.session_state['verifier_source']}. Resultado histórico, "
            "no una recomendación de operar."
        )


# =====================================================================
# TAB 1: LIVE MONITOR
# =====================================================================
with tab_live:
    # 1. Execute Analysis Pipeline
    market_engine = MarketEngine()
    analysis = market_engine.analyze(df, profile)
    signal_engine = SignalEngine()
    signal = signal_engine.evaluate(analysis, profile)
    risk_engine = RiskEngine()
    risk = risk_engine.evaluate(analysis, profile)
    summary = build_market_summary(
        symbol, df, analysis, profile, RegimeClassifier().classify(df).regime
    )
    with today_summary:
        conditions = market_conditions(df)
        st.markdown(
            f'<div class="eyebrow">Mercado de hoy / <b>{escape(symbol)} · '
            f"{escape(interval)}</b></div>",
            unsafe_allow_html=True,
        )
        st.subheader("¿Qué está pasando hoy?")
        st.markdown(
            _today_cards(summary["figures"], conditions), unsafe_allow_html=True
        )
        st.markdown(
            '<div class="panel">'
            + "".join(f"<p>{escape(line)}</p>" for line in summary["lines"])
            + "</div>",
            unsafe_allow_html=True,
        )
        conditions_box = {
            "VERDE": st.success,
            "AMARILLO": st.warning,
            "ROJO": st.error,
            "NO_DISPONIBLE": st.info,
        }[conditions["level"]]
        conditions_box(conditions["text"])
        st.caption("Descripción del mercado, no una recomendación de operar.")
    intel_engine = MarketIntelligence()
    intel = intel_engine.evaluate(analysis)
    quant_score_engine = QuantScore()
    score = quant_score_engine.calculate(analysis, signal, risk)

    if is_manual_mode:
        from src.predictive_engine import PredictiveResult
        from src.regime_classifier import RegimeResult

        regime_res = RegimeResult(
            timestamp=pd.Timestamp(df.iloc[-1]["timestamp"]),
            regime=manual_regime,
            confidence=0.90,
            features_used={"manual_override": 1.0},
        )
        pred_res = PredictiveResult(
            timestamp=pd.Timestamp(df.iloc[-1]["timestamp"]),
            probability_continuation=manual_prob_cont,
            probability_reversal=round(1.0 - manual_prob_cont, 4),
            predictive_score=manual_pred_score,
            confidence=0.85,
            regime_context=manual_regime.value,
            direction_bias="LONG"
            if manual_regime == MarketRegime.TRENDING_BULL
            else (
                "SHORT" if manual_regime == MarketRegime.TRENDING_BEAR else "NEUTRAL"
            ),
            features_used={},
        )
        opt_params = OptimizedParameters(
            regime=manual_regime.value,
            volatility_state="MANUAL",
            atr_tp_multiplier=manual_tp_mult,
            atr_sl_multiplier=manual_sl_mult,
            expected_rr=round(manual_tp_mult / max(manual_sl_mult, 0.01), 2),
            sample_size=100,
            confidence=0.90,
            validation_period={},
        )
        decision_engine = DecisionEngine(
            technical_weight=manual_tech_weight,
            predictive_weight=1.0 - manual_tech_weight,
        )
        decision = decision_engine.evaluate(
            signal=signal,
            risk=risk,
            intelligence=intel,
            predictive=pred_res,
            optimized_params=opt_params,
            regime=regime_res.regime,
            technical_score=score["score"],
            technical_score_short=score.get("score_short"),
            predictive_mode=True,
        )
    else:
        regime_classifier = RegimeClassifier()
        regime_res = regime_classifier.classify(df)

        predictive_engine = PredictiveEngine()
        pred_res = predictive_engine.evaluate(df, current_regime_res=regime_res)

        decision_engine = DecisionEngine()
        decision = decision_engine.evaluate(
            signal=signal,
            risk=risk,
            intelligence=intel,
            predictive=pred_res,
            regime=regime_res.regime,
            technical_score=score["score"],
            technical_score_short=score.get("score_short"),
            predictive_mode=True,
        )

    last_bar = df.iloc[-1]
    curr_price = float(last_bar["close"])
    trade_plan = risk_engine.plan_from_decision(
        decision=decision.decision,
        direction=decision.direction,
        reference_price=curr_price,
        atr=last_bar.get("atr"),
        sl_multiplier=decision.sl_multiplier,
        tp_multiplier=decision.tp_multiplier,
    )
    risk_decimals = 5 if is_forex else (6 if curr_price < 1 else 2)

    def format_risk_level(value):
        return f"${value:,.{risk_decimals}f}" if value is not None else "No disponible"

    if is_manual_mode:
        st.warning(
            f"🕹️ **Modo Simulación Manual Activo:** Régimen forzado a `{manual_regime.value}` • "
            f"Predictive Score: `{manual_pred_score:.2f}` • TP: `{manual_tp_mult:.2f}x ATR` • SL: `{manual_sl_mult:.2f}x ATR`."
        )

    # 3. Interactive Plotly Chart (Candles, EMAs, Volume Profile)
    df_chart = df.tail(limit)
    fig_live = go.Figure()

    # Candlestick with Fluorescent Green and Neon Coral
    fig_live.add_trace(
        go.Candlestick(
            x=df_chart["timestamp"],
            open=df_chart["open"],
            high=df_chart["high"],
            low=df_chart["low"],
            close=df_chart["close"],
            name="Precio",
            increasing_line_color="#036340",
            increasing_fillcolor="#036340",
            decreasing_line_color="#BD5B5B",
            decreasing_fillcolor="#BD5B5B",
        )
    )

    # EMAs with Cyan and Magenta
    if "ema_50" in df.columns:
        fig_live.add_trace(
            go.Scatter(
                x=df_chart["timestamp"],
                y=df_chart["ema_50"],
                name="EMA 50",
                line={"color": "#8A7A56", "width": 2},
            )
        )
    if "ema_200" in df.columns:
        fig_live.add_trace(
            go.Scatter(
                x=df_chart["timestamp"],
                y=df_chart["ema_200"],
                name="EMA 200",
                line={"color": "#191D23", "width": 2},
            )
        )

    # Volume Profile Horizontal Levels with Neon Glow Accents
    if profile.get("poc"):
        fig_live.add_hline(
            y=profile["poc"],
            line={"color": "#8A7A56", "width": 2, "dash": "dash"},
            annotation_text="POC",
            annotation_font_color="#8A7A56",
        )
    if profile.get("vah"):
        fig_live.add_hline(
            y=profile["vah"],
            line={"color": "#036340", "width": 1.5, "dash": "dot"},
            annotation_text="VAH",
            annotation_font_color="#036340",
        )
    if profile.get("val"):
        fig_live.add_hline(
            y=profile["val"],
            line={"color": "#BD5B5B", "width": 1.5, "dash": "dot"},
            annotation_text="VAL",
            annotation_font_color="#BD5B5B",
        )

    fig_live.update_layout(
        height=620,
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font={
            "family": "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto",
            "color": "#191D23",
        },
        xaxis={
            "gridcolor": "rgba(255, 255, 255, 0.06)",
            "linecolor": "rgba(25, 29, 35, 0.2)",
        },
        yaxis={
            "gridcolor": "rgba(255, 255, 255, 0.06)",
            "linecolor": "rgba(25, 29, 35, 0.2)",
        },
    )
    st.plotly_chart(fig_live, width="stretch")

# =====================================================================
# TAB 2: AI COPILOT
# =====================================================================
with tab_copilot:
    st.subheader("Copiloto de mercado")
    st.caption(
        "Conversa sobre el mercado actual. No ejecuta operaciones. Para probar una regla usa Probar mi idea."
    )

    try:
        curr_p = float(df.iloc[-1]["close"])

        live_signal_event = SignalEvent(
            timestamp=pd.Timestamp(df.iloc[-1]["timestamp"]),
            symbol=symbol,
            timeframe=interval,
            action=decision.decision
            if trade_plan["status"] == "ACTIVADA" and trade_plan["entry_confirmed"]
            else "WAIT",
            direction=trade_plan["direction"],
            confidence=decision.confidence
            if decision.confidence <= 1.0
            else decision.confidence / 100.0,
            predictive_score=pred_res.predictive_score,
            regime=regime_res.regime.value,
            reasoning=f"{decision.reasoning} Estado: {trade_plan['status']}. {trade_plan['reason']}",
            price=curr_p,
            quant_score=score["score"],
            stop_loss=trade_plan["stop_loss"],
            take_profit=trade_plan["take_profit"],
            signal_id=f"live-{symbol}-{interval}",
            metadata={
                "risk_reward_ratio": trade_plan["gross_risk_reward"],
                "risk_reward_basis": "bruto_sin_costes"
                if trade_plan["gross_risk_reward"] is not None
                else None,
                "signal_status": trade_plan["status"],
                "entry_confirmed": trade_plan["entry_confirmed"],
                "atr": trade_plan["atr"],
                "positives": decision.positives,
                "warnings": decision.warnings,
            },
        )

        context_builder = ContextBuilder()
        current_market_context = context_builder.build_context(
            signal_event=live_signal_event,
            technical_indicators={
                "rsi": float(df.iloc[-1].get("rsi", 50.0)),
                "adx": float(df.iloc[-1].get("adx", 20.0)),
                "volume": float(df.iloc[-1].get("volume", 0.0)),
            },
            volume_profile=profile,
            metadata={
                "source": "Streamlit Live Dashboard",
                "signal_status": trade_plan["status"],
                "entry_confirmed": trade_plan["entry_confirmed"],
            },
        )

        db_path = os.getenv("DATABASE_PATH", "data/market_contexts.db")
        try:
            copilot_provider = SQLiteMarketContextProvider(db_path=db_path)
        except Exception:
            copilot_provider = InMemoryMarketContextProvider()

        import asyncio

        def _safe_async_run(coro):
            if not asyncio.iscoroutine(coro) and not isinstance(coro, asyncio.Future):
                return coro
            try:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                if loop.is_running():
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(
                        max_workers=1
                    ) as executor:
                        return executor.submit(lambda: asyncio.run(coro)).result()
                else:
                    return loop.run_until_complete(coro)
            except Exception as exc:
                raise exc

        try:
            copilot_provider.update_context(current_market_context)
        except Exception:
            pass

        active_llm_provider = ProviderFactory.create_provider()
        copilot_assistant = OperatorAssistant(
            context_provider=copilot_provider,
            ai_provider=active_llm_provider,
        )
        with st.container():
            provider_name = active_llm_provider.__class__.__name__.replace(
                "Provider", ""
            )
            model_name = getattr(active_llm_provider, "model", "standard")

            # Track active conversation asset in session state to maintain conversation thread across follow-up queries
            if "copilot_active_symbol" not in st.session_state:
                st.session_state["copilot_active_symbol"] = symbol
                st.session_state["copilot_active_timeframe"] = interval
                st.session_state["copilot_active_is_forex"] = is_forex

            if "prev_sidebar_symbol" not in st.session_state:
                st.session_state["prev_sidebar_symbol"] = symbol
            elif st.session_state["prev_sidebar_symbol"] != symbol:
                st.session_state["copilot_active_symbol"] = symbol
                st.session_state["copilot_active_timeframe"] = interval
                st.session_state["copilot_active_is_forex"] = is_forex
                st.session_state["prev_sidebar_symbol"] = symbol

            active_sym_display = st.session_state.get("copilot_active_symbol", symbol)
            active_tf_display = st.session_state.get(
                "copilot_active_timeframe", interval
            ).upper()

            st.caption(
                f"🧠 Modelo: **{provider_name}** (`{model_name}`) | "
                f"🎯 Par en Conversación: **`{active_sym_display}`** ({active_tf_display}) | "
                f"Memoria Conversacional Activa"
            )

            if st.button("Limpiar conversación", key="btn_clear_chat"):
                st.session_state["copilot_chat_history"] = []
                st.session_state["copilot_active_symbol"] = symbol
                st.session_state["copilot_active_timeframe"] = interval
                st.session_state["copilot_active_is_forex"] = is_forex
                st.rerun()

            # Initialize chat history
            if (
                "copilot_chat_history" not in st.session_state
                or not st.session_state["copilot_chat_history"]
            ):
                market_label = "Divisas Forex Globales" if is_forex else "Criptomonedas"
                st.session_state["copilot_chat_history"] = [
                    {
                        "role": "assistant",
                        "content": (
                            f"👋 **Hola, soy tu copiloto de mercado.**\n\n"
                            f"Puedo responder todas tus inquietudes sobre el mercado de **{market_label}** en **lenguaje cotidiano** y con datos cuantitativos en tiempo real:\n"
                            f"- Pregúntame qué significa algo que ves en el mercado.\n"
                            f"- Puedes **adjuntar una foto o captura de pantalla de un gráfico** abajo para que lo analice visualmente.\n"
                            f"- O pregúntame sobre la señal, volumen POC y niveles de riesgo de **{symbol}**."
                        ),
                    }
                ]

            # File/Image Uploader
            with st.expander(
                "📎 Adjuntar Gráficos o Archivos para Análisis Multimodal (Fotos, TradingView o CSV)",
                expanded=False,
            ):
                uploaded_files = st.file_uploader(
                    "Sube una o varias capturas de gráficos (PNG, JPG, WEBP) o archivos de datos:",
                    type=["png", "jpg", "jpeg", "webp", "csv", "txt"],
                    accept_multiple_files=True,
                    key="copilot_file_uploader",
                )
                if uploaded_files:
                    img_files = [
                        f for f in uploaded_files if f.type.startswith("image/")
                    ]
                    other_files = [
                        f for f in uploaded_files if not f.type.startswith("image/")
                    ]
                    if img_files:
                        img_cols = st.columns(min(len(img_files), 4))
                        for idx, img_file in enumerate(img_files):
                            with img_cols[idx % len(img_cols)]:
                                st.image(
                                    img_file,
                                    caption=f"📷 {img_file.name}",
                                    width="stretch",
                                )
                    for of in other_files:
                        st.info(f"📄 Archivo cargado: {of.name} ({of.size} bytes)")

            # Render Chat Messages
            chat_container = st.container()
            with chat_container:
                for msg in st.session_state["copilot_chat_history"]:
                    with st.chat_message(
                        msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"
                    ):
                        st.markdown(msg["content"])
                        if msg.get("images"):
                            chat_img_cols = st.columns(min(len(msg["images"]), 3))
                            for idx, img_info in enumerate(msg["images"]):
                                with chat_img_cols[idx % len(chat_img_cols)]:
                                    st.image(
                                        img_info["bytes"],
                                        caption=img_info.get(
                                            "name", f"📷 Gráfico {idx + 1}"
                                        ),
                                        width="stretch",
                                    )
                        elif msg.get("image_bytes"):
                            st.image(msg["image_bytes"], width=300)

            # Handler for Market Scanner Quick Action
            # Chat Input Form
            chat_input_val = st.chat_input(
                "Escribe tu consulta al Copilot (ej. ¿Cuál es el mejor par? o analiza los gráficos adjuntos)..."
            )
            if chat_input_val:
                user_msg = {
                    "role": "user",
                    "content": chat_input_val,
                }
                images_payload = []
                img_bytes = None
                mime_type = "image/png"
                if uploaded_files:
                    for f in uploaded_files:
                        if f.type.startswith("image/"):
                            f_bytes = f.getvalue()
                            images_payload.append(
                                {
                                    "bytes": f_bytes,
                                    "mime_type": f.type,
                                    "name": f.name,
                                }
                            )
                    if images_payload:
                        user_msg["images"] = images_payload
                        # Backwards compatibility for single-image consumers
                        img_bytes = images_payload[0]["bytes"]
                        mime_type = images_payload[0]["mime_type"]
                        user_msg["image_bytes"] = img_bytes

                st.session_state["copilot_chat_history"].append(user_msg)

                # Dynamically resolve mentioned symbol using active conversation asset as fallback
                curr_active_sym = st.session_state.get("copilot_active_symbol", symbol)
                curr_active_tf = st.session_state.get(
                    "copilot_active_timeframe", interval
                )
                curr_active_fx = st.session_state.get(
                    "copilot_active_is_forex", is_forex
                )

                target_sym, target_tf, target_is_fx = resolve_mentioned_symbol(
                    chat_input_val, curr_active_sym, curr_active_tf
                )

                # Persist the active conversation target
                st.session_state["copilot_active_symbol"] = target_sym
                st.session_state["copilot_active_timeframe"] = target_tf
                st.session_state["copilot_active_is_forex"] = target_is_fx

                # Build on-demand context if target differs from current dashboard context or needs refresh
                if target_sym != symbol or target_tf != interval:
                    with st.spinner(
                        f"Analizando métricas cuantitativas en vivo para {target_sym} ({target_tf})..."
                    ):
                        od_ctx = build_on_demand_context(
                            target_sym, target_tf, target_is_fx
                        )
                        if od_ctx is not None:
                            try:
                                copilot_provider.update_context(od_ctx)
                            except Exception:
                                pass

                with st.spinner(
                    "AI Copilot razonando y formulando respuesta en español..."
                ):
                    try:
                        query_obj = OperatorQuery(
                            query=chat_input_val,
                            symbol=target_sym,
                            timeframe=target_tf,
                            operator_id="dashboard_operator",
                            metadata={
                                "images": images_payload if images_payload else None,
                                "image_bytes": img_bytes,
                                "mime_type": mime_type,
                                "market_type": "Forex" if target_is_fx else "Crypto",
                                "conversation_history": [
                                    {"role": m["role"], "content": m["content"]}
                                    for m in st.session_state["copilot_chat_history"][
                                        :-1
                                    ][-6:]
                                ],
                            },
                        )
                        copilot_res = _safe_async_run(copilot_assistant.ask(query_obj))
                        st.session_state["copilot_chat_history"].append(
                            {
                                "role": "assistant",
                                "content": copilot_res.answer,
                            }
                        )
                        st.rerun()
                    except Exception as cop_err:
                        st.error(f"Error procesando la consulta: {cop_err}")

    except Exception as cop_err:
        st.error(f"Error inicializando AI Copilot: {cop_err}")


# =====================================================================
# TAB 3: NOTIFICATION SETTINGS
# =====================================================================
with tab_settings:
    st.subheader("Notificaciones")

    c_cfg1, c_cfg2 = st.columns([1, 1])

    with c_cfg1:
        st.markdown("### Canales de Notificación")

        def _get_sec(key: str, default: str = "") -> str:
            try:
                if key in st.secrets:
                    return str(st.secrets[key])
            except Exception:
                pass
            return os.getenv(key, default)

        enable_discord = st.checkbox(
            "Habilitar Discord Webhook", value=bool(_get_sec("DISCORD_WEBHOOK_URL"))
        )
        discord_url_input = st.text_input(
            "Discord Webhook URL",
            value=_get_sec("DISCORD_WEBHOOK_URL", ""),
            type="password",
        )

        enable_telegram = st.checkbox(
            "Habilitar Telegram Bot", value=bool(_get_sec("TELEGRAM_BOT_TOKEN"))
        )
        telegram_token_input = st.text_input(
            "Telegram Bot Token",
            value=_get_sec("TELEGRAM_BOT_TOKEN", ""),
            type="password",
        )
        telegram_chat_id_input = st.text_input(
            "Telegram Chat ID",
            value=_get_sec("TELEGRAM_CHAT_ID", ""),
        )

        enable_webhook = st.checkbox(
            "Habilitar Generic Webhook", value=bool(_get_sec("GENERIC_WEBHOOK_URL"))
        )
        generic_url_input = st.text_input(
            "Webhook Target URL",
            value=_get_sec("GENERIC_WEBHOOK_URL", ""),
        )

    with c_cfg2:
        st.markdown("### Filtros y Anti-Spam (Cooldown)")
        min_pred_score = st.slider(
            "Umbral Mínimo de Predictive Score", 0.0, 1.0, 0.60, 0.05
        )
        min_conf = st.slider("Umbral Mínimo de Confianza", 0.0, 1.0, 0.60, 0.05)
        cooldown_sec = st.slider(
            "Tiempo de Cooldown Anti-Spam (Segundos)", 0, 1800, 300, 30
        )
        dry_run_mode = st.toggle(
            "Modo Simulación (Dry-Run / Sin I/O)",
            value=False,
            help="Desactiva esto para que los mensajes lleguen realmente a tu Telegram/Discord.",
        )

    st.markdown("---")
    st.subheader("Prueba de conexión")

    with st.container():
        st.caption(
            "Verifica si tu Bot de Telegram o Webhook de Discord responde correctamente."
        )
        if st.button(
            "🔔 Enviar Notificación de Prueba",
            type="secondary",
            width="stretch",
        ):
            test_channels = []
            if enable_discord and discord_url_input:
                test_channels.append(
                    DiscordWebhookChannel(
                        webhook_url=discord_url_input, dry_run=dry_run_mode
                    )
                )
            if enable_telegram and telegram_token_input and telegram_chat_id_input:
                test_channels.append(
                    TelegramChannel(
                        bot_token=telegram_token_input,
                        chat_id=telegram_chat_id_input,
                        dry_run=dry_run_mode,
                    )
                )
            if enable_webhook and generic_url_input:
                test_channels.append(
                    WebhookChannel(url=generic_url_input, dry_run=dry_run_mode)
                )

            if not test_channels:
                st.warning(
                    "⚠️ Configura y activa al menos un canal (Telegram o Discord) arriba."
                )
            else:
                dispatcher = NotificationDispatcher(
                    channels=test_channels,
                    min_predictive_score=min_pred_score,
                    min_confidence=min_conf,
                    cooldown_seconds=float(cooldown_sec),
                )

                test_signal = SignalEvent(
                    timestamp=pd.Timestamp.now("UTC"),
                    symbol=symbol,
                    timeframe=interval,
                    action="TEST",
                    direction="SIN OPERACIÓN",
                    confidence=0.0,
                    predictive_score=0.0,
                    regime="TRENDING_BULL",
                    reasoning="PRUEBA DE CANAL: no es una señal ni contiene niveles operativos.",
                    price=float(df.iloc[-1]["close"]),
                    quant_score=0.0,
                    signal_id="test-ping-01",
                )

                results = dispatcher.dispatch_signal(
                    test_signal, priority=NotificationPriority.HIGH
                )
                st.info(
                    f"Prueba procesada: {len(results)} resultados de canal; consulta éxito o fallo en la tabla."
                )
                result_rows = [r.to_dict() for r in results]
                st.table(pd.DataFrame(result_rows))


# =====================================================================
# TAB 5: GUÍA & GLOSARIO
# =====================================================================
with tab_guide:
    st.subheader("Guía Rápida & Glosario Cuantitativo")
    st.caption(
        "Referencia institucional de términos, siglas y manual paso a paso de la plataforma."
    )

    g_tab1, g_tab2 = st.tabs(
        [
            "📚 Glosario de Siglas y Métricas",
            "🕹️ Manual: Si tocas esto, obtienes esto",
        ]
    )

    with g_tab1:
        st.markdown("### Diccionario de Siglas Institucionales")

        g_col1, g_col2 = st.columns(2)

        with g_col1:
            st.markdown("""
            #### 🎯 Niveles de Volume Profile y Liquidez
            - **`POC` (Point of Control / Punto de Control):**  
              *Significado:* Nivel de precio exacto donde se transó el mayor volumen de operaciones durante el período analizado.  
              *Uso táctico:* Funciona como un poderoso imán de liquidez y soporte/resistencia gravitacional.
            
            - **`VAH` (Value Area High / Techo del Área de Valor):**  
              *Significado:* Límite superior del rango de precios donde se concentró el 70% del volumen negociado.  
              *Uso táctico:* Resistencia institucional. Si el precio supera el VAH con volumen, indica desequilibrio alcista (*premium* comprador).
            
            - **`VAL` (Value Area Low / Suelo del Área de Valor):**  
              *Significado:* Límite inferior del rango de precios que concentra el 70% del volumen negociado.  
              *Uso táctico:* Soporte institucional. Si el precio pierde el VAL con volumen, indica desequilibrio bajista (*descuento* vendedor).

            #### 🛡️ Gestión de Riesgo y Operativa
            - **`ATR` (Average True Range / Rango Verdadero Promedio):**  
              *Significado:* Métrica matemática de la volatilidad real del mercado expresada en dólares.  
              *Uso táctico:* Permite definir objetivos de ganancia y límites de pérdida dinámicos que se expanden en mercados volátiles y se comprimen en mercados tranquilos.
            
            - **`R:R` (Risk-to-Reward Ratio / Ratio Riesgo-Beneficio):**  
              *Significado:* Plan bruto: distancia desde la entrada ejecutada al TP dividida por la distancia al SL inicial. No equivale al R realizado y no incluye costes ni ejecución garantizada.
              *Ejemplo:* Un plan `1 : 2.0` describe un objetivo a dos unidades de precio por cada unidad hasta el stop inicial.
            
            - **`SL` (Stop Loss):** Nivel de invalidación propuesto. La aplicación no ejecuta órdenes.
            - **`TP` (Take Profit):** Objetivo de precio propuesto, sujeto a confirmación y costes.
            """)

        with g_col2:
            st.markdown("""
            #### 🧠 Modelos Predictivos y Regímenes
            - **`P(Cont)` (Probabilidad de Continuación):**  
              *Significado:* Cálculo estocástico derivado del modelo de Markov que estima la probabilidad de que la siguiente vela mantenga la dirección predominante.
            
            - **`Predictive Score` (0.00 a 1.00):**  
              *Significado:* Puntuación normalizada del motor predictivo probabilístico. Valores > 0.60 señalan alta probabilidad direccional.
            
            - **`Quant Score` (0 a 100):**  
              *Significado:* Puntuación cuantitativa compuesta que integra fuerza de tendencia, momento RSI/ADX, alineación de medias móviles y confluencias de volumen.
            
            - **`Regímenes de Mercado`:**
              - **`TRENDING_BULL`:** Tendencia alcista confirmada (Precio > EMA50 > EMA200).
              - **`TRENDING_BEAR`:** Tendencia bajista confirmada (Precio < EMA50 < EMA200).
              - **`RANGING`:** Mercado en consolidación lateral sin tendencia definida.
              - **`HIGH_VOLATILITY`:** Expansión violenta de rango y riesgo elevado.
              - **`COMPRESSION`:** Rango estrecho que precede a movimientos explosivos.

            #### 📈 Métricas de Backtest y Rendimiento
            - **`Win Rate`:** Porcentaje de operaciones cerradas en ganancia frente al total.
            - **`Profit Factor`:** Ganancia bruta dividida entre pérdida bruta de la muestra simulada; no predice el desempeño futuro.
            - **`Expectativa bruta/neta (R)`:** Media de R por operación matemáticamente verificable; la neta incorpora los costes simulados. N/A indica que no hay riesgo inicial verificable. La cobertura indica cuántas operaciones se excluyeron.
            - **`Max Drawdown %`:** Mayor caída porcentual experimentada desde el punto máximo de capital.
            - **`Sharpe Ratio`:** Rendimiento por unidad de volatilidad, anualizado solo con procedencia y calendario cripto 24/7 acreditados, barras regulares y tasa libre de riesgo supuesta de 0 %. N/A indica que no puede calcularse con fiabilidad.
            - **`MAE / MFE`:** Máxima excursión adversa (*peor momento en contra*) y favorable (*mejor momento a favor*) de cada trade.
            """)

    with g_tab2:
        st.markdown("### Manual Paso a Paso: Si tocas esto, obtienes esto")

        st.markdown("""
        | Sección | Control / Botón | Qué hace al interactuar | Qué obtienes en pantalla |
        | :--- | :--- | :--- | :--- |
        | **Barra Lateral** | **Par de Criptomoneda** | Seleccionas una moneda (BTC, ETH, SOL, etc.) | Descarga en tiempo real las velas institucionales de Binance para ese activo. |
        | **Barra Lateral** | **Temporalidad** | Seleccionas 15m, 1h, 4h o 1d | Cambia el horizonte temporal. Verás cómo el régimen de mercado y las medias móviles se adaptan al marco temporal elegido. |
        | **Barra Lateral** | **Velas Históricas** | Mueves el deslizador (250 a 1000 velas) | Amplía o reduce el historial cargado en memoria (ej. 300 velas en 1d = ~10 meses). |
        | **Barra Lateral** | **Modo de Análisis** | Alternas entre *Automático* y *Manual* | Activa el simulador *What-If* para forzar regímenes, probabilidades y multiplicadores a tu criterio. |
        | **📡 Live Monitor** | **🧠 Diagnóstico** | Pulsas la sub-pestaña | Muestra la decisión ejecutiva (LONG, SHORT o ESPERAR), justificación matemática y confluencias favorables/alertas. |
        | **📡 Live Monitor** | **📋 Plan de riesgo** | Pulsas la sub-pestaña | Muestra estado, entrada propuesta, SL, TP, distancias y R bruto cuando hay datos válidos. Una candidata no equivale a una entrada activada. |
        | **📡 Live Monitor** | **🎯 Niveles** | Pulsas la sub-pestaña | Entrega los precios clave del Área de Valor (POC, VAH, VAL) e indica si el precio está en zona de sobrecompra o descuento. |
        | **📡 Live Monitor** | **🔮 Predicción** | Pulsas la sub-pestaña | Muestra la probabilidad matemática de que la tendencia continúe y el desglose del modelo predictivo. |
        | **📡 Live Monitor** | **🛠️ Datos** | Pulsas la sub-pestaña | Expande la carga técnica en JSON para auditoría cuantitativa o conexión a sistemas externos. |
        | **🤖 AI Copilot** | **💬 Chat AI** | Escribes una duda y pulsas *Enviar Consulta* | Gemini analiza el contexto actual y te responde con explicación de mercado, riesgos y telemetría de latencia. |
        | **🤖 AI Copilot** | **📋 Briefing** | Pulsas la sub-pestaña | Genera un informe diario institucional estructurado con análisis de volatilidad y señales fuertes. |
        | **🤖 AI Copilot** | **🚨 Anomalías** | Pulsas la sub-pestaña | Evalúa si existen divergencias estructurales o anomalías severas de volatilidad en el activo actual. |
        | **📈 Backtest** | **🚀 Ejecutar Backtest** | Pulsas el botón con tus parámetros elegidos | Simula vela por vela la estrategia en el pasado sin repintado y grafica la Curva de Capital, Drawdown y dispersión MAE vs MFE. |
        | **⚙️ Configuración** | **🔔 Notificación de Prueba** | Pulsas el botón de prueba | Envía un ping marcado TEST, sin dirección ni niveles de operación, al canal configurado. |
        """)
