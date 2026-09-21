from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

try:
    from src.backtest_models import BacktestConfig, TradeDirection
    from src.backtest_runner import BacktestRunner
    from src.data_loader import BinanceDataLoader
    from src.decision_engine import DecisionEngine
    from src.engine import MarketEngine
    from src.indicators import TechnicalIndicators
    from src.market_intelligence import MarketIntelligence
    from src.notifications.channels.discord import DiscordWebhookChannel
    from src.notifications.channels.telegram import TelegramChannel
    from src.notifications.channels.webhook import WebhookChannel
    from src.notifications.dispatcher import NotificationDispatcher
    from src.notifications.models import NotificationPriority, SignalEvent
    from src.predictive_engine import PredictiveEngine
    from src.quant_score import QuantScore
    from src.regime_classifier import RegimeClassifier
    from src.report import MarketReport
    from src.risk_engine import RiskEngine
    from src.signal_engine import SignalEngine
    from src.volume_profile import VolumeProfile
except ImportError:
    from backtest_models import BacktestConfig, TradeDirection
    from backtest_runner import BacktestRunner
    from data_loader import BinanceDataLoader
    from decision_engine import DecisionEngine
    from engine import MarketEngine
    from indicators import TechnicalIndicators
    from market_intelligence import MarketIntelligence
    from notifications.channels.discord import DiscordWebhookChannel
    from notifications.channels.telegram import TelegramChannel
    from notifications.channels.webhook import WebhookChannel
    from notifications.dispatcher import NotificationDispatcher
    from notifications.models import NotificationPriority, SignalEvent
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

st.title("📊 Crypto Quant Monitor")
st.caption("Institutional Quantitative Engine • Predictive Intelligence • Real-Time Monitoring & Backtesting")

# =====================================================================
# SIDEBAR: DATA CONTROLS
# =====================================================================
st.sidebar.header("🕹️ Parámetros de Mercado")

symbol = st.sidebar.text_input("Símbolo", "BTCUSDT").strip().upper()
interval = st.sidebar.selectbox("Temporalidad", ["15m", "1h", "4h", "1d"], index=1)
limit = st.sidebar.slider("Velas Históricas", min_value=250, max_value=1000, value=300, step=50)

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
tab_live, tab_backtest, tab_settings = st.tabs([
    "📡 Live Monitor",
    "📈 Backtest Analytics",
    "⚙️ Notification Settings",
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

    # 2. Key Metrics Header
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Precio Actual", f"${curr_price:,.2f}")
    with col2:
        st.metric("Régimen de Mercado", regime_res.regime.value)
    with col3:
        st.metric("Decisión Estratégica", f"{decision.decision} ({decision.direction})")
    with col4:
        st.metric("Confianza", f"{decision.confidence * 100:.1f}%")
    with col5:
        st.metric(
            "Predictive Score",
            f"{pred_res.predictive_score:.2f}",
            f"P(Cont): {pred_res.probability_continuation * 100:.0f}%",
        )

    # 3. Interactive Plotly Chart (Candles, EMAs, Volume Profile)
    fig_live = go.Figure()

    # Candlestick
    fig_live.add_trace(
        go.Candlestick(
            x=df["timestamp"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Precio",
        )
    )

    # EMAs
    if "ema_50" in df.columns:
        fig_live.add_trace(go.Scatter(x=df["timestamp"], y=df["ema_50"], name="EMA 50", line={"color": "#3498DB", "width": 1.5}))
    if "ema_200" in df.columns:
        fig_live.add_trace(go.Scatter(x=df["timestamp"], y=df["ema_200"], name="EMA 200", line={"color": "#E67E22", "width": 1.5}))

    # Volume Profile Horizontal Levels
    if profile.get("poc"):
        fig_live.add_hline(y=profile["poc"], line={"color": "#F1C40F", "dash": "dash"}, annotation_text="POC")
    if profile.get("vah"):
        fig_live.add_hline(y=profile["vah"], line={"color": "#2ECC71", "dash": "dot"}, annotation_text="VAH")
    if profile.get("val"):
        fig_live.add_hline(y=profile["val"], line={"color": "#E74C3C", "dash": "dot"}, annotation_text="VAL")

    fig_live.update_layout(
        height=600,
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
    )
    st.plotly_chart(fig_live, use_container_width=True)

    # 4. Contextual Diagnostics & Active Signals
    c_diag, c_signals = st.columns([1, 1])
    with c_diag:
        st.subheader("🧠 Diagnóstico y Razonamiento")
        st.info(f"**Estado de Mercado:** {decision.market_state}")
        st.write(f"**Justificación:** {decision.reasoning}")
        if decision.positives:
            st.success("**Confluencias Positivas:**\n- " + "\n- ".join(decision.positives))
        if decision.warnings:
            st.warning("**Riesgos y Advertencias:**\n- " + "\n- ".join(decision.warnings))

    with c_signals:
        st.subheader("📋 Parámetros de Operación")
        reporter = MarketReport()
        m_report = reporter.generate(symbol, analysis, profile)

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
# TAB 2: BACKTEST ANALYTICS
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
                go.Scatter(x=eq_df["timestamp"], y=eq_df["equity"], name="Equity ($)", line={"color": "#2ECC71", "width": 2}),
                row=1,
                col=1,
            )

            fig_eq.add_trace(
                go.Scatter(
                    x=eq_df["timestamp"],
                    y=-eq_df["drawdown_pct"],
                    name="Drawdown (%)",
                    fill="tozeroy",
                    line={"color": "#E74C3C", "width": 1},
                ),
                row=2,
                col=1,
            )

            fig_eq.update_layout(height=500, template="plotly_dark", margin={"l": 20, "r": 20, "t": 40, "b": 20})
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
                            "size": 8,
                            "color": ["#2ECC71" if p > 0 else "#E74C3C" for p in trades_df["net_pnl"]],
                        },
                        text=[f"Trade {t['trade_id']} ({t['side']}): PnL ${t['net_pnl']:.2f}" for t in trade_rows],
                    )
                )
                fig_mfe.update_layout(
                    xaxis_title="Max Adverse Excursion (MAE %)",
                    yaxis_title="Max Favorable Excursion (MFE %)",
                    height=350,
                    template="plotly_dark",
                    margin={"l": 20, "r": 20, "t": 30, "b": 20},
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