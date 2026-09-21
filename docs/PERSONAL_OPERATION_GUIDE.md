# Crypto Quant Monitor — Personal Operation & Gemini Live Guide

> **Important Institutional Philosophy**  
> Crypto Quant Monitor is **NOT an automated trading bot**. It is an **AI Quant Trading Copilot** designed to work alongside a human operator. The system calculates real-time quantitative metrics, regimes, and risk thresholds at closed candle $T$, and provides AI-driven market interpretation.  
> **The human operator retains 100% of execution authority and trade decision responsibilities.**

---

## 1. System Architecture Overview

```text
                     ┌──────────────────────────────────────────────┐
                     │           Live Binance Market Feeds          │
                     │       (WebSocket Kline Stream @ 1h/15m)      │
                     └──────────────────────┬───────────────────────┘
                                            │
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │              LiveMarketWorker                │
                     │  - Bootstraps 200 warm-up candles on startup │
                     │  - Ingests closed candle T via Aggregator    │
                     │  - Runs LiveExecutionEngine (Scores/Regimes)  │
                     │  - Passes SignalEvent to LiveAIContextBridge │
                     └──────────────────────┬───────────────────────┘
                                            │
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │     Persistent Storage (market_contexts.db)  │
                     │  - SQLite repository caching latest contexts │
                     │  - Zero data loss across service restarts    │
                     └──────────────┬───────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌──────────────────┐      ┌──────────────────┐       ┌──────────────────┐
│  Operator API    │      │    Streamlit     │       │   Operator CLI   │
│  Gateway (:8000) │      │ Dashboard (:8501)│       │  (Terminal REPL) │
│ - REST Endpoints │      │ - Real-time UI   │       │ - Quick Status   │
│ - API Key & Rate │      │ - Copilot Tab    │       │ - Ad-hoc Queries │
│ - Health/Metrics │      │ - Anomaly Alerts │       │ - Daily Briefing │
└──────────────────┘      └──────────────────┘       └──────────────────┘
```

---

## 2. Configuration Setup (`.env`)

All runtime options are managed via the root `.env` file. A verified template is located at `.env.example`.

### Key Environment Variables

```bash
# ------------------------------------------------------------------------------
# Runtime & Security
# ------------------------------------------------------------------------------
ENVIRONMENT=production
LOG_LEVEL=info
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# API Gateway Security (Protecting Operator Gateway)
OPERATOR_API_KEY=your_secret_operator_api_key_here
OPERATOR_API_SECURITY_ENABLED=true
OPERATOR_API_RATE_LIMIT_ENABLED=true
OPERATOR_API_RATE_LIMIT_PER_MINUTE=60
OPERATOR_API_CORS_ORIGINS=*

# ------------------------------------------------------------------------------
# Persistent SQLite Context Storage
# ------------------------------------------------------------------------------
DATA_DIR=/app/data
DATABASE_PATH=/app/data/market_contexts.db
PARQUET_DIR=/app/data/parquet

# ------------------------------------------------------------------------------
# Market Feeds & Timeframes
# ------------------------------------------------------------------------------
SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT
SYMBOL=BTCUSDT
TIMEFRAME=1h
STREAMING_BUFFER_SIZE=500

# ------------------------------------------------------------------------------
# Real AI Provider Configuration (Google Gemini)
# ------------------------------------------------------------------------------
AI_PROVIDER=gemini
GEMINI_API_KEY=your_google_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Resilience Settings
LLM_TIMEOUT_SECONDS=10.0
LLM_MAX_RETRIES=2

# Observability
METRICS_ENABLED=true
JSON_LOGGING_ENABLED=true

# Optional Notification Integrations
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
```

