# Crypto Quant Monitor

Crypto Quant Monitor es un sistema de análisis cuantitativo para mercados de
criptomonedas. Combina indicadores técnicos, perfil de volumen, evaluación de
riesgo, generación de señales y una capa de decisión presentada mediante
Streamlit.

## Versión actual

La versión actual es **v2.0 — Notification System, Live Streaming & Dashboard Visualizer** (Tag: `v2.0-live-notifications-dashboard`), construida sobre la arquitectura del monitor en vivo (v1.6/v1.7), el motor histórico columnar Parquet (Fase 2), el framework de backtesting orientado a eventos (Fase 3) y el motor predictivo con optimización de estrategias (Fase 4). Incluye:

- streaming de baja latencia con Binance WebSocket resiliente (`ResilientWebSocketClient`) con reconexión automática y heartbeat;
- agregación de velas en buffer rodante de memoria acotada (`CandleAggregator`) con evaluación estricta anti-repintado de velas cerradas;
- motor de ejecución en tiempo real (`LiveExecutionEngine`) con paridad determinista comprobada (100%) respecto a `BacktestRunner`;
- sistema de alertas multicanal (`DiscordWebhookChannel`, `TelegramChannel`, `WebhookChannel`) con formato semántico dinámico (LONG, SHORT, WAIT);
- despachador inteligente (`NotificationDispatcher`) con gestor de cooldown anti-spam en memoria (`CooldownManager`) y filtrado por score predictivo;
- dashboard interactivo multi-pestaña en Streamlit (Live Market Monitor, Backtest & Strategy Analytics, Notification Settings);
- descarga de OHLCV en vivo e histórica desde Binance con validación de integridad;
- almacenamiento columnar optimizado en Apache Parquet con particionado anual;
- RSI, ATR, volumen promedio, EMA 50/200 y Volume Profile vectorizado de alta velocidad (`np.histogram`);
- análisis de mercado, alertas, señal, riesgo, decisión y Quant Score;
- motor de backtesting cronológico event-driven libre de look-ahead bias con soporte LONG/SHORT y contratos perpetuos;
- clasificación causal de regímenes de mercado (`RegimeClassifier`);
- capa probabilística y estimación condicional de escenarios (`PredictiveEngine`);
- optimización empírica de parámetros TP/SL basada en MFE/MAE con Walk-Forward Validation (`StrategyOptimizer`);
- capa de decisión adaptativa (`Enhanced DecisionEngine`) con trazabilidad completa (`DecisionResult`);
- cálculo de métricas institucionales (Win Rate, Profit Factor, Expectancy, Drawdown, MFE, MAE);
- historial persistente en SQLite con control de migraciones.

## Arquitectura v1.6

```text
Binance API
    |
    v
Data Loader
    |
    +--> Technical Indicators
    +--> Volume Profile (POC / VAH / VAL)
              |
              v
         Market Engine
              |
              v
         Market Report
              |
      +-------+-------------------------------+
      |       |        |       |              |
   Analyzer  Alerts   Signal   Risk      Intelligence
                       |       |
                       +---+---+
                           |
                     Decision Engine
                           |
                       Quant Score
                           |
                     Signal History
                           |
                        SQLite
```

Streamlit compone este flujo y muestra métricas, alertas, zonas de mercado,
diagnóstico y el historial reciente.

## Preparación del entorno

Se recomienda usar un Python instalado directamente y no el alias de Microsoft
Store. Desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Para desarrollo y pruebas:

```powershell
python -m pip install -r requirements-dev.txt
```

## Ejecutar el dashboard

```powershell
streamlit run src/app.py
```

La aplicación utiliza `signals.db` en el directorio de ejecución. Este archivo
es local y está excluido de Git.

## Pruebas y controles de calidad

La suite automatizada es offline: simula la API y utiliza bases SQLite
temporales.

```powershell
python -m pytest
python -m pytest --cov=src --cov-report=term-missing
python -m ruff check src tests scripts
```

Los scripts de diagnóstico manual interactivos residen en `scripts/diagnostics/` y
pueden ejecutarse directamente:

```powershell
python scripts/diagnostics/test_engine.py
```

## Capacidades incorporadas en Fase 2 (Historical Data Engine)

