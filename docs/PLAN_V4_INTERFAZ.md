# Plan: interfaz propia (opción 3)

**Objetivo:** reemplazar la interfaz de Streamlit por una propia, con el aspecto que se busca, sin tocar el motor de cálculo en Python.

## Arquitectura propuesta

```
Navegador (PC o teléfono)
   └── Interfaz web: React + TypeScript (Vite), tokens de DEC-V01
         └── API HTTP: FastAPI (ya existe en src/operator_api)
               └── Motor actual en Python: datos, cálculo, verificador, IA
```

- **Un solo servicio:** FastAPI sirve la API y también la interfaz ya compilada. Se arranca con un comando y funciona igual en tu PC, en tu teléfono (por Tailscale) o en la nube más adelante.
- **El motor no se toca:** la API llama a las mismas funciones que hoy usa Streamlit, con las mismas pruebas.
- **Gráfico de velas:** `lightweight-charts`, librería de código abierto de TradingView (licencia Apache 2.0).
- **Teléfono:** diseño adaptable desde el inicio; después se puede instalar como app web (PWA) sin tiendas.
- **Seguridad:** la API ya tiene control por clave; las claves de proveedores siguen solo en el servidor, nunca en el navegador.

Por qué React + Vite y no Next.js: no necesitamos servidor de páginas, la interfaz es una app de datos. Vite compila a archivos estáticos que FastAPI sirve, y eso evita un segundo servidor.

## Fases

| Fase | Entrega | Listo cuando |
|---|---|---|
| **1. API** | Endpoints `hoy`, `riesgo`, `radar`, `verificar`, `metodos`, `explicar` | Pruebas de cada endpoint contra los cálculos actuales |
| **2. Base visual** | Proyecto React con tokens, retícula y componentes (ficha, cifra, escala, tabla) | Página de muestra auditada con la skill |
| **3. Pantalla Hoy** | Hoy completa con gráfico de velas | Mismos números que Streamlit, capturas aprobadas por ti |
| **4. Resto** | Mi riesgo, Probar mi idea, Radar, Copiloto | Paridad con Streamlit |
| **5. Teléfono y cierre** | PWA, prueba en tu teléfono, retirar Streamlit | Tu aprobación |

Streamlit sigue funcionando hasta la fase 5; no se rompe nada mientras tanto.

## Riesgos

- **Tiempo:** es el trabajo más grande desde el motor. Cada fase se entrega y se aprueba por separado.
- **Dos lenguajes:** el proyecto pasa a tener Python y TypeScript; las pruebas de la interfaz serán nuevas (Vitest y Playwright).
- **Datos locales:** el verificador sigue usando la historia guardada en tu PC; para la nube habrá que resolverlo aparte.
- **Diseño:** sin los límites de Streamlit, la dirección visual puede ir más lejos. Se decide antes de la fase 2.
