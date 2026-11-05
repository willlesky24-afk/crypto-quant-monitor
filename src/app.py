from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from plotly.subplots import make_subplots

# Ensure project root directory is on sys.path for cloud deployment (Streamlit Cloud, Render, etc.)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Local credentials: without this the app silently used the default forex provider.
if not os.getenv("CQM_SKIP_DOTENV"):  # tests must never read real credentials
    load_dotenv(_ROOT / ".env")

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
    from src.backtest_metrics import BacktestMetricsCalculator
    from src.backtest_models import (
        EXCURSION_POLICY_VERSION,
        BacktestConfig,
        BacktestValidationError,
        ExecutionPolicyVersion,
        ExecutionTraceStatus,
    )
    from src.backtest_presets import (
        PROVEN_STRATEGIES,
        build_strategy_config,
        evaluate_backtest_verdict,
    )
    from src.backtest_runner import BacktestRunner
    from src.constants import LIVE_HISTORY_BARS
    from src.daily_summary import (
        build_market_summary,
        format_price,
        market_conditions,
    )
    from src.data_loader import BinanceDataLoader
    from src.decision_engine import DecisionEngine
    from src.engine import MarketEngine
    from src.forex_data_loader import FOREX_PAIRS, ForexDataError, ForexDataLoader
    from src.forex_sessions import get_forex_session_status
    from src.funding_rates import (
        FundingSource,
        FundingUnavailableError,
        funding_snapshot,
        provider_from_env,
    )
    from src.indicators import TechnicalIndicators
    from src.market_intelligence import MarketIntelligence
    from src.market_reports.generator import MarketReportService
    from src.market_scanner import MarketScanner
    from src.notifications.channels.discord import DiscordWebhookChannel
    from src.notifications.channels.telegram import TelegramChannel
    from src.notifications.channels.webhook import WebhookChannel
    from src.notifications.dispatcher import NotificationDispatcher
    from src.notifications.models import NotificationPriority, SignalEvent
    from src.notifications.tracker import AlertOutcomeTracker
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
    from src.report import MarketReport
    from src.risk_engine import RiskEngine
    from src.signal_engine import SignalEngine
    from src.unusual_radar import build_markets, run_radar
    from src.volume_profile import VolumeProfile
except ImportError:
    from ai_agent.context_builder import ContextBuilder
    from ai_providers.factory import ProviderFactory
    from anomaly_detection.detector import MarketAnomalyDetector
    from backtest_metrics import BacktestMetricsCalculator
    from backtest_models import (
        EXCURSION_POLICY_VERSION,
        BacktestConfig,
        BacktestValidationError,
        ExecutionPolicyVersion,
        ExecutionTraceStatus,
    )
    from backtest_presets import (
        PROVEN_STRATEGIES,
        build_strategy_config,
        evaluate_backtest_verdict,
    )
    from backtest_runner import BacktestRunner
    from constants import LIVE_HISTORY_BARS
    from daily_summary import (
        build_market_summary,
        format_price,
        market_conditions,
    )
    from data_loader import BinanceDataLoader
    from decision_engine import DecisionEngine
    from engine import MarketEngine
    from forex_data_loader import FOREX_PAIRS, ForexDataError, ForexDataLoader
    from forex_sessions import get_forex_session_status
    from funding_rates import (
        FundingSource,
        FundingUnavailableError,
        funding_snapshot,
        provider_from_env,
    )
    from indicators import TechnicalIndicators
    from market_intelligence import MarketIntelligence
    from market_reports.generator import MarketReportService
    from market_scanner import MarketScanner
    from notifications.channels.discord import DiscordWebhookChannel
    from notifications.channels.telegram import TelegramChannel
    from notifications.channels.webhook import WebhookChannel
    from notifications.dispatcher import NotificationDispatcher
    from notifications.models import NotificationPriority, SignalEvent
    from notifications.tracker import AlertOutcomeTracker
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
    from report import MarketReport
    from risk_engine import RiskEngine
    from signal_engine import SignalEngine
    from unusual_radar import build_markets, run_radar
    from volume_profile import VolumeProfile


def _run_backtest_for_ui(
    config,
    candles,
    symbol,
    interval,
    session_state,
    *,
    calibrated_params=None,
    calibration_required=False,
):
    """Replace the displayed report only after a successful validated run."""
    session_state.pop("backtest_report", None)
    report = BacktestRunner(config=config).run_backtest(
        df=candles,
        symbol=symbol,
        interval=interval,
        predictive_mode=True,
        calibrated_params=calibrated_params,
        calibration_required=calibration_required,
    )
    session_state["backtest_report"] = report
    return report


def _format_sharpe_for_ui(value):
    """Keep an unavailable Sharpe distinct from a calculated zero."""
    return "N/A" if value is None else f"{value:.2f}"


def _format_verified_expectancy_for_ui(metrics, field):
    """Never fall back to the legacy hybrid expectancy_r."""
    if metrics.get("r_coverage_status") not in {"COMPLETE", "PARTIAL"}:
        return "N/A"
    value = metrics.get(field)
    try:
        return f"{value:.2f}" if value is not None and math.isfinite(value) else "N/A"
    except (TypeError, ValueError):
        return "N/A"


def _r_coverage_for_ui(metrics):
    status = metrics.get("r_coverage_status", "UNKNOWN")
    if status == "NO_TRADES":
        return "Cobertura R: NO_TRADES — No existen operaciones; expectativas N/A."
    if status == "NONE_VERIFIED":
        return "Cobertura R: NONE_VERIFIED — Ninguna operación tiene R verificable; expectativas N/A."
    if status in {"PARTIAL", "COMPLETE"}:
        verified = metrics.get("r_verified_trades", 0)
        excluded = metrics.get("r_excluded_trades", 0)
        total = metrics.get("total_trades", verified + excluded)
        coverage = f"{verified} verificables, {excluded} excluidas, {total} en total"
        if status == "PARTIAL":
            return (
                f"Cobertura R: PARTIAL — {coverage}. "
                "Expectativa calculada únicamente sobre operaciones verificables."
            )
        return f"Cobertura R: COMPLETE — {coverage}."
    return "Cobertura R: UNKNOWN — No hay evidencia suficiente para presentar expectativa R verificada."


def _trade_field_for_ui(trade, field):
    return trade.get(field) if isinstance(trade, dict) else getattr(trade, field, None)


def _excursion_for_ui(trade, name):
    """Show exact values or justified intervals, never a legacy point proxy."""
    if (
        _trade_field_for_ui(trade, "excursion_policy_version")
        != EXCURSION_POLICY_VERSION
    ):
        return "N/A (proxy heredado; observabilidad no acreditada)"
    status = _trade_field_for_ui(trade, f"{name}_observability")
    if status == "EXACT_OHLC":
        value = _trade_field_for_ui(trade, f"{name}_exact_pct")
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        ):
            return f"{value:.2f}% (exacta OHLC)"
    if status == "BOUNDED_OHLC":
        lower = _trade_field_for_ui(trade, f"{name}_lower_bound_pct")
        upper = _trade_field_for_ui(trade, f"{name}_upper_bound_pct")
        if (
            isinstance(lower, (int, float))
            and isinstance(upper, (int, float))
            and not isinstance(lower, bool)
            and not isinstance(upper, bool)
            and math.isfinite(lower)
            and math.isfinite(upper)
            and 0 <= lower <= upper
        ):
            return f"[{lower:.2f}%, {upper:.2f}%] (cota OHLC)"
    return "N/A (indeterminada)"


def _excursion_coverage_for_ui(metrics, name):
    status = metrics.get(f"{name}_coverage_status", "UNKNOWN")
    if status == "UNKNOWN":
        return f"{name.upper()} exacta OHLC: N/A; cobertura UNKNOWN (histórico sin clasificación)."
    count = metrics.get(f"{name}_exact_trades", 0)
    total = metrics.get(f"{name}_total_trades", metrics.get("total_trades", 0))
    average = metrics.get(f"{name}_exact_avg_pct")
    displayed = (
        f"{average:.2f}%"
        if isinstance(average, (int, float)) and math.isfinite(average)
        else "N/A"
    )
    return f"{name.upper()} exacta OHLC: {displayed}; cobertura {status} ({count}/{total} operaciones)."


def _positive_finite_for_ui(value):
    try:
        return value is not None and math.isfinite(value) and value > 0
    except (TypeError, ValueError):
        return False


