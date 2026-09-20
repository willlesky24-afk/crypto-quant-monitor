# FASE 4: Predictive Market Engine & Strategy Optimization
## Documento Técnico de Planificación y Propuesta Arquitectónica

**Versión:** 1.0  
**Fecha:** Septiembre 2026  
**Estado:** Propuesta Técnica para Validación  
**Base:** v1.8 Backtesting Framework (`b25f248`, Tag `v1.8-backtesting-framework`)  

---

## 1. Contexto y Objetivos Técnicos

Tras la culminación de la **Fase 2 (Historical Data Engine)** y la **Fase 3 (Robust Backtesting Framework)**, el sistema cuenta con:
- Almacenamiento columnar Parquet multiaño sin pérdida de fidelidad.
- Motor de simulación cronológico event-driven $T+1$ con modelado de comisiones y slippage.
- Métricas institucionales calculadas rigurosamente (Win Rate, Profit Factor, Expectancy, Max Drawdown %, $, duración, MFE, MAE, Sharpe, Calmar).
- 150 pruebas automatizadas 100% offline y deterministas, con 90% de cobertura global y 0 errores de linter.

El propósito central de la **Fase 4** es transformar el sistema desde un **monitor descriptivo/reglas estáticas** hacia un **motor predictivo probabilístico y optimizado empíricamente**, sustentado por cuatro pilares:

1. **Predictive Market Engine (Capa Probabilística)**:
   - Cuantificar probabilidades objetivas de continuación y reversión de tendencia.
   - Identificar el régimen de mercado actual (*Trending Bullish*, *Trending Bearish*, *Ranging/Mean-Reverting*, *High Volatility/Breakout*).
   - Generar un *PredictiveScore* probabilístico que complemente y refine el *QuantScore* descriptivo existente.
   - **Principio cardinal:** Separación estricta entre **Análisis Descriptivo** (hechos del pasado $t \le T$) y **Proyección Probabilística** (distribuciones de probabilidad condicionales para $t > T$).

2. **Optimización Paramétrica Guiada por MFE/MAE**:
   - Emplear los datos reales de excursión favorable máxima (MFE) y excursión adversa máxima (MAE) generados por el backtest para calibrar los niveles óptimos de Take Profit, Stop Loss y múltiplos ATR.
   - Determinar dinámicamente si una configuración minimiza el riesgo de parada prematura (*noise stop-out*) maximizando a la vez la expectativa matemática ($E$).

3. **Soporte Completo para Posiciones SHORT y Futuros Perpetuos**:
   - Extender el modelo de datos y el motor de backtesting para permitir operaciones bidireccionales (LONG y SHORT).
   - Modelar el apalancamiento, comisiones diferenciadas de futuros (maker/taker contract fees) y el impacto del financiamiento (*Funding Rates* acumulados cada 8 horas).
   - Mantener resolución conservadora intra-barra para posiciones SHORT ($High \ge SL$ prioritario sobre $Low \le TP$).

4. **Optimización de Rendimiento (Profiling First)**:
   - Medir el perfil de consumo de CPU/memoria del pipeline multianual antes de alterar algoritmos.
   - Optimizar el cálculo de `VolumeProfile` en ventanas deslizantes mediante histogramas acumulativos o vectorización NumPy, reduciendo la latencia de simulación multiaño.

---

## 2. Arquitectura Propuesta

### 2.1 Diagrama de Flujo Integral de Fase 4

