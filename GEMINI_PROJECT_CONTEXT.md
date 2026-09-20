\# Crypto Quant Monitor

# Crypto Quant Monitor

# Gemini Project Context



Versión actual:

v1.9 Predictive Market Engine & Strategy Optimization (Tag: v1.9-predictive-market-engine)

Estado:
FASE 4 COMPLETADA ✅




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





## Capa de memoria



- SQLite Database

- Signal History





## Interfaz



- Streamlit Dashboard





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




## Pipeline en Vivo / Monitor Tiempo Real



```text
Market Data
      ↓
Data Loader
      ↓
Indicators
      ↓
Volume Profile
      ↓
Market Engine
      ↓
Analyzer
      ↓
Signal Engine
      ↓
Risk Engine
      ↓
Decision Engine
      ↓
Quant Score
      ↓
Report
      ↓
Dashboard
      ↓
Signal History
      ↓
SQLite
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

# 6. PROBLEMAS PENDIENTES / PRÓXIMAS FASES

Actualmente:

1. Sistema de notificaciones automáticas y multicanal (Fase 5: Notification System - Discord / Telegram).
2. Panel visual interactivo de métricas de backtesting en Streamlit (curvas de capital, drawdown submarino, distribución MFE/MAE).
3. Integración en tiempo real de WebSocket con Binance para streaming continuo de velas.


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





