# CODEX CONTEXT — Crypto Quant Monitor

## Propósito

Crypto Quant Monitor evoluciona de un monitor técnico hacia un motor
cuantitativo reproducible. Debe analizar mercados, generar señales, evaluar
riesgo, conservar trazabilidad y validar estrategias mediante backtesting.

## Base funcional

La versión base es **v1.6 — Signal History**, etiquetada como `v1.6-ready`.
Incluye:

- carga de velas OHLCV;
- indicadores técnicos;
- perfil de volumen;
- análisis, alertas e inteligencia de mercado;
- señal, riesgo, decisión y Quant Score;
- persistencia SQLite;
- dashboard Streamlit.

## Flujo actual

```text
BinanceDataLoader
  -> TechnicalIndicators
  -> VolumeProfile
  -> MarketEngine
  -> MarketReport
       -> MarketAnalyzer
       -> MarketIntelligence
       -> AlertEngine
       -> SignalEngine
       -> RiskEngine
       -> DecisionEngine
       -> QuantScore
       -> SignalHistory / SQLite
  -> Streamlit
```

## Contrato de compatibilidad v1.6

Mientras se prepara v1.7 deben conservarse:

- el comando `streamlit run src/app.py`;
- nombres y parámetros existentes de las APIs públicas;
- claves de los diccionarios devueltos;
- textos y emojis visibles;
- esquema actual de la tabla `signals`;
- lectura de registros creados por v1.6.

Los parámetros nuevos deben ser opcionales. Las pruebas deben usar bases
temporales y no modificar `signals.db`.

## Fase 1.5 — Quant Integrity

Estado: **completada e integrada**.

Objetivos completados:

1. evaluación estricta de velas cerradas (`include_open_candle=False`);
2. desacoplamiento de `MarketReport` (generación analítica pura);
3. nuevo esquema de persistencia con `UNIQUE(symbol, timeframe, candle_timestamp)`;
4. migración SQLite transaccional con backup `.bak`, validación de conteo y rollback;
5. marcado de registros heredados v1.6 como `is_legacy = 1`;
6. reubicación de scripts de diagnóstico en `scripts/diagnostics/` con soporte UTF-8.

Validación de cierre:

## Fase 2 — Historical Data Engine

Estado: **completada e integrada**.

Objetivos completados:

1. almacenamiento columnar estructurado en Apache Parquet con particionado anual (`YYYY.parquet`);
2. manifiesto de metadatos (`manifest.json`) y versionado de datasets (`1.0`);
3. validador de continuidad temporal y coherencia de precios OHLCV (`CandleValidator`);
4. cargador histórico paginado con control de rate limits y filtro anti-repintado (`HistoricalDataLoader`);
5. orquestador de datasets con sincronización incremental y caché local (`HistoricalDatasetManager`);
6. pruebas de integración de extremo a extremo multiaño (2023-2025) compatibles con motores cuantitativos.

Validación de cierre:

- 125 pruebas automatizadas 100% offline y deterministas;
- 86% de cobertura total (96%-100% en módulos del motor histórico);
- Ruff sin advertencias ni errores.

## Fase 3 — Robust Backtesting Framework

Estado: **completada e integrada** (Tag: `v1.8-backtesting-framework`).

Objetivos completados:

1. modelos de datos inmutables y contratos de eventos tipados (`SignalEvent`, `OrderEvent`, `TradeResult`, `BacktestReport`);
2. métricas de rendimiento y riesgo cuantitativo profesional (Win Rate, Profit Factor, Expectancy, Max Drawdown %, $, duración, MFE, MAE, Sharpe, Calmar);
3. motor de simulación event-driven paso a paso cronológico con modelado de slippage y comisiones de exchange;
4. orquestador de backtest integrado (`BacktestRunner`) acoplado con `HistoricalDatasetManager` y warm-up causal de indicadores;
5. pruebas de integración multianual (2023-2025) validando consistencia determinista y reproducibilidad numérica.

Reglas y conclusiones arquitectónicas aprendidas en Fase 3:

- **Cero look-ahead bias**: las señales se generan exclusivamente en el cierre de la vela $T$; la ejecución de órdenes ocurre estrictamente en el precio de apertura de la vela $T+1$ más slippage.
- **Resolución intra-barra conservadora**: ante escenarios donde el High alcanza el Take Profit y el Low alcanza el Stop Loss dentro de la misma barra, el simulador asume la ejecución del Stop Loss de manera prioritaria.
- **Warm-up causal indispensable**: para indicadores con ventanas amplias (EMA 200, Volume Profile rodante), el backtest debe comenzar a generar señales únicamente tras completar el calentamiento requerido para prevenir valores vacíos o sesgos iniciales.
- **Reportes serializables y desacoplados**: `BacktestReport` proporciona método `.to_dict()` completamente serializable a JSON, aislando el motor cuantitativo de interfaces Streamlit o APIs externas.

Validación de cierre:

- 150 pruebas automatizadas 100% offline y deterministas (0 fallos);
- 90% de cobertura de código global (100% en módulos del backtesting framework);
- Ruff limpio con 0 errores y 0 advertencias.

## Siguiente objetivo (Fase 4)

**Predictive Market Engine & Strategy Optimization**: modelado probabilístico de escenarios, cálculo de probabilidades de continuación/reversión, optimización paramétrica guiada por métricas cuantitativas y soporte para operaciones SHORT.


