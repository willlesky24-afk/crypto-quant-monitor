import plotly.graph_objects as go
import streamlit as st

from data_loader import BinanceDataLoader
from engine import MarketEngine
from indicators import TechnicalIndicators
from market_zone import get_market_zone
from report import MarketReport
from signal_history import SignalHistory
from visuals import score_to_confidence
from volume_profile import VolumeProfile

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
    "Número de velas (mínimo 250 para EMA 200)",
    250,
    1000,
    300
)


# ==========================
# Datos
# ==========================

try:
    loader = BinanceDataLoader()
    df = loader.get_klines(
        symbol=symbol.strip().upper(),
        interval=interval,
        limit=limit,
        include_open_candle=False,
    )
except Exception as exc:
    st.error(f"Error al obtener datos de mercado: {exc}")
    st.stop()

if df.empty or len(df) < 50:
    st.warning("Datos insuficientes para realizar el análisis cuantitativo.")
    st.stop()


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
    symbol.strip().upper(),
    analysis,
    profile
)


confidence = score_to_confidence(
    market_report["score"]
)


market_zone = get_market_zone(
    profile
)


signal = market_report["signal"]

risk_engine = market_report["risk_engine"]

decision = market_report["decision"]

quant_score = market_report["quant_score"]


# ==========================
# Persistencia explícita e idempotente (por vela cerrada)
# ==========================

latest_candle = df.iloc[-1]
candle_ts = str(latest_candle["timestamp"])

history = SignalHistory()
history.save(
    symbol=symbol.strip().upper(),
    analysis=analysis,
    decision=decision,
    quant_score=quant_score,
    risk=risk_engine,
    signal=signal,
    timeframe=interval,
    candle_timestamp=candle_ts,
    open=float(latest_candle["open"]),
    high=float(latest_candle["high"]),
    low=float(latest_candle["low"]),
    close=float(latest_candle["close"]),
    volume=float(latest_candle["volume"]),
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
# Quant Score
# ==========================

st.subheader("🎯 Quant Score")


st.metric(
    "Puntuación",
    f"{quant_score['score']}/100"
)


st.info(
    quant_score["label"]
)


for key, value in quant_score["breakdown"].items():

    if value >= 0:

        st.write(
            f"✓ {key.capitalize()}: +{value}"
        )

    else:

        st.write(
            f"⚠ {key.capitalize()}: {value}"
        )



# ==========================
# Decisión
# ==========================

st.subheader("🎯 Decisión del sistema")


st.info(
    decision["decision"]
)


st.metric(
    "Confianza final",
    f"{decision['confidence']}%"
)


st.write(
    "Estado del mercado:",
    decision["market_state"]
)



# ==========================
# Historial reciente
# ==========================

st.subheader("📚 Historial reciente")


records = history.get_history(
    limit=5
)


if records:

    for record in records:
        # Compatibility with both new schema (17 cols) and legacy
        if len(record) >= 15:
            rec_symbol = record[1]
            rec_tf = record[2]
            rec_ts = record[3]
            rec_price = record[4]
            rec_trend = record[10]
            rec_decision = record[12]
            rec_score = record[13]
            rec_risk = record[14]
            header = f"{rec_symbol} ({rec_tf}) | {rec_ts}"
        else:
            rec_price = record[3]
            rec_trend = record[4]
            rec_decision = record[6]
            rec_score = record[7]
            rec_risk = record[8]
            header = f"{record[2]} | {record[1]}"

        with st.expander(header):
            st.write(f"💰 Precio: ${rec_price:,.2f}")
            st.write(f"📈 Tendencia: {rec_trend}")
            st.write(f"🎯 Decisión: {rec_decision}")
            st.write(f"📊 Quant Score: {rec_score}")
            st.write(f"🛡️ Riesgo: {rec_risk}")

else:

    st.info(
        "Sin registros históricos todavía."
    )



# ==========================
# Señal
# ==========================

st.subheader("📈 Señal del mercado")


st.success(
    signal["state"]
)


st.metric(
    "Fuerza del setup",
    f"{signal['confidence']}%"
)



# ==========================
# Riesgo
# ==========================

st.subheader("🛡️ Gestión de riesgo")


r1, r2 = st.columns(2)


with r1:

    st.metric(
        "Nivel de riesgo",
        risk_engine["level"]
    )


with r2:

    st.metric(
        "Confianza ajustada",
        f"{risk_engine['final_confidence']}%"
    )



# ==========================
# Zona mercado
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
# Diagnóstico
# ==========================

st.subheader("🧠 Diagnóstico del mercado")


st.info(
    market_report["state"]
)


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