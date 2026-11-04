\# Crypto Quant Monitor

# Crypto Quant Monitor

# Gemini Project Context



Versión actual:

v2.0 Notification System, Live Streaming & Dashboard Visualizer (Tag: v2.0-live-notifications-dashboard)

Estado:
FASE 5 COMPLETADA ✅





---



# 1. IDENTIDAD DEL PROYECTO



Crypto Quant Monitor es una plataforma de análisis cuantitativo de mercados de criptomonedas.



El objetivo del proyecto NO es crear un simple indicador de trading.



El objetivo es construir un sistema profesional capaz de:



- Analizar datos de mercado.

- Interpretar estructura.

- Detectar oportunidades.

- Generar señales.

- Evaluar riesgo.

- Validar estrategias mediante datos históricos.

- Crear inteligencia cuantitativa.





---



# 2. ESTADO ACTUAL



El sistema actualmente cuenta con:





## Capa de datos en vivo e histórica



- Data Loader (tiempo real)

- Indicadores técnicos

- Volume Profile

- **Historical Data Loader (`src/historical_data_loader.py`)** (descarga paginada, throttling, retries)

- **Candle Validator (`src/candle_validator.py`)** (continuidad, detección de gaps, anomalías OHLCV)

- **Parquet Store (`src/parquet_store.py`)** (almacenamiento columnar anual, manifests, escrituras atómicas)

- **Historical Dataset Manager (`src/dataset_manager.py`)** (sincronización incremental y caché local)





## Capa analítica



- Market Engine

- Analyzer

- Market Intelligence





## Capa de decisión



- Alert Engine

- Signal Engine

- Risk Engine

- Decision Engine

- Quant Score





## Capa de Backtesting y Simulación Cuantitativa



- **Backtest Models (`src/backtest_models.py`)**: `SignalEvent`, `BacktestConfig`, `Position`, `TradeResult`, `EquityPoint`, `BacktestReport`.

- **Backtest Metrics (`src/backtest_metrics.py`)**: Win Rate, Profit Factor, Expectancy, Max Drawdown (% / $ / duration), MFE, MAE, Sharpe, Calmar.

- **Backtest Engine (`src/backtest_engine.py`)**: Simulación cronológica $T+1$ con modelado de slippage, comisiones taker/maker y resolución conservadora intra-barra.

- **Backtest Runner (`src/backtest_runner.py`)**: Orquestación integral de datasets Parquet, warm-up causal de indicadores, generación de señales y reportes.

## Capa de Streaming y Tiempo Real (Fase 5)

- **WebSocket Client (`src/streaming/websocket_client.py`)**: Cliente Binance WebSocket de baja latencia con reconexión automática, exponential backoff, jitter y heartbeat.
- **Candle Aggregator (`src/streaming/candle_aggregator.py`)**: Buffer rodante acotado en memoria, detección de vela cerrada $T$ y garantía estricta de no-repainting.
- **Live Execution Engine (`src/streaming/live_engine.py`)**: Orquestador causal que recibe velas cerradas, ejecuta el pipeline cuantitativo y predictivo, genera `SignalEvent` y enruta alertas.

## Capa de Notificaciones Multicanal (Fase 5)

- **Event Contracts (`src/notifications/models.py`)**: `SignalEvent` como fuente única de verdad, `NotificationPayload`, `NotificationResult`.
- **Canales (`src/notifications/channels/`)**: `DiscordWebhookChannel` (Rich Embeds), `TelegramChannel` (HTML, emojis, límite 4096 chars), `WebhookChannel` (POST JSON genérico).
- **Despachador Central (`src/notifications/dispatcher.py`)**: `CooldownManager` anti-spam en memoria por `(symbol, timeframe, action)`, filtrado por `predictive_score`, despacho asíncrono no bloqueante y aislamiento de fallos por canal.

## Capa de memoria

- SQLite Database
- Signal History

## Interfaz

- **Streamlit Multi-Tab Dashboard (`src/app.py`)**:
  - Pestaña 1: Live Market Monitor (velas, EMAs, Volume Profile POC/VAH/VAL, métricas de régimen y predicción).
  - Pestaña 2: Backtest & Strategy Analytics (ejecución parametrizable, curva de equity, drawdown underwater, MFE/MAE scatter, log de trades).
  - Pestaña 3: Notification Settings (configuración de credenciales, sliders de cooldown y umbrales, botón de alerta de prueba ping).






---



# 3. ARQUITECTURA ACTUAL



## Pipeline de Backtesting y Validación Histórica (Fase 4)

