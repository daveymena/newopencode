#!/bin/bash
# ============================================================
# OpenCode — Script de inicio para WSL (Windows)
# Versión adaptada del start-opencode.sh de Replit
# ============================================================

# Detectar ruta del workspace (convertir ruta Windows a WSL)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$SCRIPT_DIR"

# Binario de OpenCode (Linux ELF)
OPENCODE_BIN="$WORKSPACE/bin/opencode"

if [ ! -f "$OPENCODE_BIN" ]; then
  echo "ERROR: No se encontró el binario de OpenCode en $OPENCODE_BIN"
  exit 1
fi

chmod +x "$OPENCODE_BIN"

# ---- Cargar .env si existe ---- #
if [ -f "$WORKSPACE/.env" ]; then
  set -o allexport
  source "$WORKSPACE/.env"
  set +o allexport
  echo "  ✓ Variables de .env cargadas"
else
  echo "  ⚠ No se encontró .env — copia .env.example a .env y agrega tus API keys"
fi

export OPENCODE_WORKSPACE="$WORKSPACE"

# ---- Crear directorios necesarios ---- #
mkdir -p "$WORKSPACE/proyectos"

# ---- Puertos ---- #
PROXY_PORT="${PORT:-21293}"
OC_PORT=21294

echo ""
echo "============================================================"
echo "✦ OpenCode Evolved (WSL)"
echo "============================================================"
echo "  Motor OpenCode  → puerto $OC_PORT (interno)"
echo "  Shell / Proxy   → puerto $PROXY_PORT (acceso web)"
echo "  Workspace       → $WORKSPACE"
echo "============================================================"

# ---- Instalar deps del proxy si no están ---- #
if [ ! -d "$WORKSPACE/artifacts/opencode-ui/node_modules/express" ]; then
  echo "  Instalando dependencias del proxy..."
  cd "$WORKSPACE/artifacts/opencode-ui"
  pnpm install --no-frozen-lockfile 2>&1 | tail -3
  cd "$WORKSPACE"
  echo "  ✓ Dependencias instaladas"
fi

# ---- Iniciar OpenCode en puerto interno ---- #
echo "  Iniciando OpenCode..."
PORT=$OC_PORT "$OPENCODE_BIN" serve \
  --port "$OC_PORT" \
  --hostname 0.0.0.0 \
  &
OPENCODE_PID=$!
echo "  ✓ OpenCode iniciado (PID $OPENCODE_PID)"

# ---- Esperar a que OpenCode esté listo ---- #
echo "  Esperando que OpenCode arranque (hasta 30s)..."
for i in $(seq 1 30); do
  if nc -z 127.0.0.1 $OC_PORT; then
    echo "  ✓ OpenCode listo (${i}s)"
    break
  fi
  printf "."
  sleep 1
done
echo ""

# ---- Iniciar proxy ---- #
PROXY_DIR="$WORKSPACE/artifacts/opencode-ui"
echo "  Iniciando proxy web..."
PORT="$PROXY_PORT" \
OPENCODE_INTERNAL_PORT="$OC_PORT" \
node "$PROXY_DIR/proxy.mjs" &
PROXY_PID=$!
echo "  ✓ Proxy iniciado (PID $PROXY_PID)"

# ---- Telegram Agent (opcional) ---- #
TELEGRAM_AGENT="$WORKSPACE/bin/telegram-agent.mjs"
if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -f "$TELEGRAM_AGENT" ]; then
  node "$TELEGRAM_AGENT" &
  TELEGRAM_PID=$!
  echo "  ✓ Telegram Agent activo (PID $TELEGRAM_PID)"
else
  echo "  ℹ  Telegram: configura TELEGRAM_BOT_TOKEN en .env para activarlo"
fi

echo ""
echo "============================================================"
echo "  🌐 Abre en tu navegador: http://localhost:$PROXY_PORT"
echo "============================================================"
echo "  Ctrl+C para detener todos los servicios"
echo "============================================================"
echo ""

# ---- Trap para limpiar procesos al salir ---- #
cleanup() {
  echo ""
  echo "Deteniendo servicios..."
  [ -n "$OPENCODE_PID" ] && kill $OPENCODE_PID 2>/dev/null
  [ -n "$PROXY_PID" ]    && kill $PROXY_PID    2>/dev/null
  [ -n "$TELEGRAM_PID" ] && kill $TELEGRAM_PID 2>/dev/null
  echo "Servicios detenidos."
  exit 0
}
trap cleanup INT TERM

# ---- Mantener vivo ---- #
wait $PROXY_PID