- **Almacenamiento columnar Parquet**: Formato Apache Parquet con compresión Snappy y particionado por año (`YYYY.parquet`) en `data/historical/`.
- **Versionado y Metadatos**: Manifiestos `manifest.json` que registran versión de esquema (`1.0`), origen de datos, rangos temporales y métricas de calidad.
- **Validador de Velas (`CandleValidator`)**: Detección de huecos (*gaps*), saneamiento de límites de precio OHLCV y eliminación de marcas temporales duplicadas.
- **Descarga Paginada (`HistoricalDataLoader`)**: Paginación en bloques de 1000 velas con control de rate limit, retroceso exponencial y exclusión de velas abiertas.
- **Gestor Incremental (`HistoricalDatasetManager`)**: Sincronización inteligente que solo descarga las velas faltantes respecto a la caché local.

## Robust Backtesting Framework v1.8

La Fase 3 añade un motor de simulación cuantitativa riguroso orientado a eventos, desacoplado de la API y libre de sesgo de anticipación (*look-ahead bias*).

### Características principales
- **Ejecución estricta $T+1$**: Las señales se evalúan al cierre de la vela $T$; las órdenes se ejecutan en la apertura de $T+1$ aplicando deslizamiento (*slippage*).
- **Modelado realista de costes**: Soporte de comisiones taker/maker y slippage configurable por operación.
- **Resolución intra-barra conservadora**: En caso de ambigüedad intra-vela (donde tanto Take Profit como Stop Loss se tocan en la misma barra), se ejecuta prioritariamente el Stop Loss.
- **Métricas institucionales**: Win Rate, Profit Factor, Expectancy ($ y %), Max Drawdown (% / $ / duración), Max Favorable Excursion (MFE), Max Adverse Excursion (MAE), Sharpe Ratio y Calmar Ratio anualizados.
- **Warm-up causal de indicadores**: Calentamiento dinámico para asegurar la convergencia de EMA 200, ATR y Volume Profile antes de evaluar señales.
- **Reportes estructurados**: Serialización completa a JSON / diccionarios para su consumo en reportes o paneles de visualización.

### Arquitectura del Pipeline de Backtesting

```text
Historical Data
      ↓
ParquetStore
      ↓
HistoricalDatasetManager
      ↓
BacktestRunner
      ↓
SignalEngine / RiskEngine / DecisionEngine
      ↓
BacktestEngine
      ↓
BacktestMetricsCalculator
      ↓
BacktestReport
```

### Cobertura y Calidad
- **150 pruebas automatizadas**: Cobertura integral 100% offline y determinista.
- **90% de cobertura global**: 100% de cobertura de líneas y ramas en los módulos críticos del motor (`backtest_models.py`, `backtest_metrics.py`, `backtest_engine.py`, `backtest_runner.py`).
- **Linter**: Verificación estricta con Ruff (0 errores, 0 advertencias).

## Predictive Market Engine & Strategy Optimization (v1.9)
 
La Fase 4 expande el sistema incorporando análisis de contexto causal, estimación probabilística de escenarios y calibración empírica de parámetros de riesgo.

### Características principales
- **Clasificador causal de regímenes (`RegimeClassifier`)**: Detección determinista de regímenes de mercado (`TRENDING_BULL`, `TRENDING_BEAR`, `RANGING_CONSOLIDATION`, `HIGH_VOLATILITY_EXPANSION`) evaluada estrictamente en $t \le T$.
- **Motor probabilístico (`PredictiveEngine`)**: Estimación empírica de probabilidades condicionales de continuación y reversión mediante suavizado de Laplace y `PredictiveScore` $\in [0, 1]$.
- **Soporte bidireccional y futuros perpetuos**: Simulación completa de operaciones LONG y SHORT, comisiones de contratos perpetuos (`MarketType.PERP`) y ciclos de financiación (*funding rate* de 8h).
- **Optimización paramétrica MFE/MAE (`StrategyOptimizer`)**: Calibración dinámica de Take Profit y Stop Loss guiada por las distribuciones históricas de excursión máxima favorable (MFE) y adversa (MAE).
- **Validación Walk-Forward**: División causal obligatoria In-Sample (TRAIN: 2023-2024) y Out-of-Sample (VALIDATION: 2025) para prevenir sobreajuste (*overfitting*).
- **Capa de decisión mejorada (`Enhanced DecisionEngine`)**: Ponderación adaptativa configurable ($W_{\text{tech}} = 0.60, W_{\text{pred}} = 0.40$), filtrado preventivo contra tendencia y compatibilidad legacy retroactiva bit a bit.
- **Pipeline E2E validado**: Integración multianual fluida desde Parquet hasta el reporte final del backtest.

