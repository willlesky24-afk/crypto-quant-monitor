# 📱 Guía Rápida de Uso — Crypto Quant Monitor

> **Concepto Clave**: Este sistema es tu **Copiloto Inteligente de Trading**.  
> El sistema analiza el mercado con matemáticas avanzadas, detecta el régimen y riesgos con IA (Gemini), pero **TÚ tienes siempre el control absoluto**: el sistema nunca ejecuta operaciones automáticas ni toca tus fondos.

---

## 🚀 1. Cómo abrirlo en tu Teléfono (Móvil)

**¡Sí! Puedes usarlo directamente desde tu teléfono.**  
La interfaz web es 100% responsiva y se adapta a la pantalla de tu móvil.

### Pasos para tu teléfono:
1. Conecta tu teléfono a la **misma red Wi-Fi** que este ordenador.
2. Abre el navegador de tu teléfono (Safari, Chrome, etc.).
3. Escribe en la barra de direcciones:
   ```text
   http://192.168.1.240:8501
   ```
4. ¡Listo! Verás el panel en tiempo real en tu teléfono.  
   *(Consejo: Puedes darle a "Añadir a la pantalla de inicio" en tu navegador para tenerlo como si fuera una App).*

---

## 💻 2. Cómo abrirlo en este Ordenador

Abre tu navegador (Chrome, Edge, etc.) y entra a:
```text
http://localhost:8501
```

---

## 🧭 3. Qué verás en la pantalla (Las 4 Pestañas)

### 📊 Pestaña 1: Monitor en Vivo
- **Gráfico de Velas con Volume Profile**: Verás el precio actual y tres líneas clave:
  - **POC (Línea Dorada)**: El precio donde más volumen e interés institucional ha habido.
  - **VAH (Línea Verde)**: Techo del área de valor.
  - **VAL (Línea Roja)**: Suelo del área de valor.
- **Semáforo y Puntuación**:
  - **Quant Score (0 a 100)**: Fortaleza técnica cuantitativa.
  - **Régimen**: Te dice si el mercado está en tendencia alcista (`TRENDING_BULL`), bajista (`TRENDING_BEAR`) o lateral (`CONSOLIDATION`).

### 🤖 Pestaña 2: Copiloto IA (Gemini)
- **Escribe tu pregunta**: Hay una caja de texto donde puedes preguntar lo que quieras en lenguaje normal:
  - *"¿Qué riesgos ves en BTC ahora mismo?"*
  - *"¿Es buen momento para entrar o mejor esperar?"*
  - *"Explícame el régimen actual."*
- Haz clic en **"🔎 Submit Query to Copilot"** y Gemini te contestará analizando las métricas matemáticas actuales.
- **Briefing Diario**: Resumen ejecutivo automático de la sesión.
- **Alertas de Anomalías**: Te avisa si hay picos de volatilidad extraños o trampas de mercado.

### 📈 Pestaña 3: Backtest
- Simulación histórica para comprobar cómo habrían funcionado las estrategias en el pasado.

### ⚙️ Pestaña 4: Notificaciones
- Configura alertas directas a tu **Telegram** o Discord para que te lleguen avisos al móvil cuando se detecte una oportunidad de alta confianza.

---

## ⚡ 4. Atajos rápidos desde la Terminal (Opcional)

Si prefieres usar la consola de tu ordenador en lugar del navegador:

- **Ver estado actual de Bitcoin**:
  ```powershell
  .\.venv\Scripts\python scripts/operator_cli.py status --symbol BTCUSDT
  ```
- **Hacerle una pregunta rápida al Copiloto**:
  ```powershell
  .\.venv\Scripts\python scripts/operator_cli.py ask "¿Cuál es la tendencia y soporte principal?" --symbol BTCUSDT
  ```
- **Generar un reporte completo**:
  ```powershell
  .\.venv\Scripts\python scripts/operator_cli.py report --symbol BTCUSDT
  ```

---

## 🛡️ 5. Tu flujo de trabajo diario recomendado

1. **Revisa el panel por la mañana** en tu teléfono o PC (`http://192.168.1.240:8501`).
2. **Mira el Régimen y el Quant Score**: Si el mercado está en rango o con score bajo, paciencia.
3. **Pregúntale al Copiloto**: Si ves una señal, pregúntale a Gemini qué niveles de Stop Loss y riesgos vigilar.
4. **Toma tu decisión**: Si estás de acuerdo con el análisis, ejecuta tu orden manualmente en tu exchange habitual.
