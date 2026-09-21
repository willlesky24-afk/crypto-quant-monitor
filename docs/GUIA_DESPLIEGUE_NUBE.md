# ☁️ Guía Paso a Paso: Desplegar Crypto Quant Monitor en la Nube

Con esta guía tendrás tu **Copiloto de Trading activo las 24 horas del día, los 7 días de la semana**, sin necesidad de tener tu ordenador encendido, y accesible desde tu teléfono móvil o cualquier parte del mundo.

---

## 🏆 1. Dónde alojarlo (Opciones Recomendadas)

Para ejecutar el monitor cuantitativo y el copiloto de Gemini, recomendamos un servidor virtual (**VPS**) con al menos **2 GB de RAM** y **1 o 2 vCPU**:

| Proveedor | Modelo Recomendado | Precio Aprox. | Ventajas |
| :--- | :--- | :--- | :--- |
| **Hetzner Cloud** *(Opción #1 recomendada)* | **CX22** (Ubuntu 24.04) | ~**3,79 € / mes** | La mejor relación calidad/precio de Europa, servidores ultrarrápidos y excelente conexión con Binance. |
| **DigitalOcean** | **Basic Droplet** (2GB RAM) | ~**6,00 $ / mes** | Panel muy intuitivo para principiantes. |
| **OVHcloud / Vultr** | **Starter VPS** | ~**4,00 € / mes** | Muy estable y económico. |

---

## 🚀 2. Despliegue en 5 Pasos en tu Servidor (Ubuntu / Debian)

### Paso 1: Crea tu servidor VPS
1. Crea una cuenta en [Hetzner](https://www.hetzner.com/cloud) o [DigitalOcean](https://www.digitalocean.com/).
2. Crea un nuevo servidor seleccionando:
   - **Sistema Operativo**: `Ubuntu 24.04 LTS` o `Ubuntu 22.04 LTS`.
   - **Tamaño**: Mínimo 2 GB RAM (ej. CX22 en Hetzner).
   - **Ubicación**: Cualquiera (Falkenstein, Nuremberg o Frankfurt son ideales).
3. Copia la **dirección IP pública** que te asigne el proveedor (ejemplo: `65.108.12.34`).

---

### Paso 2: Conéctate a tu servidor desde tu ordenador
Abre PowerShell o la Terminal en tu ordenador y escribe:
```bash
ssh root@TU_IP_DEL_SERVIDOR
```
*(Introduce la contraseña que te haya enviado tu proveedor por correo o tu clave SSH).*

---

### Paso 3: Descarga el proyecto y ejecuta el instalador automático
Una vez dentro de la terminal de tu servidor, clona tu repositorio o copia la carpeta del proyecto:
```bash
git clone https://github.com/TU_USUARIO/crypto_quant_monitor.git
cd crypto_quant_monitor
```

Ahora ejecuta el script automatizado que hemos creado para configurar todo de un solo golpe:
```bash
chmod +x scripts/setup_vps.sh
./scripts/setup_vps.sh
```
*Este script instalará Docker, Docker Compose y configurará el firewall del servidor automáticamente.*

---

### Paso 4: Configura tus claves en el archivo `.env`
Abre el archivo de configuración con el editor nano:
```bash
nano .env
```
Busca la línea de Gemini y añade tu clave de Google AI Studio:
```env
AI_PROVIDER=gemini
GEMINI_API_KEY=AIzaSyTuClaveDeGeminiAqui
GEMINI_MODEL=gemini-2.5-flash
SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT
TIMEFRAME=1h
```
*(Para guardar en nano pulsa `Ctrl + O`, luego `Enter`, y para salir pulsa `Ctrl + X`).*

---

### Paso 5: ¡Inicia tu Copiloto en la Nube!
Ejecuta el siguiente comando:
```bash
docker compose up -d
```
Verás cómo Docker levanta los tres servicios en segundo plano:
1. `crypto_quant_market_worker` (capturando velas de Binance 24/7).
2. `crypto_quant_operator_api` (API gateway segura).
3. `crypto_quant_dashboard` (interfaz visual Streamlit).

---

## 📱 3. Cómo abrirlo en tu Teléfono Móvil

¡Ya está funcionando en la nube! 

1. Abre el navegador de tu teléfono (**Safari** en iPhone, **Chrome** en Android).
2. Escribe en la barra de direcciones:
   ```text
   http://TU_IP_DEL_SERVIDOR:8501
   ```
   *(Sustituye `TU_IP_DEL_SERVIDOR` por la IP de tu VPS, ej: `http://65.108.12.34:8501`).*
3. ¡Listo! Ya tienes acceso desde cualquier lugar del mundo (con Wi-Fi o datos móviles 4G/5G).

> [!TIP]
> **Crear acceso directo tipo App**: En tu móvil, pulsa en el menú del navegador y selecciona **"Añadir a pantalla de inicio"**. Tendrás el icono de tu Copiloto en la pantalla de tu móvil como una app nativa.

---

## 🔒 4. Opcional: Añadir tu propio Dominio con Candado HTTPS (SSL Gratis)

Si quieres usar un dominio propio (por ejemplo: `https://copilot.midominio.com`) con certificado SSL automático y gratuito:

1. Ve a tu registrador de dominios (Cloudflare, Namecheap, GoDaddy, etc.) y crea un **registro tipo A**:
   - **Nombre**: `copilot` (o el subdominio que quieras)
   - **Valor**: La IP de tu servidor VPS
2. En tu servidor, edita el `.env`:
   ```bash
   DOMAIN=copilot.midominio.com
   ACME_EMAIL=tu_correo@gmail.com
   ```
3. Lanza el despliegue de producción con Caddy:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
Caddy generará automáticamente tu certificado HTTPS seguro de Let's Encrypt. Ahora podrás entrar a:  
👉 **`https://copilot.midominio.com`**

---

## 🛠️ 5. Comandos Útiles de Mantenimiento

- **Ver el estado de los servicios**:
  ```bash
  docker compose ps
  ```
- **Ver lo que está analizando el worker en tiempo real**:
  ```bash
  docker compose logs -f market-worker
  ```
- **Ver las consultas que hace el copiloto**:
  ```bash
  docker compose logs -f dashboard
  ```
- **Reiniciar el sistema**:
  ```bash
  docker compose restart
  ```
- **Detener el sistema**:
  ```bash
  docker compose down
  ```
