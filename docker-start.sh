#!/bin/bash
set -e

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║     OpenCode Evolved — Iniciando en Docker   ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# ── 1. Xvfb ───────────────────────────────────────────────────────────────────
echo "[1/6] Iniciando pantalla virtual (Xvfb)..."
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
sleep 2
echo "  → Xvfb listo"

# ── 2. x11vnc ─────────────────────────────────────────────────────────────────
echo "[2/6] Iniciando VNC..."
x11vnc -display :99 -nopw -listen localhost -xkb -forever -quiet 2>/dev/null &
sleep 1
echo "  → VNC listo en :5900"

# ── 3. noVNC ──────────────────────────────────────────────────────────────────
echo "[3/6] Iniciando noVNC..."
websockify --web=/usr/share/novnc/ 0.0.0.0:6080 localhost:5900 >/dev/null 2>&1 &
sleep 1
echo "  → noVNC listo en :6080"

# ── 4. OpenCode Engine ────────────────────────────────────────────────────────
echo "[4/6] Iniciando OpenCode Engine..."
OPENCODE_PORT=${OPENCODE_PORT:-21294}

# Detectar binario: primero local, luego global
if [ -f "/app/bin/opencode" ] && [ -x "/app/bin/opencode" ]; then
  OPENCODE_BIN="/app/bin/opencode"
elif [ -f "/app/bin/opencode-linux" ] && [ -x "/app/bin/opencode-linux" ]; then
  OPENCODE_BIN="/app/bin/opencode-linux"
elif command -v opencode >/dev/null 2>&1; then
  OPENCODE_BIN="opencode"
else
  echo "  ⚠  OpenCode no encontrado — saltando engine (solo proxy+operator)"
  OPENCODE_BIN=""
fi

if [ -n "$OPENCODE_BIN" ]; then
  "$OPENCODE_BIN" serve --port $OPENCODE_PORT &
  echo "  → Esperando OpenCode en :$OPENCODE_PORT..."
  for i in $(seq 1 30); do
    if nc -z localhost $OPENCODE_PORT 2>/dev/null; then
      echo "  → OpenCode Engine listo"
      break
    fi
    sleep 1
  done
fi

# ── 5. Web Operator ───────────────────────────────────────────────────────────
echo "[5/6] Iniciando Web Operator..."
cd /app/web-operator
OPERATOR_PORT=${OPERATOR_PORT:-3001} node api-server.js &
cd /app
sleep 2
echo "  → Web Operator listo en :${OPERATOR_PORT:-3001}"

# ── 6. Proxy ──────────────────────────────────────────────────────────────────
echo "[6/6] Iniciando Proxy Web UI..."
cd /app/artifacts/opencode-ui
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
echo "  ║  Web UI:    http://TU_DOMINIO                ║"
echo "  ║  VNC:       http://TU_DOMINIO:6080/vnc.html  ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

wait
