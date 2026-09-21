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

## Fase 4 — Predictive Market Engine & Strategy Optimization

Estado: **completada e integrada** (Tag: `v1.9-predictive-market-engine`).

Estructura Arquitectónica Actual:
- **Capa descriptiva**: `MarketAnalyzer`, `MarketReport`, `QuantScore`.
- **Capa contextual**: `RegimeClassifier` (`TRENDING_BULL`, `TRENDING_BEAR`, `RANGING_CONSOLIDATION`, `HIGH_VOLATILITY_EXPANSION`).
- **Capa probabilística**: `PredictiveEngine` (estimación causal de $P(\text{continuation})$ y $P(\text{reversal})$ con suavizado de Laplace).
- **Capa de optimización**: `StrategyOptimizer` (calibración empírica MFE/MAE de TP/SL, Walk-Forward Validation TRAIN 2023-2024 vs VALIDATION 2025).
- **Capa de decisión**: `Enhanced DecisionEngine` (fusión adaptativa $W_{\text{tech}}=0.60, W_{\text{pred}}=0.40$, soporte LONG/SHORT, `DecisionResult`).
- **Capa de simulación y backtest**: `BacktestEngine`, `BacktestRunner`, `BacktestMetricsCalculator`.

Reglas y conclusiones arquitectónicas aprendidas en Fase 4:
- **Separación analítica estricta**: `PredictiveEngine` no reemplaza ni modifica el análisis técnico existente de $t \le T$; actúa como una capa probabilística desacoplada proyectando escenarios $t > T$.
- **Optimización causal fuera de muestra**: La calibración de parámetros se realiza estrictamente en el período de entrenamiento y se valida fuera de muestra, evitando el sesgo de sobreajuste (*overfitting*).
- **Soporte bidireccional y derivados**: Modelado completo de posiciones SHORT, contratos perpetuos (`MarketType.PERP`) y liquidación periódica de comisiones de financiamiento (*funding fees*).
- **Eficiencia computacional**: Volume Profile optimizado mediante `np.histogram` alcanzando de 4x a 9x de aceleración conservando estricta identidad matemática (POC, VAH, VAL).

Validación de cierre:
- 204 pruebas automatizadas 100% offline y deterministas (0 fallos);
- 92% de cobertura de código global (100% en módulos del backtesting framework y módulos optimizados);
- Ruff limpio con 0 errores y 0 advertencias.

## Fase 5 — Notification System, Live Streaming & Dashboard Visualizer

Estado: **completada e integrada** (Tag: `v2.0-live-notifications-dashboard`).

Objetivos completados:

1. contratos de eventos tipados (`SignalEvent`, `NotificationPayload`, `NotificationResult`) como fuente única de verdad para alertas y simulaciones;
2. adaptadores de canal (`DiscordWebhookChannel`, `TelegramChannel`, `WebhookChannel`) con formato enriquecido semántico, reintentos exponenciales con jitter y truncado seguro;
3. despachador central (`NotificationDispatcher`) con `CooldownManager` en memoria, filtrado por score predictivo, aislamiento de fallos por canal y concurrencia no bloqueante;
4. cliente WebSocket (`ResilientWebSocketClient`) para streams kline de Binance con reconexión automática infinita y heartbeat;
5. agregador de velas (`CandleAggregator`) con buffer rodante acotado (`deque`), evaluación estricta de vela cerrada ($T$) y garantía de no-repainting;
6. motor en tiempo real (`LiveExecutionEngine`) acoplando streaming, features, régimen, predicción, decisiones cuantitativas y emisión de alertas;
7. suite de paridad live replay vs backtest (`test_live_replay_parity.py`) certificando 100% de identidad numérica y de señal;
8. dashboard Streamlit multi-pestaña interactivo para monitoreo en vivo, analítica de backtests (curva de capital, drawdown submarino, scatter MFE/MAE) y configuración de notificaciones.

Reglas y conclusiones arquitectónicas aprendidas en Fase 5:

- **Contrato de evento inmutable y unificado**: `SignalEvent` desacopla completamente el motor de cálculo cuantitativo de los canales de entrega. Los canales son estrictamente consumidores y no calculan señales ni alteran datos.
- **Aislamiento de fallos en despacho multicanal**: Un fallo o timeout en un webhook (p. ej. Discord) nunca debe degradar o abortar el despacho a otros canales (p. ej. Telegram).
- **Anti-spam mediante cooldown contextual**: Para evitar saturar los canales con señales idénticas en consolidaciones prolongadas, el gestor de cooldown evalúa la tupla `(symbol, timeframe, action)` con retención en memoria.
- **Buffer acotado y paridad matemática exacta**: `CandleAggregator` utiliza una ventana rodante con longitud máxima fija en memoria (`buffer_size=500`), garantizando uso constante de RAM y reproduciendo exactamente los mismos indicadores y señales que el `BacktestRunner`.

Validación de cierre:

- 260 pruebas automatizadas 100% offline y deterministas (0 fallos);
- 100% de cobertura en `src/notifications/` (413/413 líneas);
- 98% de cobertura en `src/streaming/` (405/414 líneas);
- Ruff limpio con 0 errores y 0 advertencias.

## Siguiente objetivo (Fase 6)

**AI Market Agent**: Agente conversacional e inteligente para explicación y contextualización semántica de señales cuantitativas, análisis de regímenes de mercado y consulta de performance histórica.



