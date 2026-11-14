# DEC-V01 — Dirección visual de Quant Monitor

Aprobada por el supervisor el 2026-11-13. Cambiarla es una decisión suya.

## Ficha

- **Audiencia:** trader minorista serio de cripto, forex, metales e índices; desconfía del humo y de las apps de señales.
- **Emoción objetivo:** preciso, honesto, sereno.
- **Idea visual grande:** la ficha técnica del mercado — cada número con su fuente y su hora, como un informe de laboratorio.
- **Lenguaje:** Suizo / retícula técnica en claro, con el acento de datos del Industrial técnico (cifras en monoespaciada). Elegido porque la confianza del producto viene de la precisión y del orden, no del espectáculo.
- **Referencias reales (principios):** fichas técnicas de instrumentos de medición; informes de laboratorio con tablas y unidades; horarios y señalética de transporte suizos (jerarquía por tamaño y alineación).
- **Anti-referencias:** (1) app de señales cripto oscura con verde neón y cohetes; (2) panel SaaS con degradado morado y cuatro tarjetas iguales; (3) TradingView saturado de indicadores de colores.
- **Prohibido:** cohetes, toros, lunas, flechas de "ganancia", fuegos artificiales y la palabra "señal" como promesa.

## Restricciones del entorno (Streamlit)

No se controlan, y se auditan como "limitado por el entorno": la estructura de la barra lateral, los controles nativos (selectores, deslizadores, campos numéricos, pestañas), el menú superior de Streamlit y el tiempo de carga inicial. Los ajustes de CSS sobre esos controles se limitan a selectores estables (`data-testid`) y quedan comentados.

## Tokens

| Token | Valor | Por qué |
|---|---|---|
| `--font-text` | IBM Plex Sans 400/500/600 | Sans técnica con carácter, legible en datos y en español |
| `--font-mono` | IBM Plex Mono 400/500 | Firma las cifras; números tabulares que no bailan |
| Escala | 0.8 · 1 · 1.25 · 1.563 · 2.441 · 3.052 rem (razón 1.25) | Jerarquía real con pocos tamaños |
| `--bg` | `#F2F1EE` | Gris técnico cálido, papel de informe; no blanco de plantilla |
| `--surface` | `#FAF9F7` | Fondo de la ficha, apenas separado del fondo |
| `--ink` | `#1C1E21` | Grafito; contraste AA sobre ambos fondos |
| `--ink-soft` | `#5E6166` | Texto secundario; 5.9:1 sobre `--bg` |
| `--line` | `#D6D2CA` | Filetes de la retícula |
| `--accent` | `#86672E` | Bronce apagado; único acento: dato clave, foco, barra de medida |
| `--up` / `--down` | `#2F6B4F` / `#A23B3B` | Estados sobrios; solo en la cifra que los necesita |
| Radio | 2 px | Retícula suiza: esquinas casi rectas |
| Sombras | ninguna | La profundidad sale de filetes y de fondos |
| Espaciado | 4 · 8 · 12 · 16 · 24 · 40 px | Sub-retícula de 4 px |

## Movimiento (máximo 3)

1. Botón: fondo de tinta a grafito claro en 150 ms, `ease-out`.
2. Fila de la ficha: filete inferior pasa a acento al pasar el cursor, 150 ms.
3. Foco visible con contorno de 2 px en acento, sin animación.

Con `prefers-reduced-motion` no hay transiciones.

## Lo que este diseño deliberadamente NO hace

- No usa tarjetas con sombra ni esquinas redondeadas.
- No pinta de verde o rojo nada que no sea un estado.
- No muestra cifras de ejemplo ni rellena huecos: un dato ausente dice "N/D" y por qué.
- No anima la entrada de los bloques.

## Límites de la auditoría con capturas

La herramienta de capturas no puede mantener el cursor sobre un elemento ni el foco del teclado al fotografiar, y reduce la vista de 1440 px a 800 px de imagen. Por eso no hay capturas de hover ni de foco ni de 1440 a escala completa. Los estados de carga y error de Streamlit son nativos. El estado sin dato sí está en las capturas ("N/D" con su motivo). Los estados de hover y foco quedan definidos en los tokens (filete en acento y contorno de 2 px en acento).