```text
Historical Data
      ↓
ParquetStore
      ↓
HistoricalDatasetManager
      ↓
RegimeClassifier
      ↓
PredictiveEngine
      ↓
StrategyOptimizer
      ↓
Enhanced DecisionEngine
      ↓
BacktestRunner
      ↓
BacktestReport
```

### Principios Fundamentales Mantenidos
- **Zero look-ahead bias**: Las señales se calculan estrictamente con datos disponibles en el cierre de la vela $T$.
- **Ejecución en Open($T+1$)**: Simulación de órdenes en apertura de la vela siguiente con deslizamiento (*slippage*).
- **Walk-forward validation**: Parámetros calibrados exclusivamente en período de entrenamiento (2023-2024) y evaluados fuera de muestra en validación (2025).
- **Separación de capas**: Desacoplamiento estricto entre análisis descriptivo (`MarketReport`/`QuantScore`) y la capa probabilística (`PredictiveEngine`).
- **Determinismo reproducible**: Mismos datos históricos producen idénticas métricas, órdenes y reportes serializables en JSON.




## Pipeline en Vivo / Monitor Tiempo Real (Fase 5)

```text
Live Data Stream (Binance WebSocket)
      ↓
ResilientWebSocketClient
      ↓
CandleAggregator (Buffered Memory, Anti-Repainting)
      ↓
LiveExecutionEngine (Feature Warm-up, Regime, Predictive, Decision)
      ↓
SignalEvent (Single Source of Truth)
      ↓
NotificationDispatcher (CooldownManager, Score Filter)
 ┌────┼────┐
 ↓    ↓    ↓
Discord Telegram Webhook
```

---

# 4. PRINCIPIOS DEL PROYECTO

El sistema debe mantenerse:

- Modular.
- Escalable.
- Probable estadísticamente.
- Fácil de probar.
- Documentado.

No debe convertirse en:

- Un script gigante.
- Un bot de compra/venta automático sin validación.
- Un sistema basado en opiniones.

---

# 5. ESTADO DE CALIDAD ACTUAL

Fase 1 completada:
- Tests automatizados (suite offline).
- Cobertura aproximada 80%.
- Correcciones de QuantScore.
- Constantes centralizadas.
- Persistencia separada.
- SQLite inyectable.
- Validación offline.

Fase 1.5 Quant Integrity completada:
- Evaluación estricta de velas cerradas (anti-repainting).
- Desacoplamiento de generación de reportes y persistencia (MarketReport puro).
- Migración transaccional de SQLite con backup automático, validación de conteo y rollback.
- Control de versiones de esquema en `schema_migrations`.
- Idempotencia en persistencia por `(symbol, timeframe, candle_timestamp)`.
- Marcado explícito de registros históricos heredados como `is_legacy = 1`.
- Reorganización de scripts de diagnóstico en `scripts/diagnostics/` con soporte UTF-8.

Fase 2 Historical Data Engine completada:
- Almacenamiento columnar en Apache Parquet con compresión Snappy y particionado anual (`YYYY.parquet`).
- Validador riguroso de continuidad temporal, gaps y anomalías OHLCV (`CandleValidator`).
- Descargador paginado con retroceso exponencial y control de rate limits de Binance (`HistoricalDataLoader`).
- Gestor incremental de datasets con manifiestos versionados `manifest.json` (`HistoricalDatasetManager`).
- Pruebas 100% offline y deterministas con fixtures sintéticos multiaño.

Fase 3 Robust Backtesting Framework completada:
- Modelos de datos inmutables y tipados para señales, órdenes, operaciones y reportes (`src/backtest_models.py`).
- Calculadora de métricas institucionales: Win Rate, Profit Factor, Expectancy, Max Drawdown (% / $ / duración), MFE, MAE, Sharpe y Calmar (`src/backtest_metrics.py`).
- Motor de simulación cronológico event-driven con modelado de slippage, fees y resolución conservadora intra-barra (`src/backtest_engine.py`).
- Orquestador de backtest integrado con datasets Parquet y warm-up causal de indicadores (`src/backtest_runner.py`).
- Pruebas de integración E2E sobre datasets multianuales (2023-2025) verificando cero look-ahead bias y determinismo absoluto.
- Cobertura global: 90% (100% en módulos del backtesting framework), 150 tests pasando, 0 errores de linter.

---

