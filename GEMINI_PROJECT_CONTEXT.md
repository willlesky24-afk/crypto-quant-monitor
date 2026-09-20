\# Crypto Quant Monitor

\# Gemini Project Context



Versión actual:

v1.7 Quant Integrity




\---



\# 1. IDENTIDAD DEL PROYECTO



Crypto Quant Monitor es una plataforma de análisis cuantitativo de mercados de criptomonedas.



El objetivo del proyecto NO es crear un simple indicador de trading.



El objetivo es construir un sistema profesional capaz de:



\- Analizar datos de mercado.

\- Interpretar estructura.

\- Detectar oportunidades.

\- Generar señales.

\- Evaluar riesgo.

\- Validar estrategias mediante datos históricos.

\- Crear inteligencia cuantitativa.





\---



\# 2. ESTADO ACTUAL



El sistema actualmente cuenta con:





\## Capa de datos



\- Data Loader

\- Indicadores técnicos

\- Volume Profile





\## Capa analítica



\- Market Engine

\- Analyzer

\- Market Intelligence





\## Capa de decisión



\- Alert Engine

\- Signal Engine

\- Risk Engine

\- Decision Engine

\- Quant Score





\## Capa de memoria



\- SQLite Database

\- Signal History





\## Interfaz



\- Streamlit Dashboard





\---



\# 3. ARQUITECTURA ACTUAL





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





\---



\# 4. PRINCIPIOS DEL PROYECTO





El sistema debe mantenerse:





\- Modular.

\- Escalable.

\- Probable estadísticamente.

\- Fácil de probar.

\- Documentado.





No debe convertirse en:



\- Un script gigante.

\- Un bot de compra/venta automático sin validación.

\- Un sistema basado en opiniones.





\---



\# 5. ESTADO DE CALIDAD ACTUAL





Fase 1 completada:





\- Tests automatizados (suite offline).

\- Cobertura aproximada 80%.

\- Correcciones de QuantScore.

\- Constantes centralizadas.

\- Persistencia separada.

\- SQLite inyectable.

\- Validación offline.





Fase 1.5 Quant Integrity completada:





\- Evaluación estricta de velas cerradas (anti-repainting).

\- Desacoplamiento de generación de reportes y persistencia (MarketReport puro).

\- Migración transaccional de SQLite con backup automático, validación de conteo y rollback.

\- Control de versiones de esquema en `schema_migrations`.

\- Idempotencia en persistencia por `(symbol, timeframe, candle_timestamp)`.

\- Marcado explícito de registros históricos heredados como `is_legacy = 1`.

\- Reorganización de scripts de diagnóstico en `scripts/diagnostics/` con soporte UTF-8.





\---



\# 6. PROBLEMAS PENDIENTES





Actualmente:





1\. No existe backtesting.



2\. Las señales no tienen todavía una evaluación posterior.



3\. Falta almacenar contexto completo de mercado.



4\. Falta sistema histórico profesional.



5\. Falta motor probabilístico.





\---



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





