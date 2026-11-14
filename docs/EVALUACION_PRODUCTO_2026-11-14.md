# Evaluación de producto: Quant Monitor

**Fecha:** 2026-11-14. **Alcance:** producto y método, no estética (eso ya está en `docs/diseno/auditoria-fable-2026-11-14.md`).
**Base:** documentos del repo, código de `src/` (verificador, radar, estrés, tamaño de posición, agente, API web), capturas de fase 5 y búsqueda web de hoy. Los precios de terceros vienen casi todos de páginas comparadoras, no de las tarifas oficiales: tómalos como orden de magnitud.

**Veredicto corto:** el giro de "señales" a "riesgo y verificación" es correcto y poco común. Como herramienta personal está bien encaminada pero incompleta (no registra lo que haces). Como negocio, hoy no tiene un producto vendible. **Dirección: 6,5/10.**

---

## 1. Qué es realmente

**Un panel personal de preparación antes de operar (contexto del mercado + tamaño de posición) con un verificador escéptico de reglas simples.**

Categoría: analítica para trader minorista discrecional, subcategoría "riesgo pre-operación y validación de estrategias". No es terminal de datos, ni screener, ni plataforma de backtesting general, ni diario de trading.

## 2. ¿Dirección correcta?

**Sí en el giro; todavía no en el producto.**

### Fortalezas reales

- **La evidencia v3.0 es el mejor activo del proyecto.** Protocolo fijado antes, criterio de corte respetado, período 2025–2026 sin tocar, limitaciones y hasta una exposición accidental declaradas. Casi nadie en el mercado minorista publica un resultado negativo propio.
- **El verificador nunca dice "funciona".** Sus veredictos son "pierde", "no se distingue del azar" o "merece más estudio". Incluye costos, control con entradas al azar y un listón que sube con cada intento.
- **La IA está enjaulada de verdad.** Traduce a una lista cerrada de reglas y su explicación solo se muestra si todas las cifras salieron del motor y no hay palabras de acción (`idea_agent.py`). Es un diseño serio.
- **"Mi riesgo" es correcto y útil:** tamaño por % de riesgo, costos dentro de la pérdida, aviso de que el stop no es garantía.
- **Datos faltantes se muestran como N/D**, no se rellenan.

### Debilidades y riesgos de método

**Verificador ("Probar mi idea")**

1. **No prueba "mi idea": prueba una de 8 reglas del proyecto** con tus stops. Soportes, patrones, varios marcos de tiempo o noticias no caben. El nombre promete más de lo que hay.
2. **Casi no puede decir que sí (poca potencia).** Estimación mía, no del código: con stop 2 ATR y objetivo 6 ATR la dispersión por operación ronda 1,7 R; con 100 operaciones el intervalo al 95 % mide unos ±0,34 R, y en el intento 10 unos ±0,49 R. Una ventaja minorista realista es de 0,05–0,10 R. Resultado: casi todo saldrá "no se distingue", y el usuario puede leerlo como "no sirve" cuando solo significa "no hay datos suficientes para saber". Falta mostrar el **efecto mínimo detectable**.
3. **El contador de intentos vive en memoria** (`web_router.py`, `_attempts`): se reinicia al reiniciar el servidor y cuenta por dispositivo. La corrección por intentos se evade sin querer. Además Bonferroni sin tope lleva la potencia a cero: tras decenas de intentos nada puede pasar.
4. **El 20 % reservado no se usa nunca.** Solo se informa cuántas velas quedaron. "Merece más estudio" no tiene siguiente paso.
5. **Control al azar débil:** 8 corridas con entrada a cara o cruz en cada vela, comparando contra la mejor. No iguala el número de operaciones de la regla y 8 corridas no dan un valor p.
6. **El intervalo trata las operaciones como independientes.** En mercados con regímenes, eso lo hace más estrecho de lo debido.
7. **Los datos terminan lejos de hoy:** se corta en 2025-01-01 y se explora el primer 80 %, así que la prueba acaba aproximadamente a mediados de 2024. Dice poco del mercado de noviembre de 2026.
8. **La historia en dólares es lo que el usuario recordará** ("con $1.000 habrías terminado con…"). Según el docstring de `evidence_evaluation.py`, el motor compromete el 100 % del capital por operación; eso contradice el 1 % de "Mi riesgo". La cifra más persuasiva no corresponde a cómo operarías.

**Radar**

