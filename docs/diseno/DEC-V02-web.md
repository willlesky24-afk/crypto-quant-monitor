# DEC-V02 — Dirección visual de la interfaz web

Elegida por el supervisor el 2026-11-14: "Claro, estilo AURA" (su referencia `stitch_premium_financial_metrics_dashboard`). Sustituye a DEC-V01 para la interfaz web; DEC-V01 sigue vigente para Streamlit mientras exista.

## Ficha

- **Audiencia:** trader minorista serio, en PC y en teléfono.
- **Emoción objetivo:** preciso, sereno, de instrumento caro.
- **Idea visual grande:** un instrumento de medición del mercado. Cada panel es un medidor con su cifra, su escala y su fuente, como un tablero de precisión.
- **Lenguaje:** Suizo / retícula técnica en claro, con la densidad del Oscuro de precisión pero en luz (paneles de datos).
- **Referencias reales (principios):** la referencia AURA del supervisor (retícula densa, paneles con encabezado de categoría, medidores, lista de avisos); instrumentos de laboratorio; fichas técnicas de relojería.
- **Anti-referencias:** (1) app de señales cripto oscura con neón; (2) SaaS morado con cuatro tarjetas iguales; (3) TradingView saturado de indicadores.
- **Prohibido:** cohetes, toros, flechas de "ganancia", la palabra "señal" como promesa y cualquier cifra de ejemplo de la referencia AURA (VIX, GEX, dark pool, probabilidades inventadas).

## Diferencias deliberadas con la referencia AURA

- Solo datos que el motor calcula de verdad; un dato ausente dice "N/D" y por qué.
- Paneles sí, pero no todo es panel: la cabecera de mercado y el texto van sin caja.
- Radios moderados (10 px en paneles, 6 px en controles), no píldoras en todo.
- Tipografía IBM Plex Sans + Plex Mono, no Inter.

## Tokens

| Token | Valor | Por qué |
|---|---|---|
| `--font-text` | IBM Plex Sans 400/500/600 | Técnica, con carácter, buena en español |
| `--font-mono` | IBM Plex Mono 400/500 | Cifras tabulares |
| Escala | 0.75 · 0.875 · 1 · 1.25 · 1.563 · 2.441 · 3.052 rem | Razón 1.25 |
| `--bg` | `#F6F8F9` | Perla de la referencia |
| `--panel` | `#FFFFFF` | Plano de los paneles |
| `--ink` | `#191D23` | Obsidiana; texto y acción principal |
| `--ink-soft` | `#5E636B` | Texto secundario; AA sobre ambos fondos |
| `--line` | `rgba(25, 29, 35, 0.08)` | Filete de panel |
| `--accent` | `#8A7A56` | Bronce champán: escalas, foco y dato clave |
| `--up` / `--down` | `#036340` / `#B04A4A` | Estados sobrios |
| Radio | 10 px paneles · 6 px controles | Moderado, no píldora |
| Sombra | ninguna; solo en menús flotantes | La profundidad sale del fondo y los filetes |
| Espaciado | 4 · 8 · 12 · 16 · 24 · 32 px | Sub-retícula de 4 px |

## Movimiento (máximo 3)

1. Panel: filete pasa a bronce al pasar el cursor, 150 ms.
2. Cifra nueva: breve resaltado de fondo al actualizarse, 400 ms.
3. Foco visible: contorno de 2 px en bronce.

Con `prefers-reduced-motion` no hay transiciones.

## Restricciones

Ninguna del entorno: la interfaz es propia. La herramienta de capturas reduce 1440 px a 800 px y no sostiene hover ni foco; eso se declara en el acta.

## Formato numérico

Las cifras usan punto decimal y coma de miles (`66,755.66`), igual que las plataformas de trading y que el motor en Python, para que un número copiado entre pantallas sea idéntico. Los negativos llevan el signo menos real (−). Precios: 2 decimales desde 100 y 5 por debajo, también en los ejes del gráfico. Fechas en el eje: día y mes abreviado en español.

## Atribución del gráfico

El logo de TradingView se quita del área de datos y la atribución va como enlace en el pie de la navegación ("Gráficos: TradingView Lightweight Charts").