### Cobertura y Calidad
- **204 pruebas automatizadas**: Cobertura integral 100% offline y determinista.
- **92% de cobertura global**: 100% en módulos del framework de backtesting y 98%-100% en los nuevos componentes predictivos y de optimización.
- **Linter**: Verificación estricta con Ruff (0 errores, 0 advertencias).

## Notification System, Live Streaming & Dashboard Visualizer (v2.0)

La Fase 5 transforma la plataforma en un sistema operacional en tiempo real, integrando ingestión de streaming de baja latencia, ejecución causal de modelos, alertas inteligentes y visualización interactiva avanzada.

### Arquitectura de Tiempo Real

```text
Live Data Stream (Binance WebSocket)
      ↓
ResilientWebSocketClient
      ↓
CandleAggregator (Buffered Memory, Anti-Repainting)
      ↓
LiveExecutionEngine (Warm-up, Regime, Predictive, Decision)
      ↓
SignalEvent (Single Source of Truth)
      ↓
NotificationDispatcher (CooldownManager, Score Filter)
 ┌────┼────┐
 ↓    ↓    ↓
Discord Telegram Webhook
```

### Características principales
- **Streaming WebSocket Resiliente (`ResilientWebSocketClient`)**: Conexión continua a streams kline de Binance, reconexión automática infinita con exponential backoff + jitter y detección de heartbeat.
- **Agregador de Velas en Memoria (`CandleAggregator`)**: Buffer rodante de longitud fija acotada en memoria (`deque`), garantía estricta de no-repainting evaluando únicamente velas cerradas ($T$).
- **Motor en Vivo Causal (`LiveExecutionEngine`)**: Ejecución secuencial idéntica al backtest, asegurando paridad matemática absoluta (100% de concordancia comprobada en integración).
- **Contrato Unificado de Señal (`SignalEvent`)**: Contrato fuertemente tipado que actúa como fuente única de verdad para alertas, órdenes y registros históricos.
- **Alertas Multicanal Enriquecidas**: Adaptadores dedicados para Discord (Rich Embeds con colores según dirección de mercado), Telegram (formato HTML con emojis y truncado seguro) y Webhooks genéricos (POST JSON).
- **Despachador Inteligente con Anti-Spam (`NotificationDispatcher`)**: Control de saturación en memoria mediante `CooldownManager` por `(symbol, timeframe, action)`, filtrado por `predictive_score`, despacho asíncrono no bloqueante y aislamiento total de fallos entre canales.
- **Dashboard Streamlit Multi-Pestaña (`src/app.py`)**:
  - **Live Market Monitor**: Velas en vivo, EMAs 50/200, Volume Profile (POC/VAH/VAL), métricas de régimen y predicción.
  - **Backtest & Strategy Analytics**: Configuración y ejecución de simulaciones, curvas de capital acumulado, drawdown submarino, distribución MFE/MAE de trades y log detallado.
  - **Notification Settings**: Configuración segura de endpoints y credenciales de Discord/Telegram, ajuste de cooldown y umbrales mínimos de score, con disparador manual de alertas de prueba.

### Cobertura y Calidad
- **260 pruebas automatizadas**: Cobertura integral 100% offline y determinista sin llamadas a red.
- **100% de cobertura en notificaciones** (`src/notifications/`, 413/413 líneas).
- **98% de cobertura en streaming** (`src/streaming/`, 405/414 líneas).
- **Linter**: Verificación estricta con Ruff (0 errores, 0 advertencias).

## Próxima fase (Fase 6)

**AI Market Agent**: Agente conversacional e inteligente para la interpretación contextual de señales cuantitativas, análisis de regímenes de mercado y síntesis explicativa automatizada para el usuario.



