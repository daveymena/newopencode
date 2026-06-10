#!/bin/bash
# ============================================================
# OpenCode Evolved — Script de inicio
# Arranca OpenCode (interno) + Proxy con shell (expuesto)
# ============================================================

# ---- Detectar ruta del binario de OpenCode ---- #
if [ -f "/usr/local/bin/opencode" ]; then
  OPENCODE_BIN="/usr/local/bin/opencode"
elif [ -f "/home/runner/workspace/bin/opencode" ]; then
  OPENCODE_BIN="/home/runner/workspace/bin/opencode"
else
  echo "ERROR: No se encontró el binario de OpenCode"
  exit 1
fi

# ---- Detectar directorio de trabajo ---- #
if [ -d "/workspace" ] && [ -w "/workspace" ]; then
  WORKSPACE="/workspace"
elif [ -d "/home/runner/workspace" ]; then
  WORKSPACE="/home/runner/workspace"
else
  WORKSPACE="$(pwd)"
fi

export OPENCODE_WORKSPACE="$WORKSPACE"

# ---- Cargar .env si existe ---- #
if [ -f "$WORKSPACE/.env" ]; then
  set -o allexport
  source "$WORKSPACE/.env"
  set +o allexport
fi

# ---- REPLIT: mapear integraciones ---- #
if [ -n "$AI_INTEGRATIONS_ANTHROPIC_API_KEY" ]; then
  export ANTHROPIC_API_KEY="$AI_INTEGRATIONS_ANTHROPIC_API_KEY"
  export ANTHROPIC_BASE_URL="$AI_INTEGRATIONS_ANTHROPIC_BASE_URL"
fi
if [ -n "$AI_INTEGRATIONS_OPENAI_API_KEY" ]; then
  export OPENAI_API_KEY="$AI_INTEGRATIONS_OPENAI_API_KEY"
  export OPENAI_BASE_URL="$AI_INTEGRATIONS_OPENAI_BASE_URL"
fi
if [ -n "$AI_INTEGRATIONS_GEMINI_API_KEY" ]; then
  export GOOGLE_GENERATIVE_AI_API_KEY="$AI_INTEGRATIONS_GEMINI_API_KEY"
fi

# ---- Ollama (si está disponible) ---- #
if [ -n "$OLLAMA_HOST" ]; then
  export OLLAMA_BASE_URL="$OLLAMA_HOST"
elif curl -s --connect-timeout 1 http://ollama:11434 >/dev/null 2>&1; then
  export OLLAMA_BASE_URL="http://ollama:11434"
elif curl -s --connect-timeout 1 http://localhost:11434 >/dev/null 2>&1; then
  export OLLAMA_BASE_URL="http://localhost:11434"
fi

# ---- Crear estructura de directorios ---- #
mkdir -p "$WORKSPACE/proyectos"

# ---- Puerto del proxy (expuesto) y de OpenCode (interno) ---- #
PROXY_PORT="${PORT:-21293}"
OC_PORT=21294

echo "============================================================"
echo "✦ OpenCode Evolved"
echo "============================================================"
echo "  Motor OpenCode  → puerto $OC_PORT (interno)"
echo "  Shell / Proxy   → puerto $PROXY_PORT (expuesto)"
echo "============================================================"

# ---- Iniciar OpenCode en puerto interno ---- #
PORT=$OC_PORT "$OPENCODE_BIN" serve \
  --port "$OC_PORT" \
  --hostname 0.0.0.0 \
  &

OPENCODE_PID=$!

# ---- Esperar a que OpenCode esté listo ---- #
echo "  Esperando a que OpenCode inicie..."
for i in $(seq 1 30); do
  if curl -s --connect-timeout 1 "http://localhost:$OC_PORT/" >/dev/null 2>&1; then
    echo "  ✓ OpenCode listo"
    break
  fi
  sleep 1
done

# ---- Iniciar proxy con la shell Dark Glassmorphism ---- #
PROXY_DIR="$(dirname "$0")/../artifacts/opencode-ui"
if [ ! -f "$PROXY_DIR/proxy.mjs" ]; then
  PROXY_DIR="$WORKSPACE/artifacts/opencode-ui"
fi

PORT="$PROXY_PORT" \
OPENCODE_INTERNAL_PORT="$OC_PORT" \
node "$PROXY_DIR/proxy.mjs" &

PROXY_PID=$!

echo "  ✓ Proxy / Shell iniciado"
echo "  🌐 Disponible en http://0.0.0.0:$PROXY_PORT"

# ---- Iniciar Telegram Agent (si hay token) ---- #
TELEGRAM_AGENT="$(dirname "$0")/telegram-agent.mjs"
if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -f "$TELEGRAM_AGENT" ]; then
  echo "  🤖 Iniciando Telegram Agent..."
  node "$TELEGRAM_AGENT" &
  TELEGRAM_PID=$!
  echo "  ✓ Telegram Agent activo (PID $TELEGRAM_PID)"
else
  echo "  ⚠️  Telegram: configura TELEGRAM_BOT_TOKEN en Replit Secrets para activarlo"
fi

echo "============================================================"
echo "  🦾 OpenCode Evolved — Sistemas activos:"
echo "     • UI Web Dark Glassmorphism"
echo "     • 5 MCP Servers (filesystem/memory/thinking/browser/computer)"
echo "     • 27 herramientas de control remoto"
[ -n "$TELEGRAM_BOT_TOKEN" ] && echo "     • Telegram Agent 🤖" || echo "     • Telegram Agent (pendiente de token)"
echo "============================================================"

# ---- Mantener vivo el proceso ---- #
wait $PROXY_PID