def _supported_spot_long_for_ui(config):
    """Ledgers the engine validates: SPOT LONG 1x or MARGIN_1X (v2.3)."""
    if config is None or _trade_field_for_ui(config, "leverage") != 1.0:
        return False
    market = _trade_field_for_ui(config, "market_type")
    direction = _trade_field_for_ui(config, "direction")
    return (market == "SPOT" and direction == "LONG") or (
        market == "MARGIN_1X" and direction in ("LONG", "SHORT", "BOTH")
    )


def _planned_rr_for_ui(trade, config):
    """Gross planned TP/initial-stop distance for a coherent SPOT LONG trade."""
    entry = _trade_field_for_ui(trade, "entry_price")
    stop = _trade_field_for_ui(trade, "initial_stop_price")
    target = _trade_field_for_ui(trade, "tp_price")
    units = _trade_field_for_ui(trade, "size_units")
    risk = _trade_field_for_ui(trade, "initial_risk_amount")
    per_unit = _trade_field_for_ui(trade, "initial_risk_per_unit")
    side = _trade_field_for_ui(trade, "side")
    is_short = side == "SHORT"
    if (
        not _supported_spot_long_for_ui(config)
        or _trade_field_for_ui(trade, "direction") != side
        or side not in ("LONG", "SHORT")
        or (is_short and _trade_field_for_ui(config, "market_type") != "MARGIN_1X")
        or not all(
            _positive_finite_for_ui(x)
            for x in (entry, stop, target, units, risk, per_unit)
        )
        or not (target < entry < stop if is_short else stop < entry < target)
    ):
        return None
    if not math.isclose(
        per_unit, abs(entry - stop), rel_tol=1e-9, abs_tol=1e-10
    ) or not math.isclose(risk, units * per_unit, rel_tol=1e-9, abs_tol=1e-10):
        return None
    ratio = abs(target - entry) / abs(entry - stop)
    return ratio if math.isfinite(ratio) and ratio > 0 else None


def _planned_rr_summary_for_ui(trades, config):
    ratios = [
        ratio
        for trade in trades
        if (ratio := _planned_rr_for_ui(trade, config)) is not None
    ]
    return (sum(ratios) / len(ratios) if ratios else None, len(ratios))


def _verified_trade_r_for_ui(trade, config):
    if not _supported_spot_long_for_ui(config):
        return None
    try:
        return BacktestMetricsCalculator._verified_spot_long_r(trade)
    except (AttributeError, TypeError, ValueError):
        return None


def _execution_trace_for_ui(trade):
    """An absent/unknown status never proves that an old fill was unambiguous."""
    status = _trade_field_for_ui(trade, "execution_trace_status")
    if status == ExecutionTraceStatus.OPENING_LEVEL_REVIEW.value:
        if (
            _trade_field_for_ui(trade, "execution_policy_version")
            == ExecutionPolicyVersion.SPOT_LONG_C1.value
        ):
            return "Apertura/gap: fill simulado C1 (no verificado)"
        return (
            "Apertura/gap: fill pendiente de revisión (política anterior o desconocida)"
        )
    labels = {
        ExecutionTraceStatus.INTRABAR_SL_FIRST.value: "Conflicto intrabar: SL primero (simulado)",
        ExecutionTraceStatus.NO_IDENTIFIED_CONFLICT.value: "Sin conflicto identificado (no verificado)",
        ExecutionTraceStatus.UNDETERMINED.value: "N/A (niveles o apertura indeterminados)",
    }
    return labels.get(status, "N/A (histórico sin metadatos)")


def _execution_policy_for_ui(trade):
    if (
        _trade_field_for_ui(trade, "execution_policy_version")
        == ExecutionPolicyVersion.SPOT_LONG_C1.value
    ):
        return "C1: apertura prioritaria; TP limit simulado"
    return "N/A (metodología histórica no identificada)"


def _execution_trace_summary_for_ui(trades):
    statuses = [
        _trade_field_for_ui(trade, "execution_trace_status") for trade in trades
    ]
    conflicts = statuses.count(ExecutionTraceStatus.INTRABAR_SL_FIRST.value)
    openings = statuses.count(ExecutionTraceStatus.OPENING_LEVEL_REVIEW.value)
    unknown = sum(
        status
        not in {
            ExecutionTraceStatus.INTRABAR_SL_FIRST.value,
            ExecutionTraceStatus.OPENING_LEVEL_REVIEW.value,
            ExecutionTraceStatus.NO_IDENTIFIED_CONFLICT.value,
        }
        for status in statuses
    )
    c1_count = sum(
        _trade_field_for_ui(trade, "execution_policy_version")
        == ExecutionPolicyVersion.SPOT_LONG_C1.value
        for trade in trades
    )
    return (
        f"Trazabilidad de salidas: {conflicts} conflictos intrabar (SL primero), "
        f"{openings} aperturas/gaps, {unknown} estados desconocidos; "
        f"con política C1: {c1_count}; sin versión acreditada: {len(trades) - c1_count}. "
        "SL primero es una hipótesis conservadora de simulación; OHLC no revela "
        "la secuencia real ni verifica los fills."
    )


