from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# Ensure project root directory is on sys.path for cloud deployment (Streamlit Cloud, Render, etc.)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from src.ai_agent.context_builder import ContextBuilder
    from src.ai_providers.factory import ProviderFactory
    from src.anomaly_detection.detector import MarketAnomalyDetector
    from src.backtest_models import BacktestConfig, TradeDirection
    from src.backtest_runner import BacktestRunner
    from src.data_loader import BinanceDataLoader
    from src.decision_engine import DecisionEngine
    from src.engine import MarketEngine
    from src.indicators import TechnicalIndicators
    from src.market_intelligence import MarketIntelligence
    from src.market_reports.generator import MarketReportService
    from src.notifications.channels.discord import DiscordWebhookChannel
    from src.notifications.channels.telegram import TelegramChannel
    from src.notifications.channels.webhook import WebhookChannel
    from src.notifications.dispatcher import NotificationDispatcher
    from src.notifications.models import NotificationPriority, SignalEvent
    from src.operator_assistant.assistant import OperatorAssistant
    from src.operator_assistant.models import OperatorQuery
    from src.operator_service.interfaces import InMemoryMarketContextProvider
    from src.operator_service.storage.sqlite_provider import SQLiteMarketContextProvider
    from src.predictive_engine import PredictiveEngine
    from src.quant_score import QuantScore
    from src.regime_classifier import RegimeClassifier
    from src.report import MarketReport
    from src.risk_engine import RiskEngine
    from src.signal_engine import SignalEngine
    from src.volume_profile import VolumeProfile
except ImportError:
    from ai_agent.context_builder import ContextBuilder
    from ai_providers.factory import ProviderFactory
    from anomaly_detection.detector import MarketAnomalyDetector
    from backtest_models import BacktestConfig, TradeDirection
    from backtest_runner import BacktestRunner
    from data_loader import BinanceDataLoader
    from decision_engine import DecisionEngine
    from engine import MarketEngine
    from indicators import TechnicalIndicators
    from market_intelligence import MarketIntelligence
    from market_reports.generator import MarketReportService
    from notifications.channels.discord import DiscordWebhookChannel
    from notifications.channels.telegram import TelegramChannel
    from notifications.channels.webhook import WebhookChannel
    from notifications.dispatcher import NotificationDispatcher
    from notifications.models import NotificationPriority, SignalEvent
    from operator_assistant.assistant import OperatorAssistant
    from operator_assistant.models import OperatorQuery
    from operator_service.interfaces import InMemoryMarketContextProvider
    from operator_service.storage.sqlite_provider import SQLiteMarketContextProvider
    from predictive_engine import PredictiveEngine
    from quant_score import QuantScore
    from regime_classifier import RegimeClassifier
    from report import MarketReport
    from risk_engine import RiskEngine
    from signal_engine import SignalEngine
    from volume_profile import VolumeProfile



st.set_page_config(
    page_title="Crypto Quant Monitor",
    page_icon="📊",
    layout="wide",
)