```text
               HISTORICAL DATA / PARQUET / LIVE STREAM
                                 │
                                 ▼
                     HistoricalDatasetManager
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                           ▼
          TechnicalIndicators            VolumeProfile
           (EMA, ATR, RSI)           (Opt. Histograma Vectorial)
                   │                           │
                   └─────────────┬─────────────┘
                                 │
                                 ▼
                           MarketEngine
                      (Análisis Descriptivo)
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
                ▼                                 ▼
        Descriptive Layer                 Predictive Layer (NUEVO)
   ┌───────────────────────────┐    ┌──────────────────────────────────┐
   │ MarketReport              │    │ RegimeClassifier                 │
   │ MarketAnalyzer            │    │  - Regímenes: Trend/Range/Vol    │
   │ MarketIntelligence        │    │ PredictiveEngine                 │
   │ QuantScore (Descriptivo)  │    │  - P(Continuación | Régimen)     │
   │ SignalEngine (LONG/SHORT) │    │  - P(Reversión | Zonas VP, RSI)  │
   │ RiskEngine (SL/TP base)   │    │  - PredictiveScore [0-100]       │
   └───────────────────────────┘    └──────────────────────────────────┘
                │                                 │
                └────────────────┬────────────────┘
                                 │
                                 ▼
                      DecisionEngine v2
             (Ponderación Descriptiva + Probabilística)
                                 │
                                 ▼
                     SignalEvent (LONG / SHORT)
                                 │
                                 ▼
                      BacktestEngine v2
      (LONG/SHORT, Slippage, Fees Spot/Perp, Funding Rates)
                                 │
                                 ▼
                    BacktestMetricsCalculator
               (MFE, MAE, Expectancy, Drawdown, ...)
                                 │
                                 ▼
                   ParameterOptimizer (NUEVO)
      (Calibración empírica MFE/MAE de TP/SL por Régimen)
                                 │
                                 ▼
                 Comprehensive BacktestReport v2
```

---

### 2.2 Especificación de Módulos Nuevos y Modificados

#### 1. Módulo: `src/regime_classifier.py` (NUEVO)
- **Responsabilidad:** Clasificar el entorno de mercado en cada vela $T$ sin sesgo de anticipación.
- **Regímenes Identificados:**
  - `TRENDING_BULL`: Precios sobre EMA 200, pendiente EMA 50 positiva, RSI en zona de impulso $> 55$, ADX $> 25$.
  - `TRENDING_BEAR`: Precios bajo EMA 200, pendiente EMA 50 negativa, RSI $< 45$, ADX $> 25$.
  - `RANGING_CONSOLIDATION`: Precios oscilando en torno a EMA 200 o dentro de VAH-VAL, ADX $< 20$, volatilidad comprimida.
  - `HIGH_VOLATILITY_EXPANSION`: Expansión súbita de ATR respecto a su media, ruptura con volumen de zonas de valor.
- **Salida:** `MarketRegimeReport(regime: MarketRegime, confidence: float, features: dict)`.

#### 2. Módulo: `src/predictive_engine.py` (NUEVO)
- **Responsabilidad:** Cuantificar probabilidades condicionales empíricas a partir de factores técnicos y regímenes de mercado.
- **Funcionalidades:**
  - `calculate_continuation_probability(candle_context, regime)`: Probabilidad de que la tendencia actual se sostenga en los próximos $K$ periodos.
  - `calculate_reversal_probability(candle_context, regime)`: Probabilidad de rechazo en zonas clave (POC, VAH, VAL, soporte/resistencia) basada en divergencias y volumen.
  - `generate_predictive_score(descriptive_score, regime, probabilities)`: Scoring unificado combinando la solidez técnica observada con la probabilidad condicional estadística.
- **Salida:** `PredictiveResult(p_continuation: float, p_reversal: float, predictive_score: float, suggested_bias: str)`.

#### 3. Modificaciones en Modelos y Motor de Backtest (`src/backtest_models.py`, `src/backtest_engine.py`)
- **Extensión a Posiciones SHORT:**
  - `SignalType`: Soporte formal de `SELL_SHORT` y `COVER_SHORT` junto con `BUY_LONG` y `SELL_LONG`.
  - `Position`: Campo `side: PositionSide ("LONG" | "SHORT")`.
  - Cálculo de PnL para SHORT: $PnL_{bruto} = Cantidad \times (Precio_{Entrada} - Precio_{Salida})$.
  - Cálculo de MAE/MFE para SHORT:
    - $MFE = \max(Precio_{Entrada} - Low_{intra}) / Precio_{Entrada}$
    - $MAE = \max(High_{intra} - Precio_{Entrada}) / Precio_{Entrada}$
  - Resolución intra-barra conservadora para SHORT: si $High \ge SL$ y $Low \le TP$ en la misma vela, se ejecuta el Stop Loss primero.
