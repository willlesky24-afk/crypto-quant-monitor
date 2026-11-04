# Crypto Quant Monitor

Crypto Quant Monitor es un sistema de análisis cuantitativo para mercados de
criptomonedas. Combina indicadores técnicos, perfil de volumen, evaluación de
riesgo, generación de señales y una capa de decisión presentada mediante
Streamlit.

## Versión actual

### v2.3 — Simulador completo (Tag: `v2.3`)

- Mercado `MARGIN_1X` (forex y metales, sin apalancamiento) con LONG, SHORT y BOTH; SHORT es
  espejo exacto de LONG (gaps, SL primero, TP límite, trailing, MFE/MAE, R verificado).
  Cripto SPOT sigue siendo solo LONG; PERP sigue bloqueado.
- Spread bid/ask real por vela (OANDA `price=MBA`): compra al ask, venta al bid.
- Eliminado el ATR mínimo implícito del 0,5 %: un ATR no positivo es un error explícito.
- Cierre semanal y sesiones forex en hora de Nueva York con cambio de horario.
- Límites: sin swap/financiación nocturna; sin modelo de liquidación (pérdida SHORT mayor
  que el margen 1x se rechaza).


### v2.2 — Datos multiproveedor (Tag: `v2.2`)

- Proveedores enchufables vía `FOREX_PROVIDER`: `oanda` (recomendado: precio de broker y
  volumen por ticks), `twelvedata` (verificación cruzada) y `yahoo` (solo desarrollo).
- Oro y plata al contado (XAU/USD, XAG/USD) con OANDA o Twelve Data.
- Misma validación OHLC para todas las fuentes, solo velas cerradas y eliminación de velas
  publicadas dentro del cierre semanal (viernes 17:00 a domingo 17:00, hora de Nueva York).
- Procedencia por serie (`provider`, `provider_symbol`, `volume_kind`) y `compare_sources()`
  para verificar dos fuentes con tolerancia explícita.
- Caché Parquet incremental por proveedor (`FOREX_CACHE_DIR`).

### v2.1

La versión actual es **v2.1 — Integridad del backtest y observabilidad MFE/MAE** (Tag: `v2.1`).
Consolida sobre v2.0 (streaming, notificaciones y dashboard) las correcciones de rigor
cuantitativo del backtest y el cierre de la integración continua:

- **Backtest SPOT LONG 1x verificado**: validación cronológica estricta, warm-up causal,
  trailing desde la vela siguiente, prioridad de gaps de apertura y TP límite, rechazo de
  TP inválido, R bruto y neto con riesgo inicial inmutable, drawdown desde capital inicial,
  conciliación de caja/equity y anualización de Sharpe con procedencia de datos.
- **Observabilidad MFE/MAE (D1B3)**: estados independientes `EXACT_OHLC`, `BOUNDED_OHLC`,
  `UNDETERMINED` y `LEGACY_UNKNOWN` (política `OHLC_D1B3_V1`), cotas inferior/superior en
  salidas intrabar y promedios exactos con denominador y cobertura
  (`NO_TRADES`/`NONE`/`PARTIAL`/`COMPLETE`). Ningún dato ausente se convierte en cero.
- **Calibración fail-closed**: `StrategyOptimizer` solo usa excursiones exactas con
  cobertura completa y ATR válido; con muestra insuficiente o evidencia incompleta lanza
  `OptimizationUnavailableError` en lugar de devolver parámetros por defecto. La intención se
  declara con `calibration_required` (por defecto `False`) en `BacktestRunner`,
  `LiveExecutionEngine` y `DecisionEngine`.
- **Copiloto de IA** (Gemini / OpenAI / Ollama): chat, análisis de imágenes, escáner de
  mercado cripto y forex y veredicto con niveles SL/TP calculados por el motor.
- **Calidad**: 862 pruebas offline y deterministas, Ruff (lint y formato) limpio y CI en
  GitHub Actions sobre Python 3.12 y 3.13.

### Límites conocidos de v2.1

- El backtest solo simula **SPOT LONG 1x**; SHORT, PERP y apalancamiento se rechazan.
- La interfaz no solicita calibración: los backtests corren como "optimización no solicitada".
- Los datos forex provienen de un endpoint no oficial de Yahoo Finance: válido para uso
  personal, no para uso comercial.
- Pendientes fuera de alcance: D1C, D2 y P0-003C-E (política global de aceptación OHLCV).

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

## Hoja de ruta

- **v2.2 — Datos multiproveedor**: adaptador de proveedores (Twelve Data, OANDA demo),
  forex mayor y metales (XAU/USD, XAG/USD), procedencia por vela y verificación cruzada.
- **v2.3 — Simulador completo**: SHORT, spreads y sesiones forex.
- **v3.0 — Prueba de ventaja (cerrada)**: no se demostró ventaja estadística; ver [el informe](docs/INFORME_EVIDENCIA_V3.md). El producto no promete señales rentables.
- **v3.1 — Ranking de oportunidades** por contexto de mercado, sin promesa de rentabilidad, e índices bursátiles.
- **v3.2 — Agente de IA de lectura de mercado**, verificado contra los cálculos del motor.
- **v4.x — Producto**: usuarios, suscripciones, nube y marco legal.

Los planes de fases anteriores se conservan en `docs/historial/`.
