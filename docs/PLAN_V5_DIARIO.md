# Plan v5: diario de operaciones, disciplina y verificador más honesto

Origen: evaluación de producto del 2026-11-14 (`docs/EVALUACION_PRODUCTO_2026-11-14.md`). Hoy la herramienta acompaña antes de operar, pero no registra lo que haces, y en la conducta es donde se pierde el dinero. Este plan cubre eso y corrige los fallos del verificador. La parte visual va después.

Las decisiones marcadas **[APROBAR]** cambian fórmulas o el comportamiento del verificador. Según las reglas del proyecto, no se aplican sin tu aprobación.

## A. Diario (nueva pantalla "Diario")

1. **Guardar el plan desde "Mi riesgo".** Un botón guarda mercado, lado, entrada, stop, tamaño, riesgo en dólares y un motivo escrito por ti. La operación queda **abierta**.
2. **Cerrar la operación.** Escribes el precio de salida y respondes dos preguntas: ¿moviste el stop en contra? y ¿respetaste el tamaño? La app calcula el resultado en R (ganancia o pérdida dividida por el riesgo planeado) y en dólares, con costos.
3. **Almacenamiento:** archivo local `data/diario.db` (SQLite). Queda fuera de GitHub y nada sale de tu computadora.
4. **Pantalla Diario:**
   - Las operaciones abiertas y cerradas.
   - Las cifras de la semana y del mes: número de operaciones, R medio, % de operaciones que cumplieron el plan, costos pagados y peor racha.
   - Todas las cifras salen del diario. Si no hay datos, se muestra "Sin operaciones", nunca un cero inventado.

## B. Reglas de disciplina (las defines tú)

5. **Límites que tú eliges:**
   - pérdida máxima del día (% del capital);
   - pérdida máxima de la semana (% del capital);
   - riesgo abierto total máximo;
   - pausa tras N pérdidas seguidas.

   Ninguna viene puesta por defecto: si no la defines, no existe. No invento valores.
6. **Cuando se supera un límite,** "Mi riesgo" lo muestra arriba en rojo. Guardar un plan nuevo exige marcar "Entiendo que estoy fuera de mis reglas", y queda registrado en el diario.
7. **Revisión semanal:** un resumen automático en la pantalla Diario: cuántas veces rompiste tus reglas, cuánto costaron las operaciones fuera del plan frente a las del plan, y comisiones.

## C. Verificador ("Probar mi idea")

8. **Intentos guardados en disco** (en `data/diario.db`), no en memoria: ya no se reinician al reiniciar el servidor. Esto no cambia ninguna fórmula; corrige un fallo.
9. **Mostrar la ventaja mínima detectable.** Se muestra la mitad del ancho del intervalo, por ejemplo: "Con estos datos solo se distinguiría del azar una ventaja mayor a ±0,34 R por operación". Así, "no se distingue" no se lee como "no sirve". Es la misma cifra que ya calcula el motor, solo que ahora se muestra.
10. **[APROBAR] Control contra el azar más fuerte.**
    - **Hoy:** 8 corridas al azar, y la regla se compara contra la mejor de ellas.
    - **Propuesta:** 200 corridas con **el mismo número de operaciones** que la regla. Se informa qué porcentaje de esas corridas igualó o superó a la regla (un valor p empírico). Para "Merece estudio" haría falta, además del intervalo por encima de cero, que ese porcentaje sea menor que 0,05 dividido entre el número de intentos.
    - **Costo:** la prueba tarda más (estimo entre 30 s y 1 min; lo mediré).
11. **[APROBAR] Usar el 20 % reservado.** Si una regla sale "Merece estudio", aparece el botón "Confirmar con datos reservados". Solo puede usarse **una vez por regla y mercado** (queda guardado). Da un veredicto final con la misma prueba sobre datos que la regla nunca vio. Sigue sin tocar el período protegido 2025–2026.
12. **[APROBAR] Historia en dólares con tu riesgo por operación.**
    - **Hoy:** la historia supone que arriesgas el 100 % del capital en cada operación.
    - **Propuesta:** cada operación arriesga el % que pongas (por defecto, el mismo de "Mi riesgo"). El capital final sale de componer `capital × (1 + riesgo% × R_neto)` operación por operación. Así coincide con cómo operarías de verdad.
13. **[APROBAR] Intervalo que respeta los regímenes del mercado.**
    - **Hoy:** el intervalo se calcula como si cada operación fuera independiente de las demás. Por eso sale más estrecho de lo que debería.
    - **Propuesta:** usar un "bootstrap por bloques", que remuestrea operaciones seguidas en grupos. Sale más ancho y más honesto.
    - El tamaño de bloque se fijaría con una regla publicada: la de Politis y White (2004), "Automatic Block-Length Selection for the Dependent Bootstrap". Hay que confirmar la referencia exacta antes de programarla; si no se confirma, este punto queda pendiente.

## D. Limpieza

14. Actualizar `README.md` y `MANUAL_RAPIDO_USUARIO.md` al producto actual. Hoy hablan de "señales", "Quant Score" y "oportunidad de alta confianza".

## Orden y pruebas

- **Orden:** C8 y C9 → A → B → C10 a C13 (si se aprueban) → D. Cada parte lleva primero sus pruebas, con referencias calculadas a mano. El R de una operación cerrada, por ejemplo, se comprueba con un caso escrito a mano.
- **Commit** al terminar cada parte, solo con tu aprobación.
- **Fuera de este plan:**
  - avisos automáticos por Telegram (siguiente fase);
  - cambios visuales de la auditoría (después de esto);
  - importación de operaciones desde el broker.

## Estado (2026-11-14)

- **Hecho:** A (diario), B (reglas y revisión), C8, C9, C10, C11, C12 y D. Aprobados por el dueño el 2026-11-14.
- **C13 pendiente:** no se pudo instalar la librería `arch`, que implementa la regla de Politis y White (2004) con la corrección de Patton, Politis y White (2009). Sin esa implementación o el artículo a la vista, la regla no se programa a mano.
- **Velocidad:** el motor leía los datos fila por fila. Ahora los lee como listas, sin cambiar ninguna fórmula; se comparó la salida antes y después sobre datos reales de BTC y EUR/USD y es idéntica. Cada corrida al azar bajó de unos 15 s a alrededor de 1 s.
- **Tiempo de espera:** con 200 corridas, "Probar mi idea" tarda unos 2–3 minutos en 1h y menos de 1 minuto en 4h.
