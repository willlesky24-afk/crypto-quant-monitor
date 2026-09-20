\# Crypto Quant Monitor

\# Development Roadmap





\# FASE 1

\## Quality Baseline



ESTADO:



COMPLETADO





Objetivo:



Preparar la arquitectura.





Incluye:



\- Tests.

\- Limpieza.

\- Constantes.

\- Mejoras de persistencia.

\- Validación.





\---



\# FASE 1.5

\## Quant Integrity



ESTADO:



COMPLETADO



Objetivo:



Sanear la integridad de datos, eliminar sesgo de repintado y garantizar trazabilidad antes del backtesting.



Incluye:



\- Evaluación estricta de velas cerradas en DataLoader (`include_open_candle=False`).

\- Desacoplamiento de `MarketReport` (función analítica pura).

\- Migración transaccional de SQLite con backup `.bak`, validación de registros y rollback.

\- Registro de versiones de esquema (`schema_migrations`).

\- Idempotencia en persistencia con clave `UNIQUE(symbol, timeframe, candle_timestamp)`.

\- Marcado explícito de datos históricos v1.6 como `is_legacy = 1`.

\- Reubicación de scripts de diagnóstico en `scripts/diagnostics/`.





\---



\# FASE 2

## Historical Data Engine

ESTADO:

COMPLETADO

Objetivo:

Crear la infraestructura histórica columnar, de alta velocidad y libre de sesgo para soportar análisis cuantitativo multiaño y backtesting offline reproducible.

Componentes implementados:

- **Almacenamiento Columnar Parquet (`src/parquet_store.py`)**:
  - Formato Apache Parquet con compresión Snappy.
  - Particionado anual (`YYYY.parquet`) bajo `data/historical/{symbol}/{interval}/`.
  - Escritura atómica mediante archivos temporales `.tmp` para evitar corrupción por caídas.
  - Versionado de datasets (`dataset_version: 1.0`) y metadatos en `manifest.json`.

- **Validador de Calidad y Continuidad (`src/candle_validator.py`)**:
  - Detección precisa de huecos temporales (gaps) adaptada a cada intervalo (`1m` a `1w`).
  - Detección y descarte automático de velas duplicadas con ordenamiento cronológico.
  - Saneamiento de límites OHLC (High >= Open, Close; Low <= Open, Close) y volumen no negativo.
  - Modos estricto (`strict=True`) y permisivo/reparación (`repair=True`).
  - Reporte de calidad estructurado (`CandleQualityReport`).

- **Descarga Paginada y Control de Rate Limit (`src/historical_data_loader.py`)**:
  - Descarga paginada en bloques de hasta 1000 velas por solicitud.
  - Reintentos con retroceso exponencial (*exponential backoff*) ante fallos transitorios.
  - Detección de encabezado de carga de Binance (`x-mbx-used-weight-1m`) y throttling automático.
  - Filtro estricto anti-repintado de velas en formación (`include_open_candle=False`).

- **Gestor de Datasets (`src/dataset_manager.py`)**:
  - Orquestación unificada de descarga, validación y almacenamiento en disco.
  - Sincronización incremental inteligente: detecta rango existente y solo consulta a la API el tramo faltante.
  - Consultas y filtrado temporal eficiente sin recargar toda la serie.
  - Resumen consolidado de metadatos de datasets disponibles.

Métricas de Calidad y Verificación:
- 125 pruebas automatizadas offline y deterministas ejecutadas con éxito (0 fallos).
- Cobertura de tests: `CandleValidator` (100%), `HistoricalDatasetManager` (100%), `HistoricalDataLoader` (99%), `ParquetStore` (96%).
- Pipeline de integración multiaño (2023-2025) validado con indicadores técnicos y MarketEngine.





---

# FASE 3

## Robust Backtesting Framework

ESTADO:

COMPLETADO (Tag: `v1.8-backtesting-framework`)

Objetivo:

Responder rigurosamente "¿Qué ocurrió después de esta señal?" mediante un motor de simulación histórico cronológico orientado a eventos, desacoplado, libre de look-ahead bias y con modelado de comisiones y slippage.

Commits realizados:
- `1a54106`: `feat(backtest): add backtest data models, configuration, and event schemas` (`src/backtest_models.py`, `tests/unit/test_backtest_models.py`)
- `0c6950d`: `feat(backtest): implement trade performance and risk metrics calculator (MFE, MAE, Expectancy, Drawdown)` (`src/backtest_metrics.py`, `tests/unit/test_backtest_metrics.py`)
- `d2686fa`: `feat(backtest): implement chronological event-driven backtest simulation engine with fee/slippage modeling` (`src/backtest_engine.py`, `tests/unit/test_backtest_engine.py`)
- `8a6e001`: `feat(backtest): add high-level BacktestRunner integrated with HistoricalDatasetManager` (`src/backtest_runner.py`, `tests/unit/test_backtest_runner.py`)
- `d709537`: `test(backtest): add end-to-end multi-year backtesting pipeline integration tests` (`tests/integration/test_backtest_pipeline.py`)

Componentes implementados:

- **Modelos y Esquemas de Eventos (`src/backtest_models.py`)**:
  - `SignalEvent`: evento de señal generado estrictamente al cierre de la vela $T$.
  - `OrderEvent`: orden de mercado ejecutada en $Open(T+1)$ con ajuste por deslizamiento.
  - `TradeResult`: registro inmutable del resultado de la operación (precios de entrada/salida, retornos brutos/netos, MFE, MAE, motivo de salida).
  - `EquityPoint` y `BacktestReport`: serie temporal de capital y reporte cuantitativo final serializable a diccionario / JSON.

- **Calculadora de Métricas de Rendimiento y Riesgo (`src/backtest_metrics.py`)**:
  - Métricas básicas y avanzadas: Total Trades, Win Rate, Profit Factor, Expectancy ($ y %).
  - Métricas de excursión de precio: Max Favorable Excursion (MFE) y Max Adverse Excursion (MAE) individuales y promedio.
  - Métricas de riesgo y curvas de capital: Max Drawdown en porcentaje, monto absoluto en USD y duración en velas; Sharpe Ratio y Calmar Ratio anualizados.

- **Motor de Simulación Cronológica Event-Driven (`src/backtest_engine.py`)**:
  - Simulación paso a paso vela a vela sin filtración de datos futuros (zero look-ahead bias).
  - Ejecución estricta $T+1$: señal generada en cierre de vela $T$, entrada en apertura de $T+1$.
  - Modelado de costes: comisiones taker/maker y slippage porcentual configurable.
  - Resolución conservadora intra-barra: en caso de que una vela toque simultáneamente Take Profit y Stop Loss, se asume la ejecución del Stop Loss primero.
  - Manejo de cierres por límite de horizonte temporal (*max_holding_bars*) o fin de serie.

- **Orquestador Integral (`src/backtest_runner.py`)**:
  - Integración directa con `HistoricalDatasetManager` y `ParquetStore`.
  - Ventana causal de calentamiento (*warm-up*) para asegurar estabilidad de indicadores técnicos (EMA 200, ATR, RSI, Volume Profile).
  - Evaluación desacoplada y secuencial: generación de señales en tiempo real simulado -> simulación de órdenes en motor de backtest -> consolidación en reporte unificado.

Métricas de Calidad y Verificación:
- 150 pruebas automatizadas offline y deterministas pasando al 100% (0 fallos).
- 90% de cobertura de código total en el repositorio.
- 100% de cobertura en los 4 módulos críticos del motor de backtesting (`backtest_models.py`, `backtest_metrics.py`, `backtest_engine.py`, `backtest_runner.py`).
- Ruff clean (0 errores y 0 advertencias).
- Validación de pipeline multianual E2E (2023-2025) con pruebas de reproducibilidad numérica y consistencia determinista.

---



\# FASE 4

## Predictive Market Engine & Strategy Optimization

ESTADO:
COMPLETADO ✅