1. **En la práctica es un detector de récords.** Con unas 65 pruebas el umbral queda cerca de 0,0008; con 2.100 velas, solo avisa si el valor actual es casi el más extremo de toda la ventana (unos 3 meses en 1h). Conviene decirlo así.
2. **"Casos parecidos" son pocos y sin intervalo.** "3 de 7 con movimiento grande; lo normal es 12 %" se leerá como predicción. Tras una compresión, un movimiento grande es en parte el agrupamiento normal de la volatilidad.
3. **Explosividad (BSADF):** parámetros aún con `[VERIFICAR]`, valores críticos de caminatas gaussianas (las colas gordas de cripto inflan falsos positivos) y aplicada a velas de 1h, donde "burbuja" es un concepto dudoso.
4. **No es un radar si hay que pulsar un botón.** Sin aviso automático y sin dirección, su utilidad diaria es baja.

**Hoy**

- El costo de operar sale **N/D en Binance**, su mercado principal.
- La volatilidad se compara con las últimas 300 velas (12 días en 1h): memoria corta.
- Régimen y zona de valor son los mismos indicadores que en v3.0 no mostraron ventaja. Como "contexto" son legítimos, pero "Debajo" de la zona de valor se leerá como señal.

**Producto**

- **No sabe nada de lo que el dueño hace.** No registra planes ni operaciones. El fracaso minorista es sobre todo de conducta (tamaño, sobreoperar, saltarse el plan) y eso no se toca.
- **Disciplina sin ventaja es perder despacio.** El valor honesto es: descartar ideas malas barato, no sobredimensionar y operar menos. Es real, pero hay que decirlo así.
- **Se pulió antes de validar.** El plan pedía probar con 5–10 traders antes de la v4; no encontré evidencia de esa prueba y sí tres interfaces, intro animada y PWA.
- **Documentos contradictorios.** `README.md` aún describe v2.3 con "generación de señales"; `MANUAL_RAPIDO_USUARIO.md` habla de Quant Score, "oportunidad de alta confianza" y de preguntarle a la IA si "es buen momento para entrar". Siguen en el repo los módulos de señales y puntuación. Si esto se comparte, desmiente el posicionamiento.

## 3. Comparación con el mercado

| Herramienta | Qué ofrece | Precio aprox. | Tienen ellos y aquí no | Tiene Quant Monitor y ellos no |
|---|---|---|---|---|
| **TradingView** | Gráficos, Pine Script, backtest, alertas, miles de mercados | Gratis; ~$13–60/mes anual; Ultimate ~$200 | Todo lo gráfico, alertas, cualquier regla programable, comunidad | Control al azar, penalización por intentos, negativa a decir "funciona" |
| **Koyfin** | Datos fundamentales y macro, paneles | Gratis; ~$39–79/mes | Fundamentales, cobertura, noticias | Nada comparable: otra categoría |
| **Finviz** | Screener y mapas de acciones | Gratis; Elite ~$39,50/mes | Screener amplio, backtest en Elite | Otra categoría |
| **TrendSpider** | Análisis técnico automático, backtest sin código, bots | ~$39–99/mes | Reglas libres sin código, alertas, escáner | Escepticismo estadístico por defecto |
| **QuantConnect** | Backtesting profesional con código, datos, ejecución | Gratis; Researcher ~$84/mes | Rigor real, cualquier estrategia, datos amplios | Lenguaje llano, sin programar |
| **Composer** | Estrategias sin código con ejecución automática | ~$24–29/mes | Ejecución, constructor visual | No empuja a operar |
| **Portfolio Visualizer** | Backtest de carteras, factores, Monte Carlo | ~$360–660/año | Análisis de cartera a largo plazo | Otra categoría |
| **TradesViz / Tradervue / Edgewonk** | Diario de operaciones, estadísticas, disciplina | Gratis a ~$50/mes; Edgewonk ~$170–200/año | **Justo lo que aquí falta:** importación del broker, R por operación, revisión | Cálculo previo del tamaño y verificador |
| **StrategyQuant / Build Alpha** | Generación y pruebas de robustez (Monte Carlo, ruido) | Licencias de cientos a miles de USD | Robustez mucho más completa | Sencillez, español, sin promesa |
| **CoinGlass** | Derivados cripto: funding, interés abierto, liquidaciones | Gratis en web; API desde ~$29/mes | Apalancamiento de todo el mercado, en profundidad | La tarjeta de funding de aquí es un **duplicado inferior** |
| **Glassnode** | Datos on-chain | ~$49/mes; Professional ~$600–1.000/mes | On-chain | Nada |
| **Bloomberg / LSEG** | Techo profesional | ~$32.000/año por puesto | Todo | No aplica |