def _backtest_trade_table_for_ui(trades, config):
    """Keep historical missing levels/R explicit; never infer the initial stop."""

    def price(value):
        return f"{value:,.2f}" if _positive_finite_for_ui(value) else "N/A"

    rows = []
    for trade in trades:
        verified_r = _verified_trade_r_for_ui(trade, config)
        rows.append(
            {
                "ID": _trade_field_for_ui(trade, "trade_id"),
                "Dirección": _trade_field_for_ui(trade, "side")
                or _trade_field_for_ui(trade, "direction"),
                "Entrada": _trade_field_for_ui(trade, "entry_timestamp"),
                "P. entrada ejecutada": price(
                    _trade_field_for_ui(trade, "entry_price")
                ),
                "SL inicial": price(_trade_field_for_ui(trade, "initial_stop_price")),
                "SL final": price(_trade_field_for_ui(trade, "sl_price")),
                "TP planificado": price(_trade_field_for_ui(trade, "tp_price")),
                "Salida": _trade_field_for_ui(trade, "exit_timestamp"),
                "P. salida": price(_trade_field_for_ui(trade, "exit_price")),
                "R bruto simulado": f"{verified_r[0]:.2f}" if verified_r else "N/A",
                "R neto simulado": f"{verified_r[1]:.2f}" if verified_r else "N/A",
                "PnL neto ($)": _trade_field_for_ui(trade, "net_pnl"),
                "Causa cierre": _trade_field_for_ui(trade, "exit_reason"),
                "Trazabilidad salida": _execution_trace_for_ui(trade),
                "Política ejecución": _execution_policy_for_ui(trade),
            }
        )
    return pd.DataFrame(rows)


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
    try:
        forex_pairs = ForexDataLoader().available_pairs()
    except ForexDataError as exc:
        st.sidebar.error(f"Proveedor forex no disponible: {exc}")
        st.stop()
    selected_label = st.sidebar.selectbox(
        "Par de Divisas Forex / Metales",
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
market_desc = (
    "💱 Divisas Forex Globales (Interbancario)"
    if is_forex
    else "🪙 Criptomonedas (Binance Spot & Futuros)"
)
st.caption(
    f"{market_desc} • Quantitative Engine • Predictive Intelligence • Real-Time Monitoring & Backtesting"
)

# =====================================================================
# SIDEBAR: MODO DE ANÁLISIS (AUTOMÁTICO VS MANUAL / WHAT-IF)
# =====================================================================
st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Modo de Análisis")
sim_mode = st.sidebar.radio(
    "Fuente de Parámetros",
    ["🕹️ Manual (Simulador de Escenarios)", "🟢 Automático (En Vivo)"],
    index=1,
)

is_manual_mode = "Manual" in sim_mode

if is_manual_mode:
    st.sidebar.markdown("##### ⚙️ Parámetros Forzados")
    from src.regime_classifier import MarketRegime
    from src.strategy_optimizer import OptimizedParameters

    regime_options = [r.value for r in MarketRegime]
    manual_regime_str = st.sidebar.selectbox(
        "Régimen de Mercado", regime_options, index=0
    )
    manual_regime = MarketRegime(manual_regime_str)

    manual_pred_score = st.sidebar.slider("Predictive Score", 0.0, 1.0, 0.65, 0.05)
    manual_prob_cont = st.sidebar.slider("P(Continuación)", 0.0, 1.0, 0.60, 0.05)
    manual_tp_mult = st.sidebar.slider("Target TP (x ATR)", 1.0, 6.0, 3.0, 0.25)
    manual_sl_mult = st.sidebar.slider("Stop Loss SL (x ATR)", 0.5, 4.0, 1.5, 0.25)
    manual_tech_weight = st.sidebar.slider(
        "Peso Análisis Técnico", 0.1, 0.9, 0.60, 0.05
    )

# Fetch Market Data (Crypto vs Forex)
try:
    if is_forex:
        forex_loader = ForexDataLoader()
        # Analysis always uses the shared history (v3.0); the slider only
        # sets how many candles the chart displays.
        df_raw = forex_loader.get_forex_klines(
            symbol=symbol,
            interval=interval,
            limit=max(limit, LIVE_HISTORY_BARS),
        )
    else:
        loader = BinanceDataLoader()
        df_raw = loader.get_klines(
            symbol=symbol,
            interval=interval,
            limit=max(limit, LIVE_HISTORY_BARS),
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
tab_live, tab_risk, tab_radar, tab_copilot, tab_backtest, tab_settings, tab_guide = (
    st.tabs(
        [
            "📡 Live Monitor",
            "🛡️ Calculadora de Riesgo",
            "🛰️ Radar",
            "🤖 AI Copilot",
            "📈 Backtest Analytics",
            "⚙️ Notification Settings",
            "📖 Guía & Glosario",
        ]
    )
)


# =====================================================================
# TAB: CALCULADORA DE RIESGO (v3.1)
# =====================================================================
with tab_risk:
    st.subheader("🛡️ ¿Cuánto puedo operar sin arriesgar de más?")
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
            ["Comprar (LONG)", "Vender (SHORT)"],
            horizontal=True,
        )
        risk_side = "SHORT" if "SHORT" in risk_side_label else "LONG"
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
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Tamaño (unidades)", f"{risk_plan.units:,.4f}")
        m2.metric("Valor de la posición", f"${risk_plan.notional:,.2f}")
        m3.metric("Pérdida si toca el stop", f"${risk_plan.max_loss:,.2f}")
        m4.metric("Costos incluidos", f"${risk_plan.costs:,.2f}")
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
]


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
    st.subheader("🛰️ ¿Qué está fuera de lo normal?")
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
                [RADAR_CRYPTO, radar_forex],
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
            st.warning(f"**{radar_alert.market}.** {radar_alert.text}")
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
    with st.expander("☀️ ¿Qué está pasando hoy?", expanded=True):
        for summary_line in summary["lines"]:
            st.write(summary_line)
        conditions = market_conditions(df)
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

    # 2. Key Metrics Header
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Precio Actual", f"${format_price(curr_price)}")
    with col2:
        st.metric("Régimen de Mercado", regime_res.regime.value)
    with col3:
        st.metric(
            "Estado de señal", f"{trade_plan['status']} ({trade_plan['direction']})"
        )
        st.caption(f"Decisión técnica: {decision.decision}")
    with col4:
        conf_pct = (
            decision.confidence
            if decision.confidence > 1.0
            else decision.confidence * 100.0
        )
        st.metric("Confianza", f"{conf_pct:.1f}%")
    with col5:
        st.metric(
            "Predictive Score",
            f"{pred_res.predictive_score:.2f}",
            f"P(Cont): {pred_res.probability_continuation * 100:.0f}%",
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
            increasing_line_color="#00FF88",
            increasing_fillcolor="#00FF88",
            decreasing_line_color="#FF2E63",
            decreasing_fillcolor="#FF2E63",
        )
    )

    # EMAs with Cyan and Magenta
    if "ema_50" in df.columns:
        fig_live.add_trace(
            go.Scatter(
                x=df_chart["timestamp"],
                y=df_chart["ema_50"],
                name="EMA 50",
                line={"color": "#00E5FF", "width": 2},
            )
        )
    if "ema_200" in df.columns:
        fig_live.add_trace(
            go.Scatter(
                x=df_chart["timestamp"],
                y=df_chart["ema_200"],
                name="EMA 200",
                line={"color": "#BD00FF", "width": 2},
            )
        )

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
        font={
            "family": "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto",
            "color": "#E6EDF3",
        },
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
    c_layer1, c_layer2, c_layer3, c_layer4, c_layer5 = st.tabs(
        [
            "🧠 Diagnóstico",
            "📋 Plan de riesgo",
            "🎯 Niveles",
            "🔮 Predicción",
            "🛠️ Datos",
        ]
    )

    reporter = MarketReport()
    m_report = reporter.generate(symbol, analysis, profile)

    with c_layer1:
        conf_val = (
            decision.confidence
            if decision.confidence > 1.0
            else decision.confidence * 100.0
        )
        tech_score = getattr(decision, "technical_score", score.get("score", 70.0))
        pred_sc = getattr(decision, "predictive_score", pred_res.predictive_score)

        narrative_p = (
            f"El motor cuantitativo clasifica a <strong>{symbol}</strong> ({interval}) como "
            f"<strong>{trade_plan['status']}</strong>, dirección <strong>{trade_plan['direction']}</strong>. "
            f"Puntaje técnico: {tech_score:.1f}; puntaje predictivo: {pred_sc:.2f}. "
            f"{trade_plan['reason']}"
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
                    <span class="metric-pill metric-pill-coral">🛑 SL: {format_risk_level(trade_plan["stop_loss"])}</span>
                    <span class="metric-pill metric-pill-green">🎯 TP: {format_risk_level(trade_plan["take_profit"])}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        market_badge_text = (
            "💱 Mercado Forex Global" if is_forex else "🪙 Mercado Criptomonedas 24/7"
        )
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
                st.caption(
                    "Sin confluencias alcistas de alta significancia detectadas."
                )

        with col_warn:
            st.markdown("##### ⚠️ Factores de Riesgo")
            if decision.warnings:
                for warn in decision.warnings:
                    st.markdown(f"- ⚠️ **{warn}**")
            else:
                st.caption("No se registran factores de riesgo estructural inmediatos.")

        with st.expander(
            "🔬 Ver fórmula técnica y parámetros detallados", expanded=False
        ):
            st.code(decision.reasoning, language="text")
            conclusion = (
                m_report.get("conclusion")
                or "Evaluación en curso con parámetros de riesgo definidos."
            )
            st.caption(f"📌 Conclusión del Reporte: {conclusion}")

    with c_layer2:
        st.caption(
            f"{symbol} · {interval} · {trade_plan['status']} · {trade_plan['direction']}"
        )
        p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns(5)
        with p_col1:
            st.metric("Referencia", format_risk_level(trade_plan["reference_price"]))
        with p_col2:
            st.metric("Entrada propuesta", format_risk_level(trade_plan["entry_price"]))
        with p_col3:
            st.metric("Stop Loss", format_risk_level(trade_plan["stop_loss"]))
        with p_col4:
            st.metric("Take Profit", format_risk_level(trade_plan["take_profit"]))
        with p_col5:
            gross_rr = trade_plan["gross_risk_reward"]
            st.metric(
                "R bruto indicativo",
                f"1 : {gross_rr:.2f}" if gross_rr is not None else "No disponible",
            )

        if trade_plan["risk_distance"] is not None:
            st.caption(
                f"Distancia de riesgo: {trade_plan['risk_distance']:.6g} · "
                f"distancia de beneficio: {trade_plan['reward_distance']:.6g}. "
                "R calculado desde entrada propuesta, SL y TP; sin spread, comisiones ni deslizamiento."
            )
        st.info(trade_plan["reason"])
        if trade_plan["methodology"] is not None:
            st.caption(f"Método: {trade_plan['methodology']}. Entrada no confirmada.")

    with c_layer3:
        poc_val = profile.get("poc")
        vah_val = profile.get("vah")
        val_val = profile.get("val")

        v_col1, v_col2, v_col3 = st.columns(3)
        with v_col1:
            if poc_val:
                st.metric(
                    "🟡 POC (Control)", f"${format_price(poc_val)}", "Mayor liquidez"
                )
        with v_col2:
            if vah_val:
                st.metric("🟢 VAH (Techo)", f"${format_price(vah_val)}", "Resistencia")
        with v_col3:
            if val_val:
                st.metric("🔴 VAL (Suelo)", f"${format_price(val_val)}", "Soporte")

        pos_text = "dentro del Área de Valor"
        if vah_val and curr_price > vah_val:
            pos_text = "por encima del VAH (desequilibrio alcista / premium)"
        elif val_val and curr_price < val_val:
            pos_text = "por debajo del VAL (desequilibrio bajista / descuento)"
        st.info(
            f"📊 **Lectura de Liquidez:** El precio actual (${curr_price:,.2f}) se encuentra {pos_text}."
        )

    with c_layer4:
        pr_col1, pr_col2, pr_col3 = st.columns(3)
        with pr_col1:
            st.metric("Predictive Score", f"{pred_res.predictive_score:.2f} / 1.00")
        with pr_col2:
            st.metric(
                "Prob. Continuación", f"{pred_res.probability_continuation * 100:.0f}%"
            )
        with pr_col3:
            st.metric("Régimen Activo", regime_res.regime.value)

        st.write(
            f"**Justificación de Régimen:** {regime_res.details.get('reason', 'Clasificación basada en estructura técnica y volatilidad.') if hasattr(regime_res, 'details') else 'Régimen cuantitativo activo.'}"
        )

    with c_layer5:
        st.caption("Datos técnicos sin procesar para auditoría o conexión vía API:")
        st.json(
            {
                "symbol": symbol,
                "timeframe": interval,
                "direction": decision.direction,
                "action": decision.decision,
                "quant_score": score["score"],
                "predictive_score": pred_res.predictive_score,
                "tp_multiplier": decision.tp_multiplier,
                "sl_multiplier": decision.sl_multiplier,
                "risk_plan": trade_plan,
                "poc": profile.get("poc"),
                "vah": profile.get("vah"),
                "val": profile.get("val"),
                "risk_assessment": m_report.get("conclusion", ""),
            }
        )


# =====================================================================
# TAB 2: AI COPILOT
# =====================================================================
with tab_copilot:
    st.subheader("🤖 Institutional AI Quant Copilot")
    st.caption(
        "Asistente de inteligencia de mercado • Razonamiento contextual con Gemini • Sin ejecución automática"
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

        # AI Model Configuration Controls (Gemini 3.8 / 3.5 / 3.7)
        with st.expander(
            "⚙️ Selección de Modelo AI Copilot (Gemini 3.8 / 3.5 / 3.7)", expanded=False
        ):
            cfg_col1, cfg_col2 = st.columns([2, 1])
            with cfg_col1:
                gemini_model_options = [
                    "gemini-flash-latest (Recomendado • Máxima Disponibilidad y Visión Multimodal)",
                    "gemini-3.8-flash (Nueva Generación • Mayor Capacidad)",
                    "gemini-3.7-flash (Estándar)",
                    "gemini-3.5-flash-lite (Ultra Rápido)",
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
        cop_tab1, cop_tab2, cop_tab3, cop_tab4 = st.tabs(
            [
                "💬 Chat AI",
                "📋 Briefing",
                "🚨 Anomalías",
                "🕒 Contexto",
            ]
        )

        with cop_tab1:
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

            # Quick Action Buttons
            q_col1, q_col2, q_col3 = st.columns([1.5, 1.5, 0.8])
            scan_triggered = False
            explain_triggered = False

            scan_btn_label = (
                "💱 Escanear Divisas Forex" if is_forex else "🚀 Escanear Criptomonedas"
            )
            with q_col1:
                if st.button(
                    scan_btn_label, key="btn_scan_market", use_container_width=True
                ):
                    scan_triggered = True
            with q_col2:
                if st.button(
                    f"🗣️ Explicar {symbol} en Lenguaje Sencillo",
                    key="btn_explain_current",
                    use_container_width=True,
                ):
                    explain_triggered = True
            with q_col3:
                if st.button(
                    "🗑️ Limpiar", key="btn_clear_chat", use_container_width=True
                ):
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
                            f"👋 **¡Hola! Soy tu AI Quant Copilot.**\n\n"
                            f"Puedo responder todas tus inquietudes sobre el mercado de **{market_label}** en **lenguaje cotidiano** y con datos cuantitativos en tiempo real:\n"
                            f"- Pregúntame: *¿Qué par presenta el mejor escenario para hacer trading hoy?*\n"
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
                                    use_container_width=True,
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
                                        use_container_width=True,
                                    )
                        elif msg.get("image_bytes"):
                            st.image(msg["image_bytes"], width=300)

            # Handler for Market Scanner Quick Action
            if scan_triggered:
                scan_market_name = (
                    "Forex (EUR/USD, GBP/USD, USD/JPY...)"
                    if is_forex
                    else "Binance (BTC, ETH, SOL, BNB, XRP)"
                )
                with st.spinner(
                    f"🔍 Analizando y comparando pares principales en {scan_market_name}..."
                ):
                    try:
                        if is_forex:
                            scanner = MarketScanner(data_loader=ForexDataLoader())
                            forex_symbols = [
                                s
                                for s in FOREX_PAIRS.values()
                                if not s.startswith("CUSTOM")
                            ][:6]
                            scan_results = scanner.scan_market(
                                symbols=forex_symbols, timeframe=interval
                            )
                            user_prompt = "¿Puedes analizar el mercado Forex y ver qué par me presenta el mejor escenario para operar hoy considerando las sesiones bancarias? Explícalo con datos y en lenguaje cotidiano."
                        else:
                            scanner = MarketScanner()
                            scan_results = scanner.scan_market()
                            user_prompt = "¿Puedes analizar el mercado crypto y ver qué par me presenta el mejor escenario para hacer trading? Explícalo con datos y en lenguaje cotidiano."

                        scan_summary = scanner.format_scanner_summary_es(scan_results)

                        st.session_state["copilot_chat_history"].append(
                            {
                                "role": "user",
                                "content": user_prompt,
                            }
                        )

                        query_obj = OperatorQuery(
                            query=f"Basado en este escaneo de mercado cuantitativo en tiempo real ({'Forex' if is_forex else 'Crypto'}):\n\n{scan_summary}\n\nExplica en lenguaje cotidiano al operador cuál es el mejor par para trading, por qué supera a los otros, qué significan sus números y cuáles son los niveles clave de entrada y riesgo.",
                            symbol=scan_results[0].symbol if scan_results else symbol,
                            timeframe=interval,
                            operator_id="dashboard_operator",
                            metadata={
                                "market_type": "Forex" if is_forex else "Crypto",
                                "conversation_history": [
                                    {"role": m["role"], "content": m["content"]}
                                    for m in st.session_state["copilot_chat_history"][
                                        -6:
                                    ]
                                ],
                            },
                        )
                        copilot_res = _safe_async_run(copilot_assistant.ask(query_obj))
                        if (
                            "⚠️" in copilot_res.answer
                            or "fallback" in copilot_res.answer.lower()
                            or "503" in copilot_res.answer
                            or "unable to analyze" in copilot_res.answer.lower()
                        ):
                            answer_text = (
                                f"{scan_summary}\n\n---\n"
                                f"💡 *Nota: Diagnóstico generado directamente por el motor cuantitativo algorítmico local "
                                f"(la API de Gemini presentó alta demanda temporal en Google).* "
                            )
                        else:
                            answer_text = f"{copilot_res.answer}\n\n---\n{scan_summary}"

                        st.session_state["copilot_chat_history"].append(
                            {
                                "role": "assistant",
                                "content": answer_text,
                            }
                        )
                        st.rerun()
                    except Exception as scan_err:
                        st.error(f"Error ejecutando escaneo de mercado: {scan_err}")

            # Handler for Explain Current Asset Quick Action
            if explain_triggered:
                market_label = "Forex" if is_forex else "Cripto"
                user_prompt = f"Explícame en lenguaje cotidiano la situación actual de {symbol} ({market_label}): qué significa su Quant Score, el régimen de mercado y sus niveles de soporte y riesgo."
                st.session_state["copilot_chat_history"].append(
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                )
                with st.spinner(
                    f"AI Copilot traduciendo métricas de {symbol} a lenguaje cotidiano..."
                ):
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
                                    for m in st.session_state["copilot_chat_history"][
                                        -6:
                                    ]
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
                    except Exception as exp_err:
                        st.error(f"Error generando explicación: {exp_err}")

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

        with cop_tab2:
            st.markdown("#### 📋 Briefing Diario del Mercado")
            daily_rep = market_report_svc.generate_daily_briefing(
                current_market_context
            )
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
                st.success(
                    "✅ Sin anomalías estructurales ni divergencias severas de volatilidad detectadas en este activo."
                )
            else:
                for alt in detected_anomalies:
                    if alt.severity.value == "CRITICAL":
                        st.error(
                            f"**[{alt.severity.value}] {alt.headline}**\n\n{alt.reason}"
                        )
                    elif alt.severity.value == "WARNING":
                        st.warning(
                            f"**[{alt.severity.value}] {alt.headline}**\n\n{alt.reason}"
                        )
                    else:
                        st.info(
                            f"**[{alt.severity.value}] {alt.headline}**\n\n{alt.reason}"
                        )

        with cop_tab4:
            st.markdown("#### 🕒 Snapshot de Contexto Activo")
            snap_col1, snap_col2, snap_col3, snap_col4 = st.columns(4)
            with snap_col1:
                st.metric("Régimen Activo", current_market_context.market_regime)
            with snap_col2:
                st.metric(
                    "Puntuación Quant", f"{current_market_context.quant_score:.1f}/100"
                )
            with snap_col3:
                st.metric(
                    "Predictive Score", f"{current_market_context.predictive_score:.2f}"
                )
            with snap_col4:
                context_status = current_market_context.metadata.get(
                    "signal_status", "NO DISPONIBLE"
                )
                st.metric(
                    "Estado de señal",
                    f"{context_status} ({current_market_context.signal.direction})",
                )

            with st.expander(
                "🛠️ Ver snapshot técnico completo en formato JSON (Avanzado)",
                expanded=False,
            ):
                st.json(
                    {
                        "symbol": current_market_context.symbol,
                        "timeframe": current_market_context.timeframe,
                        "regime": current_market_context.market_regime,
                        "quant_score": current_market_context.quant_score,
                        "predictive_score": current_market_context.predictive_score,
                        "action": current_market_context.signal.action,
                        "signal_status": context_status,
                        "direction": current_market_context.signal.direction,
                        "confidence": current_market_context.signal.confidence,
                        "stop_loss": current_market_context.risk.stop_loss,
                        "take_profit": current_market_context.risk.take_profit,
                        "atr": current_market_context.risk.atr,
                    }
                )
    except Exception as cop_err:
        st.error(f"Error inicializando AI Copilot: {cop_err}")


# =====================================================================
# TAB 3: BACKTEST ANALYTICS
with tab_backtest:
    market_name_cap = "Divisas Forex" if is_forex else "Criptomonedas"
    st.subheader(f"📈 Simulación Histórica & Backtest Analytics ({market_name_cap})")
    st.caption(
        "Simulación sobre datos históricos cargados • No ejecuta operaciones ni acredita resultados futuros"
    )

    market_advice = (
        "💡 **Forex:** Los enfoques de reversión a la media y seguimiento de tendencia son hipótesis de simulación; sus resultados dependen de la muestra, los costes y la calidad de los datos."
        if is_forex
        else "💡 **Cripto:** Los presets de ruptura de volatilidad y modelo híbrido permiten explorar hipótesis históricas; no acreditan desempeño futuro."
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
            "👶 Modo Guiado (Presets de Simulación & Capital Flexible)",
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
                if st.button(
                    f"${int(amt)}", key=f"cap_btn_{int(amt)}", use_container_width=True
                ):
                    st.session_state["guided_capital"] = float(amt)
                    st.session_state["input_guided_cap"] = float(amt)
                    st.rerun()

        if "input_guided_cap" not in st.session_state:
            st.session_state["input_guided_cap"] = float(
                st.session_state["guided_capital"]
            )

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
                    f"{int(x)}x (Spot • Sin apalancamiento)"
                    if x == 1.0
                    else (
                        f"{int(x)}x (Moderado • Doble Retorno / Doble Riesgo)"
                        if x == 2.0
                        else (
                            f"{int(x)}x (Avanzado • Triple Exposición)"
                            if x == 3.0
                            else f"{int(x)}x (Agresivo • Alto Riesgo)"
                        )
                    )
                ),
                index=0,
                key="sel_guided_leverage",
            )
        with lev_c2:
            if selected_leverage == 1.0:
                st.info(
                    "**SPOT LONG 1x disponible**: la simulación no utiliza apalancamiento; el capital sigue expuesto a pérdidas de mercado."
                )
            else:
                st.warning(
                    f"⚠️ **Apalancamiento {int(selected_leverage)}x no disponible** en "
                    "backtests SPOT. La simulación rechazará esta selección; solo SPOT LONG 1x está validado."
                )

        st.markdown("##### 2️⃣ Elige un preset de estrategia para la simulación")
        strategy_keys = list(PROVEN_STRATEGIES.keys())
        strategy_labels = [PROVEN_STRATEGIES[k]["name"] for k in strategy_keys]
        selected_strategy_label = st.selectbox(
            "Estrategia Cuantitativa:",
            options=strategy_labels,
            index=0,
        )
        chosen_strategy_key = strategy_keys[
            strategy_labels.index(selected_strategy_label)
        ]
        chosen_strategy_info = PROVEN_STRATEGIES[chosen_strategy_key]

        st.markdown(
            f"""
            <div class="strategy-preset-card">
                <strong style="color: #00E5FF;">{chosen_strategy_info["name"]}</strong><br/>
                <span style="color: #F0F6FC; font-size: 0.88rem; line-height: 1.5;">{chosen_strategy_info["description"]}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        run_sim = st.button(
            "🚀 Simular Estrategia con Datos Históricos",
            type="primary",
            use_container_width=True,
        )

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
            if is_forex:
                # Forex/metals presets run on MARGIN_1X: cost = per-candle spread,
                # not crypto taker fees (v2.3 D1/D2).
                b_cfg.market_type = "MARGIN_1X"
                b_cfg.taker_fee_pct = 0.0
                b_cfg.slippage_pct = 0.0

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
            taker_fee_pct = (
                st.number_input(
                    "Comisión Taker (%)",
                    min_value=0.0,
                    max_value=1.0,
                    # Forex/metals (MARGIN_1X): the cost is the per-candle spread.
                    value=0.0 if is_forex else 0.05,
                    step=0.01,
                )
                / 100.0
            )
        with b_col3:
            slippage_pct = (
                st.number_input(
                    "Slippage (%)",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.0 if is_forex else 0.05,
                    step=0.01,
                )
                / 100.0
            )
        with b_col4:
            direction_choice = st.selectbox(
                "Dirección de Operación",
                ["LONG", "BOTH", "SHORT"],
                index=0,
            )
            if is_forex:
                st.caption(
                    "MARGIN_1X (forex/metales, sin apalancamiento). Coste: spread "
                    "bid/ask real por vela cuando el proveedor lo publica (OANDA)."
                )
            elif direction_choice != "LONG":
                st.warning(
                    "Cripto SPOT solo admite LONG: SHORT/BOTH requieren MARGIN_1X "
                    "(forex y metales)."
                )

        run_sim = st.button(
            "🚀 Ejecutar Backtest Personalizado",
            type="primary",
            use_container_width=True,
        )

        if run_sim:
            b_cfg = BacktestConfig(
                initial_capital=initial_cap,
                taker_fee_pct=taker_fee_pct,
                slippage_pct=slippage_pct,
                direction=direction_choice,
                market_type="MARGIN_1X" if is_forex else "SPOT",
                leverage=1.0,
            )

    if run_sim or "backtest_report" in st.session_state:
        if run_sim and b_cfg is not None:
            source_label = "Forex Global" if is_forex else "Binance"
            with st.spinner(
                f"Ejecutando simulación vela por vela sobre datos cargados de {source_label}..."
            ):
                try:
                    _run_backtest_for_ui(
                        config=b_cfg,
                        candles=df,
                        symbol=symbol,
                        interval=interval,
                        session_state=st.session_state,
                    )
                except BacktestValidationError as exc:
                    st.error(
                        f"Backtest rechazado ({b_cfg.market_type}, {b_cfg.direction}, "
                        f"{b_cfg.leverage}x): {exc} "
                        "Configuraciones disponibles: SPOT LONG 1x (cripto) o "
                        "MARGIN_1X LONG/SHORT 1x (forex y metales)."
                    )
                    st.stop()

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
            <div class="verdict-card" style="border: 1px solid {verdict["color"]};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="color: {verdict["color"]}; font-weight: 700; font-size: 0.95rem; letter-spacing: 0.5px;">{verdict["badge"]}</span>
                    <span style="color: #8B949E; font-size: 0.80rem;">{symbol} • {interval}</span>
                </div>
                <div style="color: #F0F6FC; font-size: 1.05rem; font-weight: 600; margin-bottom: 6px;">
                    {verdict["title"]}
                </div>
                <div style="color: #C9D1D9; font-size: 0.88rem; line-height: 1.6;">
                    {verdict["description"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "Clasificación por umbrales configurados en esta simulación; no es validación prospectiva ni garantía de resultados."
        )
        provenance = getattr(report, "data_provenance", None)
        provenance_status = (
            provenance.get("status")
            if isinstance(provenance, dict)
            else getattr(provenance, "status", "UNKNOWN")
        )
        if provenance_status == "UNKNOWN":
            st.warning(
                "Procedencia del dataset: UNKNOWN. La coherencia matemática del R no acredita el origen de los datos históricos."
            )

        # AI Copilot Integration Button
        c_consult_btn, _ = st.columns([1.5, 2.0])
        with c_consult_btn:
            if st.button(
                "🤖 Preguntar al Copilot: ¿Qué significa este resultado para mí?",
                key="btn_ask_copilot_backtest",
                use_container_width=True,
            ):
                backtest_prompt = (
                    f"Acabo de ejecutar un backtest para {symbol} ({interval}) con los siguientes resultados cuantitativos:\n"
                    f"- Total de Trades: {metrics.get('total_trades', 0)}\n"
                    f"- Win Rate: {metrics.get('win_rate', 0.0) * 100:.1f}%\n"
                    f"- Profit Factor: {metrics.get('profit_factor', 0.0):.2f}\n"
                    f"- Caída Máxima (Max Drawdown): {metrics.get('max_drawdown_pct', 0.0):.2f}%\n"
                    f"- Retorno Neto: ${metrics.get('net_pnl', 0.0):,.2f}\n"
                    f"- Veredicto: {verdict['badge']} - {verdict['title']}\n\n"
                    "Explica en lenguaje cotidiano qué describen estos resultados de simulación, sus límites de procedencia y cobertura, sin recomendar una operación ni inferir rentabilidad futura."
                )
                if "copilot_chat_history" not in st.session_state:
                    st.session_state["copilot_chat_history"] = []
                st.session_state["copilot_chat_history"].append(
                    {
                        "role": "user",
                        "content": backtest_prompt,
                    }
                )
                try:
                    q_obj = OperatorQuery(
                        query=backtest_prompt,
                        symbol=symbol,
                        timeframe=interval,
                        operator_id="dashboard_operator",
                    )
                    cop_res = _safe_async_run(copilot_assistant.ask(q_obj))
                    st.session_state["copilot_chat_history"].append(
                        {
                            "role": "assistant",
                            "content": cop_res.answer,
                        }
                    )
                    st.success(
                        "✅ ¡El Copilot ha analizado tu backtest! Ve a la pestaña '🤖 AI Copilot' para leer su recomendación personalizada."
                    )
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
            sharpe_value = metrics.get("sharpe_ratio")
            st.metric("Sharpe Ratio", _format_sharpe_for_ui(sharpe_value))
            if sharpe_value is None:
                st.caption(
                    metrics.get("sharpe_unavailable_reason")
                    or "Datos insuficientes para Sharpe."
                )
            else:
                st.caption(
                    "Anualizado con barras regulares de cripto 24/7; tasa libre de riesgo 0 %."
                )
        with m_col6:
            st.metric("Retorno Neto", f"${metrics.get('net_pnl', 0.0):,.2f}")

        exp_c1, exp_c2 = st.columns(2)
        with exp_c1:
            st.metric(
                "Expectativa bruta (R) — Simulación",
                _format_verified_expectancy_for_ui(metrics, "gross_expectancy_r"),
            )
        with exp_c2:
            st.metric(
                "Expectativa neta (R) — Simulación",
                _format_verified_expectancy_for_ui(metrics, "net_expectancy_r"),
            )
        st.caption(_r_coverage_for_ui(metrics))
        if metrics.get("r_unavailable_reason"):
            st.caption(metrics["r_unavailable_reason"])
        st.caption(
            "R bruto/neto: media por operación con riesgo inicial matemáticamente verificable. No certifica la fuente histórica ni predice resultados futuros."
        )
        st.caption(_excursion_coverage_for_ui(metrics, "mfe"))
        st.caption(_excursion_coverage_for_ui(metrics, "mae"))
        calibration_state = metrics.get("calibration_state", "UNKNOWN")
        if calibration_state == "AVAILABLE":
            st.caption(
                "Optimización disponible: parámetros derivados de excursiones exactas OHLC con cobertura completa."
            )
        elif calibration_state == "NOT_REQUESTED":
            st.caption(
                "Optimización no solicitada: parámetros manuales, presets o predeterminados no son calibración empírica."
            )
        else:
            st.warning(
                "Optimización no disponible o no acreditada: no se muestran parámetros calibrados."
            )

        # 1.1 Breakdown: LONG vs SHORT
        long_trades = [
            t
            for t in report.trades
            if str(
                _trade_field_for_ui(t, "side") or _trade_field_for_ui(t, "direction")
            ).upper()
            == "LONG"
        ]
        short_trades = [
            t
            for t in report.trades
            if str(
                _trade_field_for_ui(t, "side") or _trade_field_for_ui(t, "direction")
            ).upper()
            == "SHORT"
        ]

        long_count = len(long_trades)
        short_count = len(short_trades)
        long_wins = sum(
            1 for t in long_trades if (_trade_field_for_ui(t, "net_pnl") or 0) > 0
        )
        short_wins = sum(
            1 for t in short_trades if (_trade_field_for_ui(t, "net_pnl") or 0) > 0
        )
        long_wr = (long_wins / long_count * 100) if long_count > 0 else 0.0
        short_wr = (short_wins / short_count * 100) if short_count > 0 else 0.0
        long_pnl = sum(_trade_field_for_ui(t, "net_pnl") or 0 for t in long_trades)
        short_pnl = sum(_trade_field_for_ui(t, "net_pnl") or 0 for t in short_trades)

        st.markdown(
            "##### ⚖️ ¿Qué Convino Más en Este Período? Compras (LONG) vs Ventas (SHORT)"
        )
        dir_c1, dir_c2 = st.columns(2)
        with dir_c1:
            st.markdown(
                f"""
                <div style="background: rgba(0, 255, 136, 0.06); border: 1px solid rgba(0, 255, 136, 0.3); border-radius: 10px; padding: 12px 14px;">
                    <div style="font-weight: 700; color: #00FF88; font-size: 0.95rem;">🟢 Operaciones de Compra (LONG)</div>
                    <div style="color: #F0F6FC; font-size: 0.88rem; margin-top: 4px; line-height: 1.6;">
                        • <strong>{long_count}</strong> operaciones ejecutadas<br/>
                        • Tasa de Acierto: <strong>{long_wr:.1f}%</strong> ({long_wins} ganadas)<br/>
                        • Retorno Acumulado: <strong style="color: {"#00FF88" if long_pnl >= 0 else "#FF2E63"};">${long_pnl:+,.2f}</strong>
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
                        • Retorno Acumulado: <strong style="color: {"#00FF88" if short_pnl >= 0 else "#FF2E63"};">${short_pnl:+,.2f}</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if long_count > 0 and short_count > 0:
            if long_pnl > short_pnl:
                st.caption(
                    f"🏆 **Conclusión Cuantitativa**: En este período el mercado recompensó con mayor fuerza las **COMPRAS (LONG)** (+${long_pnl:,.2f} vs ${short_pnl:,.2f} en Ventas)."
                )
            elif short_pnl > long_pnl:
                st.caption(
                    f"🏆 **Conclusión Cuantitativa**: En este período el mercado recompensó con mayor fuerza las **VENTAS (SHORT)** (+${short_pnl:,.2f} vs ${long_pnl:,.2f} en Compras)."
                )
            else:
                st.caption(
                    "⚖️ **Conclusión Cuantitativa**: Compras y Ventas tuvieron rendimientos equivalentes en esta muestra histórica."
                )
        elif long_count > 0 and short_count == 0:
            st.caption(
                f"**Estrategia Unidireccional**: Esta simulación registró exclusivamente **COMPRAS (LONG)** ({long_count} compras, {long_wr:.1f}% acierto observado)."
            )
        elif short_count > 0 and long_count == 0:
            st.caption(
                f"📉 **Estrategia en Corto**: Esta configuración operó exclusivamente **VENTAS (SHORT)** ({short_count} ventas, {short_wr:.1f}% acierto)."
            )

        # Mean of individual verified plans, not a ratio of average distances.
        avg_planned_rr, planned_count = _planned_rr_summary_for_ui(
            report.trades, getattr(report, "config", None)
        )

        winning_pnls = [
            _trade_field_for_ui(t, "net_pnl")
            for t in report.trades
            if (_trade_field_for_ui(t, "net_pnl") or 0) > 0
        ]
        losing_pnls = [
            abs(_trade_field_for_ui(t, "net_pnl"))
            for t in report.trades
            if (_trade_field_for_ui(t, "net_pnl") or 0) < 0
        ]
        avg_win_usd = (sum(winning_pnls) / len(winning_pnls)) if winning_pnls else 0.0
        avg_loss_usd = (sum(losing_pnls) / len(losing_pnls)) if losing_pnls else 0.0

        st.markdown("##### Planes de riesgo y resultados de la simulación")
        r_col1, r_col2 = st.columns(2)
        with r_col1:
            st.metric(
                "R:R planificado medio — Simulación",
                f"1 : {avg_planned_rr:.2f}" if avg_planned_rr is not None else "N/A",
                help="Media de los ratios individuales TP–entrada / entrada–SL inicial; no es R realizado ni incluye costes.",
            )
        with r_col2:
            st.metric(
                "Ganancia Media / Pérdida Media",
                f"${avg_win_usd:,.2f} / -${avg_loss_usd:,.2f}",
                help="Promedio de PnL neto positivo y negativo en operaciones cerradas.",
            )
        st.caption(
            f"Planes R:R verificables: {planned_count} de {len(report.trades)} operaciones. Los planes incompletos no se estiman."
        )

        # 2. Equity Curve & Underwater Drawdown Plot
        if report.equity_curve:
            eq_df = pd.DataFrame(
                [
                    pt.to_dict() if hasattr(pt, "to_dict") else dict(pt)
                    for pt in report.equity_curve
                ]
            )
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
                go.Scatter(
                    x=eq_df["timestamp"],
                    y=eq_df["equity"],
                    name="Equity ($)",
                    line={"color": "#00FF88", "width": 2.5},
                ),
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
                trade_rows = [
                    t.to_dict() if hasattr(t, "to_dict") else dict(t)
                    for t in report.trades
                ]

                exact_rows = [
                    t
                    for t in trade_rows
                    if (
                        t.get("excursion_policy_version") == EXCURSION_POLICY_VERSION
                        and t.get("mfe_observability") == "EXACT_OHLC"
                        and t.get("mae_observability") == "EXACT_OHLC"
                        and isinstance(t.get("mfe_exact_pct"), (int, float))
                        and isinstance(t.get("mae_exact_pct"), (int, float))
                        and math.isfinite(t["mfe_exact_pct"])
                        and math.isfinite(t["mae_exact_pct"])
                    )
                ]
                if exact_rows:
                    fig_mfe = go.Figure()
                    fig_mfe.add_trace(
                        go.Scatter(
                            x=[t["mae_exact_pct"] for t in exact_rows],
                            y=[t["mfe_exact_pct"] for t in exact_rows],
                            mode="markers",
                            marker={
                                "size": 9,
                                "color": [
                                    "#00FF88" if t.get("net_pnl", 0) > 0 else "#FF2E63"
                                    for t in exact_rows
                                ],
                            },
                            text=[
                                f"Trade {t.get('trade_id', '')}: MAE {t['mae_exact_pct']:.2f}%, MFE {t['mfe_exact_pct']:.2f}% (OHLC)"
                                for t in exact_rows
                            ],
                            hoverinfo="text",
                        )
                    )
                    fig_mfe.update_layout(
                        xaxis_title="MAE exacta bajo OHLC (%)",
                        yaxis_title="MFE exacta bajo OHLC (%)",
                        height=360,
                        template="plotly_dark",
                        paper_bgcolor="#07090E",
                        plot_bgcolor="#07090E",
                        margin={"l": 20, "r": 20, "t": 30, "b": 20},
                    )
                    st.plotly_chart(fig_mfe, use_container_width=True)
                else:
                    st.info(
                        "No hay operaciones con MFE y MAE exactas conjuntamente para el gráfico."
                    )
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Trade": t.get("trade_id", ""),
                                "MFE": _excursion_for_ui(t, "mfe"),
                                "MAE": _excursion_for_ui(t, "mae"),
                            }
                            for t in trade_rows
                        ]
                    ),
                    use_container_width=True,
                )
                st.caption(
                    "Las cotas OHLC no revelan el orden intrabar ni prueban ejecución real. Los proxies históricos no se muestran como puntos exactos."
                )
            else:
                st.info("No se registraron operaciones en este período de simulación.")

        with t_right:
            st.subheader("📋 Registro de Transacciones")
            if report.trades:
                st.caption(_execution_trace_summary_for_ui(report.trades))
                st.dataframe(
                    _backtest_trade_table_for_ui(
                        report.trades, getattr(report, "config", None)
                    ),
                    height=350,
                    use_container_width=True,
                )
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
        st.markdown("### 🛡️ Filtros y Anti-Spam (Cooldown)")
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
    st.subheader("⚡ Acciones de Despacho de Señales")

    act_col1, act_col2 = st.columns([1, 1])

    with act_col1:
        st.markdown("#### 🧪 1. Prueba de Conexión (Ping)")
        st.caption(
            "Verifica si tu Bot de Telegram o Webhook de Discord responde correctamente."
        )
        if st.button(
            "🔔 Enviar Notificación de Prueba",
            type="secondary",
            use_container_width=True,
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

    with act_col2:
        st.markdown("#### 📡 2. Escanear y Despachar Alertas Reales")
        st.caption(
            "Solo se despachan señales ACTIVADAS con entrada confirmada y niveles válidos. Las candidatas no se envían como operables."
        )
        min_quant_thresh = st.slider(
            "Quant Score Mínimo para Alerta Real", 60.0, 95.0, 75.0, 5.0
        )

        if st.button(
            "🚀 Escanear Mercado y Enviar Alertas Reales",
            type="primary",
            use_container_width=True,
        ):
            alert_channels = []
            if enable_discord and discord_url_input:
                alert_channels.append(
                    DiscordWebhookChannel(
                        webhook_url=discord_url_input, dry_run=dry_run_mode
                    )
                )
            if enable_telegram and telegram_token_input and telegram_chat_id_input:
                alert_channels.append(
                    TelegramChannel(
                        bot_token=telegram_token_input,
                        chat_id=telegram_chat_id_input,
                        dry_run=dry_run_mode,
                    )
                )

            if not alert_channels:
                st.warning(
                    "⚠️ Debes habilitar y configurar Telegram o Discord para despachar alertas."
                )
            else:
                with st.spinner(
                    "Escaneando mercado institucional y evaluando confluencias..."
                ):
                    dispatcher = NotificationDispatcher(
                        channels=alert_channels,
                        min_predictive_score=min_pred_score,
                        min_confidence=min_conf,
                        cooldown_seconds=float(cooldown_sec),
                    )

                    # Scan pairs based on active market
                    if is_forex:
                        scanner = MarketScanner(data_loader=ForexDataLoader())
                        f_pairs = [
                            s
                            for s in FOREX_PAIRS.values()
                            if not s.startswith("CUSTOM")
                        ][:8]
                        scan_results = scanner.scan_market(
                            symbols=f_pairs, timeframe=interval
                        )
                    else:
                        scanner = MarketScanner()
                        scan_results = scanner.scan_market(timeframe=interval)

                    accepted_count = 0
                    failed_count = 0
                    if "dispatched_signals_history" not in st.session_state:
                        st.session_state["dispatched_signals_history"] = []

                    tracker = AlertOutcomeTracker()
                    for cand in scan_results:
                        if cand.quant_score >= min_quant_thresh and cand.is_operable():
                            is_cand_fx = "=X" in cand.symbol
                            cand_decimals = (
                                5 if is_cand_fx else (6 if cand.entry_price < 1 else 2)
                            )
                            sig_ev = SignalEvent(
                                timestamp=pd.Timestamp.now("UTC"),
                                symbol=cand.symbol,
                                timeframe=interval,
                                action=cand.action,
                                direction=cand.direction,
                                confidence=cand.confidence,
                                predictive_score=cand.predictive_score,
                                regime=cand.regime,
                                reasoning=f"Quant Score {cand.quant_score:.1f}/100. Confluencia: {cand.primary_reason}.",
                                price=cand.entry_price,
                                quant_score=cand.quant_score,
                                stop_loss=cand.stop_loss,
                                take_profit=cand.take_profit,
                                signal_id=f"alert-{cand.symbol}-{interval}-{int(pd.Timestamp.now('UTC').timestamp())}",
                                metadata={
                                    "risk_reward_ratio": cand.risk_reward,
                                    "risk_reward_basis": "bruto_sin_costes",
                                    "signal_status": cand.status,
                                    "entry_confirmed": cand.entry_confirmed,
                                },
                            )
                            try:
                                alert_record, delivery_results = (
                                    dispatcher.dispatch_tracked_signal(
                                        sig_ev,
                                        tracker,
                                        is_forex=is_cand_fx,
                                        risk_reward=cand.risk_reward,
                                        priority=NotificationPriority.HIGH,
                                    )
                                )
                            except Exception as alert_error:
                                st.warning(
                                    f"Alerta {cand.symbol} no enviada: registro inválido o no disponible ({alert_error})."
                                )
                                continue
                            if alert_record is None:
                                continue
                            accepted_channels = [
                                r.channel.value for r in delivery_results if r.success
                            ]
                            failed_channels = [
                                r.channel.value
                                for r in delivery_results
                                if not r.success
                            ]
                            if not accepted_channels:
                                failed_count += 1
                                st.warning(
                                    f"Se registró la señal {alert_record['id']} para seguimiento, "
                                    "pero ningún canal confirmó la aceptación del envío. "
                                    f"Fallos: {', '.join(failed_channels) or 'sin resultado de canal'}."
                                )
                                continue
                            accepted_count += 1
                            if failed_channels:
                                st.warning(
                                    f"Señal {alert_record['id']}: aceptación parcial. "
                                    f"Fallaron: {', '.join(failed_channels)}."
                                )
                            if "dispatched_signals_history" not in st.session_state:
                                st.session_state["dispatched_signals_history"] = []
                            st.session_state["dispatched_signals_history"].append(
                                {
                                    "ID de seguimiento": alert_record["id"],
                                    "Fecha (UTC)": str(sig_ev.timestamp)[:19],
                                    "Par": cand.symbol,
                                    "Estado señal": cand.status,
                                    "Resultado inmediato de canales": (
                                        f"{len(accepted_channels)} {'simulados' if dry_run_mode else 'aceptados'}; "
                                        f"{len(failed_channels)} fallidos"
                                    ),
                                    "Dirección": cand.direction,
                                    "Precio Entrada": f"${alert_record['entry_price']:,.{cand_decimals}f}",
                                    "Stop Loss": f"${alert_record['stop_loss']:,.{cand_decimals}f}",
                                    "Take Profit": f"${alert_record['take_profit']:,.{cand_decimals}f}",
                                    "Quant Score": f"{cand.quant_score:.1f}",
                                    "R bruto (sin costes)": f"1:{alert_record['risk_reward']:.2f}",
                                }
                            )

                    if accepted_count > 0:
                        st.success(
                            f"{accepted_count} señales registradas con aceptación de al menos un canal"
                            f"{' (simulada)' if dry_run_mode else ''}. Esto no confirma lectura por el destinatario."
                        )
                    elif failed_count > 0:
                        st.warning(
                            f"{failed_count} señales quedaron registradas para seguimiento, "
                            "pero ningún canal confirmó la aceptación del envío."
                        )
                    else:
                        candidate_count = sum(
                            cand.status == "CANDIDATA" for cand in scan_results
                        )
                        st.info(
                            f"No hubo señales activadas aceptadas por canales. Hay {candidate_count} candidatas sin entrada confirmada."
                        )

    # Persistent audit log and automated TP/SL outcome tracking
    tracker = AlertOutcomeTracker()
    all_alerts = tracker.get_all_alerts()

    st.markdown("---")
    st.markdown("### 📋 Historial de señales registradas y auditoría de resultados")
    st.caption(
        "OPEN indica seguimiento de mercado, no envío confirmado. "
        "El estado histórico de entrega no está disponible: no se persiste por registro."
    )

    if all_alerts:
        st.caption(
            "Registros anteriores a P0-002 pueden contener niveles aproximados; su R histórico no se ha revalidado."
        )
        stats = tracker.compute_statistics()

        stat_c1, stat_c2, stat_c3, stat_c4, stat_c5 = st.columns(5)
        stat_c1.metric(
            "🎯 Win Rate (Acierto)",
            f"{stats['win_rate']:.1f}%",
            help="Porcentaje de operaciones que tocaron Take Profit sobre las cerradas.",
        )
        stat_c2.metric("🟢 Ganadas (TP)", f"{stats['wins']}")
        stat_c3.metric("🔴 En Stop Loss", f"{stats['losses']}")
        stat_c4.metric("🟡 En Curso", f"{stats['open_alerts']}")
        stat_c5.metric(
            "📈 Retorno R Acumulado",
            f"{stats['total_r']:+.1f} R",
            help="Múltiplo de Riesgo acumulado ganado o perdido.",
        )

        btn_c1, btn_c2 = st.columns([1, 2])
        with btn_c1:
            if st.button(
                "🔄 Actualizar Resultados (Verificar TP / SL)",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner(
                    "Descargando velas recientes y evaluando TP / SL para cada alerta..."
                ):
                    f_ldr = ForexDataLoader() if is_forex else None
                    c_ldr = BinanceDataLoader() if not is_forex else None
                    upd = tracker.update_alert_outcomes(
                        forex_loader=f_ldr, crypto_loader=c_ldr
                    )
                    st.success(
                        f"¡Auditoría actualizada! {upd} alertas verificadas contra el mercado."
                    )
                    st.rerun()

        display_rows = []
        for a in all_alerts:
            is_fx_row = bool(a["is_forex"]) or "=X" in a["symbol"]
            dec = 5 if is_fx_row else (6 if a["entry_price"] < 1 else 2)

            st_val = a["status"]
            if st_val == "WIN":
                status_str = f"🟢 TP ALCANZADO (+{a['r_multiple']:.1f}R)"
            elif st_val == "LOSS":
                status_str = "🔴 STOP LOSS (-1.0R)"
            else:
                status_str = f"🟡 EN CURSO ({a['pnl_percent']:+.2f}%)"

            exit_p = a["current_or_exit_price"]
            exit_str = f"${exit_p:,.{dec}f}" if exit_p else "-"

            display_rows.append(
                {
                    "Fecha (UTC)": a["timestamp"][:16],
                    "Par": a["symbol"],
                    "Dirección": a["direction"],
                    "Estado de seguimiento": status_str,
                    "Estado de entrega": "No disponible (no persistido)",
                    "Entrada": f"${a['entry_price']:,.{dec}f}",
                    "Stop Loss": f"${a['stop_loss']:,.{dec}f}",
                    "Take Profit": f"${a['take_profit']:,.{dec}f}",
                    "Precio Actual/Salida": exit_str,
                    "PnL (%)": f"{a['pnl_percent']:+.2f}%",
                    "Quant Score": f"{a['quant_score']:.1f}",
                    "R registrado (sin costes)": f"1:{a['risk_reward']:.2f}",
                }
            )

        st.dataframe(pd.DataFrame(display_rows), use_container_width=True)
    else:
        st.info(
            "ℹ️ Aún no hay señales registradas para seguimiento en la base de datos."
        )


# =====================================================================
# TAB 5: GUÍA & GLOSARIO
# =====================================================================
with tab_guide:
    st.subheader("📖 Guía Rápida & Glosario Cuantitativo")
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
        st.markdown("### 🕹️ Manual Paso a Paso: Si tocas esto, obtienes esto")

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