Objetivo:
Evolucionar desde el análisis descriptivo hacia una arquitectura probabilística causal y optimización empírica de parámetros sin look-ahead bias ni overfitting.

Componentes Implementados:
- **Aceleración de Volume Profile**: Vectorización con `np.histogram` alcanzando de 4x a 9x de aceleración (`VolumeProfile.calculate`).
- **Soporte Bidireccional y Futuros Perpetuos**: Posiciones LONG/SHORT, comisiones de perpetuos (`MarketType.PERP`) y funding fees de 8h (`src/backtest_engine.py`).
- **Clasificador Causal de Regímenes de Mercado (`src/regime_classifier.py`)**: Identificación determinista en vela $T$ de `TRENDING_BULL`, `TRENDING_BEAR`, `RANGING_CONSOLIDATION`, `HIGH_VOLATILITY_EXPANSION`.
- **Motor Predictivo de Escenarios (`src/predictive_engine.py`)**: Estimación empírica de $P(\text{continuation})$ y $P(\text{reversal})$ con suavizado de Laplace y cálculo ponderado de `PredictiveScore` $\in [0, 1]$.
- **Optimizador Empírico de Estrategias (`src/strategy_optimizer.py`)**: Análisis de distribución MFE/MAE, calibración de TP/SL por régimen, Walk-Forward Validation (TRAIN: 2023-2024 vs VALIDATION: 2025) y controles anti-overfitting.
- **Capa de Decisión Mejorada (`src/decision_engine.py`)**: Ponderación adaptativa ($W_{\text{tech}} = 0.60$, $W_{\text{pred}} = 0.40$), asignación LONG/SHORT y compatibilidad legacy total (`DecisionResult`).
- **Integración de Backtesting E2E (`src/backtest_runner.py`)**: Orquestación de pipeline predictivo multianual sobre datasets Parquet.

Commits Realizados:
- `e27d103` perf(volume-profile): profile and optimize Volume Profile calculation with vectorized binning
- `075ab1a` feat(backtest): implement SHORT positions, perpetual futures fees, and funding rate modeling
- `e839eaa` feat(regime): implement market regime classifier (trend, range, volatility expansion)
- `ca97f72` feat(predictive): implement predictive market engine and conditional probability scoring
- `72e46a1` feat(optimizer): implement MFE/MAE empirical parameter optimizer with walk-forward validation
- `0456802` feat(strategy): implement predictive-enhanced strategy decision logic
- `83fe25d` test(integration): create end-to-end predictive backtest pipeline validation

Métricas de Calidad y Verificación:
- 204 pruebas automatizadas offline y deterministas pasando al 100% (0 fallos).
- 92% de cobertura de código global (100% en módulos del backtesting framework y módulos optimizados).
- Ruff clean (0 errores y 0 advertencias).
- Validación de pipeline multianual E2E (2023-2025) con pruebas de no-lookahead bias y determinismo.
-



\# FASE 5
\# Notification System





Integrar:





\## Discord





Servidor privado:





Ejemplo:





🚨 BTCUSDT ALERT





Precio:

81250





Score:

92





Decisión:

Esperar confirmación





Riesgo:

Medio







\---



También:



\- Telegram.

\- Email.





\---



\# FASE 6

\# AI Market Agent





Crear agente capaz de:





\- Explicar señales.

\- Resumir mercado.

\- Consultar históricos.

\- Responder preguntas.





Ejemplo:





¿Por qué BTC tiene señal amarilla?





Respuesta:





"La tendencia es positiva, pero falta confirmación de volumen."





\---



\# FASE 7

\# Plataforma Completa





Funciones:





\- Usuarios.

\- Dashboard avanzado.

\- Múltiples activos.

\- Alertas personalizadas.

\- Comunidad.





\---



\# REGLA PRINCIPAL





Cada fase debe:





1\. Analizar.

2\. Diseñar.

3\. Probar.

4\. Implementar.

5\. Documentar.

6\. Commit.





Nunca saltar fases.

