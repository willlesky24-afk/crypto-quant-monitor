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

## Fase 1 — Base de calidad

Estado: **implementada y validada localmente; pendiente de commit**.

Objetivos:

1. crear una suite pytest offline y determinista;
2. corregir inconsistencias confirmadas de Quant Score;
3. incluir el precio máximo en Volume Profile;
4. separar correctamente señal y decisión en registros nuevos;
5. permitir inyección de la base SQLite para pruebas;
6. soportar imports como paquete y ejecución desde `src`;
7. centralizar estados internos sin cambiar sus valores visibles.

Esta fase no implementa todavía el motor de backtesting ni cambia el esquema de
SQLite.

Validación de cierre:

- 76 pruebas automatizadas offline;
- 80% de cobertura total, con al menos 89% en cada módulo funcional modificado;
- Ruff sin errores;
- imports compatibles como paquete y desde `src`;
- `signals.db` sin modificaciones.

## Reglas de desarrollo

- Mantener arquitectura modular y separación de responsabilidades.
- Evitar red y estado persistente en pruebas automáticas.
- No incorporar datos futuros a cálculos históricos.
- Hacer cambios funcionales acompañados de pruebas de regresión.
- No cambiar pesos o reglas de estrategia sin documentar su efecto.
- Mantener Streamlit como capa de presentación, no como núcleo del motor.

## Siguiente objetivo

Después de completar la Fase 1, v1.7 añadirá datos históricos reproducibles,
un pipeline puro por vela, eventos de señal idempotentes, evaluación de
resultados y métricas de backtesting.
