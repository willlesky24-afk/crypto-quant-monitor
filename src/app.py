import streamlit as st
import plotly.graph_objects as go

from data_loader import BinanceDataLoader
from indicators import TechnicalIndicators
from volume_profile import VolumeProfile
from engine import MarketEngine
from report import MarketReport
from visuals import score_to_confidence
from market_zone import get_market_zone


st.set_page_config(
    page_title="Crypto Quant Monitor",
    layout="wide"
)


st.title("📊 Crypto Quant Monitor")


# ==========================
# Configuración
# ==========================

symbol = st.sidebar.text_input(
    "Símbolo",
    "BTCUSDT"
)


interval = st.sidebar.selectbox(
    "Temporalidad",
    [
        "15m",
        "1h",
        "4h",
        "1d"
    ],
    index=1
)


limit = st.sidebar.slider(
    "Número de velas",
    50,
    500,
    200
)


# ==========================
# Carga de datos
# ==========================

loader = BinanceDataLoader()


df = loader.get_klines(
    symbol=symbol,
    interval=interval,
    limit=limit
)


# ==========================
# Indicadores
# ==========================

indicators = TechnicalIndicators()

df = indicators.calculate_all(df)


# ==========================
# Volume Profile
# ==========================

vp = VolumeProfile()

profile = vp.calculate(df)


# ==========================
# Engine
# ==========================

engine = MarketEngine()


analysis = engine.analyze(
    df,
    profile
)


# ==========================
# Report
# ==========================

reporter = MarketReport()


market_report = reporter.generate(
    symbol,
    analysis,
    profile
)


confidence = score_to_confidence(
    market_report["score"]
)


market_zone = get_market_zone(
    profile
)


# ==========================
# Métricas
# ==========================

col1, col2, col3, col4 = st.columns(4)


col1.metric(
    "Precio",
    f"${market_report['price']:,.2f}"
)


col2.metric(
    "Tendencia",
    market_report["trend"]
)


col3.metric(
    "Momentum",
    market_report["momentum"]
)


col4.metric(
    "Confianza",
    f"{confidence['emoji']} {confidence['label']}"
)


# ==========================
# Confianza
# ==========================

st.subheader("📊 Confianza del modelo")


st.progress(
    confidence["percent"] / 100
)


st.caption(
    f"{confidence['percent']}% - {confidence['label']}"
)


# ==========================
# Zona de mercado
# ==========================

st.subheader("📍 Zona de mercado")


z1, z2, z3 = st.columns(3)


z1.metric(
    "POC",
    f"${market_zone['poc']:,.2f}"
)


z2.metric(
    "VAH",
    f"${market_zone['vah']:,.2f}"
)


z3.metric(
    "VAL",
    f"${market_zone['val']:,.2f}"
)


# ==========================
# Alertas
# ==========================

st.subheader("🚨 Alertas activas")


if market_report["alerts"]:

    for alert in market_report["alerts"]:

        st.warning(
            f"{alert['type']}: {alert['message']}"
        )

else:

    st.success(
        "Sin alertas activas"
    )


# ==========================
# Gráfico
# ==========================

fig = go.Figure()


fig.add_trace(
    go.Candlestick(
        x=df["timestamp"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Precio"
    )
)


fig.add_trace(
    go.Scatter(
        x=df["timestamp"],
        y=df["ema_50"],
        name="EMA 50"
    )
)


fig.add_trace(
    go.Scatter(
        x=df["timestamp"],
        y=df["ema_200"],
        name="EMA 200"
    )
)


fig.add_hline(
    y=profile["poc"],
    annotation_text="POC"
)


fig.add_hline(
    y=profile["vah"],
    annotation_text="VAH"
)


fig.add_hline(
    y=profile["val"],
    annotation_text="VAL"
)


fig.update_layout(
    height=700,
    xaxis_rangeslider_visible=False
)


st.plotly_chart(
    fig,
    use_container_width=True
)


# ==========================
# Diagnóstico Inteligente
# ==========================

st.subheader("🧠 Diagnóstico del mercado")


st.info(
    market_report["state"]
)


col1, col2 = st.columns(2)


with col1:

    st.markdown("### 📈 Estructura")

    st.write(
        market_report["trend_analysis"]
    )


with col2:

    st.markdown("### ⚠️ Riesgo")

    st.write(
        market_report["risk"]
    )


st.markdown("### 📌 Motivo")


st.write(
    market_report["risk_reason"]
)


st.markdown("### 💡 Lectura")


st.write(
    market_report["summary"]
)


st.success(
    market_report["conclusion"]
)


# ==========================
# Datos técnicos
# ==========================

with st.expander("📊 Datos técnicos"):

    st.json(
        analysis
    )

    