- **Modelado de Futuros y Financiación (*Funding Rates*):**
  - Parámetros en `BacktestConfig`:
    - `market_type: str = "SPOT" | "PERP"`
    - `funding_rate_8h: float = 0.0001` (tasa de financiamiento por defecto de 0.01% por período de 8h).
    - `leverage: float = 1.0`.
  - Deducción periódica del funding fee en posiciones abiertas sobre contratos perpetuos al cruzar los timestamps estándar (00:00, 08:00, 16:00 UTC).

#### 4. Módulo: `src/parameter_optimizer.py` (NUEVO)
- **Responsabilidad:** Calibrador empírico de parámetros de gestión de riesgo basado en distribuciones históricas de MFE y MAE.
- **Funcionalidades:**
  - Análisis de distribución de MAE en operaciones ganadoras para ubicar el Stop Loss justo por encima del percentil 90 o 95 de ruido adverso.
  - Análisis de distribución de MFE para ubicar Take Profit en el punto que maximiza la esperanza matemática:  
    $$E(TP, SL) = (WinRate(TP, SL) \times R_{gain}) - ((1 - WinRate(TP, SL)) \times R_{loss})$$
  - Búsqueda en grilla acotada (*grid search*) o algoritmo unidimensional para calibrar multiplicadores de ATR (`atr_multiplier_sl`, `atr_multiplier_tp`) segmentados por régimen de mercado.
  - Validación cruzada temporal (Walk-Forward) para evitar sobreajuste (*overfitting*).

#### 5. Optimización de Rendimiento de `VolumeProfile` (`src/volume_profile.py`)
- **Profiling preliminar:** Medir con precisión los puntos de congestión mediante `cProfile` sobre ejecuciones multianuales.
- **Optimización vectorizada:**
  - Reemplazar la asignación iterativa en loops de Python por binning vectorizado de NumPy (`np.histogram`).
  - Implementación opcional de actualización en ventana deslizante (*rolling window histogram*) donde solo se resta la vela que sale y se suma la vela que entra.

---

## 3. Dependencias Nuevas y Compatibilidad

### 3.1 Evaluación de Dependencias
- **NumPy y Pandas:** Ya presentes en `requirements.txt`. Suficientes para la mayoría de cálculos vectorizados de histogramas y regímenes.
- **SciPy (`scipy`):**
  - *Evaluación:* Aporta `scipy.stats` (para estimación de densidad por kernel KDE sobre MFE/MAE y tests de normalidad) y `scipy.optimize`.
  - *Decisión:* Evaluar su incorporación formal en `requirements.txt` / `requirements-dev.txt` únicamente si las funciones de percentiles de NumPy no resultan suficientes para la optimización paramétrica. Se priorizará mantener dependencias mínimas.

### 3.2 Contrato de Compatibilidad
- Las funciones y endpoints existentes de `MarketEngine`, `DecisionEngine` y `Streamlit` mantendrán retrocompatibilidad absoluta.
- El `PredictiveEngine` se conectará como una capa opcional o desacoplada, asegurando que si se deshabilita, el sistema opera con el flujo clásico v1.6/v1.7/v1.8.
- Todos los tests de regresión previos (150 tests) deberán mantenerse pasando al 100%.

---

## 4. Análisis de Riesgos y Mitigaciones

| Riesgo Técnico | Impacto | Mitigación Arquitectónica |
| :--- | :--- | :--- |
| **Sobreajuste (Overfitting)** en optimización de TP/SL | Alto: Parámetros excelentes en el pasado que fallan en el futuro. | Implementación estricta de particionado temporal *In-Sample* (ej. 2023) y *Out-of-Sample* (ej. 2024-2025). Límites razonables en el rango de búsqueda de múltiplos ATR. |
| **Look-ahead Bias** en el cálculo probabilístico | Crítico: Señales predictivas contaminadas con velas futuras. | Todas las métricas de régimen y probabilidades se calculan sobre la ventana causal $[0, T]$ con el corte estricto en la vela cerrada $T$. |
| **Asimetría y Riesgo de Liquidación en SHORT** | Medio-Alto: Pérdida ilimitada teórica si el precio sube bruscamente. | Modelado explícito de Stop Loss obligatorio para posiciones cortas y cálculo de margen de mantenimiento en contratos perpetuos. |
| **Optimización Prematura** en Volume Profile | Bajo-Medio: Complejidad accidental en el código sin beneficio perceptible. | Regla estricta: No alterar `src/volume_profile.py` sin una prueba de profiling previa que documente cuantitativamente el cuello de botella. |

