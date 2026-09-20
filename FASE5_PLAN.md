# FASE 5: Notification System, Live Streaming & Dashboard Visualizer
## Documento Técnico de Planificación y Propuesta Arquitectónica

**Versión:** 1.0  
**Fecha:** Septiembre 2026  
**Estado:** Propuesta Técnica para Validación  
**Base:** v1.9 Predictive Market Engine (`e8e0a0e`, Tag `v1.9-predictive-market-engine`)  

---

## 1. Contexto y Objetivos Técnicos

Tras la culminación exitosa de las fases previas:
- **Fase 1 (Quantitative Core & Descriptive Engine)**: Indicadores técnicos, Volume Profile, Quant Score.
- **Fase 2 (Historical Data Engine)**: Almacenamiento columnar Parquet multiaño y gestión de datasets.
- **Fase 3 (Robust Backtesting Framework)**: Motor cronológico event-driven $T+1$, modelado de comisiones y métricas institucionales (Win Rate, Profit Factor, Expectancy, Max Drawdown, MFE/MAE, Sharpe, Calmar).
- **Fase 4 (Predictive Market Engine & Strategy Optimization)**: Clasificación causal de regímenes de mercado (`RegimeClassifier`), estimación probabilística condicional (`PredictiveEngine`), optimización empírica MFE/MAE con validación Walk-Forward (`StrategyOptimizer`), soporte bidireccional LONG/SHORT y contratos perpetuos con tasas de financiamiento.
- **Base de Calidad:** 204 tests automatizados pasando al 100%, 92% de cobertura global (100% en el framework de backtesting y optimización) y 0 advertencias de linter.

El propósito central de la **Fase 5** es **cerrar el ciclo operativo entre el análisis cuantitativo/predictivo y el usuario final en tiempo real**, dotando al sistema de capacidades de operación continua, distribución de alertas institucionales y visualización analítica avanzada:

