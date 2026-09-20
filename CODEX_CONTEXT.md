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

- 84 pruebas automatizadas offline;
- 80%+ de cobertura total;
- Ruff sin errores;
- `signals.db` migrada de forma segura e idempotente.

## Siguiente objetivo (Fase 2)

v1.7 continuará con la construcción del **Historical Data Engine**: datasets históricos reproducibles, almacenamiento en Parquet, particionado y validación de continuidad de velas antes del motor de backtesting.

