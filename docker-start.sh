#!/bin/bash
set -e

# ════════════════════════════════════════════════════════
#  OpenCode Evolved — Docker Start Script
#  Inicia: Xvfb + noVNC + OpenCode Engine + Web Operator + Proxy
# ════════════════════════════════════════════════════════

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║     OpenCode Evolved — Iniciando en Docker   ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# ── 1. Xvfb — Pantalla virtual (para que Chrome funcione sin monitor) ─────────
echo "[1/5] Iniciando pantalla virtual (Xvfb)..."
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
sleep 2
echo "  → Pantalla virtual lista en DISPLAY=:99"

# ── 2. x11vnc — Servidor VNC (para poder ver la pantalla remotamente) ─────────
echo "[2/5] Iniciando VNC server..."
x11vnc -display :99 -nopw -listen localhost -xkb -noxrecord -noxfixes -noxdamage -forever &
sleep 1
echo "  → VNC listo en localhost:5900"

# ── 3. noVNC — Acceso a la pantalla por el navegador web ─────────────────────
echo "[3/5] Iniciando noVNC (acceso web)..."
websockify --web=/usr/share/novnc/ 0.0.0.0:6080 localhost:5900 &
sleep 1
echo "  → Acceso remoto disponible en http://TU_SERVIDOR:6080/vnc.html"

# ── 4. OpenCode Engine ────────────────────────────────────────────────────────
echo "[4/5] Iniciando OpenCode Engine..."
OPENCODE_PORT=${OPENCODE_PORT:-21294}
/app/bin/opencode-linux serve --port $OPENCODE_PORT &
OC_PID=$!
echo "  → Esperando OpenCode en :$OPENCODE_PORT..."
for i in $(seq 1 20); do
  if nc -z localhost $OPENCODE_PORT 2>/dev/null; then
    echo "  → OpenCode Engine listo"
    break
  fi
  sleep 1
done

# ── 5. Web Operator ───────────────────────────────────────────────────────────
echo "[5/5] Iniciando Web Operator..."
cd /app/web-operator
OPERATOR_PORT=${OPERATOR_PORT:-3001} node api-server.js &
cd /app
sleep 2
echo "  → Web Operator listo en :${OPERATOR_PORT:-3001}"

# ── 6. Proxy / Web UI ─────────────────────────────────────────────────────────
echo "[6/6] Iniciando Proxy Web UI..."
cd /app/artifacts/opencode-ui

# Exportar variables de entorno para el proxy
export PORT=${PORT:-21293}
export OPENCODE_PORT=${OPENCODE_PORT:-21294}
export OPERATOR_PORT=${OPERATOR_PORT:-3001}
export API_SERVER_PORT=${OPERATOR_PORT:-3001}

node proxy.mjs &
cd /app

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║          TODO LISTO EN EASYPANEL             ║"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║  Web UI:         http://TU_DOMINIO           ║"
echo "  ║  Pantalla VNC:   http://TU_DOMINIO:6080      ║"
echo "  ║  Web Operator:   http://TU_DOMINIO:3001      ║"
echo "  ║  OpenCode API:   http://localhost:21294      ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# Mantener el contenedor vivo
wait
