# Auditoría visual — Ronda 1 — 2026-11-13

Auditor: subagente independiente (otra instancia de la IA, no una persona). Trabajó solo con las capturas de `capturas/` y la DEC-V01, sin ver el código.

- **Lista negra:** limpia, con una observación sobre el ítem 5 (los cuatro métodos de "Probar mi idea" en retícula 2×2 con botones iguales).
- **Puntajes:** Originalidad 15/20 · Tipografía 15/20 · Composición 12/20 · Color 12/15 · Imagen 11/15 · Detalle 6/10 = **71/100**.
- **Veredicto:** DEVUELTO (mínimo 80).

## Cambios pedidos

1. "Probar mi idea": lista de una columna en forma de ficha y un único botón de acción, en lugar de cuatro botones negros.
2. "Zona de valor": que el precio fuera del rango se lea como tal, no como una barra vacía.
3. Cada barra con escala explicada; quitar la de "Apalancamiento" si no tiene escala con sentido.
4. El resumen en prosa como bloque secundario, con encabezado propio.
5. En 390 px, la línea de procedencia en dos renglones deliberados.
6. Barra lateral: el estado del mercado sin caja.
7. Capturas de hover, foco, carga y error; 1440 px a escala completa.
8. Revisar el contraste de las notas pequeñas y del texto de ejemplo.

Limitado por el entorno, sin contar como falla: menú de Streamlit, barra lateral y sus controles, deslizador, campo de texto nativo y el blanco superior.

## Respuesta del diseño (ronda 2)

Se registra en la siguiente sección cuando se haga la ronda 2.

# Ronda 2

- **Lista negra:** limpia.
- **Puntajes:** Originalidad 16/20 · Tipografía 15/20 · Composición 14/20 · Color 12/15 · Imagen 12/15 · Detalle 5/10 = **74/100**.
- **Veredicto:** DEVUELTO (mínimo 80).
- **Estado de los cambios de la ronda 1:** resueltos 3 (escalas, apalancamiento, barra lateral); parciales 1, 2, 4, 5; no resueltos 7 y 8.

## Cambios pedidos para la ronda 3

1. Quitar la fila de radios duplicada: que la propia lista sea el selector.
2. Zona de valor: escala que incluya el precio, con el rango como tramo y el precio dentro de la columna.
3. "En palabras" con trato de etiqueta (tinta, 600) y filete grueso.
4. Procedencia en 390 sin separador colgando.
5. Solo dos niveles de titular en "Probar mi idea".
6. Capturas de foco, hover, carga y error, o declarar la limitación.
7. Medir contraste.

## Medición de contraste (WCAG, hecha con código)

| Token | Sobre `#F2F1EE` | Sobre `#FAF9F7` |
|---|---|---|
| `--ink-soft` `#5E6166` | 5.50 | 5.91 |
| `--accent` `#86672E` | 4.66 | 5.00 |
| `--down` `#A23B3B` | 5.76 | 6.19 |
| `--up` `#2F6B4F` | 5.57 | 5.98 |
| `--ink` `#1C1E21` | 14.79 | 15.88 |

Todos superan 4.5:1. Los textos de ayuda y de ejemplo de Streamlit usan su propio color con transparencia; en la ronda 3 se fuerzan a `--ink-soft`.

# Ronda 3

- **Lista negra:** limpia.
- **Puntajes:** Originalidad 16/20 · Tipografía 16/20 · Composición 16/20 · Color 13/15 · Imagen 12/15 · Detalle 7/10 = **80/100**.
- **Veredicto:** APROBADO, justo en el mínimo.
- **Cambios de la ronda 2:** los 7 resueltos (el 6 por declaración de límites en la DEC-V01).

## Recomendaciones aplicadas después de la aprobación

- El filete de "En palabras" ocupa todo el ancho de la columna.
- Los valores de la ficha no se parten en dos renglones.
- La volatilidad alta y el costo caro se marcan en bronce, no en rojo: el rojo queda para la variación negativa de precio.
- Las etiquetas de estado ya estaban en el paso 0.8 rem de la escala.

Estos ajustes no se re-auditaron. Pendiente: aprobación del usuario sobre las capturas y registro del diseño como congelado.