Fase 4 Predictive Market Engine & Strategy Optimization completada:
- Aceleración vectorizada de Volume Profile mediante `np.histogram` (4x-9x de velocidad manteniendo 100% identidad matemática).
- Soporte para posiciones SHORT, comisiones de futuros perpetuos (`MarketType.PERP`) y ciclos de financiación (*funding fees* cada 8h).
- Clasificador causal de regímenes de mercado (`RegimeClassifier`): `TRENDING_BULL`, `TRENDING_BEAR`, `RANGING_CONSOLIDATION`, `HIGH_VOLATILITY_EXPANSION`.
- Motor predictivo desacoplado (`PredictiveEngine`) con cálculo empírico de probabilidades condicionales de continuación/reversión y `PredictiveScore` en $[0, 1]$.
- Optimizador empírico de parámetros de riesgo (`StrategyOptimizer`) basado en distribución MFE/MAE con Walk-Forward Validation (TRAIN: 2023-2024 vs VALIDATION: 2025) y protecciones anti-overfitting.
- Capa de decisión mejorada (`Enhanced DecisionEngine`) con ponderación adaptativa ($W_{\text{tech}} = 0.60$, $W_{\text{pred}} = 0.40$), asignación LONG/SHORT y compatibilidad retroactiva legacy certificada.
- Validación de pipeline multianual E2E en `test_predictive_backtest_pipeline.py`.
- Cobertura global: 92%, 204 tests automatizados pasando al 100%, Ruff limpio con 0 errores y 0 advertencias.

---

Fase 5 Notification System, Live Streaming & Dashboard Visualizer completada:
- Modelos de eventos desacoplados y contratos unificados (`SignalEvent`, `NotificationPayload`, `NotificationResult`).
- Adaptadores de canal multicanal (`DiscordWebhookChannel`, `TelegramChannel`, `WebhookChannel`) con formato semántico dinámico (LONG, SHORT, WAIT), retry con retroceso exponencial, jitter y truncado defensivo.
- Despachador de notificaciones (`NotificationDispatcher`) con gestor de cooldown anti-spam en memoria (`CooldownManager`) por `(symbol, timeframe, action)`, filtrado por umbral de `predictive_score`, despacho asíncrono no bloqueante y aislamiento total de fallos por canal.
- Cliente WebSocket resiliente (`ResilientWebSocketClient`) con reconexión automática, exponential backoff, heartbeat activo y soporte para streams kline de Binance.
- Agregador de velas (`CandleAggregator`) con buffer rodante acotado en memoria, detección estricta de vela cerrada $T$ (`is_closed=True`) y garantía estricta de no-repainting.
- Motor de ejecución en tiempo real (`LiveExecutionEngine`) con warmup dinámico de indicadores, cálculo en vivo de régimen, predicción y decisión, y emisión de eventos.
- Verificación rigurosa de paridad live replay vs backtest (`test_live_replay_parity.py`) con 100% de coincidencia exacta (25/25 barras) en timestamps, acciones, direcciones, scores y regímenes.
- Dashboard Streamlit modular con interfaz multi-pestaña: Live Market Monitor, Backtest & Strategy Analytics (curva de equity, drawdown underwater, MFE/MAE scatter) y Notification Settings.
- Cobertura: 100% en `src/notifications/` (413/413 líneas), 98% en `src/streaming/` (405/414 líneas).
- 260 tests automatizados offline y deterministas pasando al 100% (0 fallos).
- Ruff limpio con 0 errores y 0 advertencias.

---

# 6. PRÓXIMA FASE

Fase 6 — AI Market Agent:
1. Agente conversacional y analítico para explicación e interpretación semántica de señales cuantitativas.
2. Síntesis automatizada del contexto de mercado (régimen actual, probabilidades predictivas, estructura de volumen POC/VAH/VAL).
3. Consulta interactiva de estadísticas históricas, drawdown y performance de estrategias.


---



\# 7. VISIÓN FINAL





El objetivo es crear:





Crypto Quant Intelligence Platform





Capaz de:





Analizar:



\- BTC

\- ETH

\- Altcoins





Calcular:



\- Tendencia

\- Momentum

\- Volumen

\- Estructura

\- Probabilidad





Generar:



\- Señales

\- Zonas de compra

\- Zonas de venta

\- Rebotes

\- Objetivos





Validar:



\- Win rate

\- Profit factor

\- Drawdown

\- Rendimiento histórico





Comunicar:



\- Dashboard web

\- Discord

\- Telegram

\- Móvil





\---



\# 8. FILOSOFÍA DE DESARROLLO





Primero:



Datos confiables.





Después:



Modelos estadísticos.





Después:



Automatización.





Nunca al revés.





