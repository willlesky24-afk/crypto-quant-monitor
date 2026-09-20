# Crypto Quant Monitor

Crypto Quant Monitor es un sistema de análisis cuantitativo para mercados de
criptomonedas. Combina indicadores técnicos, perfil de volumen, evaluación de
riesgo, generación de señales y una capa de decisión presentada mediante
Streamlit.

## Versión actual

La base funcional es **v1.6 — Signal History**. Incluye:

- descarga de OHLCV desde la API pública de Binance;
- RSI, ATR, volumen promedio y EMA 50/200;
- Volume Profile con POC, VAH y VAL;
- análisis de mercado, alertas, señal, riesgo y decisión;
- Quant Score;
- historial persistente en SQLite;
- dashboard Streamlit.

La Fase 1 de v1.7 estabiliza esta base con pruebas automatizadas, correcciones
de consistencia y dependencias inyectables. El motor de backtesting se añadirá
en fases posteriores.

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

## Próxima fase (Fase 3)

**Robust Backtesting Framework**: motor de backtesting vectorizado y orientado a eventos, métricas de rendimiento cuantitativas (Sharpe Ratio, Max Drawdown, Calmar Ratio, Win Rate, Profit Factor), simulación de deslizamiento (slippage) y comisiones de exchange.