# =====================================================================
# CUSTOM NEON CYBER FINANCE THEME & STYLING
# =====================================================================
st.markdown(
    """
    <style>
    /* Neon Cyber Finance Dark Theme */
    :root {
        --bg-main: #07090e;
        --card-bg: rgba(14, 22, 38, 0.85);
        --neon-green: #00ff88;
        --neon-cyan: #00e5ff;
        --neon-coral: #ff2e63;
        --neon-gold: #ffd600;
        --neon-purple: #bd00ff;
        --text-bright: #f0f6fc;
        --text-sub: #8b949e;
    }

    /* Overall App Background & Typography */
    .stApp {
        background-color: var(--bg-main);
        color: var(--text-bright);
    }

    /* Metric Cards: Futuristic Floating Glassmorphism - Compact & Balanced */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(16, 26, 46, 0.9) 0%, rgba(10, 16, 30, 0.95) 100%) !important;
        border: 1px solid rgba(0, 229, 255, 0.22) !important;
        border-radius: 18px !important;
        padding: 10px 14px !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.1) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease !important;
    }

    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: var(--neon-green) !important;
        box-shadow: 0 8px 24px rgba(0, 255, 136, 0.22), inset 0 1px 1px rgba(255, 255, 255, 0.2) !important;
    }

    [data-testid="stMetricLabel"] {
        color: var(--text-sub) !important;
        font-size: 0.74rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
        text-transform: uppercase !important;
        margin-bottom: 2px !important;
    }

    [data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
        color: #ffffff !important;
        font-size: 1.25rem !important;
        font-weight: 700 !important;
        line-height: 1.25 !important;
        text-shadow: 0 0 10px rgba(0, 229, 255, 0.35) !important;
    }

    [data-testid="stMetricDelta"] {
        font-size: 0.75rem !important;
    }

    /* Sleek, Compact Rounded Pill Buttons with Fluorescent Glow */
    .stButton > button {
        border-radius: 20px !important;
        font-weight: 600 !important;
        font-size: 0.80rem !important;
        letter-spacing: 0.3px !important;
        padding: 6px 18px !important;
        border: 1px solid rgba(0, 255, 136, 0.45) !important;
        background: linear-gradient(135deg, rgba(0, 255, 136, 0.14) 0%, rgba(0, 229, 255, 0.10) 100%) !important;
        color: #00ff88 !important;
        box-shadow: 0 2px 12px rgba(0, 255, 136, 0.18) !important;
        transition: all 0.2s ease-in-out !important;
    }

    .stButton > button:hover {
        border-color: #00ff88 !important;
        color: #07090e !important;
        background: linear-gradient(135deg, #00ff88 0%, #00e5ff 100%) !important;
        box-shadow: 0 0 18px rgba(0, 255, 136, 0.65) !important;
        transform: scale(1.01);
    }

    .stButton > button:active {
        transform: scale(0.99);
    }

    /* Download Buttons */
    .stDownloadButton > button {
        border-radius: 20px !important;
        font-weight: 600 !important;
        font-size: 0.80rem !important;
        padding: 6px 18px !important;
        border: 1px solid rgba(0, 229, 255, 0.45) !important;
        background: linear-gradient(135deg, rgba(0, 229, 255, 0.14) 0%, rgba(189, 0, 255, 0.10) 100%) !important;
        color: #00e5ff !important;
        box-shadow: 0 2px 12px rgba(0, 229, 255, 0.18) !important;
        transition: all 0.2s ease !important;
    }

    .stDownloadButton > button:hover {
        border-color: #00e5ff !important;
        color: #07090e !important;
        background: linear-gradient(135deg, #00e5ff 0%, #bd00ff 100%) !important;
        box-shadow: 0 0 18px rgba(0, 229, 255, 0.65) !important;
    }

    /* Sleek, Compact Rounded Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(14, 22, 38, 0.65);
        padding: 4px 6px;
        border-radius: 24px;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 18px !important;
        padding: 5px 16px !important;
        font-size: 0.80rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.2px !important;
        color: var(--text-sub) !important;
        border: none !important;
        transition: all 0.2s ease !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(0, 255, 136, 0.22) 0%, rgba(0, 229, 255, 0.15) 100%) !important;
        color: #00ff88 !important;
        border: 1px solid rgba(0, 255, 136, 0.5) !important;
        box-shadow: 0 0 12px rgba(0, 255, 136, 0.25) !important;
    }

    /* Inputs, Selectboxes, and Text Areas */
    div[data-baseweb="select"] > div {
        border-radius: 20px !important;
        background-color: rgba(14, 22, 38, 0.9) !important;
        border: 1px solid rgba(0, 229, 255, 0.25) !important;
    }

    div[data-baseweb="select"]:hover > div {
        border-color: var(--neon-cyan) !important;
        box-shadow: 0 0 12px rgba(0, 229, 255, 0.3) !important;
    }

    div[data-baseweb="input"] > input {
        border-radius: 18px !important;
    }

    /* Alert / Status Callouts */
    .stAlert {
        border-radius: 22px !important;
        backdrop-filter: blur(10px) !important;
    }

    /* Glowing Titles & Section Headers */
    h1 {
        text-shadow: 0 0 24px rgba(0, 255, 136, 0.35);
    }
    h2, h3 {
        text-shadow: 0 0 16px rgba(0, 229, 255, 0.25);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 Crypto Quant Monitor")
st.caption("Institutional Quantitative Engine • Predictive Intelligence • Real-Time Monitoring & Backtesting")

# =====================================================================
# SIDEBAR: DATA CONTROLS
# =====================================================================
st.sidebar.header("🕹️ Parámetros de Mercado")

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

selected_label = st.sidebar.selectbox(
    "Par de Criptomoneda",
    options=list(POPULAR_PAIRS.keys()),
    index=0,
)

if POPULAR_PAIRS[selected_label] == "CUSTOM":
    symbol = st.sidebar.text_input("Ingresa el símbolo (ej. SUIUSDT)", "BTCUSDT").strip().upper()
else:
    symbol = POPULAR_PAIRS[selected_label]
interval = st.sidebar.selectbox("Temporalidad", ["15m", "1h", "4h", "1d"], index=1)
limit = st.sidebar.slider("Velas Históricas", min_value=250, max_value=1000, value=300, step=50)

# =====================================================================
# SIDEBAR: MODO DE ANÁLISIS (AUTOMÁTICO VS MANUAL / WHAT-IF)
# =====================================================================
st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Modo de Análisis")
sim_mode = st.sidebar.radio(
    "Fuente de Parámetros",
    ["🟢 Automático (En Vivo)", "🕹️ Manual (Simulador de Escenarios)"],
    index=0,
)

is_manual_mode = "Manual" in sim_mode

if is_manual_mode:
    st.sidebar.markdown("##### ⚙️ Parámetros Forzados")
    from src.regime_classifier import MarketRegime
    from src.strategy_optimizer import OptimizedParameters

    regime_options = [r.value for r in MarketRegime]
    manual_regime_str = st.sidebar.selectbox("Régimen de Mercado", regime_options, index=0)
    manual_regime = MarketRegime(manual_regime_str)

    manual_pred_score = st.sidebar.slider("Predictive Score", 0.0, 1.0, 0.65, 0.05)
    manual_prob_cont = st.sidebar.slider("P(Continuación)", 0.0, 1.0, 0.60, 0.05)
    manual_tp_mult = st.sidebar.slider("Target TP (x ATR)", 1.0, 6.0, 3.0, 0.25)
    manual_sl_mult = st.sidebar.slider("Stop Loss SL (x ATR)", 0.5, 4.0, 1.5, 0.25)
    manual_tech_weight = st.sidebar.slider("Peso Análisis Técnico", 0.1, 0.9, 0.60, 0.05)

# Fetch Market Data
try:
    loader = BinanceDataLoader()
    df_raw = loader.get_klines(
        symbol=symbol,
        interval=interval,
        limit=limit,
        include_open_candle=False,
    )
except Exception as exc:
    st.error(f"Error cargando datos de mercado para {symbol}: {exc}")
    st.stop()

if df_raw.empty or len(df_raw) < 50:
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
tab_live, tab_copilot, tab_backtest, tab_settings, tab_guide = st.tabs([
    "📡 Live Monitor",
    "🤖 AI Copilot",
    "📈 Backtest Analytics",
    "⚙️ Notification Settings",
    "📖 Guía & Glosario",
])



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
            direction_bias="LONG" if manual_regime == MarketRegime.TRENDING_BULL else ("SHORT" if manual_regime == MarketRegime.TRENDING_BEAR else "NEUTRAL"),
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
            predictive_mode=True,
        )

    last_bar = df.iloc[-1]
    curr_price = float(last_bar["close"])

    if is_manual_mode:
        st.warning(
            f"🕹️ **Modo Simulación Manual Activo:** Régimen forzado a `{manual_regime.value}` • "
            f"Predictive Score: `{manual_pred_score:.2f}` • TP: `{manual_tp_mult:.2f}x ATR` • SL: `{manual_sl_mult:.2f}x ATR`."
        )

    # 2. Key Metrics Header
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Precio Actual", f"${curr_price:,.2f}")
    with col2:
        st.metric("Régimen de Mercado", regime_res.regime.value)
    with col3:
        st.metric("Decisión Estratégica", f"{decision.decision} ({decision.direction})")
    with col4:
        conf_pct = decision.confidence if decision.confidence > 1.0 else decision.confidence * 100.0
        st.metric("Confianza", f"{conf_pct:.1f}%")
    with col5:
        st.metric(
            "Predictive Score",
            f"{pred_res.predictive_score:.2f}",
            f"P(Cont): {pred_res.probability_continuation * 100:.0f}%",
        )

    # 3. Interactive Plotly Chart (Candles, EMAs, Volume Profile)
    fig_live = go.Figure()

    # Candlestick with Fluorescent Green and Neon Coral
    fig_live.add_trace(
        go.Candlestick(
            x=df["timestamp"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Precio",
            increasing_line_color="#00FF88",
            increasing_fillcolor="#00FF88",
            decreasing_line_color="#FF2E63",
            decreasing_fillcolor="#FF2E63",
        )
    )

    # EMAs with Cyan and Magenta
    if "ema_50" in df.columns:
        fig_live.add_trace(go.Scatter(x=df["timestamp"], y=df["ema_50"], name="EMA 50", line={"color": "#00E5FF", "width": 2}))
    if "ema_200" in df.columns:
        fig_live.add_trace(go.Scatter(x=df["timestamp"], y=df["ema_200"], name="EMA 200", line={"color": "#BD00FF", "width": 2}))

    # Volume Profile Horizontal Levels with Neon Glow Accents
    if profile.get("poc"):
        fig_live.add_hline(
            y=profile["poc"],
            line={"color": "#FFD600", "width": 2, "dash": "dash"},
            annotation_text="POC",
            annotation_font_color="#FFD600",
        )
    if profile.get("vah"):
        fig_live.add_hline(
            y=profile["vah"],
            line={"color": "#00FF88", "width": 1.5, "dash": "dot"},
            annotation_text="VAH",
            annotation_font_color="#00FF88",
        )
    if profile.get("val"):
        fig_live.add_hline(
            y=profile["val"],
            line={"color": "#FF2E63", "width": 1.5, "dash": "dot"},
            annotation_text="VAL",
            annotation_font_color="#FF2E63",
        )

    fig_live.update_layout(
        height=620,
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        paper_bgcolor="#07090E",
        plot_bgcolor="#07090E",
        font={"family": "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto", "color": "#E6EDF3"},
        xaxis={
            "gridcolor": "rgba(255, 255, 255, 0.06)",
            "linecolor": "rgba(0, 229, 255, 0.2)",
        },
        yaxis={
            "gridcolor": "rgba(255, 255, 255, 0.06)",
            "linecolor": "rgba(0, 229, 255, 0.2)",
        },
    )
    st.plotly_chart(fig_live, use_container_width=True)

    # 4. Contextual Diagnostics & Modular Layer Navigation
    c_layer1, c_layer2, c_layer3, c_layer4, c_layer5 = st.tabs([
        "🧠 Diagnóstico",
        "📋 Operación",
        "🎯 Niveles",
        "🔮 Predicción",
        "🛠️ Datos",
    ])

    reporter = MarketReport()
    m_report = reporter.generate(symbol, analysis, profile)

    with c_layer1:
        d_col1, d_col2 = st.columns([1.2, 1.0])
        with d_col1:
            st.info(f"**Estado de Mercado:** {decision.market_state}")
            st.write(f"**Justificación:** {decision.reasoning}")
            conclusion = m_report.get("conclusion") or "Evaluación en curso con parámetros de riesgo definidos."
            st.caption(f"📌 **Conclusión Cuantitativa:** {conclusion}")
        with d_col2:
            if decision.positives:
                st.success("**Confluencias Favorables:**\n- " + "\n- ".join(decision.positives))
            if decision.warnings:
                st.warning("**Riesgos y Advertencias:**\n- " + "\n- ".join(decision.warnings))

    with c_layer2:
        tp_mult = getattr(decision, "tp_multiplier", 3.0)
        sl_mult = getattr(decision, "sl_multiplier", 1.5)
        atr_val = risk.get("atr", 0.0)

        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        with p_col1:
            st.metric("Sesgo Sugerido", f"{decision.decision} ({decision.direction})")
        with p_col2:
            st.metric("Target (TP)", f"{tp_mult:.2f}x ATR", f"+${(tp_mult * atr_val):,.2f}" if atr_val else None)
        with p_col3:
            st.metric("Stop Loss (SL)", f"{sl_mult:.2f}x ATR", f"-${(sl_mult * atr_val):,.2f}" if atr_val else None)
        with p_col4:
            rr_ratio = tp_mult / max(sl_mult, 0.01)
            st.metric("Ratio R:R", f"1 : {rr_ratio:.2f}")

        st.caption("ℹ️ Multiplicadores calculados en base a la volatilidad ATR de velas cerradas.")

    with c_layer3:
        poc_val = profile.get("poc")
        vah_val = profile.get("vah")
        val_val = profile.get("val")

        v_col1, v_col2, v_col3 = st.columns(3)
        with v_col1:
            if poc_val:
                st.metric("🟡 POC (Control)", f"${poc_val:,.2f}", "Mayor liquidez")
        with v_col2:
            if vah_val:
                st.metric("🟢 VAH (Techo)", f"${vah_val:,.2f}", "Resistencia")
        with v_col3:
            if val_val:
                st.metric("🔴 VAL (Suelo)", f"${val_val:,.2f}", "Soporte")

        pos_text = "dentro del Área de Valor"
        if vah_val and curr_price > vah_val:
            pos_text = "por encima del VAH (desequilibrio alcista / premium)"
        elif val_val and curr_price < val_val:
            pos_text = "por debajo del VAL (desequilibrio bajista / descuento)"
        st.info(f"📊 **Lectura de Liquidez:** El precio actual (${curr_price:,.2f}) se encuentra {pos_text}.")

    with c_layer4:
        pr_col1, pr_col2, pr_col3 = st.columns(3)
        with pr_col1:
            st.metric("Predictive Score", f"{pred_res.predictive_score:.2f} / 1.00")
        with pr_col2:
            st.metric("Prob. Continuación", f"{pred_res.probability_continuation * 100:.0f}%")
        with pr_col3:
            st.metric("Régimen Activo", regime_res.regime.value)

        st.write(f"**Justificación de Régimen:** {regime_res.details.get('reason', 'Clasificación basada en estructura técnica y volatilidad.') if hasattr(regime_res, 'details') else 'Régimen cuantitativo activo.'}")

    with c_layer5:
        st.caption("Datos técnicos sin procesar para auditoría o conexión vía API:")
        st.json({
            "symbol": symbol,
            "timeframe": interval,
            "direction": decision.direction,
            "action": decision.decision,
            "quant_score": score["score"],
            "predictive_score": pred_res.predictive_score,
            "tp_multiplier": decision.tp_multiplier,
            "sl_multiplier": decision.sl_multiplier,
            "poc": profile.get("poc"),
            "vah": profile.get("vah"),
            "val": profile.get("val"),
            "risk_assessment": m_report.get("conclusion", ""),
        })


# =====================================================================
# TAB 2: AI COPILOT
# =====================================================================
with tab_copilot:
    st.subheader("🤖 Institutional AI Quant Copilot")
    st.caption("Asistente de inteligencia de mercado • Razonamiento contextual con Gemini • Sin ejecución automática")

    try:
        live_signal_event = SignalEvent(
            timestamp=pd.Timestamp(df.iloc[-1]["timestamp"]),
            symbol=symbol,
            timeframe=interval,
            action=decision.decision,
            direction=decision.direction,
            confidence=decision.confidence if decision.confidence <= 1.0 else decision.confidence / 100.0,
            predictive_score=pred_res.predictive_score,
            regime=regime_res.regime.value,
            reasoning=decision.reasoning,
            price=float(df.iloc[-1]["close"]),
            quant_score=score["score"],
            stop_loss=risk.get("stop_loss"),
            take_profit=risk.get("take_profit"),
            signal_id=f"live-{symbol}-{interval}",
            metadata={
                "risk_reward_ratio": risk.get("risk_ratio"),
                "atr": risk.get("atr"),
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
            metadata={"source": "Streamlit Live Dashboard"},
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

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        return executor.submit(lambda: asyncio.run(coro)).result()
                else:
                    return loop.run_until_complete(coro)
            except Exception as exc:
                raise exc

        try:
            copilot_provider.update_context(current_market_context)
        except Exception:
            pass

        # Real AI Provider Resolution via ProviderFactory
        active_llm_provider = ProviderFactory.create_provider()
        copilot_assistant = OperatorAssistant(
            context_provider=copilot_provider,
            ai_provider=active_llm_provider,
        )
        market_report_svc = MarketReportService()
        anomaly_detector = MarketAnomalyDetector()

        # Copilot Modular Layer Sub-tabs
        cop_tab1, cop_tab2, cop_tab3, cop_tab4 = st.tabs([
            "💬 Chat AI",
            "📋 Briefing",
            "🚨 Anomalías",
            "🕒 Contexto",
        ])

        with cop_tab1:
            provider_name = active_llm_provider.__class__.__name__.replace("Provider", "")
            model_name = getattr(active_llm_provider, "model", "standard")
            st.caption(f"🧠 Modelo: **{provider_name}** (`{model_name}`) | BD: `{db_path}`")
            user_query_input = st.text_input("Consulta:", value=f"Analiza la situación cuantitativa de {symbol} ahora", key="copilot_input")

            if st.button("🔎 Enviar Consulta a Copilot", type="primary"):
                with st.spinner("AI Copilot sintetizando contexto cuantitativo con Gemini..."):
                    query_obj = OperatorQuery(
                        query=user_query_input,
                        symbol=symbol,
                        timeframe=interval,
                        operator_id="dashboard_operator",
                    )
                    try:
                        copilot_res = _safe_async_run(copilot_assistant.ask(query_obj))
                        st.markdown("---")
                        st.markdown(copilot_res.answer)
                        latency_ms = copilot_res.metadata.get("latency_ms", 0.0)
                        tokens = copilot_res.metadata.get("total_tokens", 0)
                        meta_str = f"⚡ Latencia: {latency_ms:.1f}ms" + (f" | 🪙 Tokens: {tokens}" if tokens else "")
                        st.caption(f"🛡️ {copilot_res.disclaimer} • {meta_str}")
                    except Exception as copilot_err:
                        st.error(f"Error procesando la consulta con AI Copilot: {copilot_err}")

        with cop_tab2:
            st.markdown("#### 📋 Briefing Diario del Mercado")
            daily_rep = market_report_svc.generate_daily_briefing(current_market_context)
            st.markdown(f"**Panorama General:** {daily_rep.market_overview}")
            br_c1, br_c2, br_c3 = st.columns(3)
            with br_c1:
                st.metric("Régimen", daily_rep.current_regime)
            with br_c2:
                st.metric("Puntuación Quant", f"{daily_rep.quant_score:.1f}/100")
            with br_c3:
                st.metric("Predictive Score", f"{daily_rep.predictive_score:.2f}")

            st.markdown(f"**Análisis de Volatilidad:** {daily_rep.volatility_analysis}")
            if daily_rep.strongest_signals:
                st.markdown("**Señales Más Fuertes:**")
                for s in daily_rep.strongest_signals:
                    st.markdown(f"- {s}")
            if daily_rep.main_risks:
                st.markdown("**Riesgos Identificados:**")
                for r in daily_rep.main_risks:
                    st.markdown(f"- ⚠️ {r}")

        with cop_tab3:
            st.markdown("#### 🚨 Detección Pasiva de Anomalías Estructurales")
            detected_anomalies = anomaly_detector.evaluate(current_market_context)
            if not detected_anomalies:
                st.success("✅ Sin anomalías estructurales ni divergencias severas de volatilidad detectadas en este activo.")
            else:
                for alt in detected_anomalies:
                    if alt.severity.value == "CRITICAL":
                        st.error(f"**[{alt.severity.value}] {alt.headline}**\n\n{alt.reason}")
                    elif alt.severity.value == "WARNING":
                        st.warning(f"**[{alt.severity.value}] {alt.headline}**\n\n{alt.reason}")
                    else:
                        st.info(f"**[{alt.severity.value}] {alt.headline}**\n\n{alt.reason}")

        with cop_tab4:
            st.markdown("#### 🕒 Snapshot de Contexto Activo")
            snap_col1, snap_col2, snap_col3, snap_col4 = st.columns(4)
            with snap_col1:
                st.metric("Régimen Activo", current_market_context.market_regime)
            with snap_col2:
                st.metric("Puntuación Quant", f"{current_market_context.quant_score:.1f}/100")
            with snap_col3:
                st.metric("Predictive Score", f"{current_market_context.predictive_score:.2f}")
            with snap_col4:
                st.metric("Sesgo Operativo", f"{current_market_context.signal.action} ({current_market_context.signal.direction})")

            with st.expander("🛠️ Ver snapshot técnico completo en formato JSON (Avanzado)", expanded=False):
                st.json({
                    "symbol": current_market_context.symbol,
                    "timeframe": current_market_context.timeframe,
                    "regime": current_market_context.market_regime,
                    "quant_score": current_market_context.quant_score,
                    "predictive_score": current_market_context.predictive_score,
                    "action": current_market_context.signal.action,
                    "direction": current_market_context.signal.direction,
                    "confidence": current_market_context.signal.confidence,
                    "stop_loss": current_market_context.risk.stop_loss,
                    "take_profit": current_market_context.risk.take_profit,
                    "atr": current_market_context.risk.atr,
                })
    except Exception as cop_err:
        st.error(f"Error inicializando AI Copilot: {cop_err}")


# =====================================================================
# TAB 3: BACKTEST ANALYTICS
# =====================================================================
with tab_backtest:
    st.subheader("📈 Simulación Cronológica y Desempeño Histórico")


    # Backtest Execution Controls
    b_col1, b_col2, b_col3, b_col4 = st.columns(4)
    with b_col1:
        initial_cap = st.number_input("Capital Inicial ($)", min_value=1_000.0, max_value=1_000_000.0, value=10_000.0, step=1000.0)
    with b_col2:
        taker_fee_pct = st.number_input("Comisión Taker (%)", min_value=0.0, max_value=1.0, value=0.05, step=0.01) / 100.0
    with b_col3:
        slippage_pct = st.number_input("Slippage (%)", min_value=0.0, max_value=1.0, value=0.05, step=0.01) / 100.0
    with b_col4:
        direction_choice = st.selectbox("Dirección de Operación", ["BOTH", "LONG", "SHORT"], index=0)

    run_sim = st.button("🚀 Ejecutar Backtest", type="primary")

    if run_sim or "backtest_report" in st.session_state:
        if run_sim:
            with st.spinner("Ejecutando simulación event-driven..."):
                b_cfg = BacktestConfig(
                    initial_capital=initial_cap,
                    taker_fee_pct=taker_fee_pct,
                    slippage_pct=slippage_pct,
                    trade_direction=TradeDirection(direction_choice),
                )
                runner = BacktestRunner(config=b_cfg)
                st.session_state["backtest_report"] = runner.run_backtest(
                    df=df,
                    symbol=symbol,
                    interval=interval,
                    predictive_mode=True,
                )

        report = st.session_state["backtest_report"]
        metrics = report.metrics

        # 1. Performance Metrics Grid
        m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)
        with m_col1:
            st.metric("Total Trades", metrics.get("total_trades", 0))
        with m_col2:
            st.metric("Win Rate", f"{metrics.get('win_rate', 0.0) * 100:.1f}%")
        with m_col3:
            st.metric("Profit Factor", f"{metrics.get('profit_factor', 0.0):.2f}")
        with m_col4:
            st.metric("Max Drawdown %", f"{metrics.get('max_drawdown_pct', 0.0):.2f}%")
        with m_col5:
            st.metric("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0.0):.2f}")
        with m_col6:
            st.metric("Retorno Neto", f"${metrics.get('net_pnl', 0.0):,.2f}")

        # 2. Equity Curve & Underwater Drawdown Plot
        if report.equity_curve:
            eq_df = pd.DataFrame([pt.to_dict() for pt in report.equity_curve])
            eq_df["timestamp"] = pd.to_datetime(eq_df["timestamp"])

            fig_eq = make_subplots(
                rows=2,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.08,
                subplot_titles=("Curva de Capital (Equity)", "Drawdown Subyacente (%)"),
                row_heights=[0.7, 0.3],
            )

            fig_eq.add_trace(
                go.Scatter(x=eq_df["timestamp"], y=eq_df["equity"], name="Equity ($)", line={"color": "#00FF88", "width": 2.5}),
                row=1,
                col=1,
            )

            fig_eq.add_trace(
                go.Scatter(
                    x=eq_df["timestamp"],
                    y=-eq_df["drawdown_pct"],
                    name="Drawdown (%)",
                    fill="tozeroy",
                    fillcolor="rgba(255, 46, 99, 0.25)",
                    line={"color": "#FF2E63", "width": 1.5},
                ),
                row=2,
                col=1,
            )

            fig_eq.update_layout(
                height=520,
                template="plotly_dark",
                paper_bgcolor="#07090E",
                plot_bgcolor="#07090E",
                margin={"l": 20, "r": 20, "t": 40, "b": 20},
                xaxis={"gridcolor": "rgba(255, 255, 255, 0.06)"},
                yaxis={"gridcolor": "rgba(255, 255, 255, 0.06)"},
                xaxis2={"gridcolor": "rgba(255, 255, 255, 0.06)"},
                yaxis2={"gridcolor": "rgba(255, 255, 255, 0.06)"},
            )
            st.plotly_chart(fig_eq, use_container_width=True)

        # 3. MFE vs MAE Scatter Plot & Trades Table
        t_left, t_right = st.columns([1, 1])

        with t_left:
            st.subheader("🎯 Distribución MFE vs MAE")
            if report.trades:
                trade_rows = [t.to_dict() for t in report.trades]
                trades_df = pd.DataFrame(trade_rows)

                fig_mfe = go.Figure()
                fig_mfe.add_trace(
                    go.Scatter(
                        x=trades_df["mae"] * 100,
                        y=trades_df["mfe"] * 100,
                        mode="markers",
                        marker={
                            "size": 9,
                            "color": ["#00FF88" if p > 0 else "#FF2E63" for p in trades_df["net_pnl"]],
                            "line": {"width": 1, "color": "#FFFFFF"},
                        },
                        text=[f"Trade {t['trade_id']} ({t['side']}): PnL ${t['net_pnl']:.2f}" for t in trade_rows],
                    )
                )
                fig_mfe.update_layout(
                    xaxis_title="Max Adverse Excursion (MAE %)",
                    yaxis_title="Max Favorable Excursion (MFE %)",
                    height=360,
                    template="plotly_dark",
                    paper_bgcolor="#07090E",
                    plot_bgcolor="#07090E",
                    margin={"l": 20, "r": 20, "t": 30, "b": 20},
                    xaxis={"gridcolor": "rgba(255, 255, 255, 0.06)"},
                    yaxis={"gridcolor": "rgba(255, 255, 255, 0.06)"},
                )
                st.plotly_chart(fig_mfe, use_container_width=True)
            else:
                st.info("No se registraron operaciones en este período de simulación.")

        with t_right:
            st.subheader("📋 Registro de Transacciones")
            if report.trades:
                trades_display = trades_df[[
                    "trade_id",
                    "side",
                    "entry_time",
                    "entry_price",
                    "exit_time",
                    "exit_price",
                    "net_pnl",
                    "exit_reason",
                ]]
                st.dataframe(trades_display, height=350, use_container_width=True)
            else:
                st.info("Sin transacciones.")


# =====================================================================
# TAB 3: NOTIFICATION SETTINGS
# =====================================================================
with tab_settings:
    st.subheader("⚙️ Configuración del Sistema de Alertas Multicanal")

    c_cfg1, c_cfg2 = st.columns([1, 1])

    with c_cfg1:
        st.markdown("### 📢 Canales de Notificación")
        enable_discord = st.checkbox("Habilitar Discord Webhook", value=bool(os.getenv("DISCORD_WEBHOOK_URL")))
        discord_url_input = st.text_input(
            "Discord Webhook URL",
            value=os.getenv("DISCORD_WEBHOOK_URL", ""),
            type="password",
        )

        enable_telegram = st.checkbox("Habilitar Telegram Bot", value=bool(os.getenv("TELEGRAM_BOT_TOKEN")))
        telegram_token_input = st.text_input(
            "Telegram Bot Token",
            value=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            type="password",
        )
        telegram_chat_id_input = st.text_input(
            "Telegram Chat ID",
            value=os.getenv("TELEGRAM_CHAT_ID", ""),
        )

        enable_webhook = st.checkbox("Habilitar Generic Webhook", value=bool(os.getenv("GENERIC_WEBHOOK_URL")))
        generic_url_input = st.text_input(
            "Webhook Target URL",
            value=os.getenv("GENERIC_WEBHOOK_URL", ""),
        )

    with c_cfg2:
        st.markdown("### 🛡️ Filtros y Anti-Spam (Cooldown)")
        min_pred_score = st.slider("Umbral Mínimo de Predictive Score", 0.0, 1.0, 0.60, 0.05)
        min_conf = st.slider("Umbral Mínimo de Confianza", 0.0, 1.0, 0.60, 0.05)
        cooldown_sec = st.slider("Tiempo de Cooldown Anti-Spam (Segundos)", 0, 1800, 300, 30)
        dry_run_mode = st.toggle("Modo Simulación (Dry-Run / Sin I/O)", value=True)

    st.markdown("---")
    st.subheader("🧪 Envío de Alerta de Prueba (Test Ping)")

    if st.button("🔔 Enviar Notificación de Prueba", type="primary"):
        test_channels = []
        if enable_discord and discord_url_input:
            test_channels.append(DiscordWebhookChannel(webhook_url=discord_url_input, dry_run=dry_run_mode))
        if enable_telegram and telegram_token_input and telegram_chat_id_input:
            test_channels.append(
                TelegramChannel(bot_token=telegram_token_input, chat_id=telegram_chat_id_input, dry_run=dry_run_mode)
            )
        if enable_webhook and generic_url_input:
            test_channels.append(WebhookChannel(url=generic_url_input, dry_run=dry_run_mode))

        if not test_channels:
            st.warning("No hay ningún canal configurado y habilitado para enviar alertas.")
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
                action="BUY",
                direction="LONG",
                confidence=0.88,
                predictive_score=0.82,
                regime="TRENDING_BULL",
                reasoning="Test ping de verificación de canal desde Crypto Quant Monitor Dashboard.",
                price=float(df.iloc[-1]["close"]),
                quant_score=85.0,
                stop_loss=round(float(df.iloc[-1]["close"]) * 0.98, 2),
                take_profit=round(float(df.iloc[-1]["close"]) * 1.04, 2),
                signal_id="test-ping-01",
            )

            results = dispatcher.dispatch_signal(test_signal, priority=NotificationPriority.HIGH)

            st.success(f"Despacho completado. {len(results)} canales procesados.")
            result_rows = [r.to_dict() for r in results]
            st.table(pd.DataFrame(result_rows))


# =====================================================================
# TAB 5: GUÍA & GLOSARIO
# =====================================================================
with tab_guide:
    st.subheader("📖 Guía Rápida & Glosario Cuantitativo")
    st.caption("Referencia institucional de términos, siglas y manual paso a paso de la plataforma.")

    g_tab1, g_tab2 = st.tabs([
        "📚 Glosario de Siglas y Métricas",
        "🕹️ Manual: Si tocas esto, obtienes esto",
    ])

    with g_tab1:
        st.markdown("### 📚 Diccionario de Siglas Institucionales")

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
              *Significado:* Proporción entre el beneficio proyectado (Take Profit) y la pérdida máxima aceptada (Stop Loss).  
              *Ejemplo:* Un R:R de `1 : 2.0` significa que por cada $1 arriesgado, se busca una ganancia de $2.
            
            - **`SL` (Stop Loss):** Nivel de corte de pérdidas protector automático.
            - **`TP` (Take Profit):** Nivel objetivo de toma de ganancias programado.
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
            - **`Profit Factor`:** Ganancia bruta dividida entre pérdida bruta (Institucional > 1.5).
            - **`Max Drawdown %`:** Mayor caída porcentual experimentada desde el punto máximo de capital.
            - **`Sharpe Ratio`:** Rendimiento generado por cada unidad de volatilidad asumida (> 1.0 es sólido).
            - **`MAE / MFE`:** Máxima excursión adversa (*peor momento en contra*) y favorable (*mejor momento a favor*) de cada trade.
            """)

    with g_tab2:
        st.markdown("### 🕹️ Manual Paso a Paso: Si tocas esto, obtienes esto")

        st.markdown("""
        | Sección | Control / Botón | Qué hace al interactuar | Qué obtienes en pantalla |
        | :--- | :--- | :--- | :--- |
        | **Barra Lateral** | **Par de Criptomoneda** | Seleccionas una moneda (BTC, ETH, SOL, etc.) | Descarga en tiempo real las velas institucionales de Binance para ese activo. |
        | **Barra Lateral** | **Temporalidad** | Seleccionas 15m, 1h, 4h o 1d | Cambia el horizonte temporal. Verás cómo el régimen de mercado y las medias móviles se adaptan al marco temporal elegido. |
        | **Barra Lateral** | **Velas Históricas** | Mueves el deslizador (250 a 1000 velas) | Amplía o reduce el historial cargado en memoria (ej. 300 velas en 1d = ~10 meses). |
        | **Barra Lateral** | **Modo de Análisis** | Alternas entre *Automático* y *Manual* | Activa el simulador *What-If* para forzar regímenes, probabilidades y multiplicadores a tu criterio. |
        | **📡 Live Monitor** | **🧠 Diagnóstico** | Pulsas la sub-pestaña | Muestra la decisión ejecutiva (LONG, SHORT o ESPERAR), justificación matemática y confluencias favorables/alertas. |
        | **📡 Live Monitor** | **📋 Operación** | Pulsas la sub-pestaña | Muestra los precios sugeridos de entrada, Stop Loss (SL), Take Profit (TP), distancias en ATR y ratio R:R. |
        | **📡 Live Monitor** | **🎯 Niveles** | Pulsas la sub-pestaña | Entrega los precios clave del Área de Valor (POC, VAH, VAL) e indica si el precio está en zona de sobrecompra o descuento. |
        | **📡 Live Monitor** | **🔮 Predicción** | Pulsas la sub-pestaña | Muestra la probabilidad matemática de que la tendencia continúe y el desglose del modelo predictivo. |
        | **📡 Live Monitor** | **🛠️ Datos** | Pulsas la sub-pestaña | Expande la carga técnica en JSON para auditoría cuantitativa o conexión a sistemas externos. |
        | **🤖 AI Copilot** | **💬 Chat AI** | Escribes una duda y pulsas *Enviar Consulta* | Gemini analiza el contexto actual y te responde con explicación de mercado, riesgos y telemetría de latencia. |
        | **🤖 AI Copilot** | **📋 Briefing** | Pulsas la sub-pestaña | Genera un informe diario institucional estructurado con análisis de volatilidad y señales fuertes. |
        | **🤖 AI Copilot** | **🚨 Anomalías** | Pulsas la sub-pestaña | Evalúa si existen divergencias estructurales o anomalías severas de volatilidad en el activo actual. |
        | **📈 Backtest** | **🚀 Ejecutar Backtest** | Pulsas el botón con tus parámetros elegidos | Simula vela por vela la estrategia en el pasado sin repintado y grafica la Curva de Capital, Drawdown y dispersión MAE vs MFE. |
        | **⚙️ Configuración** | **🔔 Notificación de Prueba** | Pulsas el botón de prueba | Envía un ping de prueba simulado a tus canales de Telegram, Discord o Webhook configurados. |
        """)