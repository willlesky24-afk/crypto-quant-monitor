import streamlit as st
import plotly.graph_objects as go

from data_loader import BinanceDataLoader
from indicators import TechnicalIndicators
from volume_profile import VolumeProfile
from engine import MarketEngine
from report import MarketReport


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
    analysis
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
    "Score",
    market_report["score"]
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
# Reporte Mentor
# ==========================

st.subheader("🧠 Lectura del mercado")


st.info(
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