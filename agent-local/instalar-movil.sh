#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# OpenCode Mobile Agent - Instalador para Termux (Android)
# Conecta tu Móvil a OpenCode en EasyPanel
# ============================================================

echo ""
echo "============================================================"
echo "  OpenCode Mobile Agent - Instalador (Android)"
echo "============================================================"
echo ""

# 1. Actualizar repositorios e instalar dependencias
echo "[1/4] Instalando dependencias de Termux..."
pkg update -y
pkg install -y nodejs termux-api curl jq

# 2. Configurar almacenamiento
echo "[2/4] Solicitando acceso al almacenamiento..."
termux-setup-storage
sleep 2

# 3. Descargar el agente
echo "[3/4] Descargando el agente..."
mkdir -p ~/.opencode-agent
cd ~/.opencode-agent

# NOTA: Cuando subas esto a github, asegúrate de que la URL apunte al archivo raw
# Para probar ahora, si tienes esto en local, tendrás que subirlo o copiarlo manualmente a termux.
# Por defecto lo bajará de tu repo de GitHub (asumiendo rama main).
AGENT_URL="https://raw.githubusercontent.com/daveymena162-alt/opencode-/main/agent-local/mobile-agent.mjs"

curl -fsSL -o mobile-agent.mjs "$AGENT_URL"

# 4. Instalar ws (WebSocket)
echo "[4/4] Instalando paquetes de Node.js..."
npm init -y >/dev/null 2>&1
npm install ws --silent

# 5. Pedir la URL del servidor
echo ""
echo "============================================================"
echo "  Configuración del Servidor"
echo "============================================================"
echo "  Ingresa la URL de tu OpenCode en EasyPanel."
echo "  Ejemplo: https://opencode.midominio.com"
echo ""

if [ -n "$1" ]; then
    SERVER_URL="$1"
    echo "  URL configurada automáticamente: $SERVER_URL"
else
    read -p "  URL del servidor: " SERVER_URL
fi

if [ -z "$SERVER_URL" ]; then
    echo "  [ERROR] La URL no puede estar vacía."
    exit 1
fi

cat <<EOF > config.json
{
  "serverUrl": "$SERVER_URL",
  "agentName": "Android-$(whoami)",
  "agentId": null,
  "reconnectDelay": 5000
}
EOF

# 6. Crear comando rápido de inicio
echo "node ~/.opencode-agent/mobile-agent.mjs" > ~/iniciar-agente.sh
chmod +x ~/iniciar-agente.sh

echo ""
echo "============================================================"
echo "  ✅ INSTALACIÓN COMPLETADA"
echo "============================================================"
echo "  Para iniciar el agente manualmente, escribe:"
echo "    ./iniciar-agente.sh"
echo ""
echo "  ¿Deseas iniciarlo ahora? (s/n)"
read -p "  " INICIAR

if [ "$INICIAR" = "s" ]; then
    echo "  Iniciando... (El teléfono vibrará si se conecta)"
    ./iniciar-agente.sh
fi
