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

## Enmienda 1 (2026-11-15, aprobada por el dueño tras la auditoría de Fable 58/100)

Motivo: con "sombra: ninguna" y valores tan tímidos, la interfaz quedó en un solo plano ("luce muerta"). La idea de "instrumento" estaba escrita, pero no dibujada.

| Token | Antes | Ahora | Por qué |
|---|---|---|---|
| `--bg` | `#F6F8F9` (gris frío) | `#F3F2EE` (perla tibia) | Conversa con el bronce y separa el fondo de los paneles blancos |
| `--line` | tinta al 8 % | `rgba(60, 50, 30, 0.10)` | Filete tibio, más suave |
| `--accent-ink` | — | `#6F6140` | Bronce para texto pequeño (AA). `--accent` queda para trazos y rellenos |
| Radio | 10 / 6 px | 14 px paneles · 8 px controles · 4 px etiquetas | Líneas más suaves, sin llegar a píldora |
| Sombra | ninguna | **Solo paneles de datos:** `0 1px 2px` al 5 % + `0 8px 24px -12px` al 10 %, en tinta, más una luz interior superior de 1 px | Dos planos reales. Formularios y texto siguen planos. |
| Navegación activa | bloque negro | fondo de tinta al 6 %, barra bronce de 2 px y peso 600 | El precio manda, no el menú |
| Textura | — | grano estático al 2,5 % solo en el fondo | Textura, sin ensuciar |

**Motivo de firma: la escala graduada.** Todos los medidores (volatilidad, costo, zona de valor, riesgo) usan la misma escala: pista de 2 px, marcas menores cada 10 y mayores cada 50, y un índice triangular fino en lugar de una barra rellena. Es la única ornamentación del sistema.

**Gráfico:**
- Zona de valor dibujada como banda bronce al 9 % sobre el precio, con bordes de 1 px.
- Volumen en gris al pie.
- Leyenda de la vela (apertura, máximo, mínimo, cierre) en mono, arriba a la izquierda.
- Etiqueta del último precio en tinta, no en rojo.
- Sin indicadores añadidos.

**Movimiento (sube de 3 a 4):**
1. Panel de datos: la sombra crece al pasar el cursor, 200 ms.
2. Medidor: el índice se asienta al cargar, 450 ms con frenado suave.
3. Foco visible: contorno bronce de 2 px.
4. Marca de arranque: las marcas de una escala se trazan y el índice se asienta, en 800 ms como máximo, solo en el primer arranque de la sesión.

Nada se repite en bucle. Se retiran la moneda dorada, las barras de la intro y el punto que late. Con `prefers-reduced-motion` no hay animación.

**Marca:** el símbolo ₿ sale del logo, porque el producto cubre cuatro clases de activos. En su lugar va un índice sobre una escala, el mismo motivo de firma, en tinta y bronce.

**Carga:** esqueletos con la forma de cada dato, en tinta al 6 %, y una línea honesta, por ejemplo "Leyendo BTCUSDT · Binance". Si pasan más de 8 s, se dice qué ocurre y se ofrece reintentar.
