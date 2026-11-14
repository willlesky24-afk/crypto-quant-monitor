# Usar Quant Monitor en el teléfono

La app corre en tu computadora. El teléfono la abre por una red privada (Tailscale) que solo incluye tus dispositivos: nadie más en internet la ve.

## 1. Crea tu contraseña (una vez)

En la carpeta del proyecto:

```bash
.\.venv\Scripts\python.exe scripts\set_web_password.py
```

Pide la contraseña dos veces (no se ve al escribir; mínimo 12 caracteres). En `.env` solo se guarda su huella cifrada, nunca la contraseña. Ejecutarlo otra vez la cambia y cierra todas las sesiones abiertas.

Sin este paso la interfaz muestra "Falta crear la contraseña" y no entrega datos.

## 2. Arranca el servidor

```bash
.\.venv\Scripts\python.exe -m uvicorn src.operator_api.app:app --host 127.0.0.1 --port 8010
```

`127.0.0.1` significa que solo tu computadora lo ve directamente. Antes, compila la interfaz una vez con `npm run build` en la carpeta `web`.

## 3. Tailscale (para entrar desde el teléfono)

1. Crea una cuenta gratuita en tailscale.com e instala Tailscale en la computadora y en el teléfono, con la misma cuenta.
2. En la consola de Tailscale, en **DNS**, activa **MagicDNS** y **HTTPS Certificates**.
3. En la computadora:

   ```bash
   tailscale serve --bg 8010
   ```

   Te muestra una dirección del tipo `https://tu-pc.nombre.ts.net`. Esa dirección solo funciona en tus dispositivos de Tailscale.

## 4. Instálala en el teléfono

- **Android (Chrome):** abre la dirección, entra con tu contraseña, menú ⋮ → **Instalar app**.
- **iPhone (Safari):** abre la dirección, botón Compartir → **Agregar a inicio**.

Queda un ícono con la moneda ₿. La sesión dura 7 días.

## Qué protege y qué no

- Sin sesión, ningún dato sale del servidor. Tras 5 contraseñas incorrectas, ese dispositivo espera 15 minutos.
- La app instalada no guarda precios: sin conexión muestra un error, nunca un precio viejo como si fuera actual.
- **No abras el puerto 8010 a internet** (por ejemplo con `tailscale funnel` o abriendo puertos en el router). Las rutas antiguas del operador (`/api/...` fuera de `/api/v1`) siguen protegidas solo por la clave de API, que en la configuración actual está desactivada.
