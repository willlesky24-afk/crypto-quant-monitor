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
