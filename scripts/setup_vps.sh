#!/usr/bin/env bash
# ==============================================================================
# Crypto Quant Monitor — 1-Click Ubuntu VPS Cloud Deployment Script
# ==============================================================================
set -e

echo "========================================================"
echo "🚀 Instalando Crypto Quant Monitor en la Nube (VPS)"
echo "========================================================"

# 1. Update system & install prerequisites
echo "📦 [1/4] Actualizando sistema e instalando herramientas básicas..."
sudo apt-get update && sudo apt-get install -y curl git ufw

# 2. Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "🐳 [2/4] Instalando Docker y Docker Compose..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
else
    echo "✅ [2/4] Docker ya está instalado."
fi

# 3. Setup firewall
echo "🛡️ [3/4] Configurando firewall (puertos 22 SSH, 80 HTTP, 443 HTTPS, 8501 Dashboard)..."
sudo ufw allow 22/tcp || true
sudo ufw allow 80/tcp || true
sudo ufw allow 443/tcp || true
sudo ufw allow 8501/tcp || true

# 4. Check for .env file
if [ ! -f .env ]; then
    echo "⚙️ [4/4] Creando .env inicial desde .env.example..."
    cp .env.example .env
    echo "⚠️ Por favor, edita el archivo .env con tu GEMINI_API_KEY:"
    echo "   nano .env"
fi

echo "========================================================"
echo "✅ Servidor listo. Para iniciar el sistema:"
echo "   docker compose up -d"
echo ""
echo "Podrás entrar desde tu teléfono a:"
echo "   http://TU_IP_DEL_VPS:8501"
echo "========================================================"
