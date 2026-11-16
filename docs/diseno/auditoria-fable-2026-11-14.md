# Auditoría visual independiente — Quant Monitor (web, fase 5)

- **Fecha:** 2026-11-14
- **Auditor:** agente independiente (no diseñó la interfaz; juzga solo capturas, sin leer código)
- **Material visto:** 10 capturas de `docs/diseno/capturas-web/fase5/`, la DEC-V02, la rúbrica `auditoria-visual.md`, la lista negra `anti-ia.md` y `paneles-de-datos.md`.

## Límites de esta auditoría (léelos antes del veredicto)

1. **Faltan anchos.** La rúbrica exige 1440, 768 y 390 px. No hay ninguna captura de 768 px. Según la propia rúbrica, sin los tres anchos esto es "opinión", no auditoría formal. Lo trato como auditoría con esa salvedad.
2. **Las capturas están reducidas.** Las de 1440 llegan a 800 px de ancho y `hoy-390.jpg` llega a 187 px. Los detalles finos (si hay sombra o no, grosor exacto de filetes) no se pueden afirmar con certeza; donde dudo, lo digo.
3. **No vi estados con movimiento** (hover, foco, cifra que se actualiza), ni el Radar después de escanear, ni el resultado de "Probar mi idea". Esas pantallas son justo donde el producto entrega valor; quedan sin juzgar.
4. **Referentes del mercado:** las páginas públicas de varios productos no describen su aspecto en texto, así que parte de la comparación sale de mi conocimiento general de esos productos y no de una fuente citada. Lo marco en cada caso.

---

## 1. Qué es hoy vs. qué pretende ser

**Qué pretende ser (DEC-V02):** "un instrumento de medición del mercado": cada panel un medidor con cifra, escala y fuente; emoción "preciso, sereno, de instrumento caro"; referencias de laboratorio y fichas de relojería.

**Qué comunica hoy a primera vista:** un panel administrativo claro, ordenado y honesto, con un gráfico de velas de librería y cuatro tarjetas pequeñas. Tapando el nombre, `hoy-1440.jpg` podría ser la demo de casi cualquier plantilla de panel financiero claro. Es correcta; no es reconocible.

**La brecha, en concreto:**

| La DEC promete | Lo que se ve | Captura |
|---|---|---|
| "Cada panel es un medidor con su escala" | El "medidor" es una barra de avance de unos 3 px con "0" y "100" en los extremos. No hay graduaciones, marcas ni aguja. | `hoy-1440` (Volatilidad, Zona de valor), `riesgo-1440` |
| "Instrumento caro" | El elemento visual más pesado de toda la pantalla es el botón de navegación activo (bloque negro), no un dato. | las cuatro de 1440 |
| "La profundidad sale del fondo y los filetes" | Fondo perla y panel blanco se diferencian apenas; el resultado es un solo plano. | todas |
| Acento bronce para "escalas, foco y dato clave" | El bronce ocupa menos del 1 % de la pantalla y en tono apagado; se lee como beige. | `hoy-1440`, `riesgo-1440` |
| Máximo 3 movimientos, sobrios | Una intro de barras de colores y una moneda dorada de bitcoin girando, que no está en la DEC. | `intro-1`, `intro-2`, `intro-3` |
| Anti-referencia 1: app de señales cripto | La marca es una "B" de bitcoin y la intro es una moneda de oro. El producto cubre forex, metales e índices. | `intro-2`, `intro-3`, `login-390` |

Lo que sí cumple y hay que conservar: el texto. "¿Cuánto puedo operar sin arriesgar de más?", "¿Tu regla resiste los datos?", "N/D — Este proveedor no da spread", "El stop no es una garantía". Ese es el mejor activo de la interfaz: voz propia, honesta, sin promesa. La parte visual no está a la altura de la parte escrita.

---

## 2. Comparación con productos del mercado