---

## 5. Plan de Implementación Commit por Commit

Para mantener la cadencia iterativa, verificable y con aprobación paso a paso:

```text
Commit 1: perf(volume-profile): profile and optimize Volume Profile calculation with vectorized binning
Commit 2: feat(backtest): implement SHORT positions, perpetual futures fees, and funding rate modeling
Commit 3: feat(regime): implement market regime classifier (trend, range, volatility expansion)
Commit 4: feat(predictive): implement predictive market engine and conditional probability scoring
Commit 5: feat(optimizer): implement MFE/MAE empirical parameter optimizer with walk-forward validation
Commit 6: test(e2e): add end-to-end multi-year backtesting tests with predictive signals and SHORT execution
Commit 7: docs(release): update project context, architecture diagrams, walkthrough, and tag v1.9
```

### Detalle de cada Commit:

- **Commit 1 (`perf`): Profiling y Optimización de Volume Profile**
  - Crear script de profiling `scripts/diagnostics/profile_volume_profile.py`.
  - Medir tiempo base en series de 10,000+ velas.
  - Implementar aceleración con `np.histogram` vectorizado sin modificar la interfaz pública de `VolumeProfile`.
  - Validar que los resultados de POC, VAH y VAL sigan siendo idénticos a los tests de Fase 1.

- **Commit 2 (`feat`): Soporte SHORT y Modelado de Futuros Perpetuos**
  - Modificar `src/backtest_models.py` para admitir `PositionSide.SHORT`, `market_type` y `funding_rate_8h`.
  - Actualizar `src/backtest_engine.py` para gestionar entradas en corto, trailing/stops para cortos, y deducción periódica de tasas de financiamiento.
  - Tests unitarios completos de ejecución SHORT, incluyendo resolución pesimista intra-barra.

- **Commit 3 (`feat`): Clasificador de Regímenes de Mercado**
  - Crear `src/regime_classifier.py` con métricas de fuerza de tendencia, volatilidad y detección de rango.
  - Definir dataclasses `MarketRegimeReport` y `MarketRegime`.
  - Suite de tests unitarios verificando clasificación correcta en mercados alcistas, bajistas y laterales.

- **Commit 4 (`feat`): Predictive Market Engine y Probabilidades Condicionales**
  - Crear `src/predictive_engine.py` para calcular probabilidades de continuación y reversión.
  - Integrar el cálculo con `QuantScore` existente generando `PredictiveScore` unificado.
  - Tests unitarios que certifiquen aislamiento causal y ausencia de look-ahead bias.

- **Commit 5 (`feat`): Optimizador Paramétrico MFE / MAE**
  - Crear `src/parameter_optimizer.py` que reciba un `BacktestReport` y extraiga la distribución estadística de MFE y MAE.
  - Calcular los niveles de TP/SL que optimizan la expectativa matemática.
  - Pruebas unitarias de optimización y validación cruzada temporal.

- **Commit 6 (`test`): Pruebas de Integración Extremo a Extremo**
  - Crear `tests/integration/test_predictive_pipeline.py`.
  - Ejecución de pipeline completo multiaño combinando señales LONG/SHORT, regímenes de mercado y parámetros optimizados.

- **Commit 7 (`docs`): Cierre y Etiquetado**
  - Actualizar documentación de sistema, diagramas de arquitectura, métricas de cobertura y crear tag `v1.9-predictive-optimization`.

---

## 6. Plan de Verificación y Criterios de Aceptación

### 6.1 Automated Tests

#### 1. Unit Tests por Módulo
- **`pytest tests/unit/test_volume_profile.py`**:
  - Validar compatibilidad estricta con el cálculo histórico existente.
  - Comparar numéricamente los resultados de POC, VAH y VAL antes y después de las optimizaciones vectorizadas.
  - Garantizar que no cambie la lógica cuantitativa.
