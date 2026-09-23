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

# Synchronize Streamlit Cloud secrets into os.environ
try:
    if hasattr(st, "secrets"):
        for sec_k, sec_v in st.secrets.items():
            if isinstance(sec_v, str) and not os.getenv(sec_k):
                os.environ[sec_k] = sec_v
except Exception:
    pass

try:
    from src.ai_agent.context_builder import ContextBuilder
    from src.ai_providers.factory import ProviderFactory
    from src.anomaly_detection.detector import MarketAnomalyDetector
    from src.backtest_models import BacktestConfig
    from src.backtest_presets import (
        PROVEN_STRATEGIES,
        build_strategy_config,
        evaluate_backtest_verdict,
    )
    from src.backtest_runner import BacktestRunner
    from src.data_loader import BinanceDataLoader
    from src.decision_engine import DecisionEngine
    from src.engine import MarketEngine
    from src.forex_data_loader import FOREX_PAIRS, ForexDataLoader
    from src.forex_sessions import get_forex_session_status
    from src.indicators import TechnicalIndicators
    from src.market_intelligence import MarketIntelligence
    from src.market_reports.generator import MarketReportService
    from src.market_scanner import MarketScanner
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
    from backtest_models import BacktestConfig
    from backtest_presets import (
        PROVEN_STRATEGIES,
        build_strategy_config,
        evaluate_backtest_verdict,
    )
    from backtest_runner import BacktestRunner
    from data_loader import BinanceDataLoader
    from decision_engine import DecisionEngine
    from engine import MarketEngine
    from forex_data_loader import FOREX_PAIRS, ForexDataLoader
    from forex_sessions import get_forex_session_status
    from indicators import TechnicalIndicators
    from market_intelligence import MarketIntelligence
    from market_reports.generator import MarketReportService
    from market_scanner import MarketScanner
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

    /* Executive Justification Card & Pills */
    .justification-card {
        background: linear-gradient(135deg, rgba(16, 26, 46, 0.85) 0%, rgba(10, 16, 30, 0.95) 100%);
        border: 1px solid rgba(0, 229, 255, 0.25);
        border-radius: 18px;
        padding: 18px 22px;
        margin-bottom: 16px;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
    }
    .justification-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 8px;
    }
    .justification-title {
        color: #00E5FF;
        font-size: 0.92rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .justification-text {
        color: #F0F6FC;
        font-size: 0.92rem;
        line-height: 1.7;
        letter-spacing: 0.3px;
        margin-bottom: 14px;
    }
    .metric-pill {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 14px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-right: 8px;
        margin-bottom: 6px;
    }
    .metric-pill-cyan {
        background: rgba(0, 229, 255, 0.12);
        border: 1px solid rgba(0, 229, 255, 0.35);
        color: #00E5FF;
    }
    .metric-pill-green {
        background: rgba(0, 255, 136, 0.12);
        border: 1px solid rgba(0, 255, 136, 0.35);
        color: #00FF88;
    }
    .metric-pill-gold {
        background: rgba(255, 214, 0, 0.12);
        border: 1px solid rgba(255, 214, 0, 0.35);
        color: #FFD600;
    }
    .metric-pill-coral {
        background: rgba(255, 46, 99, 0.12);
        border: 1px solid rgba(255, 46, 99, 0.35);
        color: #FF2E63;
    }

    /* Mobile Responsive Optimizations (Smartphones & Tablets) */
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            padding-top: 1.0rem !important;
        }
        .stHorizontalBlock {
            flex-direction: column !important;
            gap: 0.6rem !important;
        }
        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
        .metric-card {
            padding: 12px 14px !important;
            margin-bottom: 8px !important;
        }
        .metric-value {
            font-size: 1.15rem !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px !important;
            overflow-x: auto !important;
            flex-wrap: nowrap !important;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 6px 10px !important;
            font-size: 0.76rem !important;
        }
        .justification-card {
            padding: 14px 16px !important;
        }
        .justification-title {
            font-size: 0.85rem !important;
        }
        .justification-text {
            font-size: 0.85rem !important;
            line-height: 1.55 !important;
        }
        .metric-pill {
            display: inline-block !important;
            margin-bottom: 5px !important;
            font-size: 0.72rem !important;
            padding: 3px 8px !important;
        }
        .stButton>button {
            width: 100% !important;
            min-height: 42px !important;
            font-size: 0.84rem !important;
        }
    /* Intelligent Traffic Light Verdict Card & Presets */
    .verdict-card {
        background: linear-gradient(135deg, rgba(16, 26, 46, 0.95) 0%, rgba(10, 16, 30, 0.98) 100%);
        border-radius: 18px;
        padding: 18px 22px;
        margin-bottom: 18px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    }
    .strategy-preset-card {
        background: rgba(16, 26, 46, 0.65);
        border: 1px solid rgba(0, 229, 255, 0.25);
        border-radius: 14px;
        padding: 12px 16px;
        margin-bottom: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 Crypto & Forex Quant Monitor")

# =====================================================================
# SIDEBAR: MASTER MARKET SELECTOR (CRYPTO VS FOREX)
# =====================================================================
st.sidebar.subheader("🌐 Mercado Activo")
market_choice = st.sidebar.radio(
    "Selecciona el Mercado:",
    ["🪙 Criptomonedas (24/7)", "💱 Divisas Forex (Lun - Vie)"],
    index=0,
)

is_forex = "Forex" in market_choice

# Live Market Status & Session Schedule
if is_forex:
    forex_status = get_forex_session_status()
    status_color = "#00FF88" if forex_status.is_market_open else "#FF2E63"
    st.sidebar.markdown(
        f"""
        <div style="background: rgba(16, 26, 46, 0.85); border: 1px solid rgba(0, 229, 255, 0.35); border-radius: 14px; padding: 12px 14px; margin-bottom: 12px;">
            <div style="font-weight: 700; font-size: 0.84rem; color: {status_color};">{forex_status.status_headline}</div>
            <div style="font-size: 0.76rem; color: #8B949E; margin-top: 4px;">🕒 {forex_status.current_utc_time}</div>
            <div style="font-size: 0.74rem; color: #00E5FF; margin-top: 3px;">📌 {forex_status.weekend_reopen_info}</div>
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
        <div style="background: rgba(16, 26, 46, 0.85); border: 1px solid rgba(0, 255, 136, 0.35); border-radius: 14px; padding: 12px 14px; margin-bottom: 12px;">
            <div style="font-weight: 700; font-size: 0.84rem; color: #00FF88;">🟢 Mercado Cripto Abierto 24/7</div>
            <div style="font-size: 0.76rem; color: #8B949E; margin-top: 4px;">Operaciones continuas los 365 días del año sin cierres</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.sidebar.header("🕹️ Parámetros de Selección")

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
    selected_label = st.sidebar.selectbox(
        "Par de Divisas Forex",
        options=list(FOREX_PAIRS.keys()),
        index=0,
    )
    symbol = FOREX_PAIRS[selected_label]
else:
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
limit = st.sidebar.slider("Velas Históricas", min_value=150, max_value=1000, value=300, step=50)

# Caption under title
market_desc = "💱 Divisas Forex Globales (Interbancario)" if is_forex else "🪙 Criptomonedas (Binance Spot & Futuros)"
st.caption(f"{market_desc} • Quantitative Engine • Predictive Intelligence • Real-Time Monitoring & Backtesting")

# =====================================================================
# SIDEBAR: MODO DE ANÁLISIS (AUTOMÁTICO VS MANUAL / WHAT-IF)
# =====================================================================
st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Modo de Análisis")
sim_mode = st.sidebar.radio(
    "Fuente de Parámetros",
    ["🕹️ Manual (Simulador de Escenarios)", "🟢 Automático (En Vivo)"],
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

# Fetch Market Data (Crypto vs Forex)
try:
    if is_forex:
        forex_loader = ForexDataLoader()
        df_raw = forex_loader.get_forex_klines(
            symbol=symbol,
            interval=interval,
            limit=limit,
        )
    else:
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
        conf_val = decision.confidence if decision.confidence > 1.0 else decision.confidence * 100.0
        tech_score = getattr(decision, "technical_score", score.get("score", 70.0))
        pred_sc = getattr(decision, "predictive_score", pred_res.predictive_score)

        narrative_p = (
            f"El motor cuantitativo determinó una postura de <strong>{decision.decision}</strong> en dirección <strong>{decision.direction}</strong> "
            f"para <strong>{symbol}</strong> ({interval}). "
            f"La señal técnica ({tech_score:.1f} pts) y la proyección predictiva ({pred_sc:.2f}) "
            f"arrojan una confianza ponderada de <strong>{conf_val:.1f}%</strong>, con objetivo dinámico en <strong>{decision.tp_multiplier:.2f}x ATR</strong> "
            f"y corte de riesgo en <strong>{decision.sl_multiplier:.2f}x ATR</strong>."
        )

        st.markdown(
            f"""
            <div class="justification-card">
                <div class="justification-header">
                    <span class="justification-title">🧠 Razonamiento Cuantitativo & Estado</span>
                    <span class="metric-pill metric-pill-cyan">{decision.market_state}</span>
                </div>
                <div class="justification-text">
                    {narrative_p}
                </div>
                <div>
                    <span class="metric-pill metric-pill-green">📊 Técnico: {tech_score:.1f} pts</span>
                    <span class="metric-pill metric-pill-cyan">🔮 Predictivo: {pred_sc:.2f}</span>
                    <span class="metric-pill metric-pill-gold">🎯 Confianza: {conf_val:.1f}%</span>
                    <span class="metric-pill metric-pill-coral">🛑 SL: {decision.sl_multiplier:.2f}x ATR</span>
                    <span class="metric-pill metric-pill-green">🎯 TP: {decision.tp_multiplier:.2f}x ATR</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        market_badge_text = "💱 Mercado Forex Global" if is_forex else "🪙 Mercado Criptomonedas 24/7"
        strategy_recommendation = (
            "🏛️ <strong>Método Recomendado en Forex:</strong> Reversión a la Media en zonas de valor institucional (VAL/VAH) y Seguimiento de Tendencia macroeconómico."
            if is_forex
            else "🚀 <strong>Método Recomendado en Cripto:</strong> Rupturas de Volatilidad (Breakouts) y Modelo Híbrido Dinámico para expansiones de impulso 24/7."
        )

        st.markdown(
            f"""
            <div style="background: rgba(16, 26, 46, 0.6); border: 1px solid rgba(0, 229, 255, 0.2); border-radius: 12px; padding: 10px 14px; margin-bottom: 14px;">
                <span class="metric-pill metric-pill-gold">{market_badge_text}</span>
                <span style="font-size: 0.85rem; color: #C9D1D9;">{strategy_recommendation}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_pos, col_warn = st.columns(2)
        with col_pos:
            st.markdown("##### 🟢 Confluencias Favorables")
            if decision.positives:
                for pos in decision.positives:
                    st.markdown(f"- ✅ **{pos}**")
            else:
                st.caption("Sin confluencias alcistas de alta significancia detectadas.")

        with col_warn:
            st.markdown("##### ⚠️ Factores de Riesgo")
            if decision.warnings:
                for warn in decision.warnings:
                    st.markdown(f"- ⚠️ **{warn}**")
            else:
                st.caption("No se registran factores de riesgo estructural inmediatos.")

        with st.expander("🔬 Ver fórmula técnica y parámetros detallados", expanded=False):
            st.code(decision.reasoning, language="text")
            conclusion = m_report.get("conclusion") or "Evaluación en curso con parámetros de riesgo definidos."
            st.caption(f"📌 Conclusión del Reporte: {conclusion}")

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

        # AI Model Configuration Controls (Gemini 3.8 / 3.5 / 3.7)
        with st.expander("⚙️ Selección de Modelo AI Copilot (Gemini 3.8 / 3.5 / 3.7)", expanded=False):
            cfg_col1, cfg_col2 = st.columns([2, 1])
            with cfg_col1:
                gemini_model_options = [
                    "gemini-2.0-flash (Recomendado • Máxima Estabilidad y Disponibilidad)",
                    "gemini-3.8-flash (Nueva Generación • Mayor Capacidad)",
                    "gemini-3.5-flash-lite (Ultra Rápido • Menor Demanda)",
                    "gemini-2.0-flash-lite (Rápido • Menor Consumo)",
                    "gemini-3.7-flash (Estándar)",
                    "gemini-1.5-flash (Universal)",
                ]
                selected_model_str = st.selectbox(
                    "Modelo Activo de Google Gemini:",
                    options=gemini_model_options,
                    index=0,
                    key="sel_copilot_model",
                )
                chosen_gemini_model = selected_model_str.split(" ")[0]
            with cfg_col2:
                custom_gemini_key = st.text_input(
                    "Clave API Personal (Opcional):",
                    type="password",
                    help="Déjalo vacío para usar la clave configurada en Streamlit Secrets o .env.",
                    key="input_copilot_custom_key",
                ).strip()

        # Real AI Provider Resolution via ProviderFactory
        provider_kwargs = {"model": chosen_gemini_model}
        if custom_gemini_key:
            provider_kwargs["api_key"] = custom_gemini_key

        active_llm_provider = ProviderFactory.create_provider(**provider_kwargs)
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
            st.caption(f"🧠 Modelo: **{provider_name}** (`{model_name}`) | Memoria Conversacional • Explicación en Lenguaje Cotidiano")

            # Quick Action Buttons
            q_col1, q_col2, q_col3 = st.columns([1.5, 1.5, 0.8])
            scan_triggered = False
            explain_triggered = False

            scan_btn_label = "💱 Escanear Divisas Forex" if is_forex else "🚀 Escanear Criptomonedas"
            with q_col1:
                if st.button(scan_btn_label, key="btn_scan_market", use_container_width=True):
                    scan_triggered = True
            with q_col2:
                if st.button(f"🗣️ Explicar {symbol} en Lenguaje Sencillo", key="btn_explain_current", use_container_width=True):
                    explain_triggered = True
            with q_col3:
                if st.button("🗑️ Limpiar", key="btn_clear_chat", use_container_width=True):
                    st.session_state["copilot_chat_history"] = []
                    st.rerun()

            # Initialize chat history
            if "copilot_chat_history" not in st.session_state or not st.session_state["copilot_chat_history"]:
                market_label = "Divisas Forex Globales" if is_forex else "Criptomonedas"
                st.session_state["copilot_chat_history"] = [
                    {
                        "role": "assistant",
                        "content": (
                            f"👋 **¡Hola! Soy tu AI Quant Copilot.**\n\n"
                            f"Puedo responder todas tus inquietudes sobre el mercado de **{market_label}** en **lenguaje cotidiano** y con datos cuantitativos en tiempo real:\n"
                            f"- Pregúntame: *¿Qué par presenta el mejor escenario para hacer trading hoy?*\n"
                            f"- Puedes **adjuntar una foto o captura de pantalla de un gráfico** abajo para que lo analice visualmente.\n"
                            f"- O pregúntame sobre la señal, volumen POC y niveles de riesgo de **{symbol}**."
                        ),
                    }
                ]

            # File/Image Uploader
            with st.expander("📎 Adjuntar Gráfico o Archivo para Análisis Multimodal (Foto, TradingView o CSV)", expanded=False):
                uploaded_file = st.file_uploader(
                    "Sube una captura de gráfico (PNG, JPG, WEBP) o archivo de datos:",
                    type=["png", "jpg", "jpeg", "webp", "csv", "txt"],
                    key="copilot_file_uploader",
                )
                if uploaded_file is not None:
                    if uploaded_file.type.startswith("image/"):
                        st.image(uploaded_file, caption="📷 Gráfico adjunto para análisis visual", width=320)
                    else:
                        st.info(f"📄 Archivo cargado: {uploaded_file.name} ({uploaded_file.size} bytes)")

            # Render Chat Messages
            chat_container = st.container()
            with chat_container:
                for msg in st.session_state["copilot_chat_history"]:
                    with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"):
                        st.markdown(msg["content"])
                        if msg.get("image_bytes"):
                            st.image(msg["image_bytes"], width=300)

            # Handler for Market Scanner Quick Action
            if scan_triggered:
                scan_market_name = "Forex (EUR/USD, GBP/USD, USD/JPY...)" if is_forex else "Binance (BTC, ETH, SOL, BNB, XRP)"
                with st.spinner(f"🔍 Analizando y comparando pares principales en {scan_market_name}..."):
                    try:
                        if is_forex:
                            scanner = MarketScanner(data_loader=ForexDataLoader())
                            forex_symbols = [s for s in FOREX_PAIRS.values() if not s.startswith("CUSTOM")][:6]
                            scan_results = scanner.scan_market(symbols=forex_symbols, timeframe=interval)
                            user_prompt = "¿Puedes analizar el mercado Forex y ver qué par me presenta el mejor escenario para operar hoy considerando las sesiones bancarias? Explícalo con datos y en lenguaje cotidiano."
                        else:
                            scanner = MarketScanner()
                            scan_results = scanner.scan_market()
                            user_prompt = "¿Puedes analizar el mercado crypto y ver qué par me presenta el mejor escenario para hacer trading? Explícalo con datos y en lenguaje cotidiano."

                        scan_summary = scanner.format_scanner_summary_es(scan_results)

                        st.session_state["copilot_chat_history"].append({
                            "role": "user",
                            "content": user_prompt,
                        })

                        query_obj = OperatorQuery(
                            query=f"Basado en este escaneo de mercado cuantitativo en tiempo real ({'Forex' if is_forex else 'Crypto'}):\n\n{scan_summary}\n\nExplica en lenguaje cotidiano al operador cuál es el mejor par para trading, por qué supera a los otros, qué significan sus números y cuáles son los niveles clave de entrada y riesgo.",
                            symbol=scan_results[0].symbol if scan_results else symbol,
                            timeframe=interval,
                            operator_id="dashboard_operator",
                            metadata={
                                "market_type": "Forex" if is_forex else "Crypto",
                                "conversation_history": [
                                    {"role": m["role"], "content": m["content"]}
                                    for m in st.session_state["copilot_chat_history"][-6:]
                                ],
                            },
                        )
                        copilot_res = _safe_async_run(copilot_assistant.ask(query_obj))
                        if "⚠️" in copilot_res.answer or "fallback" in copilot_res.answer.lower() or "503" in copilot_res.answer or "unable to analyze" in copilot_res.answer.lower():
                            answer_text = (
                                f"{scan_summary}\n\n---\n"
                                f"💡 *Nota: Diagnóstico generado directamente por el motor cuantitativo algorítmico local "
                                f"(la API de Gemini presentó alta demanda temporal en Google).* "
                            )
                        else:
                            answer_text = f"{copilot_res.answer}\n\n---\n{scan_summary}"

                        st.session_state["copilot_chat_history"].append({
                            "role": "assistant",
                            "content": answer_text,
                        })
                        st.rerun()
                    except Exception as scan_err:
                        st.error(f"Error ejecutando escaneo de mercado: {scan_err}")

            # Handler for Explain Current Asset Quick Action
            if explain_triggered:
                market_label = "Forex" if is_forex else "Cripto"
                user_prompt = f"Explícame en lenguaje cotidiano la situación actual de {symbol} ({market_label}): qué significa su Quant Score, el régimen de mercado y sus niveles de soporte y riesgo."
                st.session_state["copilot_chat_history"].append({
                    "role": "user",
                    "content": user_prompt,
                })
                with st.spinner(f"AI Copilot traduciendo métricas de {symbol} a lenguaje cotidiano..."):
                    try:
                        query_obj = OperatorQuery(
                            query=user_prompt,
                            symbol=symbol,
                            timeframe=interval,
                            operator_id="dashboard_operator",
                            metadata={
                                "market_type": "Forex" if is_forex else "Crypto",
                                "conversation_history": [
                                    {"role": m["role"], "content": m["content"]}
                                    for m in st.session_state["copilot_chat_history"][-6:]
                                ],
                            },
                        )
                        copilot_res = _safe_async_run(copilot_assistant.ask(query_obj))
                        st.session_state["copilot_chat_history"].append({
                            "role": "assistant",
                            "content": copilot_res.answer,
                        })
                        st.rerun()
                    except Exception as exp_err:
                        st.error(f"Error generando explicación: {exp_err}")

            # Chat Input Form
            chat_input_val = st.chat_input("Escribe tu consulta al Copilot (ej. ¿Cuál es el mejor par? o analiza la foto adjunta)...")
            if chat_input_val:
                user_msg = {
                    "role": "user",
                    "content": chat_input_val,
                }
                img_bytes = None
                mime_type = "image/png"
                if uploaded_file is not None and uploaded_file.type.startswith("image/"):
                    img_bytes = uploaded_file.getvalue()
                    mime_type = uploaded_file.type
                    user_msg["image_bytes"] = img_bytes

                st.session_state["copilot_chat_history"].append(user_msg)

                with st.spinner("AI Copilot razonando y formulando respuesta en español..."):
                    try:
                        query_obj = OperatorQuery(
                            query=chat_input_val,
                            symbol=symbol,
                            timeframe=interval,
                            operator_id="dashboard_operator",
                            metadata={
                                "image_bytes": img_bytes,
                                "mime_type": mime_type,
                                "market_type": "Forex" if is_forex else "Crypto",
                                "conversation_history": [
                                    {"role": m["role"], "content": m["content"]}
                                    for m in st.session_state["copilot_chat_history"][-6:]
                                ],
                            },
                        )
                        copilot_res = _safe_async_run(copilot_assistant.ask(query_obj))
                        st.session_state["copilot_chat_history"].append({
                            "role": "assistant",
                            "content": copilot_res.answer,
                        })
                        st.rerun()
                    except Exception as cop_err:
                        st.error(f"Error procesando la consulta: {cop_err}")

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
with tab_backtest:
    market_name_cap = "Divisas Forex" if is_forex else "Criptomonedas"
    st.subheader(f"📈 Simulación Histórica & Backtest Analytics ({market_name_cap})")
    st.caption("Prueba de estrategias cuantitativas con datos reales de mercado • Sin riesgo de capital real")

    market_advice = (
        "💡 **Consejo Cuantitativo para Forex:** En el mercado de divisas, las mejores rentabilidades con menor drawdown suelen obtenerse con **Reversión a la Media (RSI + Value Area VAL/VAH)** aprovechando que los bancos devuelven los precios a su equilibrio, o con **Seguimiento de Tendencia Macro**."
        if is_forex
        else "💡 **Consejo Cuantitativo para Cripto:** Las criptomonedas tienen expansiones explosivas 24/7. Las estrategias de **Ruptura de Volatilidad (Breakout)** y el **Modelo Híbrido Cuantitativo** están optimizadas para capturar esos movimientos direccionales rápidos."
    )
    st.markdown(
        f"""
        <div style="background: rgba(16, 26, 46, 0.65); border: 1px solid rgba(0, 229, 255, 0.25); border-radius: 10px; padding: 10px 14px; margin-bottom: 14px; font-size: 0.86rem; color: #E6EDF3;">
            {market_advice}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Experience Level Selector
    exp_level = st.radio(
        "Nivel de Experiencia",
        [
            "👶 Modo Guiado (Estrategias Probadas & Capital Flexible)",
            "👨‍💻 Modo Personalizado (Control Total para Expertos)",
        ],
        horizontal=True,
    )

    is_guided = "Guiado" in exp_level
    b_cfg = None

    if is_guided:
        st.markdown("##### 1️⃣ Define tu Capital Inicial Disponible")
        if "guided_capital" not in st.session_state:
            st.session_state["guided_capital"] = 100.0

        cap_cols = st.columns(6)
        preset_caps = [25.0, 50.0, 100.0, 250.0, 500.0, 1000.0]
        for col, amt in zip(cap_cols, preset_caps):
            with col:
                if st.button(f"${int(amt)}", key=f"cap_btn_{int(amt)}", use_container_width=True):
                    st.session_state["guided_capital"] = float(amt)
                    st.session_state["input_guided_cap"] = float(amt)
                    st.rerun()

        if "input_guided_cap" not in st.session_state:
            st.session_state["input_guided_cap"] = float(st.session_state["guided_capital"])

        selected_cap = st.number_input(
            "O escribe el monto exacto en dólares ($):",
            min_value=5.0,
            max_value=1_000_000.0,
            value=float(st.session_state["input_guided_cap"]),
            step=10.0,
            format="%.2f",
            key="input_guided_cap",
        )
        st.session_state["guided_capital"] = selected_cap

        # Educational Leverage Selector
        lev_c1, lev_c2 = st.columns([1.6, 2.4])
        with lev_c1:
            selected_leverage = st.selectbox(
                "⚡ Nivel de Apalancamiento:",
                options=[1.0, 2.0, 3.0, 5.0],
                format_func=lambda x: (
                    f"{int(x)}x (Spot • Sin Deuda • Seguro Novato)" if x == 1.0 else (
                        f"{int(x)}x (Moderado • Doble Retorno / Doble Riesgo)" if x == 2.0 else (
                            f"{int(x)}x (Avanzado • Triple Exposición)" if x == 3.0 else f"{int(x)}x (Agresivo • Alto Riesgo)"
                        )
                    )
                ),
                index=0,
                key="sel_guided_leverage",
            )
        with lev_c2:
            if selected_leverage == 1.0:
                st.info("🛡️ **Apalancamiento 1x (Recomendado Novatos)**: Operas exclusivamente con tu capital real. Sin riesgo de liquidación forzada.")
            else:
                st.warning(
                    f"⚠️ **Apalancamiento {int(selected_leverage)}x Activo**: Tu posición será de "
                    f"**${selected_cap * selected_leverage:,.2f}**. Tus ganancias y pérdidas se multiplicarán por {int(selected_leverage)}."
                )

        st.markdown("##### 2️⃣ Elige una Estrategia Estándar Probada de la Industria")
        strategy_keys = list(PROVEN_STRATEGIES.keys())
        strategy_labels = [PROVEN_STRATEGIES[k]["name"] for k in strategy_keys]
        selected_strategy_label = st.selectbox(
            "Estrategia Cuantitativa:",
            options=strategy_labels,
            index=0,
        )
        chosen_strategy_key = strategy_keys[strategy_labels.index(selected_strategy_label)]
        chosen_strategy_info = PROVEN_STRATEGIES[chosen_strategy_key]

        st.markdown(
            f"""
            <div class="strategy-preset-card">
                <strong style="color: #00E5FF;">{chosen_strategy_info['name']}</strong><br/>
                <span style="color: #F0F6FC; font-size: 0.88rem; line-height: 1.5;">{chosen_strategy_info['description']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        run_sim = st.button("🚀 Simular Estrategia con Datos Reales", type="primary", use_container_width=True)

        if run_sim:
            try:
                b_cfg = build_strategy_config(
                    strategy_key=chosen_strategy_key,
                    initial_capital=selected_cap,
                    taker_fee_pct=0.0005,
                    slippage_pct=0.0005,
                    leverage=selected_leverage,
                )
            except TypeError:
                b_cfg = build_strategy_config(
                    strategy_key=chosen_strategy_key,
                    initial_capital=selected_cap,
                    taker_fee_pct=0.0005,
                    slippage_pct=0.0005,
                )
                b_cfg.leverage = float(selected_leverage)

    else:
        st.markdown("##### ⚙️ Parámetros Avanzados de Simulación")
        b_col1, b_col2, b_col3, b_col4 = st.columns(4)
        with b_col1:
            initial_cap = st.number_input(
                "Capital Inicial ($)",
                min_value=5.0,
                max_value=1_000_000.0,
                value=10_000.0,
                step=100.0,
            )
        with b_col2:
            taker_fee_pct = st.number_input(
                "Comisión Taker (%)",
                min_value=0.0,
                max_value=1.0,
                value=0.05,
                step=0.01,
            ) / 100.0
        with b_col3:
            slippage_pct = st.number_input(
                "Slippage (%)",
                min_value=0.0,
                max_value=1.0,
                value=0.05,
                step=0.01,
            ) / 100.0
        with b_col4:
            direction_choice = st.selectbox(
                "Dirección de Operación",
                ["BOTH", "LONG", "SHORT"],
                index=0,
            )

        run_sim = st.button("🚀 Ejecutar Backtest Personalizado", type="primary", use_container_width=True)

        if run_sim:
            b_cfg = BacktestConfig(
                initial_capital=initial_cap,
                taker_fee_pct=taker_fee_pct,
                slippage_pct=slippage_pct,
                direction=direction_choice,
            )

    if run_sim or "backtest_report" in st.session_state:
        if run_sim and b_cfg is not None:
            source_label = "Forex Global" if is_forex else "Binance"
            with st.spinner(f"Ejecutando simulación cuantitativa vela por vela sobre datos reales de {source_label}..."):
                runner = BacktestRunner(config=b_cfg)
                st.session_state["backtest_report"] = runner.run_backtest(
                    df=df,
                    symbol=symbol,
                    interval=interval,
                    predictive_mode=True,
                )

        report = st.session_state.get("backtest_report")
        if report is None:
            st.stop()
        if hasattr(report, "metrics"):
            metrics = report.metrics
        elif isinstance(report, dict):
            metrics = report.get("metrics", report)
        else:
            metrics = getattr(report, "__dict__", {})

        # Intelligent Traffic Light Verdict
        verdict = evaluate_backtest_verdict(metrics)
        st.markdown(
            f"""
            <div class="verdict-card" style="border: 1px solid {verdict['color']};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="color: {verdict['color']}; font-weight: 700; font-size: 0.95rem; letter-spacing: 0.5px;">{verdict['badge']}</span>
                    <span style="color: #8B949E; font-size: 0.80rem;">{symbol} • {interval}</span>
                </div>
                <div style="color: #F0F6FC; font-size: 1.05rem; font-weight: 600; margin-bottom: 6px;">
                    {verdict['title']}
                </div>
                <div style="color: #C9D1D9; font-size: 0.88rem; line-height: 1.6;">
                    {verdict['description']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # AI Copilot Integration Button
        c_consult_btn, _ = st.columns([1.5, 2.0])
        with c_consult_btn:
            if st.button("🤖 Preguntar al Copilot: ¿Qué significa este resultado para mí?", key="btn_ask_copilot_backtest", use_container_width=True):
                backtest_prompt = (
                    f"Acabo de ejecutar un backtest para {symbol} ({interval}) con los siguientes resultados cuantitativos:\n"
                    f"- Total de Trades: {metrics.get('total_trades', 0)}\n"
                    f"- Win Rate: {metrics.get('win_rate', 0.0)*100:.1f}%\n"
                    f"- Profit Factor: {metrics.get('profit_factor', 0.0):.2f}\n"
                    f"- Caída Máxima (Max Drawdown): {metrics.get('max_drawdown_pct', 0.0):.2f}%\n"
                    f"- Retorno Neto: ${metrics.get('net_pnl', 0.0):,.2f}\n"
                    f"- Veredicto: {verdict['badge']} - {verdict['title']}\n\n"
                    f"Explícame en lenguaje cotidiano qué significan estos resultados para mí, si me conviene o no operar este par con esta estrategia, y qué consejos me das para cuidar mi dinero."
                )
                if "copilot_chat_history" not in st.session_state:
                    st.session_state["copilot_chat_history"] = []
                st.session_state["copilot_chat_history"].append({
                    "role": "user",
                    "content": backtest_prompt,
                })
                try:
                    q_obj = OperatorQuery(
                        query=backtest_prompt,
                        symbol=symbol,
                        timeframe=interval,
                        operator_id="dashboard_operator",
                    )
                    cop_res = _safe_async_run(copilot_assistant.ask(q_obj))
                    st.session_state["copilot_chat_history"].append({
                        "role": "assistant",
                        "content": cop_res.answer,
                    })
                    st.success("✅ ¡El Copilot ha analizado tu backtest! Ve a la pestaña '🤖 AI Copilot' para leer su recomendación personalizada.")
                except Exception as exc:
                    st.info(f"Consulta agregada al chat de Copilot: {exc}")

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

        # 1.1 Breakdown: LONG vs SHORT
        long_trades = [t for t in report.trades if str(getattr(t, "side", getattr(t, "direction", ""))).upper() == "LONG"]
        short_trades = [t for t in report.trades if str(getattr(t, "side", getattr(t, "direction", ""))).upper() == "SHORT"]

        long_count = len(long_trades)
        short_count = len(short_trades)
        long_wins = sum(1 for t in long_trades if t.net_pnl > 0)
        short_wins = sum(1 for t in short_trades if t.net_pnl > 0)
        long_wr = (long_wins / long_count * 100) if long_count > 0 else 0.0
        short_wr = (short_wins / short_count * 100) if short_count > 0 else 0.0
        long_pnl = sum(t.net_pnl for t in long_trades)
        short_pnl = sum(t.net_pnl for t in short_trades)

        st.markdown("##### ⚖️ ¿Qué Convino Más en Este Período? Compras (LONG) vs Ventas (SHORT)")
        dir_c1, dir_c2 = st.columns(2)
        with dir_c1:
            st.markdown(
                f"""
                <div style="background: rgba(0, 255, 136, 0.06); border: 1px solid rgba(0, 255, 136, 0.3); border-radius: 10px; padding: 12px 14px;">
                    <div style="font-weight: 700; color: #00FF88; font-size: 0.95rem;">🟢 Operaciones de Compra (LONG)</div>
                    <div style="color: #F0F6FC; font-size: 0.88rem; margin-top: 4px; line-height: 1.6;">
                        • <strong>{long_count}</strong> operaciones ejecutadas<br/>
                        • Tasa de Acierto: <strong>{long_wr:.1f}%</strong> ({long_wins} ganadas)<br/>
                        • Retorno Acumulado: <strong style="color: {'#00FF88' if long_pnl >= 0 else '#FF2E63'};">${long_pnl:+,.2f}</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with dir_c2:
            st.markdown(
                f"""
                <div style="background: rgba(255, 46, 99, 0.06); border: 1px solid rgba(255, 46, 99, 0.3); border-radius: 10px; padding: 12px 14px;">
                    <div style="font-weight: 700; color: #FF2E63; font-size: 0.95rem;">🔴 Operaciones de Venta (SHORT)</div>
                    <div style="color: #F0F6FC; font-size: 0.88rem; margin-top: 4px; line-height: 1.6;">
                        • <strong>{short_count}</strong> operaciones ejecutadas<br/>
                        • Tasa de Acierto: <strong>{short_wr:.1f}%</strong> ({short_wins} ganadas)<br/>
                        • Retorno Acumulado: <strong style="color: {'#00FF88' if short_pnl >= 0 else '#FF2E63'};">${short_pnl:+,.2f}</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if long_count > 0 and short_count > 0:
            if long_pnl > short_pnl:
                st.caption(f"🏆 **Conclusión Cuantitativa**: En este período el mercado recompensó con mayor fuerza las **COMPRAS (LONG)** (+${long_pnl:,.2f} vs ${short_pnl:,.2f} en Ventas).")
            elif short_pnl > long_pnl:
                st.caption(f"🏆 **Conclusión Cuantitativa**: En este período el mercado recompensó con mayor fuerza las **VENTAS (SHORT)** (+${short_pnl:,.2f} vs ${long_pnl:,.2f} en Compras).")
            else:
                st.caption("⚖️ **Conclusión Cuantitativa**: Compras y Ventas tuvieron rendimientos equivalentes en esta muestra histórica.")
        elif long_count > 0 and short_count == 0:
            st.caption(f"🛡️ **Estrategia Unidireccional**: Esta configuración operó exclusivamente **COMPRAS (LONG)** para protegerte de la volatilidad corta ({long_count} compras, {long_wr:.1f}% acierto).")
        elif short_count > 0 and long_count == 0:
            st.caption(f"📉 **Estrategia en Corto**: Esta configuración operó exclusivamente **VENTAS (SHORT)** ({short_count} ventas, {short_wr:.1f}% acierto).")

        # 1.2 Risk Management Metrics (Stop Loss, Take Profit, Risk/Reward)
        sl_pct_list = []
        tp_pct_list = []
        for t in report.trades:
            e_p = getattr(t, "entry_price", 0.0)
            if e_p > 0:
                s_p = getattr(t, "sl_price", 0.0)
                if s_p > 0:
                    sl_pct_list.append(abs(e_p - s_p) / e_p * 100.0)
                t_p = getattr(t, "tp_price", 0.0)
                if t_p > 0:
                    tp_pct_list.append(abs(t_p - e_p) / e_p * 100.0)

        avg_sl_pct = (sum(sl_pct_list) / len(sl_pct_list)) if sl_pct_list else 0.0
        avg_tp_pct = (sum(tp_pct_list) / len(tp_pct_list)) if tp_pct_list else 0.0
        default_rr = (b_cfg.tp_atr_multiple / max(b_cfg.sl_atr_multiple, 0.01)) if b_cfg else 2.0
        avg_rr = (avg_tp_pct / avg_sl_pct) if avg_sl_pct > 0 else default_rr

        winning_pnls = [t.net_pnl for t in report.trades if t.net_pnl > 0]
        losing_pnls = [abs(t.net_pnl) for t in report.trades if t.net_pnl < 0]
        avg_win_usd = (sum(winning_pnls) / len(winning_pnls)) if winning_pnls else 0.0
        avg_loss_usd = (sum(losing_pnls) / len(losing_pnls)) if losing_pnls else 0.0

        st.markdown("##### 🛡️ Parámetros de Riesgo Promedio Aplicados a Cada Orden")
        r_col1, r_col2, r_col3, r_col4 = st.columns(4)
        with r_col1:
            st.metric("Stop Loss Promedio", f"-{avg_sl_pct:.2f}%", help="Distancia porcentual media a la que se colocó la orden de corte de pérdidas.")
        with r_col2:
            st.metric("Take Profit Promedio", f"+{avg_tp_pct:.2f}%", help="Distancia porcentual media a la que se colocó la orden de recogida de beneficios.")
        with r_col3:
            st.metric("Ratio Riesgo : Beneficio", f"1 : {avg_rr:.2f}", help="Por cada dólar que arriesgó la estrategia, buscó ganar esta proporción.")
        with r_col4:
            st.metric("Ganancia Media / Pérdida Media", f"${avg_win_usd:,.2f} / -${avg_loss_usd:,.2f}", help="Promedio ganado en trades positivos vs promedio perdido en fallos.")

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

                mae_col = trades_df["mae_pct"] if "mae_pct" in trades_df.columns else trades_df.get("mae", 0.0)
                mfe_col = trades_df["mfe_pct"] if "mfe_pct" in trades_df.columns else trades_df.get("mfe", 0.0)

                fig_mfe = go.Figure()
                fig_mfe.add_trace(
                    go.Scatter(
                        x=mae_col,
                        y=mfe_col,
                        mode="markers",
                        marker={
                            "size": 9,
                            "color": ["#00FF88" if p > 0 else "#FF2E63" for p in trades_df.get("net_pnl", [])],
                            "line": {"width": 1, "color": "#FFFFFF"},
                        },
                        text=[
                            f"Trade {t.get('trade_id', '')} ({t.get('side', '')}): PnL ${t.get('net_pnl', 0.0):.2f}<br>Máx Caída (MAE): {t.get('mae_pct', 0.0):.2f}%<br>Máx Ganancia (MFE): {t.get('mfe_pct', 0.0):.2f}%"
                            for t in trade_rows
                        ],
                        hoverinfo="text",
                    )
                )
                fig_mfe.update_layout(
                    xaxis_title="Pérdida Máxima Temporal (MAE %)",
                    yaxis_title="Ganancia Máxima Alcanzada (MFE %)",
                    height=360,
                    template="plotly_dark",
                    paper_bgcolor="#07090E",
                    plot_bgcolor="#07090E",
                    margin={"l": 20, "r": 20, "t": 30, "b": 20},
                    xaxis={"gridcolor": "rgba(255, 255, 255, 0.06)"},
                    yaxis={"gridcolor": "rgba(255, 255, 255, 0.06)"},
                )
                st.plotly_chart(fig_mfe, use_container_width=True)
                st.caption("💡 **MAE (Eje X)**: Peor caída temporal sufrida antes del cierre. **MFE (Eje Y)**: Mayor ganancia alcanzada durante el trade.")
            else:
                st.info("No se registraron operaciones en este período de simulación.")

        with t_right:
            st.subheader("📋 Registro de Transacciones")
            if report.trades:
                display_cols = {
                    "trade_id": "ID",
                    "side": "Dirección",
                    "entry_timestamp": "Entrada",
                    "entry_price": "P. Entrada",
                    "sl_price": "P. Stop Loss",
                    "tp_price": "P. Take Profit",
                    "exit_timestamp": "Salida",
                    "exit_price": "P. Salida",
                    "net_pnl": "PnL Neto ($)",
                    "exit_reason": "Causa Cierre",
                }
                valid_cols = [c for c in display_cols if c in trades_df.columns]
                trades_display = trades_df[valid_cols].rename(columns=display_cols)
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