| Referente | Recurso concreto que le da vida | ¿Aplica aquí? |
|---|---|---|
| **Linear** (pulido) | En su último rediseño: menos líneas divisorias y las que quedan suavizadas; barra lateral atenuada "unos puntos" para que mande el contenido; grises pasados de azulados a un gris más cálido y menos saturado; menos íconos. Fuente: [Linear, Behind the latest design refresh](https://linear.app/now/behind-the-latest-design-refresh). | **Sí, directo.** Es exactamente "líneas más suaves". Aquí la barra lateral hace lo contrario: su ítem activo es lo más oscuro de la pantalla. |
| **Robinhood** (móvil) | Cifra grande y gráfico que se animan juntos cuando cambia el valor; el fondo completo pasa de blanco a gris oscuro al cerrar el mercado (el estado del mercado se ve sin leer). Fuente: [Google Design, Robinhood](https://design.google/library/robinhood-investing-material). Bloomberg describe los destellos verde/rojo en tiempo real: [Bloomberg](https://www.bloomberg.com/features/2021-robinhood-stock-trading-design). | **A medias.** Sí: cifra y gráfico enlazados, y un estado "mercado cerrado" visible (útil en forex e índices). **No:** destellos, confeti ni nada que premie operar; a Robinhood se le criticó por eso: [UX Collective](https://uxdesign.cc/how-robinhood-gamified-investing-and-exploited-users-633152780355). |
| **TradingView / Lightweight Charts** | La misma librería que ya usa el proyecto ofrece serie de área con degradado (`topColor`/`bottomColor`), y su tutorial oficial enseña leyenda propia y a ocultar la línea horizontal del cursor para un aspecto más limpio. Fuentes: [AreaStyleOptions](https://tradingview.github.io/lightweight-charts/docs/api/interfaces/AreaStyleOptions), [tutorial de tooltips](https://tradingview.github.io/lightweight-charts/tutorials/how_to/tooltips), [tutorial de leyendas](https://tradingview.github.io/lightweight-charts/tutorials/how_to/legends). | **Sí.** El gráfico actual se ve con los valores por defecto de la librería. Personalizarlo es el cambio de mayor impacto y no rompe nada. |
| **Stripe Dashboard** (pulido en claro) | Sombras en varias capas y teñidas (no negras), texto en azul muy oscuro en vez de negro, cifras tabulares, y el color de marca en menos del 5 % de los píxeles. **Aviso:** estos datos salen de análisis de terceros, no de Stripe; los valores exactos no están verificados. Fuentes: [open-design.ai](https://open-design.ai/plugins/design-system-stripe/), [guía SaaS](https://mcpservers.org/agent-skills/cloudflare/frontend-design-saas). | **Sí, el principio.** Es la prueba de que un panel claro puede tener profundidad sin parecer plantilla: sombra corta, en capas y teñida con el color de la tinta. |
| **Koyfin** | Densidad ("ver más en menos tiempo") y temas intercambiables. Fuente: [koyfin.com](https://www.koyfin.com/). Usuarios lo describen como más agradable que Bloomberg: [G2](https://www.g2.com/products/koyfin/reviews). | **Solo en el Radar**, que será una tabla de muchos mercados. No en "Hoy": la serenidad de una sola lectura es una ventaja frente a Koyfin, no un defecto. |
| **Glassnode Studio** | Anotaciones sobre el propio gráfico y varias fuentes en una sola vista. Fuente: [glassnode.com/products/studio](https://glassnode.com/products/studio). Por conocimiento propio (sin fuente citada): el precio va en gris como contexto y la métrica en un solo color fuerte. | **Sí.** La "Zona de valor" hoy es un par de números en una tarjeta; debería estar dibujada sobre el gráfico como banda. |
| **CoinGlass / Finviz** | El dato es la imagen: mapas de calor densos donde el color codifica la magnitud. CoinGlass tiene tema oscuro ([enlace con `theme=dark`](https://www.coinglass.com/pro/futures/LiquidationMap?theme=dark)); Finviz ofrece claro/oscuro ([finviz.com/map.ashx](https://finviz.com/map.ashx)). La descripción visual es conocimiento propio; las páginas no la dan en texto. | **La idea sí, el tono no.** El Radar puede ser una retícula mercado × medida con escala de color sobria. La saturación de ambos es justo la anti-referencia. |

**Lectura de conjunto.** Casi todos los paneles de trading son oscuros ([AdminLTE, 2026](https://adminlte.io/?p=7054)). Elegir claro es una decisión que distingue, pero es más difícil: en oscuro la vida sale gratis del brillo de los datos sobre negro; en claro hay que construirla con capas, tinta y dato dibujado. La DEC eligió claro y además prohibió la sombra; se quedó sin herramientas.

---

## 3. Puntaje y lista negra

### Lista negra: **DEVUELTA**

| Ítem | Estado | Evidencia |
|---|---|---|
| 4. Más de un acento compitiendo | **Presente** | Bronce (interfaz), naranja (la "B" del logo), dorado amarillo (moneda de la intro), verde y bronce en degradado (barras de la intro) y azul de enlace por defecto del navegador en el pie ("TradingView Lightweight Charts"). `intro-1`, `intro-3`, `login-390`, `hoy-390-cargando`, pie de `riesgo-1440`. |
| 19. Ícono que no significa nada | **Presente** | El símbolo de bitcoin como marca de un producto de cripto, forex, metales e índices. Significa lo que el producto no es. |
| 9. Sombra suave idéntica | **Dudoso** | En `login-390` y `riesgo-1440` las tarjetas parecen tener un halo suave. La DEC dice "sombra: ninguna". Con la reducción de las capturas no puedo afirmarlo; verificar. |
| 5 / 7. Tarjetas iguales / todo en tarjetas | Pasa con observación | Las cuatro tarjetas 2×2 de `hoy-1440` tienen igual tamaño, pero contenido distinto, y la cabecera y el texto van sin caja. |
| 12, 15, 17, 1, 2, 3 | Limpio | Plex en vez de Inter, sin mayúsculas espaciadas, sin emojis, sin morado, sin vidrio. |

Además, dos incumplimientos de la propia DEC-V02: la intro es movimiento no declarado (el máximo era 3), y el bronce `#8A7A56` como texto pequeño sobre blanco (la miga "Mi riesgo") da un contraste aproximado de 4.2:1 según mi cálculo, por debajo del 4.5:1 del nivel AA que la DEC exige. Conviene medirlo con una herramienta.

### Rúbrica

| Criterio | Puntaje | Evidencia |
|---|---|---|
| Originalidad / firma | **11 / 20** (crítico, bajo el mínimo de 12) | No pasa la prueba de tapar el logo: `hoy-1440` es un panel claro genérico. La idea "instrumento" está escrita en la DEC y no dibujada. La única personalidad visual (la moneda) pertenece a otro lenguaje. |
| Tipografía | **14 / 20** | Plex Sans + Plex Mono es buena pareja y el precio en mono a gran tamaño manda bien. Pero los títulos de tarjeta, etiquetas y notas se amontonan en dos tamaños muy cercanos, y `65,914.01` y `$10.00` son los únicos momentos tipográficos. |
| Composición | **12 / 20** | "Probar mi idea" es la mejor: lista sin caja con filetes gruesos a la izquierda y formulario a la derecha. Lo demás falla por vacío no compuesto: Radar con 70 % de pantalla en blanco, Riesgo termina a media altura, y el panel del gráfico tiene una franja muerta debajo. En móvil, un hueco de unos 100 px entre el lema y la navegación (`hoy-390-cargando`). |
| Color | **9 / 15** | Paleta sobria, verde y rojo bien contenidos. Pero el fondo es gris frío y el acento es cálido (no conversan), el acento casi no aparece, y hay cuatro acentos intrusos (ver lista negra). |
| Imagen | **7 / 15** | En un panel, el dato es la imagen. El gráfico es el de fábrica y los medidores son barras. La marca es un símbolo ajeno. |
| Detalle y acabado | **5 / 10** | Enlace azul por defecto; botón "Entrar" gris que parece deshabilitado; "Cargando BTCUSDT…" como texto suelto y no como esqueleto; "Cerrar sesión" como enlace subrayado en el pie; etiqueta del eje cortada en móvil ("nov"). Hover y foco no se pudieron ver. |
| **Total** | **58 / 100** | Umbral: 80 y ningún crítico bajo 12. **No aprueba.** |

### Las tres preguntas

1. **Sin leer el texto, ¿sector y sensación?** Finanzas; sensación de "panel interno bien ordenado", neutral. La emoción objetivo era "instrumento caro": cumple "sereno", no cumple "caro" ni "instrumento".
2. **¿Parecido con las anti-referencias?** (1) App de señales cripto: **sí**, en la moneda dorada y el logo de bitcoin. (2) SaaS morado de cuatro tarjetas: parecido parcial en la estructura 2×2 de tarjetas iguales, sin el morado. (3) TradingView saturado: ninguno.
3. **¿Qué quitaría para que se vea más premium?** La moneda de bitcoin, de la intro y del logo.

---

## 4. Por qué "luce muerta": causas de fondo

1. **Hay un solo plano.** Fondo `#F6F8F9` y panel `#FFFFFF` difieren alrededor de un 3 % de luminosidad, el filete está al 8 % y la sombra está prohibida. El ojo no encuentra nada delante ni detrás. La DEC confió en que "la profundidad sale del fondo y los filetes" con valores demasiado tímidos para lograrlo.
2. **El dato no está dibujado, está escrito.** Volatilidad, zona de valor y apalancamiento son números con una rayita. El gráfico es el de fábrica y no muestra nada de lo que el motor calcula (la zona de valor no aparece sobre el precio). En un panel de datos eso equivale a una revista sin fotos.
3. **El color no tiene temperatura.** Gris frío de base, acento cálido casi invisible, y las mayores masas de color son un botón negro y velas verde/rojo estándar. Nada dice "bronce champán".
4. **Los vacíos no están compuestos.** Radar en reposo, Riesgo a media página, la franja bajo el gráfico, la carga como texto. El blanco deliberado da lujo; el blanco por falta de contenido da abandono.
5. **Nada responde.** Los tres movimientos de la DEC son tan discretos que no se perciben, y todo el presupuesto de animación se gastó en una intro ajena al producto. La vida de una herramienta está en que la cifra, el medidor y el gráfico reaccionen, no en la portada.

---

## 5. Qué le falta, priorizado

| # | Cambio | Valores aproximados | Impacto | Riesgo para la elegancia |
|---|---|---|---|---|
| 1 | **Gráfico propio, no de fábrica.** Banda de la zona de valor dibujada sobre el precio, leyenda OHLC en mono arriba a la izquierda, volumen en gris al pie, etiqueta de último precio en tinta (no roja), y que el gráfico llene su panel. | Banda bronce al 8–10 % de opacidad con bordes de 1 px al 40 %; volumen gris al 25 %; mechas al 70 %. | Muy alto: es el 50 % de la pantalla principal. | Bajo. No añadir indicadores: uno más y se cae en la anti-referencia 3. |
| 2 | **Dibujar el instrumento: escalas graduadas.** Marcas menores cada 10 y mayores cada 50, cifras de escala en mono, y un índice triangular fino en vez de barra rellena. El mismo motivo en Volatilidad, Zona de valor y la barra de Riesgo. | Marcas de 1 px, 4 y 8 px de alto, al 25 % y 50 % de tinta; pista de 2 px. | Muy alto en originalidad: es la firma que falta. | Bajo si es un solo motivo repetido; alto si cada medidor inventa el suyo. |
| 3 | **Dos planos reales.** Oscurecer y entibiar un poco el fondo, y dar a los paneles de datos una sombra corta, en capas y teñida, más una luz superior interior. Requiere enmendar "sombra: ninguna" en la DEC. | Fondo hacia `#F3F2EE`; sombra `0 1px 2px` al 5 % + `0 8px 24px -12px` al 10 %, ambas en tinta `#191D23`; luz interior superior blanca de 1 px. | Alto: ataca la causa 1. | Medio. Si la sombra es difusa o va en todo, cae en el ítem 9 de la lista negra. Solo en paneles de datos; formularios y texto, planos. |
| 4 | **Navegación atenuada.** Cambiar el bloque negro del ítem activo por fondo tenue, barra bronce y texto en peso 600; resto de ítems en tinta suave. | Fondo tinta al 6 %; barra bronce de 2 px; radio 8 px. | Alto: devuelve el protagonismo al precio y reserva el negro para la acción principal. | Muy bajo. Es lo que hizo Linear. |
| 5 | **Líneas más suaves.** Subir radios y bajar filetes. | Paneles 10 → 14 px; controles 6 → 8 px; etiquetas 4 px; filete 8 % → 6 % donde ya hay sombra. | Medio: responde literalmente al pedido del dueño. | Medio. Por encima de 16 px o con botones píldora cae en el ítem 8. |
| 6 | **Dar temperatura.** Teñir todos los grises hacia el bronce y oscurecer el bronce cuando sea texto. | Filetes `rgba(60,50,30,0.10)`; bronce para texto hacia `#74653F` (verificar AA); bronce actual solo para trazos y rellenos. | Medio-alto: unifica y corrige el contraste. | Bajo. No pasarse a crema: debe seguir leyéndose como blanco técnico. |
| 7 | **Estados vacíos y de carga diseñados.** Radar en reposo mostrando la retícula de mercados que va a revisar, en estado "sin escanear", con fecha del último escaneo. Carga con esqueleto en la forma del dato. Riesgo con un esquema vertical de entrada y stop que ocupe la altura libre. | Esqueleto en tinta al 6 %, brillo opcional de 1.2 s. | Alto en Radar y móvil. | Bajo. Prohibido rellenar con cifras de muestra (regla del proyecto). |
| 8 | **Vida en el dato, no en la portada.** Medidor que se llena al cargar, cifra que cambia dígito a dígito, cursor del gráfico con lectura en la leyenda, y un indicador de "mercado cerrado" para forex e índices. Requiere ampliar el máximo de 3 movimientos de la DEC. | Medidor 400–500 ms con frenado suave; cifra 200 ms; nada en bucle. | Alto: ataca la causa 5. | Medio. Cualquier animación continua o destello verde/rojo lleva al casino. |
| 9 | **Reparar lo roto.** Enlace azul por defecto → tinta subrayada; botón "Entrar" en tinta plena; "Cerrar sesión" fuera del pie; hueco de la cabecera móvil; etiqueta de eje cortada. | — | Medio; son señales de descuido que restan "caro". | Ninguno. |
| 10 | **Grano sutil en el fondo** (solo fondo, nunca paneles). | Ruido estático al 2–3 % de opacidad. | Bajo. Es lo último, no lo primero: da textura, no vida. | Bajo. Más de 4 % ensucia. |

Para una fase posterior, no ahora: un tema oscuro (la DEC ya nombra el "Oscuro de precisión"). Es lo que el mercado espera, pero hacerlo antes de resolver los puntos 1 a 4 solo duplicaría el problema.

### Qué NO hacer

- Vidrio translúcido con desenfoque, manchas de color de fondo, degradados morado-azul o texto con degradado: plantilla de IA instantánea.
- Brillos de neón, verde y rojo saturados, cifras parpadeando, confeti o cualquier premio visual por operar: casino cripto.
- Monedas, cohetes, toros, objetos 3D dorados.
- Sombra grande y difusa en todos los elementos, o que todo se levante al pasar el cursor.
- Radios de 20 px o más y botones píldora.
- Degradado bajo las velas. `paneles-de-datos.md` lo prohíbe salvo declaración; como mucho, un área bronce del 12 % al 0 % en un modo de línea para móvil, y declarándolo en la DEC.
- Más tarjetas de métrica para "llenar". Falta dibujo, no cantidad.

---

## 6. La intro

**Veredicto: resta. Rehacerla.**

- **Bloquea.** A los 11 segundos (`intro-3`) el usuario sigue viendo una moneda. Una herramienta de disciplina que hace esperar sin mostrar nada contradice "preciso, sereno".
- **Miente sobre el producto.** Una moneda de bitcoin anuncia una app cripto; el producto cubre cuatro clases de activos y se define contra las apps de señales.
- **Es de otro lenguaje.** Oro con volumen y sombra, y barras con degradado en tres colores, dentro de un sistema que prohíbe sombras y permite un solo acento.
- **Su duración depende de la red.** Una animación de marca no debe ser la pantalla de carga.

**Cómo debería ser:**

1. **Marca: 600 a 900 ms como máximo, solo en arranque en frío** de la app instalada, y nunca al volver a una sesión abierta. Un solo gesto del lenguaje propio: las marcas de una escala que se trazan y un índice que se asienta. Un color (tinta) más el bronce.
2. **Después, la interfaz completa de inmediato**, con esqueletos en el lugar exacto de cada dato y una línea honesta: "Leyendo BTCUSDT · Binance".
3. **Si hay datos guardados**, mostrarlos al instante marcados como desactualizados con su hora, y reemplazarlos cuando llegue lo nuevo.
4. **Si pasa de unos 8 s**, decir qué ocurre y ofrecer reintentar. Nunca una animación sin fin.
5. Con `prefers-reduced-motion`, sin animación.

---

## 7. Veredicto final

**Aprobado con cambios** (por rúbrica: devuelto, 58/100, lista negra con dos ítems): la dirección, la estructura y el texto son buenos y no hay que rehacerlos; lo que falla es que la idea de "instrumento" no está dibujada, no hay profundidad y la intro y el logo contradicen al producto. Los cambios 1 a 4 y la intro son condición para una segunda ronda, que debe traer capturas en 768 px y de los estados con resultados.

---

# Ronda 2 (2026-11-15)

- **Auditor:** el mismo agente independiente de la ronda 1 (no diseñó la interfaz; juzga solo capturas, sin leer código).
- **Material visto:** 12 capturas de `docs/diseno/capturas-web/ronda2/`, la DEC-V02 con su Enmienda 1, la rúbrica y la lista negra.

## Límites de esta ronda

1. **Ya están los tres anchos** (1440, 768 y 390 px). Esta vez sí es auditoría formal.
2. **Las capturas llegan más reducidas que en la ronda 1** (1440 → 634 px; antes 800). El grano del fondo, el color exacto del bronce, el grosor de las marcas de escala y el dibujo del logo no se pueden afirmar con certeza. Donde dudo, lo digo.
3. **Siguen sin verse** las dos pantallas que pedí como condición: el Radar después de escanear y el resultado de "Probar mi idea". Tampoco hay captura del inicio de sesión, ni de hover, foco o movimiento. Lo que no vi, no lo puntúo a favor.
4. La intro se evalúa por descripción, no por imagen.

## 1. Qué cambió frente a la ronda 1

| # | Cambio pedido | Estado | Qué veo y dónde |
|---|---|---|---|
| 1 | Gráfico propio | **Resuelto, con defectos de acabado** | `hoy-1440`, `hoy-768`, `hoy-390`: banda de la zona de valor sobre el precio, leyenda de la vela en mono arriba a la izquierda, volumen gris al pie, etiqueta del último precio en tinta, sin indicadores añadidos, y una nota al pie que explica la banda. Defectos: la primera y la última cifra del eje de precios salen cortadas por arriba y por abajo (`hoy-1440`, `hoy-768`); la última fecha sigue cortada ("16 n", `hoy-1440` y `hoy-390`); la banda casi no se distingue en 1440; el cierre de la leyenda va en rojo. |
| 2 | Escalas graduadas (la firma) | **Parcial** | Existe y es el mismo motivo en Volatilidad, Zona de valor y Riesgo: pista fina, marcas e índice triangular (`hoy-390-medidores` es donde mejor se ve; `riesgo-768`). Pero: (a) en 1440, que es la pantalla principal, las tarjetas son tan angostas que la escala queda diminuta y apenas se percibe (`hoy-1440`); (b) Apalancamiento escribe su posición ("mayor que el 9 % de 293 registros") en vez de dibujarla en la misma escala; (c) en 768 la escala a todo el ancho se lee como una línea con tres marcas: las menores casi no se ven. La firma existe, pero habla en voz muy baja. |
| 3 | Dos planos reales | **Resuelto** | Fondo tibio y paneles blancos con sombra corta: ahora hay delante y detrás (`hoy-1440`, `diario-1440`). Duda: los paneles de formulario (Riesgo, Probar, "Mis reglas") parecen llevar la misma sombra que los de datos; la Enmienda dice que van planos. Verificar. |
| 4 | Navegación atenuada | **Resuelto** | El bloque negro desapareció; el ítem activo es un fondo tenue con barra lateral (`hoy-1440`). El precio vuelve a mandar. Queda un bloque negro pequeño: el intervalo activo "1h", que compite con los botones de acción. |
| 5 | Líneas más suaves | **Resuelto** | Radios mayores sin llegar a píldora (todas). |
| 6 | Dar temperatura | **Resuelto en el fondo; el bronce no es verificable** | El gris frío desapareció; fondo y filetes conversan (todas). El bronce sigue siendo escasísimo y con esta reducción no puedo confirmar ni su tono ni el contraste AA de la miga. Medirlo con herramienta. |
| 7 | Vacíos y carga diseñados | **Parcial** | Carga: resuelto, esqueletos con la forma del dato y la línea "Leyendo BTCUSDT · 1h…" (`hoy-1440-cargando`, `hoy-390-cargando`). Radar en reposo: mejor, muestra los 25 mercados que revisará como etiquetas "sin escanear" (`radar-1440-reposo`), pero sin fecha del último escaneo y con más de la mitad de la pantalla vacía. Riesgo: ya no termina a media altura (`riesgo-1440`); el esquema vertical de entrada y stop no se hizo, y no hace falta insistir. Observación: al pasar de carga a dato las cuatro tarjetas cambian de alto, así que la página da un salto. |
| 8 | Vida en el dato | **No verificable** | No hay capturas en movimiento. No veo indicador de "mercado cerrado" (con BTC no puede aparecer; falta una captura con forex o un índice fuera de horario). |
| 9 | Reparar lo roto | **Parcial** | Enlace azul: resuelto, ahora en tinta subrayada (`hoy-1440-cargando`, `probar-1440`). Hueco de la cabecera móvil: resuelto (`hoy-390`). "Cerrar sesión" fuera del pie: resuelto a medias; ahora es un botón "Salir" gris que parece deshabilitado, y en `diario-390` queda huérfano, solo en su renglón. Etiqueta de eje cortada: **no resuelto** ("16 n"). Botón "Entrar": sin captura, no verificable. |
| 10 | Grano en el fondo | **No verificable** | A 634 px no se distingue. Tampoco ensucia, que era el riesgo. |
| — | Intro y marca | **Resuelto por descripción** | Menos de 1 s, una vez por sesión, con el motivo propio (escala e índice): es lo que pedí. La moneda y el símbolo de bitcoin ya no aparecen en ninguna captura. El logo nuevo se ve como un cuadro oscuro con marcas (`hoy-768`, `hoy-390`); a ese tamaño el dibujo es apenas legible. |

**Resumen:** de 10 cambios, 5 resueltos (1, 3, 4, 5, 6), 3 parciales (2, 7, 9) y 2 que no se pueden juzgar con este material (8, 10). La intro, resuelta.

## 2. Lista negra: **LIMPIA, con tres observaciones**

Los dos ítems de la ronda 1 desaparecieron: ya no hay acentos compitiendo (ítem 4) ni símbolo ajeno como marca (ítem 19).

| Ítem | Estado | Evidencia |
|---|---|---|
| 7. Todo en tarjetas | Pasa, al límite | `diario-1440` y `diario-390`: cinco cajas blancas apiladas, y dos de ellas solo contienen una frase de vacío ("Sin operaciones cerradas", "Ninguna abierta"). El título y el aviso van sin caja, por eso pasa. Una caja más y no pasa. |
| 9. Sombra idéntica en todo | Dudoso | Los formularios parecen llevar la misma sombra que los paneles de datos (`riesgo-768`, `probar-1440`). Si es así, incumple la Enmienda 1 y se acerca a este ítem. Verificar. |
| 5. Tarjetas iguales | Pasa con observación | Las cuatro tarjetas 2×2 de `hoy-1440` siguen siendo del mismo tamaño; el contenido es distinto y dos llevan escala. |
| 1, 2, 3, 4, 8, 12, 15, 17, 19 | Limpio | Sin morado, sin vidrio, un solo acento, radios moderados, Plex, sin emojis, marca propia. |

## 3. Rúbrica

| Criterio | Ronda 1 | Ronda 2 | Evidencia |
|---|---|---|---|
| Originalidad / firma (crítico) | 11 | **14 / 20** | Ya hay una idea dibujada: la escala con índice, repetida en tres medidores, y la zona de valor sobre el precio. Pero tapando el logo en `hoy-1440`, la firma ocupa unos pocos píxeles dentro de tarjetas angostas; lo que se reconoce es "panel claro bien hecho", no todavía "instrumento". En móvil (`hoy-390-medidores`) sí se reconoce. |
| Tipografía (crítico) | 14 | **15 / 20** | Precio, "91 / 100", "$10.00" y "−1.00 R" en mono mandan bien; los títulos en forma de pregunta tienen voz. Persiste el amontonamiento de etiquetas y notas en dos tamaños casi iguales, y en 1440 las notas de las tarjetas se parten en tres y cuatro renglones de pocas palabras. |
| Composición (crítico) | 12 | **15 / 20** | "Hoy" tiene ahora orden claro: precio, gráfico, medidores. Riesgo ya llena su página. Fallan: tarjetas de medidor demasiado angostas en 1440; Radar en reposo con más de media pantalla vacía; Diario como pila de cajas sin que una mande; "Salir" huérfano en `diario-390`. |
| Color | 9 | **11 / 15** | Paleta cerrada y por fin con temperatura; los intrusos se fueron; el rojo del aviso es estado real y está contenido. El bronce sigue casi ausente y su contraste como texto está sin medir. |
| Imagen | 7 | **11 / 15** | El gráfico dejó de ser el de fábrica y los medidores están dibujados. Restan: cifras del eje cortadas, banda casi invisible en 1440, escalas muy tenues. |
| Detalle y acabado | 5 | **6 / 10** | Suman los esqueletos y el enlace corregido. Restan: fecha del eje aún cortada, cifras del eje cortadas, "Salir" con aspecto de deshabilitado, salto de la página al terminar la carga, y hover y foco otra vez sin evidencia. |
| **Total** | 58 | **72 / 100** | Umbral: 80 y ningún crítico bajo 12. Ningún crítico bajo el mínimo, pero **no alcanza 80**. |

### Las tres preguntas

1. **Sin leer el texto, ¿sector y sensación?** Finanzas; sensación de herramienta seria, tibia y ordenada. Cumple "sereno" y ahora también "preciso". "Instrumento caro" se cumple en móvil y a medias en escritorio.
2. **¿Parecido con las anti-referencias?** (1) App de señales cripto: ninguno. (2) SaaS de cuatro tarjetas iguales: parecido parcial que persiste en el bloque 2×2 de "Hoy" y en la pila de cajas del Diario. (3) TradingView saturado: ninguno.
3. **¿Qué quitaría?** Las cajas alrededor de los estados vacíos del Diario. Una frase de vacío no necesita panel ni sombra.

## 4. Lo que aún falta, priorizado

| # | Cambio | Concreto | Riesgo para la elegancia |
|---|---|---|---|
| 1 | **Que la firma se vea en 1440.** | Dar más ancho a los medidores de "Hoy": o la columna derecha pasa a una sola columna de cuatro medidores horizontales, o el reparto gráfico/medidores pasa de aprox. 70/30 a 60/40. Meta: escala de al menos 280 px reales. Marcas mayores de 10 px al 60 % de tinta, menores de 5 px al 30 %; índice en bronce pleno. Dibujar Apalancamiento en la misma escala (su posición 9 de 100 ya la calcula el motor). Costo sigue en "N/D" sin escala: correcto. | Bajo. No añadir color ni un segundo motivo. Si las marcas pasan del 60 % empiezan a parecer regla escolar. |
| 2 | **Mostrar lo que falta por ver.** | Capturas del Radar con resultados, del resultado de "Probar mi idea", del inicio de sesión, de un mercado cerrado, y de hover y foco. Deben usar el mismo motivo de escala, no inventar otro. | Ninguno; es evidencia. Sin esto no puedo aprobar aunque el puntaje suba. |
| 3 | **Terminar el gráfico.** | Margen arriba y abajo para que no se corten la primera y la última cifra del eje; margen derecho para la última fecha; banda de la zona de valor al 12–14 % o con bordes al 50 % para que se vea en escritorio; cierre de la leyenda en tinta. | Ninguno. No subir la banda de 15 %: se vuelve mancha. |
| 4 | **Diario: menos cajas, una que mande.** | Estados vacíos como renglón sin caja; "Últimos 30 días" como bloque principal con sus tres cifras más grandes; el resto subordinado. | Bajo. No compensar el vacío con más métricas. |
| 5 | **"Salir" y el intervalo activo.** | "Salir" como botón de contorno en tinta suave (que no parezca deshabilitado), al pie de la navegación en escritorio y en la misma línea de la marca en móvil. Intervalo activo "1h" con el mismo trato que la navegación activa (tinta al 6 % y peso 600), para reservar el negro a la acción principal. | Muy bajo. |
| 6 | **Medir, no suponer.** | Contraste AA del bronce de texto con herramienta; confirmar que los formularios van sin sombra; igualar el alto de los esqueletos al de las tarjetas para que la página no salte; en el Radar en reposo, fecha del último escaneo. | Ninguno. |

## 5. Veredicto

**Devuelto**, a ronda 3 (la última que permite la rúbrica): 72/100, bajo el umbral de 80. La lista negra queda limpia y ningún criterio crítico está bajo 12, así que **no** corresponde volver a la Fase 0: la dirección es buena y la Enmienda 1 funcionó (subió 14 puntos). Lo que separa esto de la aprobación es acabado y evidencia, no rumbo: los puntos 1, 2 y 3 son condición; 4 a 6 suman los puntos que faltan.

```
AUDITORÍA VISUAL — Quant Monitor (web) — 2026-11-15 — Ronda 2
Auditor: agente independiente (distinto del diseñador)
Lista negra: LIMPIA (observaciones en ítems 5, 7 y 9)
Puntajes: Originalidad 14/20 · Tipografía 15/20 · Composición 15/20 · Color 11/15 · Imagen 11/15 · Detalle 6/10 = 72/100
Preguntas: 1) finanzas, herramienta seria y tibia; "instrumento caro" a medias en escritorio 2) señales cripto: ninguno; cuatro tarjetas: parcial; TradingView saturado: ninguno 3) las cajas de los estados vacíos del Diario
Veredicto: DEVUELTO con cambios: firma visible en 1440; capturas de Radar con resultados, resultado de Probar, login, hover y foco; ejes del gráfico sin cortes y banda visible; Diario con menos cajas; "Salir" e intervalo activo; medir contraste y sombras.
```

---

# Ronda 3 (2026-11-15)

- **Auditor:** el mismo agente independiente de las rondas 1 y 2 (no diseñó la interfaz; juzga solo capturas, sin leer código).
- **Material visto:** 13 capturas de `docs/diseno/capturas-web/ronda3/`, la DEC-V02 con su Enmienda 1, la rúbrica y la lista negra.
- **Es la última ronda que permite la rúbrica.**

## Límites de esta ronda

1. **Tres anchos presentes.** Las de 768 y 390 px llegan a tamaño real. Las de 1440 siguen reducidas a 800 px de ancho (factor 0.56): en ellas el grano del fondo, el grosor de las marcas menores y el tono exacto del bronce no se pueden afirmar con certeza.
2. **Hover no verificable.** `hoy-1440-hover.png` no muestra diferencia apreciable frente al estado normal. El equipo declara que es un límite de la herramienta de captura; lo acepto como límite, pero el estado hover queda **sin evidencia** y no suma puntos.
3. **Datos declarados por el equipo, que no puedo ver:** contraste del bronce de texto `#6F6140` = 6.07 sobre blanco y 5.42 sobre el fondo `#F3F2EE` (ambos por encima del 4.5 de AA); formularios sin sombra por regla de estilo; escala de "Hoy" en 1440 = 427 px. Los tomo como dato declarado. Dos de ellos coinciden con lo que veo: la escala mide unos 240 px en la captura reducida (≈ 430 px reales) y los formularios se ven planos junto a paneles de datos con sombra (`riesgo-1440-foco`, `diario-1440`).
4. **No hay captura de carga** en esta ronda: el salto de la página al pasar de esqueleto a dato no se puede juzgar.
5. **"Mercado cerrado" no se implementó** (declarado por el equipo).

## 1. Estado de los 6 pendientes de la ronda 2

| # | Pendiente | Estado | Qué veo y dónde |
|---|---|---|---|
| 1 | Que la firma se vea en 1440 | **Resuelto** | `hoy-1440`, `hoy-1440-medidores`: los medidores pasaron a una sola columna de cuatro paneles anchos; la escala ocupa casi todo el ancho del panel (≈ 430 px reales), con marcas mayores en los extremos y el centro, menores intermedias e índice triangular en bronce. Apalancamiento ya está dibujado en la misma escala (índice cerca del 9). Zona de valor dibuja el rango como tramo bronce y el precio como índice fuera del tramo: se entiende "debajo" sin leer. Costo sigue en "N/D" sin escala: correcto. Las notas ya no se parten en tres o cuatro renglones. Reserva: a esta reducción las marcas menores siguen muy tenues. |
| 2 | Mostrar lo que faltaba por ver | **Parcial** | Radar con escaneo real: visto (`radar-1440-escaneado`). Resultado de "Probar mi idea": visto, dos casos (`probar-1440-resultado`, `probar-1440-pocas-operaciones`). Inicio de sesión: visto (`login-1440`). Foco por teclado: visto, contorno bronce de 2 px con esquinas redondeadas sobre "Probar mi idea" (`riesgo-1440-foco`, y también en `radar` y `diario`). **Hover: sin evidencia. Mercado cerrado: no implementado.** Nota: ninguna de las pantallas nuevas inventa un motivo distinto (bien), pero tampoco usan la escala; Radar y Probar muestran cifras escritas, no dibujadas. |
| 3 | Terminar el gráfico | **Parcial (casi resuelto)** | Resuelto: la banda de la zona de valor ahora se ve con claridad en 1440, 768 y 390; la cifra superior del eje ya no se corta (`hoy-1440`, `hoy-768`, `hoy-390`); el cierre de la leyenda va en tinta. Queda: la cifra inferior del eje sale cortada contra el eje de fechas en `hoy-1440-medidores` ("56,000.00" a medias); la última fecha sigue cortada en móvil al desplazar ("16 no", `hoy-390-medidores`), y la primera también ("nov"); la etiqueta del último precio se monta sobre la cifra del eje que tiene detrás (`hoy-768`, `hoy-390`). |
| 4 | Diario: menos cajas, una que mande | **Resuelto** | `diario-1440`, `diario-390`: "Esta semana" y "Abiertas" son ahora renglones sin caja con un filete; "Últimos 30 días" manda, con tres cifras grandes en mono (1, −1.00 R, 100 %); la tabla de cerradas queda subordinada. De cinco cajas a tres. |
| 5 | "Salir" y el intervalo activo | **Resuelto** | "Salir" es un botón de contorno legible, bajo la navegación en escritorio y en la línea de la marca en 768 y 390; ya no queda huérfano. El intervalo activo "1h" lleva fondo tenue y peso 600: el negro queda reservado a la acción principal ("Escanear mercados"). |
| 6 | Medir, no suponer | **Parcial** | Contraste: medido y dentro de AA (dato declarado). Formularios sin sombra: declarado y coincide con lo que veo. Altura de esqueletos: sin captura, no verificable. Fecha del último escaneo en el Radar: aparece la hora ("01:36 UTC") tras escanear, sin fecha, y no hay captura del reposo. |

**Resumen:** 3 resueltos (1, 4, 5) y 3 parciales (2, 3, 6). Ninguno queda en "no". Lo parcial es acabado y evidencia, no rumbo.

## 2. Lista negra: **LIMPIA**

| Ítem | Estado | Evidencia |
|---|---|---|
| 5. Tarjetas idénticas en fila | Pasa | Los cuatro medidores de `hoy-1440` son ahora una columna de paneles de alto distinto y contenido distinto (escala, N/D, rango, escala). Las tiras de cuatro cifras de Radar y Probar no llevan ícono ni son tarjetas separadas. |
| 7. Todo en tarjetas | Pasa | `diario-1440`: los vacíos salieron de las cajas. Título, aviso, "En palabras" y "Fuentes y método" van sin caja. La observación de la ronda 2 queda cerrada. |
| 9. Sombra idéntica en todo | Pasa | Los formularios (Riesgo, "Mis reglas") se ven planos y los paneles de datos con sombra corta (`riesgo-1440-foco`, `diario-1440`); coincide con lo declarado. La duda de las rondas 1 y 2 queda cerrada, con la salvedad de la reducción. |
| 21. Hover que levanta todo | No verificable | Sin evidencia de hover. No lo marco presente: no lo vi. |
| 1, 2, 3, 4, 6, 8, 10–20 | Limpio | Sin morado, sin vidrio, un solo acento, radios moderados, Plex, sin emojis, sin texto de relleno, marca propia. |

## 3. Rúbrica

| Criterio | R1 | R2 | Ronda 3 | Evidencia |
|---|---|---|---|---|
| Originalidad / firma (crítico) | 11 | 14 | **16 / 20** | Tapando el logo, `hoy-1440` ya se reconoce: precio en mono, banda de valor sobre el gráfico y una columna de cuatro escalas graduadas con índice. Riesgo repite el motivo. No sube más porque Radar y Probar, que son donde el producto entrega su resultado, son pantallas limpias pero sin firma: tapando el logo podrían ser de otro producto sobrio. |
| Tipografía (crítico) | 14 | 15 | **16 / 20** | Las tres cifras del Diario y el veredicto como titular ("No se distingue del azar", "Pocas operaciones") dan jerarquía real; las notas de los medidores ya caben en un renglón. Persiste el amontonamiento de etiqueta, pastilla de estado y nota en dos tamaños casi iguales dentro de cada panel. |
| Composición (crítico) | 12 | 15 | **16 / 20** | "Hoy", Riesgo, Probar y Diario tienen una cosa que manda. Fallan: el Radar tras escanear deja más de media pantalla vacía y no muestra qué revisó (`radar-1440-escaneado`); en 1440 la columna de medidores es más alta que el gráfico y deja una franja blanca muerta bajo la nota del gráfico (`hoy-1440-medidores`). |
| Color | 9 | 11 | **13 / 15** | Paleta cerrada y tibia; el bronce por fin aparece donde debe (índices, tramo de la zona de valor, banda, foco, miga) sin dejar de ser escaso; contraste AA medido (declarado). El rojo queda en estado real. Resta: el botón "Entrar" en gris medio, un tono que no es ni tinta ni estado claro. |
| Imagen | 7 | 11 | **12 / 15** | El gráfico es propio y la banda se lee; las escalas ya son imagen. Restan los cortes que quedan en el eje (cifra inferior en 1440, fechas en 390 desplazado) y la etiqueta del precio montada sobre el eje. |
| Detalle y acabado | 5 | 6 | **7 / 10** | Suma el foco diseñado y visto, "Salir" y el intervalo. Restan: hover sin evidencia; fecha cortada en 390 (la rúbrica pide "nada roto en 390"); el Radar muestra los códigos crudos del proveedor ("EURUSD=X"); una marca negra suelta sobre la esquina del panel "Zona de valor" en `hoy-1440` (no aparece en las otras capturas: puede ser un defecto de la captura; verificar). |
| **Total** | 58 | 72 | **80 / 100** | Umbral: 80 y ningún crítico bajo 12. **Alcanza el umbral, justo.** Críticos en 16, 16 y 16. |

El 80 es exacto y sin margen: lo sostienen los tres criterios críticos, no el acabado. Si los pendientes menores de abajo se dejan sin cerrar, el diseño no retrocede, pero tampoco tiene colchón.

### Las tres preguntas

1. **Sin leer el texto, ¿sector y sensación?** Finanzas; herramienta de medición serena y precisa. "Instrumento" ya se cumple en "Hoy" y Riesgo, en escritorio y en móvil. "Caro" se cumple en esas dos pantallas; Radar y Probar se ven correctas, no caras.
2. **¿Parecido con las anti-referencias?** (1) App de señales cripto con neón: ninguno. (2) SaaS de cuatro tarjetas iguales: ninguno ya en "Hoy" ni en el Diario; queda un eco leve en las tiras de cuatro cifras de Radar y Probar, sin íconos ni color. (3) TradingView saturado: ninguno.
3. **¿Qué quitaría?** La franja blanca vacía bajo el gráfico en 1440: o el gráfico crece hasta la altura de los medidores, o el panel termina donde termina su contenido.

## 4. Pendientes menores (máximo 5)

Ninguno exige otra ronda de auditoría (no queda ninguna); se pueden cerrar y mostrar al dueño en capturas.

| # | Pendiente | Concreto |
|---|---|---|
| 1 | **Últimos cortes del gráfico** | Margen inferior para la cifra más baja del eje en 1440; que la primera y la última fecha no se corten en 390; que la etiqueta del último precio tape por completo la cifra del eje que tiene detrás; y que el gráfico llene su panel en 1440. |
| 2 | **Radar tras escanear** | Mostrar la retícula de mercados revisados con su estado (como en reposo), fecha además de hora, nombres legibles en vez de "EURUSD=X", y el motivo de los que faltan ("mercado cerrado" o "el proveedor no respondió"). Con eso se cubre también el indicador de mercado cerrado que no se hizo. |
| 3 | **Resultado de Probar, dibujado** | El intervalo de la R media (−0.217 a +0.250) pide la escala de firma con el cero marcado: es la misma idea que la Zona de valor. Además, observación de lectura, no de cálculo: "Azar igual o mejor 0.5 %" junto al veredicto "No se distingue del azar" puede leerse como contradicción por alguien no técnico; conviene una frase que lo aclare. |
| 4 | **Botón "Entrar"** | En tinta plena como "Escanear mercados". Si el gris es el estado "campo vacío", mostrar una captura con la contraseña escrita para comprobar el estado activo. |
| 5 | **Evidencia que se debe** | Hover de los paneles de datos (aunque sea con una foto de pantalla), paso de esqueleto a dato sin salto, y confirmar que la marca negra sobre "Zona de valor" en `hoy-1440` es de la captura y no de la página. |

## 5. Veredicto

**Aprobado con cambios.** Lista negra limpia, 80/100 (umbral 80) y ningún criterio crítico bajo 12 (16, 16 y 16). La dirección de la DEC-V02 con su Enmienda 1 queda validada: en tres rondas pasó de 58 a 72 a 80, y lo que subió fue lo de fondo (firma, composición, color), no solo el pulido. No corresponde volver a la Fase 0.

"Con cambios" significa: los cinco pendientes menores se cierran antes de congelar el diseño. Según la rúbrica, la aprobación final además exige la **aprobación del dueño sobre capturas** y el registro del diseño como **congelado** en la documentación; eso no lo decide el auditor.

```
AUDITORÍA VISUAL — Quant Monitor (web) — 2026-11-15 — Ronda 3
Auditor: agente independiente (distinto del diseñador)
Lista negra: LIMPIA (ítem 21 no verificable: sin evidencia de hover)
Puntajes: Originalidad 16/20 · Tipografía 16/20 · Composición 16/20 · Color 13/15 · Imagen 12/15 · Detalle 7/10 = 80/100
Preguntas: 1) finanzas, instrumento de medición sereno y preciso; "caro" en Hoy y Riesgo, no en Radar ni Probar 2) señales cripto: ninguno; cuatro tarjetas: eco leve en las tiras de cifras; TradingView saturado: ninguno 3) la franja blanca vacía bajo el gráfico en 1440
Veredicto: APROBADO CON CAMBIOS: últimos cortes del eje del gráfico; Radar tras escanear con retícula, fecha, nombres legibles y motivo de lo que falta; intervalo de R dibujado en la escala; botón "Entrar" en tinta; evidencia de hover y de carga sin salto.
```

## Cierre de los pendientes menores de la ronda 3 (2026-11-16, equipo)

Capturas en `docs/diseno/capturas-web/cierre/`.

1. **Eje del gráfico:** las cifras que no caben enteras ya no se dibujan (`entireTextOnly`), y el gráfico llena su panel. Las fechas de los extremos en teléfono siguen dependiendo de la librería.
2. **Radar después de escanear:** muestra cada mercado revisado con su estado ("normal", "aviso" o "sin datos"), nombres legibles, fecha y hora, y el motivo de los que faltan. Si es fin de semana, lo dice.
3. **Probar mi idea:** el intervalo de la R media se dibuja en la escala de firma, con el cero en la marca central. Una frase aclara por qué superar al azar no basta si el intervalo cruza el cero.
4. **Botón "Entrar":** siempre en tinta. Si la contraseña está vacía, se avisa al pulsarlo.
5. **Evidencia:**
   - El efecto al pasar el cursor sigue sin poder capturarse con la herramienta.
   - La marca negra suelta no reapareció en las capturas siguientes.
   - El paso de las siluetas de carga al dato no se volvió a medir.
