# Informe de evidencia v3.0

**Conclusión:** con los métodos y salidas evaluados, **no se demostró una ventaja estadística**
después de costos. Crypto Quant Monitor no se presenta como generador de señales rentables, sino
como herramienta de **lectura y análisis de mercado**.

## Protocolo fijado antes de ver resultados

- Datos: 8 pares cripto (Binance) y 9 de forex y metales (OANDA, con spread real), 1h y 4h,
  2021-11-01 a 2026-11-01.
- Períodos: entrenamiento hasta 2023, validación 2024, prueba 2025-01-01 a 2026-10-31.
- Criterios de éxito: PF ≥ 1.2; IC 95 % de la R neta media por encima de 0; ≥ 100 operaciones;
  drawdown Monte Carlo p95 ≤ 20 %; ≥ 60 % de instrumentos positivos.

## Resultados

### 1. Modelo combinado, validación 2024 (34 series): no pasa

| Criterio | Exigido | Obtenido |
|---|---|---|
| Operaciones | ≥ 100 | 12 496 |
| PF | ≥ 1.2 | 0.92 |
| IC 95 % de R neta media | > 0 | [−0.120, −0.073] |
| Drawdown Monte Carlo p95 | ≤ 20 % | 99.99 % (ver limitaciones) |
| Series con ganancia | ≥ 60 % | 17.6 % |

### 2. Filtrado de 11 entradas, entrenamiento, 4h: ninguna pasa

Mismo motor, costos y salida (SL 1 ATR, TP 2 ATR, 24 velas). Listón: IC 99.55 % sobre 0
(corrección de Bonferroni). La mejor R media fue −0.058 (tendencia EMA); el control al azar, −0.114.

### 3. Ronda de 12 combinaciones con 3 salidas, entrenamiento, 4h: ninguna pasa

Listón: IC 99.78 % sobre 0 (23 pruebas acumuladas). La mejor fue perfil de volumen + tendencia
larga: 677 operaciones, PF 1.25, R +0.158, IC [−0.089, +0.431], 65 % de series positivas. Es la
línea más interesante para investigar en el futuro, pero **no es evidencia de ventaja**: el
intervalo incluye el cero y es la mejor de 23 pruebas.

## Decisión

Se aplicó el corte acordado antes de la última ronda: si nada pasa, no se insiste. El período de
prueba **2025–2026 no se ejecutó** y queda intacto para evaluar en el futuro un método nuevo, una
sola vez.

## Limitaciones

- Cripto se evaluó solo en largo (spot), con el mercado bajista de 2022 dentro del entrenamiento.
- Forex y metales no incluyen swap ni financiamiento, lo que los favorece.
- El drawdown Monte Carlo encadena todas las operaciones como si fueran una sola secuencia con el
  100 % del capital; ese 99.99 % exagera el riesgo.
- Los filtrados usaron solo 4h. Los parámetros de las salidas son elecciones del proyecto, no
  valores de una publicación.
- Durante estas corridas el análisis redondeaba precio y ATR a 2 decimales, lo que falseaba reglas
  de riesgo y señal en forex. Se corrigió después. Al repetir forex y metales en 4h (validación
  2024), 8 de 9 series quedaron iguales y GBP/USD pasó de PF 0.857 a 0.854. Forex en 1h y los filtrados no
  se repitieron.
- El perfil de volumen también redondeaba POC, VAH y VAL a 2 decimales; se corrigió después. Con
  la ronda de salidas repetida, perfil + tendencia larga pasó de 65 % a 59 % de series positivas y
  de PF 1.25 a 1.25, y ninguna combinación pasó el listón. Forex y metales 4h en 2024 quedaron en
  PF 0.96. Las rondas 1 y 2 del informe no se repitieron con esta corrección.
- Exposición accidental, 2026-11-05: dos corridas del verificador leyeron datos de 2025 (BTC 4h
  tendencia con SL 2/TP 6 y 120 velas; SPX500 no pertenece al universo). Esa combinación ya no es
  una evaluación limpia del período de prueba. El verificador ahora corta en 2025-01-01.
- Un resultado negativo vale para estas reglas, no para cualquier estrategia posible.

## Reproducir

Los resultados se generan en `reports/evidence/`:

```bash
python scripts/download_evidence_dataset.py
python scripts/run_evidence.py validation
python scripts/run_screening.py
python scripts/run_screening_exits.py
```

No ejecutar `run_evidence.py test` salvo para un método nuevo fijado de antemano.
