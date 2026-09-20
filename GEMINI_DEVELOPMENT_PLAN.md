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