1. **Sistema de Notificaciones Multicanal Institucional (Discord / Telegram / Webhook)**:
   - Despacho desacoplado y estructurado de alertas y señales operativas.
   - Formateo enriquecido (Discord Rich Embeds y Telegram Markdown/HTML): Símbolo, precio actual, `QuantScore`, `PredictiveScore`, régimen de mercado (`TRENDING_BULL`, etc.), probabilidades $P(\text{cont})$ y $P(\text{rev})$, decisión (`BUY_LONG`, `SELL_SHORT`, `WAIT`), niveles de invalidación (SL) y objetivos (TP), ratio R:R.
   - Mecanismo anti-spam y deduplicación con cooldown configurable por símbolo y temporalidad (evitar inundación de alertas idénticas en la misma barra).
   - Gestión segura de credenciales (`DISCORD_WEBHOOK_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) mediante variables de entorno (`.env`), sin credenciales hardcodeadas.
   - Modo simulación (*Dry-run / Mock mode*) para pruebas 100% offline y deterministas.

2. **Ingesta de Mercado en Tiempo Real (Live Streaming & Candle Aggregator)**:
   - Cliente de streaming WebSocket de baja latencia (`BinanceWebSocketClient`) con reconexión automática y retroceso exponencial (*exponential backoff*).
   - Agregador de velas en tiempo real (`LiveCandleAggregator`): procesamiento de kline events, actualización del estado intra-barra y detección determinista del cierre de vela ($T$).
   - Alimentación en caliente y causal de la cadena de análisis: `MarketAnalyzer` $\rightarrow$ `RegimeClassifier` $\rightarrow$ `PredictiveEngine` $\rightarrow$ `DecisionEngine` $\rightarrow$ `NotificationDispatcher`.
   - **Principio cardinal:** Preservación estricta de causalidad: las señales de alta convicción se evalúan al cierre definitivo de la vela $T$; el seguimiento intra-barra se utiliza exclusivamente para alertas de monitorización y gestión de riesgo en tiempo real.

3. **Dashboard Visualizador Interactivo Avanzado (Streamlit UI)**:
   - Modernización de la interfaz en `src/app.py` estructurada en pestañas modulares:
     - **Pestaña 1: Live Market Monitor**: Semáforo visual del régimen actual, probabilidades de continuación/reversión, gráfico interactivo Plotly (velas, EMAs, Volume Profile POC/VAH/VAL), historial de alertas recientes y estado de conexión WebSocket.
     - **Pestaña 2: Backtest & Strategy Analytics**: Visualizador interactivo de reportes de backtest (`BacktestReport`), curvas de equity con drawdown subyacente, distribución scatter de MFE/MAE, tabla detallada de operaciones (`TradeResult`) y métricas institucionales.
     - **Pestaña 3: Alert & Notification Settings**: Configuración dinámica de canales (Discord, Telegram, Webhook genérico), test interactivo de conexión (envío de alerta de prueba), sliders de cooldown y umbrales mínimos de convicción (`PredictiveScore`).

4. **Garantías de No Regresión y Calidad**:
   - Mantener intactos los 204 tests existentes.
   - Pruebas unitarias completas con aislamiento total de red (0 llamadas HTTP/WebSocket reales en `pytest`).
   - Cobertura de código global $\ge 90\%$ y $100\%$ en módulos críticos nuevos de despacho y agregación.
   - Código validado por Ruff (0 errores y 0 advertencias).

---

## 2. Arquitectura Propuesta

### 2.1 Diagrama de Flujo Integral de Fase 5

```text
               LIVE MARKET FEED (Binance WebSocket / Mock Stream)
                                     │
                                     ▼
                          BinanceWebSocketClient
                   (Auto-reconnect, Heartbeat, Backoff)
                                     │
                                     ▼
                           LiveCandleAggregator
                     (Tick/Kline Buffer -> Closed Bar T)
                                     │
                                     ▼
                            LiveExecutionEngine
                                     │
        ┌────────────────────────────┴────────────────────────────┐
        ▼                                                         ▼
  Descriptive Layer                                       Predictive Layer
  - MarketAnalyzer                                        - RegimeClassifier
  - TechnicalIndicators                                   - PredictiveEngine
  - VolumeProfile                                         - StrategyOptimizer
        │                                                         │
        └────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
                            Enhanced DecisionEngine
                           (SignalEvent LONG/SHORT)
                                     │
                                     ▼
                           NotificationDispatcher
                   (Cooldown Manager, Anti-Spam Cache)
                                     │
                 ┌───────────────────┼───────────────────┐
                 ▼                   ▼                   ▼
           DiscordChannel     TelegramChannel      WebhookChannel
          (Rich Embed JSON)   (HTML / Markdown)   (Raw Payload)
                 │                   │                   │
                 └───────────────────┼───────────────────┘
                                     │
                                     ▼
                           Streamlit Dashboard
            (Live Monitor | Backtest Visualizer | Alert Manager)
```

---

### 2.2 Especificación de Módulos Nuevos y Modificados

#### 1. Módulo: `src/notifications/models.py` (NUEVO)
- **Responsabilidad:** Definir contratos de datos inmutables y tipados para el sistema de alertas.
- **Entidades:**
  - `NotificationChannelType`: Enum (`DISCORD`, `TELEGRAM`, `WEBHOOK`, `LOG`).
  - `NotificationPriority`: Enum (`LOW`, `NORMAL`, `HIGH`, `CRITICAL`).
  - `NotificationPayload`: Dataclass con:
    - `timestamp`: datetime UTC.
    - `symbol`: str (ej. `"BTCUSDT"`).
    - `timeframe`: str (ej. `"1h"`).
    - `action`: ActionType (`LONG`, `SHORT`, `WAIT`).
    - `price`: float.
    - `quant_score`: float.
    - `predictive_score`: float.
    - `regime`: str.
    - `p_continuation`: float.
    - `p_reversal`: float.
    - `stop_loss`: Optional[float].
    - `take_profit`: Optional[float].
    - `risk_reward_ratio`: Optional[float].
    - `summary`: str.
    - `metadata`: dict.
  - `NotificationResult`: Dataclass con `success: bool`, `channel: NotificationChannelType`, `status_code: Optional[int]`, `error_message: Optional[str]`, `delivered_at: Optional[datetime]`.

#### 2. Módulo: `src/notifications/channels/` (NUEVO)
- **`src/notifications/channels/base.py`**:
  - Interfaz abstracta `BaseNotificationChannel(ABC)`:
    - `send(payload: NotificationPayload) -> NotificationResult`
    - `format_message(payload: NotificationPayload) -> dict | str`
- **`src/notifications/channels/discord.py`**:
  - Implementación para Discord Webhooks usando formato Rich Embeds con colores dinámicos (Verde para LONG, Rojo para SHORT, Azul para neutral/alerta).
  - Campos estructurados con métricas clave y formato monetario.
- **`src/notifications/channels/telegram.py`**:
  - Implementación para Telegram Bot API (`send_message` con formato HTML o MarkdownV2).
  - Emojis contextuales (🟢, 🔴, ⚠️, 📊) y enlaces directos.
- **`src/notifications/channels/webhook.py`**:
  - Canal genérico HTTP POST enviando JSON estándar para integraciones externas.

#### 3. Módulo: `src/notifications/dispatcher.py` (NUEVO)
- **Responsabilidad:** Orquestar el envío a múltiples canales de forma síncrona o asíncrona, gestionando:
  - **Cooldown & Anti-Spam Manager**: Registro temporal en memoria de última alerta emitida por tupla `(symbol, timeframe, action)`. Si no ha transcurrido el tiempo mínimo de cooldown (ej. 300 segundos o 1 vela), la alerta es descartada silenciosamente.
  - **Priorización & Filtros**: Despachar solo alertas que superen un umbral mínimo de convicción (`PredictiveScore` $\ge 0.65$ o señales accionables de `DecisionEngine`).
  - **Fallback & Tolerancia a Fallos**: Si un canal falla, no interrumpe el despacho hacia los demás canales y registra el error formalmente en `NotificationResult`.
  - **Modo Dry-Run / Mock**: Activación mediante configuración para simular envíos sin I/O de red.

#### 4. Módulo: `src/streaming/websocket_client.py` (NUEVO)
- **Responsabilidad:** Manejo resiliente de streams WebSocket para datos de mercado.
- **Funcionalidades:**
  - Conexión al stream de klines de Binance (`<symbol>@kline_<interval>`).
  - Ciclo de vida con reconexión automática (*reconnect loop*) ante desconexiones o errores de red con retroceso exponencial (*exponential backoff* con jitter).
  - Manejo de hilos en segundo plano (`threading.Thread`) o bucle `asyncio` desacoplado.
  - Despacho de eventos vía callbacks registrados.

#### 5. Módulo: `src/streaming/candle_aggregator.py` (NUEVO)
- **Responsabilidad:** Mantener el estado de la serie temporal en memoria y detectar el cierre de velas.
- **Funcionalidades:**
  - Mantener un DataFrame rodante (`rolling buffer`) con el historial necesario para el calentamiento (*warm-up*) de indicadores (mínimo 200-250 velas).
  - Procesar eventos de tick/kline en tiempo real actualizando la vela en curso ($T$).
  - Detectar el evento de cierre de vela (`is_closed == True`) para desencadenar la evaluación formal del pipeline cuantitativo y predictivo.

#### 6. Módulo: `src/streaming/live_engine.py` (NUEVO)
- **Responsabilidad:** Orquestador de tiempo real que une el stream de velas con los motores cuantitativos y de notificación.
- **Flujo:**
  1. Recibe vela cerrada $T$ desde `CandleAggregator`.
  2. Ejecuta `TechnicalIndicators` y `VolumeProfile`.
  3. Ejecuta `RegimeClassifier` obteniendo el régimen causal.
  4. Ejecuta `PredictiveEngine` calculando $P(\text{continuation})$, $P(\text{reversal})$ y `predictive_score`.
  5. Ejecuta `DecisionEngine` obteniendo `DecisionResult` (`BUY_LONG`, `SELL_SHORT`, `WAIT`).
  6. Si la decisión es de alta convicción o se genera un cambio de régimen, construye `NotificationPayload` y llama a `NotificationDispatcher.dispatch()`.

#### 7. Modernización de `src/app.py` (Dashboard Streamlit)
- Reestructuración de la interfaz en tres pestañas principales (`st.tabs`):
  1. **📡 Monitor en Vivo (Live Monitor)**:
     - Gráfico interactivo de velas y Volume Profile (Plotly) actualizado.
     - Tarjetas métricas con régimen de mercado actual, confianza, $P(\text{cont})$ y $P(\text{rev})$.
     - Registro de alertas emitidas en tiempo real.
  2. **📈 Backtesting & Optimización (Backtest Visualizer)**:
     - Carga de reportes históricos desde `ParquetStore` o simulación bajo demanda.
     - Curva de equity interactiva con visualización de drawdowns bajo el agua (*underwater plot*).
     - Gráficos de distribución MFE vs MAE para diagnóstico de operaciones ganadoras y perdedoras.
     - Tabla detallada de transacciones con filtrado por tipo (`LONG` vs `SHORT`).
  3. **⚙️ Configuración y Notificaciones (Settings)**:
     - Activación/desactivación de canales (Discord / Telegram / Webhooks).
     - Botón de envío de alerta de prueba (Test Ping).
     - Sliders interactivos para umbral mínimo de `predictive_score` y minutos de cooldown.

---

## 3. Dependencias y Compatibilidad

### 3.1 Evaluación de Dependencias
Todas las librerías necesarias ya se encuentran instaladas en el entorno virtual (`requirements.txt`):
- `requests==2.34.2` / `httpx==0.28.1` / `aiohttp==3.14.3`: Clientes HTTP para despacho de webhooks y APIs.
- `websockets==16.1.1`: Cliente nativo de WebSocket de alto rendimiento.
- `python-dotenv==1.2.3`: Carga limpia de variables de entorno para tokens y URLs.
- `streamlit==1.64.0`: Framework de dashboard interactivo.
- `plotly==7.1.0`: Renderizado interactivo de gráficos financieros y de rendimiento.
- **No se requieren nuevas dependencias externas en el entorno.**

### 3.2 Contrato de Compatibilidad
- **Retrocompatibilidad Absoluta:** Las interfaces de `MarketAnalyzer`, `RegimeClassifier`, `PredictiveEngine`, `DecisionEngine` y `BacktestRunner` no sufrirán alteraciones disruptivas.
- **Desacoplamiento Estricto:** La capa de notificaciones y streaming se construye de forma puramente compositiva: si el streaming o las notificaciones están desactivados, el sistema opera idénticamente a las fases previas.
- **Aislamiento Total de Pruebas:** Todos los tests de canales de notificación y streaming utilizarán mocks (`unittest.mock`), garantizando que la suite se ejecute de forma 100% determinista y offline sin conexión a internet.

---

## 4. Análisis de Riesgos y Mitigaciones

| Riesgo Técnico | Impacto | Mitigación Arquitectónica |
| :--- | :--- | :--- |
| **Spam / Saturación de Webhooks (Rate Limits)** | Alto: Discord o Telegram bloquean temporalmente el bot por exceso de peticiones (código HTTP 429). | Implementación de `CooldownManager` con ventana deslizante por `(symbol, timeframe)`. Límite máximo de 1 notificación por vela cerrada salvo alertas de emergencia (SL hit). |
| **Pérdida de Conexión WebSocket en Vivo** | Medio-Alto: El cliente pierde sincronización de velas durante caídas temporales de red. | Patrón `ReconnectingWebSocket` con retroceso exponencial, latidos *ping/pong* y mecanismo de *catch-up* (consulta REST a través de `BinanceDataLoader` para rellenar velas faltantes al reconectar). |
| **Bloqueo por I/O de Red (Latencia en Streaming)** | Alto: Una petición HTTP lenta a Discord congela el bucle de procesamiento de velas. | Despacho desacoplado en hilos de trabajo en segundo plano (`ThreadPoolExecutor` o colas no bloqueantes), aislando el motor de análisis de la latencia de red. |
| **Filtración Accidental de Credenciales / Tokens** | Crítico: Exposición de claves de Telegram o URLs de Webhook en commits o logs. | Carga estricta mediante `os.getenv()` / `python-dotenv`. Archivo `.env.example` sanitizado. Tests automatizados que validan que no existan tokens reales en repositorios o reportes. |
| **Look-Ahead Bias en Alertas de Tiempo Real** | Crítico: Enviar alertas basadas en velas incompletas que cambian su cierre. | Distinción formal: Señales de estrategia (`BUY_LONG`/`SELL_SHORT`) se generan únicamente al recibir el evento de cierre definitivo de la vela $T$. |

---

## 5. Plan de Implementación Commit por Commit

Para mantener la cadencia iterativa, verificable y con aprobación paso a paso:

```text
Commit 1: feat(notifications): implement notification data contracts, formatters, and channel abstractions
Commit 2: feat(notifications): implement Discord webhook and Telegram bot dispatchers with retry logic
Commit 3: feat(notifications): implement notification dispatcher with anti-spam, rate limiting, and cooldown manager
Commit 4: feat(streaming): implement resilient WebSocket client and live candle aggregator
Commit 5: feat(streaming): implement real-time live execution engine linking stream, predictive decision, and alerts
Commit 6: feat(dashboard): enhance Streamlit UI with multi-tab interface for live monitoring and backtest analytics
Commit 7: test(integration): create end-to-end live streaming and alert dispatch pipeline integration tests
Commit 8: docs(fase5): update documentation, user guides, architecture diagrams, and release tag v2.0
```

### Detalle de cada Commit:

- **Commit 1 (`feat`): Contratos de Datos, Formateadores y Abstracciones de Canal**
  - Crear `src/notifications/models.py` (`NotificationPayload`, `NotificationResult`, `NotificationChannelType`).
  - Crear `src/notifications/channels/base.py` con interfaz abstracta y formateadores base.
  - Tests unitarios de validación de modelos y formateo de mensajes.

- **Commit 2 (`feat`): Despachadores de Discord y Telegram con Lógica de Reintentos**
  - Crear `src/notifications/channels/discord.py` (Discord Rich Embeds con colores por acción).
  - Crear `src/notifications/channels/telegram.py` (Telegram Bot API con formato HTML y emojis).
  - Crear `src/notifications/channels/webhook.py` (HTTP POST estándar).
  - Tests unitarios con mocks completos de HTTP (`status_code`, timeout, retry).

- **Commit 3 (`feat`): Despachador Central con Cooldown y Anti-Spam**
  - Crear `src/notifications/dispatcher.py` (`NotificationDispatcher`).
  - Implementar `CooldownManager` en memoria para filtrado por símbolo/temporalidad/acción.
  - Integrar filtro por umbral de `predictive_score` y ejecución asíncrona en hilo desacoplado.
  - Tests unitarios de anti-spam, cooldown y despacho tolerante a fallos.

- **Commit 4 (`feat`): Cliente WebSocket Resiliente y Agregador de Velas**
  - Crear `src/streaming/websocket_client.py` con reconexión automática y retroceso exponencial.
  - Crear `src/streaming/candle_aggregator.py` con buffer rodante de velas y detección de vela cerrada.
  - Tests unitarios simulando flujo continuo de ticks y eventos de cierre.

- **Commit 5 (`feat`): Motor de Ejecución en Vivo**
  - Crear `src/streaming/live_engine.py` uniendo `CandleAggregator` $\rightarrow$ `MarketAnalyzer` $\rightarrow$ `RegimeClassifier` $\rightarrow$ `PredictiveEngine` $\rightarrow$ `DecisionEngine` $\rightarrow$ `NotificationDispatcher`.
  - Pruebas unitarias de flujo completo paso a paso en modo offline.

- **Commit 6 (`feat`): Visualizador y Dashboard Interactivo Streamlit**
  - Actualizar `src/app.py` implementando pestañas modulares (`Monitor en Vivo`, `Backtest Analytics`, `Configuración`).
  - Integrar gráficos Plotly interactivos para curvas de equity, drawdowns y distribución MFE/MAE.
  - Formulario de configuración de credenciales y prueba interactiva de envío de alertas.

- **Commit 7 (`test`): Pruebas de Integración Extremo a Extremo**
  - Crear `tests/integration/test_live_notification_pipeline.py`.
  - Validación del flujo E2E simulado: Stream de mercado sintético $\rightarrow$ Detección de vela $\rightarrow$ Decisión cuantitativa $\rightarrow$ Despacho exitoso verificado en mock de notificación.
  - Validación de cero look-ahead bias e integridad de métricas.

- **Commit 8 (`docs`): Cierre de Fase 5 y Etiquetado de Release v2.0**
  - Actualizar `GEMINI_PROJECT_CONTEXT.md`, `GEMINI_DEVELOPMENT_PLAN.md`, `CODEX_CONTEXT.md`, `README.md` y `walkthrough.md`.
  - Crear tag de lanzamiento `v2.0-live-notifications-dashboard`.

---

## 6. Plan de Verificación y Criterios de Aceptación

### 6.1 Automated Tests

#### 1. Unit Tests por Módulo
- **`pytest tests/unit/test_notification_models.py`**:
  - Creación correcta de payloads inmutables.
  - Serialización a diccionario y JSON.
- **`pytest tests/unit/test_notification_channels.py`**:
  - Formato de payloads para Discord (Embeds, campos, colores según `LONG`/`SHORT`).
  - Formato de mensajes para Telegram (HTML tags válidos, longitud de caracteres).
  - Manejo de reintentos ante códigos 429 (Rate Limit) y 500 (Server Error) usando mocks.
- **`pytest tests/unit/test_notification_dispatcher.py`**:
  - Cooldown efectivo: Bloqueo de alertas consecutivas para el mismo par/temporalidad dentro de la ventana de enfriamiento.
  - Filtrado por umbral de confianza (`predictive_score`).
  - Despacho tolerante a fallos: Si Discord falla, Telegram sigue entregando con éxito.
- **`pytest tests/unit/test_candle_aggregator.py`**:
  - Acumulación de ticks en la vela abierta.
  - Emisión del evento de vela cerrada en el timestamp exacto.
  - Mantenimiento del tamaño máximo del buffer rodante (rolling window memory safety).
- **`pytest tests/unit/test_live_engine.py`**:
  - Ejecución causal paso a paso del pipeline de análisis y emisión de señales.
  - Ausencia total de anticipación de datos en tiempo real.

#### 2. Integration Tests
- **`pytest tests/integration/test_live_notification_pipeline.py`**:
  - Ingestión de secuencia de velas históricas simulando stream en vivo.
  - Detección de señales de alta convicción (`DecisionEngine`).
  - Despacho verificado a través de mocks de Discord y Telegram.
  - Comprobación de que no se produzcan excepciones ni pérdidas de memoria.

#### 3. Criterios de Cobertura y Linter
- **Comando de Cobertura:** `pytest --cov=src --cov-report=term-missing`
  - Cobertura global del repositorio $\ge 90\%$.
  - Cobertura del $100\%$ en módulos críticos nuevos (`src/notifications/`, `src/streaming/`).
- **Comando de Linter:** `ruff check src tests scripts`
  - 0 errores y 0 advertencias.

---

## 7. Criterio Final de Aceptación de la Fase 5 (Definition of Done)

1. ✅ Suite completa de tests automatizados pasando al 100% en modo offline ($\ge 230$ tests estimados).
2. ✅ Sistema de notificaciones multicanal (Discord, Telegram, Webhook) desacoplado, con cooldown y anti-spam operativo.
3. ✅ Cliente de streaming en vivo y agregador de velas con reconexión automática y cero look-ahead bias.
4. ✅ Dashboard de Streamlit actualizado con visualización en tiempo real y análisis interactivo de backtesting.
5. ✅ Cero almacenamiento o exposición de credenciales privadas.
6. ✅ Cobertura global $\ge 90\%$ y linter limpio (0 errores).
