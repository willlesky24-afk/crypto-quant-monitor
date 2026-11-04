# Plan v3.1 a v3.2: copiloto de riesgo y verificador de ideas

**Dirección:** información y proceso, no promesas de ganancia. Un solo motor con dos puertas:
principiante ("¿qué miro y cuánto arriesgo?") y trader con experiencia ("¿mi regla funciona?").

## v3.1: base útil para los dos públicos

1. **Calculadora de riesgo guiada.** Capital, % a arriesgar, instrumento y stop por ATR dan tamaño
   de posición, pérdida máxima y costo por spread. Sin datos faltantes rellenados.
   *Listo cuando:* los resultados coinciden con casos calculados a mano en cripto, forex y oro.
2. **Resumen diario de mercado.** Régimen, volatilidad, spread y zonas de valor en lenguaje simple,
   con todos los números salidos del motor.
   *Listo cuando:* cada cifra del resumen se puede rastrear a un cálculo.
3. **Semáforo de condiciones.** Dificultad del mercado (volatilidad y spread), nunca "compra" o
   "vende". Los umbrales se fijan y se justifican antes de publicarlo.
4. **Radar de cosas inusuales.** Reemplaza al ranking de oportunidades. Compresión de volatilidad,
   fuerza relativa y ruptura de correlación. Cada aviso muestra su historial (cuántas veces pasó y
   qué ocurrió), corrige por el número de mercados y medidas, y nunca es una señal de compra. Antes
   hay que acelerar la clasificación de régimen del escáner (hoy unos 15 s por par).
5. **Mediciones de estrés (investigación).** Ver abajo. Solo pasan al producto si superan su prueba.
6. **Índices.** Tres índices, como estaba previsto.

## v3.2: agente verificado y verificador

7. **Verificador de ideas.** Reglas sin programar, prueba con costos reales y veredicto honesto.
   Cuenta los intentos de cada usuario y avisa del riesgo de ganar por suerte.
8. **Agente de IA.** Traduce la idea a reglas y explica resultados. No calcula ni inventa cifras.
9. **Prueba con 5 a 10 traders reales** antes de construir la v4.

## Después

Modo práctica con datos históricos y diario de operaciones con IA.

## Línea de investigación: estrés, burbujas y manipulación

Objetivo: **describir el estado del mercado**, no predecir la fecha de un giro.

| Medición | Qué busca | Datos | Estado |
|---|---|---|---|
| Prueba de explosividad (SADF/GSADF) | Precio con crecimiento explosivo | Velas, ya disponibles | Primero |
| Apalancamiento en cripto | Funding e interés abierto extremos | Binance futuros, por integrar | Segundo |
| Lectura de volumen anómalo | Volumen que no cuadra con el precio | Velas | Tercero |
| LPPLS | Patrón previo a un colapso | Velas | Exploratorio |
| Libro de órdenes (VPIN, spoofing) | Flujo tóxico y órdenes falsas | Datos de muy alta frecuencia | Fuera de alcance |

Reglas: cada medición se valida con casos publicados y con los datos de 2021 a 2024; las señales
falsas se reportan siempre; el período 2025–2026 solo se usa una vez, para algo fijado de antemano.

## Reglas del producto

- No se promete rentabilidad ni se empuja a operar más.
- Se muestran el riesgo y la evidencia v3.0.
- El límite entre educación y recomendación se revisa con un abogado antes de la v4.