**Dónde es duplicado inferior, sin rodeos:** la pantalla Hoy frente a TradingView (gráfico, medias, perfil de volumen); el funding frente a CoinGlass; la calculadora de tamaño frente a calculadoras gratuitas y la herramienta de posición de TradingView; el radar frente a los escáneres de volatilidad existentes. **Donde no es duplicado:** el verificador, por su actitud, no por su alcance.

## 4. El diferencial defendible

**Existe y es uno solo: un verificador para no programadores cuyo resultado por defecto es el escepticismo**, con control al azar, penalización por intentos, datos reservados, lenguaje llano en español y una IA que no puede inventar cifras. Las herramientas minoristas venden lo contrario: curvas de capital atractivas sin prueba de significancia. Las profesionales lo hacen mejor, pero exigen programar o pagar licencias caras.

**¿Es suficiente?** Para uso personal, sí. Para un negocio, no por sí solo:

- Su respuesta habitual es "no". Es valiosa y difícil de vender.
- Hoy cubre 8 reglas y tiene los huecos de método del punto 2.
- Es copiable en semanas. Lo defendible no es el código sino la reputación de honestidad, y esa se construye publicando.

## 5. Para que le sirva al dueño

**Lo que usaría a diario:** "Mi riesgo" antes de cada operación y "Hoy" como vistazo de 30 segundos. "Probar mi idea" es ocasional. El radar, tal como está, casi nunca.

**Lo que falta, por prioridad:**

1. **Diario unido a "Mi riesgo".** Guardar el plan (entrada, stop, tamaño, motivo) con un toque, cerrar con el resultado y ver R por operación y cumplimiento del plan. Es la mayor carencia: sin esto no hay disciplina medible.
2. **Reglas de disciplina propias:** pérdida máxima diaria y semanal, riesgo abierto total, pausa tras N pérdidas, lista de comprobación previa.
3. **Revisión semanal automática** con cifras del diario: ¿respeté el tamaño?, ¿moví stops?, ¿cuánto costaron las comisiones?
4. **Arreglos del verificador:** intentos persistentes, efecto mínimo detectable a la vista, usar el 20 % reservado como confirmación de un solo uso, control al azar con igual número de operaciones y cientos de corridas, y tamaño por % de riesgo en la historia en dólares.
5. **Avisos automáticos** del radar y de condiciones (el canal de Telegram ya existe), sin la palabra "oportunidad".
6. **Spread real en cripto** para que "Costo de operar" no salga vacío.

**Lo que sobra:** la intro animada; los módulos de señales, Quant Score y motor predictivo; el copiloto de chat abierto; tres proveedores de IA; la explosividad en 1h mientras no se verifique; y los documentos viejos.

## 6. Para que genere valor sin vender ilusiones

| Camino | Obstáculo principal | Viabilidad honesta |
|---|---|---|
| **A. Herramienta personal + código abierto**, con el informe de evidencia como carta de presentación | Limpiar el código heredado; cero ingresos directos | **Alta** como reputación y aprendizaje; ingreso nulo |
| **B. Contenido y educación en español** ("probé 23 reglas populares con costos reales y ninguna pasó"), con la herramienta como laboratorio | Distribución: el público premia las promesas; la honestidad crece despacio | **Media** para audiencia, **baja-media** para ingresos |
| **C. SaaS pequeño: riesgo previo + diario + verificador**, quizá para traders en pruebas de fondeo, donde respetar límites de pérdida vale dinero | Mercado de diarios saturado y barato; licencias de datos; soporte; marco legal | **Baja-media.** Unos cientos de clientes ya sería un éxito; que pague tu tiempo es improbable |
| **D. Verificador para comunidades o academias** | Conflicto de interés: la mayoría vive de la ilusión que el verificador desmonta | **Baja** |

**Recomendación:** A ahora, B como experimento barato de demanda, y C solo si B demuestra que alguien lo quiere. Ir directo a C repetiría el error de construir antes de validar.

**Riesgos legales generales (no es asesoría legal):**