### Obtaining and Configuring Your Gemini API Key
1. Visit [Google AI Studio](https://aistudio.google.com/) and generate a Gemini API key.
2. In your `.env` file, paste your key:
   ```bash
   GEMINI_API_KEY=AIzaSy...
   ```
3. Set `GEMINI_MODEL=gemini-2.5-flash` for high-speed, cost-effective market reasoning.

> **Graceful Offline Fallback**  
> If `GEMINI_API_KEY` is not provided or Gemini is unreachable, the system automatically falls back to deterministic rule-based quantitative interpretation:  
> `"AI provider unavailable. Quantitative analysis remains active."`  
> Market monitoring and quantitative engines are completely decoupled from external LLM availability.

---

## 3. Production Deployment with Docker

The platform is designed to run via Docker Compose with three interconnected services sharing the persistent SQLite context volume.

### 3.1 Starting the Services
```bash
# Launch all services in detached mode
docker compose up -d

# Check running containers
docker compose ps
```

### 3.2 Inspecting Service Logs
```bash
# Live Market Worker logs (market feeds, warm-up, candle processing)
docker compose logs -f market-worker

# Operator API Gateway logs
docker compose logs -f operator-api

# Streamlit Dashboard logs
docker compose logs -f dashboard
```

### 3.3 Verifying Health
```bash
# Query the ready endpoint directly
curl http://localhost:8000/health/ready

# Or via container entrypoint
docker compose exec operator-api python scripts/entrypoint.py health
```

---

## 4. Local Native Operation (PowerShell / Bash)

You can also run components individually without Docker inside your local Python virtual environment.

### 4.1 Run Pre-Flight Validation
Before starting a trading session, execute the pre-flight validator to verify exchange connectivity and quantitative invariants:
```powershell
.\.venv\Scripts\python scripts/validate_live_deployment.py --symbol BTCUSDT --interval 1h --dry-run
```

### 4.2 Run the Live Market Worker
Starts the background daemon that streams live Binance data, updates technical indicators on closed candles, and saves context to SQLite:
```powershell
.\.venv\Scripts\python scripts/entrypoint.py worker --symbols BTCUSDT,ETHUSDT,SOLUSDT --interval 1h
```

### 4.3 Run the Operator API Gateway
```powershell
.\.venv\Scripts\python scripts/entrypoint.py api --port 8000
```

### 4.4 Run the Streamlit Dashboard
```powershell
.\.venv\Scripts\python scripts/entrypoint.py ui --port 8501
```

---

## 5. Web Dashboard Guide (`http://localhost:8501`)

Open your browser to `http://localhost:8501`.

### Tab 1: Live Market Monitor
- **Interactive Candlestick Chart**: Plotly chart with 50 EMA, 200 EMA, and Volume Profile (POC in gold, VAH in green, VAL in red).
- **Executive Diagnostic**: Current market state, textual rationale, positive confluence list, and active warning indicators.
- **Quantitative Parameters**: Direction, Action, Quant Score (0-100), Predictive Score (0-1), ATR-based TP/SL multipliers.

### Tab 2: Institutional AI Copilot
- **Provider Status Badge**: Displays active provider (e.g. `Gemini` or `Mock`) and model (`gemini-2.5-flash`), plus database connection path.
- **Interactive Query**: Ask ad-hoc questions (e.g. *"What is the probability of a breakout above POC?"*, *"Explain current regime"*). View response latency in milliseconds and token usage.
- **Daily Market Briefing**: Automatically synthesized briefing covering market overview, regime, volatility metrics, and key risks.
- **Passive Anomaly Alerts**: Real-time detection of volatility spikes, structural divergences, or regime transitions without spamming the operator.
- **Context Snapshot**: Live JSON representation of the latest closed candle context.

### Tab 3: Backtest Analytics
- Simulate chronological performance with custom initial capital, taker fees, slippage, and direction filters.
- Review Sharpe Ratio, Profit Factor, Win Rate, Max Drawdown, and MAE/MFE scatter plots.

### Tab 4: Multichannel Alerts & Settings
- Configure Discord Webhooks, Telegram Bot, or Generic Webhooks with custom predictive score thresholds and anti-spam cooldown sliders.

---

## 6. Operator CLI Guide (`scripts/operator_cli.py`)

The terminal CLI provides instant, keyboard-driven access to the Copilot.

### 6.1 Check Market Status
```powershell
.\.venv\Scripts\python scripts/operator_cli.py status --symbol BTCUSDT --interval 1h
```
**Sample Output:**
```text
========================================================
📊 MARKET STATUS: BTCUSDT [1H]
========================================================
Candle Time:      2026-09-21 03:00:00
Current Price:    $81,425.23
Market Regime:    TRENDING_BULL
Action / Dir:     🟡 Esperar confirmación (LONG)
Quant Score:      95.00
Predictive Score: 0.57
Stop Loss:        None
Take Profit:      None
Active Anomalies: 0
========================================================
```

### 6.2 Ask the AI Copilot
```powershell
.\.venv\Scripts\python scripts/operator_cli.py ask "What are the primary support levels and risks for BTC?" --symbol BTCUSDT
```

### 6.3 Generate an Institutional Daily Briefing
```powershell
.\.venv\Scripts\python scripts/operator_cli.py report --symbol BTCUSDT --interval 1h
```

### 6.4 Interactive Terminal REPL
Launch an ongoing terminal dialogue session:
```powershell
.\.venv\Scripts\python scripts/operator_cli.py repl
```
**Available REPL Commands:**
- `status`: Re-print latest status.
- `report`: Print detailed daily briefing.
- `ask <question>`: Send a query to the Copilot.
- `switch <symbol> <interval>`: Switch tracking target (e.g. `switch ETHUSDT 15m`).
- `quit` or `exit`: Exit the session.

---

## 7. Human Decision Support Workflow

As an AI Copilot, Crypto Quant Monitor empowers human operators to make disciplined, data-backed decisions:

```text
[Step 1: Ingestion & Closed Candle T]
  LiveMarketWorker validates bar close -> Evaluates indicators -> Computes QuantScore & PredictiveScore.
       │
[Step 2: Pre-Session Intelligence]
  Operator opens Dashboard Tab 2 or runs `operator_cli.py report`.
  Reviews macro regime, volatility levels, and detected anomalies.
       │
[Step 3: Signal Notification & Review]
  Notification triggers on Telegram/Discord when Predictive Score >= threshold.
  Operator inspects confluence checklist and Value Area levels (POC/VAH/VAL).
       │
[Step 4: Interrogation & Risk Boundary Analysis]
  Operator queries Copilot: "What are the failure conditions for this long signal?"
  Copilot highlights ATR stop-loss distance, nearest volume nodes, and warning flags.
       │
[Step 5: Operator Discretion & Manual Execution]
  Human trader evaluates broader market context (news, liquidity, portfolio heat).
  Human trader manually executes order on exchange or broker terminal.
```

---

## 8. Troubleshooting & FAQ

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `HTTP Error 451: Unavailable For Legal Reasons` | Direct Binance REST API blocked from your IP location. | Use a VPN or Binance.US configuration, or rely on local candle cache / dry-run mode. |
| `⚠️ Gemini API key is not configured` | Empty `GEMINI_API_KEY` in `.env`. | Provide a valid key in `.env` or continue operating under deterministic fallback mode. |
| `No persisted context found in data/market_contexts.db` | Live market worker has not run or has not processed a closed candle yet. | Start `live_worker.py` or execute `validate_live_deployment.py` to seed context. |
| `Unauthorized: Invalid or missing API key` | `OPERATOR_API_SECURITY_ENABLED=true` without passing `X-API-Key`. | Add header `X-API-Key: <your_key>` in client requests or set `OPERATOR_API_KEY` appropriately. |
