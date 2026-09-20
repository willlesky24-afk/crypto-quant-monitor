# Crypto Quant Monitor

Crypto Quant Monitor es un sistema de análisis cuantitativo para mercados de
criptomonedas. Combina indicadores técnicos, perfil de volumen, evaluación de
riesgo, generación de señales y una capa de decisión presentada mediante
Streamlit.

## Versión actual

La versión actual es **v1.9 — Predictive Market Engine & Strategy Optimization** (Tag: `v1.9-predictive-market-engine`), construida sobre la arquitectura del monitor en vivo (v1.6/v1.7), el motor histórico columnar Parquet (Fase 2) y el framework de backtesting orientado a eventos (Fase 3). Incluye:

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
- historial persistente en SQLite con control de migraciones y dashboard Streamlit.

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

## Próxima fase (Fase 5)

**Notification System & Live Streaming**: Sistema de alertas automáticas multicanal (Discord / Telegram), streaming continuo en tiempo real vía WebSocket y panel interactivo avanzado de métricas de backtesting en Streamlit.