- **Recomendación personalizada.** En la UE, la recomendación personalizada es un servicio que exige licencia, y opinar en público sobre si un activo subirá puede contar como recomendación de inversión (ESMA). En EE. UU. existe la exclusión del editor (*Lowe v. SEC*) y la exención de la regla 4.14(a)(9) de la CFTC para software no personalizado, pero un software que da órdenes concretas de compra y venta puede tratarse como asesor (*CFTC v. Vartuli*). Mantenerse en cálculo e información, sin dirección ni instrumento sugerido, es la zona más segura. "Mi riesgo" usa el capital del usuario: revisarlo con abogado, como ya prevé el plan.
- **Licencias de datos.** Los términos de los datos descargables de Binance excluyen el uso comercial sin acuerdo aparte; no pude confirmar los de OANDA. El uso personal de hoy no equivale a permiso para revender.
- **Resultados hipotéticos.** Mostrar "habrías terminado con $X" a clientes suele exigir advertencias específicas.
- **Privacidad.** Con usuarios, sus textos irían a un proveedor de IA externo (DeepSeek): hay que declararlo.
- **Seguridad.** La guía ya advierte que hay rutas antiguas sin protección efectiva; no es publicable así.

## 7. Lo que NO hacer

- No reintroducir puntuaciones, "oportunidades", semáforos de compra ni rankings, aunque los pidan los usuarios.
- No publicar capturas de un "merece más estudio" como si fuera un hallazgo.
- No usar el período 2025–2026 hasta tener un método fijado; es irrecuperable.
- No dejar que la IA responda "¿es buen momento para entrar?".
- No cobrar por el radar como si anticipara movimientos.
- No añadir apalancamiento ni perpetuos a la calculadora sin modelo de liquidación.
- No usar testimonios de ganancias ni marketing de afiliados de brokers o exchanges: es el mismo conflicto de interés que el producto critica.
- No construir cuentas, suscripciones y nube antes de que 5–10 personas reales lo hayan usado.

## 8. Veredicto final

El giro es la decisión correcta y el rigor es real, pero el producto se queda antes de la operación y no acompaña la conducta, que es donde se pierde el dinero. Lo siguiente no es más interfaz: es el diario, las reglas de disciplina y reparar el verificador. Después, publicar la evidencia y medir si a alguien más le importa.

**Calificación de la dirección: 6,5/10.** Como herramienta personal de disciplina, 8 en intención y 6 en ejecución (falta el ciclo plan–operación–revisión). Como negocio, 4: diferencial real pero estrecho, difícil de vender, con datos y marco legal sin resolver. Sube a 8 si incorpora el diario, corrige la potencia y el contador del verificador, y valida con usuarios antes de construir más.

---

## Fuentes web

- TradingView: https://pricingsaas.com/companies/tradingview · https://www.cmcmarkets.com/en-gb/trading-platforms/tradingview/tradingview-pricing-explained
- Koyfin: https://koyfin.com/pricing
- Finviz: https://www.liberatedstocktrader.com/finviz-pricing-discounts/
- TrendSpider: https://chartinglens.com/blog/is-trendspider-worth-it
- QuantConnect: https://www.quantconnect.com/pricing.md
- Composer: https://www.composer.trade/learn/composer-vs-trendspider
- Portfolio Visualizer: https://pinklion.xyz/blog/portfolio-visualizer-alternatives/
- Diarios: https://www.stockbrokers.com/guides/best-trading-journals · https://www.tradesviz.com/tradesviz-vs-tradervue/
- StrategyQuant: https://strategyquant.com/doc/monte-carlo-tests/
- CoinGlass: https://coinglass.com/pricing · https://comparedge.com/tools/coinglass/pricing
- Glassnode: https://studio.glassnode.com/pricing · https://www.costbench.com/software/onchain-analytics/glassnode/
- Bloomberg: https://www.koyfin.com/blog/bloomberg-terminal-cost/
- CFTC regla 4.14(a)(9): https://www.cftc.gov/sites/default/files/foia/fedreg00/foi000310a.htm
- *Lowe v. SEC*: https://quimbee.com/cases/lowe-v-sec
- *CFTC v. Vartuli*: https://www.studicata.com/summaries/united-states-court-of-appeals-second-circuit/commodity-futures-trading-comn-v-vartuli-2000-5rf40f
- ESMA, advertencias a inversores y finfluencers: https://www.esma.europa.eu/investor-corner/warning-and-publications-investors · https://www.esma.europa.eu/sites/default/files/2026-01/ES_Spain_es_-_Finfluencers_factsheet.pdf
- Binance, términos de datos: https://data.binance.vision/Binance_Vision-Terms_of_Use.pdf

**Lo que no pude verificar:** tarifas oficiales de la mayoría de proveedores (salvo QuantConnect y Koyfin), precios de StrategyQuant y Build Alpha, términos de datos de OANDA y de la API pública de Binance, y si hubo pruebas con usuarios reales fuera del repo. La estimación de potencia del verificador es un cálculo aproximado mío, no una corrida del código.
