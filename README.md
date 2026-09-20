# Crypto Quant Monitor

Crypto Quant Monitor es un sistema de análisis cuantitativo para mercados de
criptomonedas. Combina indicadores técnicos, perfil de volumen, evaluación de
riesgo, generación de señales y una capa de decisión presentada mediante
Streamlit.

## Versión actual

La versión actual es **v1.8 — Robust Backtesting Framework** (Tag: `v1.8-backtesting-framework`), construida sobre la arquitectura de monitor en vivo (v1.6/v1.7), el motor histórico columnar Parquet (Fase 2) y el framework de backtesting orientado a eventos (Fase 3). Incluye:

- descarga de OHLCV en vivo e histórica desde Binance con validación de integridad;
- almacenamiento columnar optimizado en Apache Parquet con particionado anual;
- RSI, ATR, volumen promedio, EMA 50/200 y Volume Profile (POC, VAH, VAL);
- análisis de mercado, alertas, señal, riesgo, decisión y Quant Score;
- motor de backtesting cronológico event-driven libre de look-ahead bias;
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

## Próxima fase (Fase 4)

**Predictive Market Engine & Strategy Optimization**: Modelado probabilístico de escenarios, cálculo de probabilidades de continuación y reversión, optimización cuantitativa de parámetros TP/SL guiada por MFE/MAE y soporte para posiciones SHORT.