- **`pytest tests/unit/test_backtest_engine.py`**:
  - **SHORT**: Apertura correcta de posiciones cortas, cierre por TP, cierre por SL, cálculo exacto de PnL positivo y negativo, y resolución conservadora intra-barra ($High \ge SL$ prioritario).
  - **Funding Fees**: Deducción correcta de tasas de financiamiento por intervalo temporal (cada 8h), impacto reflejado en curvas de capital y métricas, y compatibilidad con comisiones taker/maker existentes.
- **`pytest tests/unit/test_regime_classifier.py`**:
  - Clasificación 100% determinista y causal (cero información futura).
  - Transición y distinción correcta entre regímenes (`trending`, `ranging`, `high volatility`, `low volatility`).
- **`pytest tests/unit/test_predictive_engine.py`**:
  - Probabilidades condicionales reproducibles y acotadas $[0, 1]$.
  - Verificación formal de ausencia de *look-ahead bias* (uso exclusivo de datos $t \le T$).
  - Separación estricta entre señal técnica descriptiva y proyección predictiva.
- **`pytest tests/unit/test_parameter_optimizer.py`**:
  - Optimización determinista y reproducible a partir de `BacktestReport`.
  - Prevención de sobreajuste mediante validaciones temporales (*Walk-Forward*).
  - Parámetros generados estrictamente dentro de los rangos válidos permitidos.

#### 2. Integration Tests
- **`pytest tests/integration/test_predictive_pipeline.py`**:
  - **Pipeline completo evaluado**:
    ```text
    Historical Data
          ↓
    ParquetStore
          ↓
    HistoricalDatasetManager
          ↓
    RegimeClassifier
          ↓
    PredictiveEngine
          ↓
    Strategy Parameters (MFE/MAE Optimized)
          ↓
    BacktestRunner
          ↓
    BacktestReport
    ```
  - **Validaciones obligatorias**:
    - ✅ Ejecución autónoma de extremo a extremo sin intervención manual.
    - ✅ Resultados 100% deterministas en ejecuciones consecutivas.
    - ✅ Compatibilidad total con la arquitectura v1.8.
    - ✅ Reportes completamente serializables a JSON / diccionarios.

#### 3. Regression Tests y Cobertura
- **Comando:** `pytest --cov=src --cov-report=term-missing`
- **Criterios de Cobertura:**
  - Cobertura global del repositorio $\ge 90\%$.
  - Ningún módulo crítico por debajo del $95\%$.
  - Cobertura del $100\%$ en el núcleo de backtesting y nuevos motores:
    - `src/backtest_models.py` (100%)
    - `src/backtest_metrics.py` (100%)
    - `src/backtest_engine.py` (100%)
    - `src/backtest_runner.py` (100%)
    - `src/regime_classifier.py` (100%)
    - `src/predictive_engine.py` (100%)
    - `src/parameter_optimizer.py` (100%)

#### 4. Data Integrity & Bias Checks
- **Walk-Forward Validation**: Particionado temporal estricto (ej. Train *In-Sample* 2023-2024, Validación *Out-of-Sample* 2025) evitando fuga de datos futuros en la optimización.
- **Reproducibilidad Numérica**: Dos ejecuciones idénticas sobre el mismo dataset deben generar exactamente los mismos parámetros, probabilidades y `BacktestReport`.
- **Comprobación de Sesgos**: Confirmar ausencia total de:
  - *Look-ahead bias* (anticipación de precios).
  - *Survivorship bias* (sesgo de supervivencia).
  - *Parameter leakage* (filtración de parámetros en testing).

#### 5. Linter y Formato
- **Comando:** `ruff check src tests scripts`
- **Resultado requerido:** 0 errores y 0 advertencias.

---

## 7. Criterio Final de Aceptación de la Fase 4

1. ✅ Suite completa de tests pasando al 100% en modo offline.
2. ✅ Motor de backtesting v1.8 intacto y retrocompatible.
3. ✅ Nuevos módulos probabilísticos y de optimización formalmente implementados y documentados.
4. ✅ Resultados deterministas y reproducibles.
5. ✅ Cero degradación en la cobertura global de código ($\ge 90\%$).

