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

\# Historical Data Engine





OBJETIVO:



Crear la infraestructura histórica.





Construir:





\## Historical Data Loader





Debe permitir:





\- Descargar datos históricos.

\- Trabajar por fechas.

\- Guardar datasets.

\- Evitar depender siempre de API.





\---



\## Data Storage





Implementar:





\- Parquet.

\- Cache histórico.

\- Versionado de datasets.





\---



\## Candle Validation





Controlar:





\- Velas incompletas.

\- Datos faltantes.

\- Errores.





\---



\# FASE 3

\# Backtesting Engine





OBJETIVO:



Responder:





"¿Qué ocurrió después de esta señal?"





Crear:





\## Signal Outcome Evaluator





Medir:





\- Movimiento posterior.

\- Tiempo hasta objetivo.

\- Máximo favorable.

\- Máximo adverso.





\---



\## Metrics Engine





Calcular:





\- Win rate.

\- Loss rate.

\- Profit factor.

\- Expectativa.

\- Drawdown.





\---



\# FASE 4

\# Predictive Market Engine





OBJETIVO:





Pasar de análisis descriptivo a probabilístico.





Crear:





\- Probabilidad de continuación.

\- Probabilidad de reversión.

\- Zonas futuras.

\- Escenarios.





\---



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

