#!/bin/bash
# ============================================================
# OpenCode - Script de inicio para Docker/EasyPanel
# Lanza: Motor OpenCode + Proxy Web + DB Sync (PostgreSQL)
# ============================================================
set -e

echo "🚀 Iniciando OpenCode (EasyPanel)..."
echo "   Versión: $(opencode --version 2>/dev/null || echo 'desconocida')"

# ---- Cargar .env si existe ---- #
if [ -f "/workspace/.env" ]; then
  echo "   Cargando .env..."
  set -o allexport
  source /workspace/.env
  set +o allexport
fi

# ---- Mostrar proveedores configurados ---- #
[ -n "$ANTHROPIC_API_KEY" ]             && echo "   ✅ Anthropic Claude"
[ -n "$OPENAI_API_KEY" ]               && echo "   ✅ OpenAI GPT"
[ -n "$GOOGLE_GENERATIVE_AI_API_KEY" ] && echo "   ✅ Google Gemini"
[ -n "$GROQ_API_KEY" ]                 && echo "   ✅ Groq (gratis)"
[ -n "$OPENROUTER_API_KEY" ]           && echo "   ✅ OpenRouter"
[ -n "$CEREBRAS_API_KEY" ]             && echo "   ✅ Cerebras (gratis)"
[ -n "$TOGETHER_AI_API_KEY" ]          && echo "   ✅ Together AI"
[ -n "$XAI_API_KEY" ]                  && echo "   ✅ xAI Grok"

# ---- Ollama (modelos locales) ---- #
if [ -n "$OLLAMA_HOST" ]; then
  export OLLAMA_BASE_URL="$OLLAMA_HOST"
  echo "   ✅ Ollama: $OLLAMA_HOST"
elif curl -s --connect-timeout 2 http://ollama:11434 > /dev/null 2>&1; then
  export OLLAMA_BASE_URL="http://ollama:11434"
  echo "   ✅ Ollama: detectado automáticamente"
fi

# ---- Puertos ---- #
OPENCODE_INTERNAL_PORT=${OPENCODE_INTERNAL_PORT:-3001}
PROXY_PORT=${PORT:-3000}
SYNC_PORT=${SYNC_API_PORT:-3002}

# ---- Crear estructura de directorios ---- #
mkdir -p "${OPENCODE_WORKSPACE:-/workspace}/proyectos"

echo ""
echo "============================================================"
echo "  Arrancando servicios..."
echo "============================================================"

# 1. Motor OpenCode (interno)
cd "${OPENCODE_WORKSPACE:-/workspace}"
opencode serve \
  --port "$OPENCODE_INTERNAL_PORT" \
  --hostname 0.0.0.0 &
OC_PID=$!
echo "  ✓ Motor OpenCode PID=$OC_PID → puerto $OPENCODE_INTERNAL_PORT"

# 2. Proxy web (puerto público)
PORT=$PROXY_PORT \
OPENCODE_INTERNAL_PORT=$OPENCODE_INTERNAL_PORT \
  node /app/proxy.mjs &
PROXY_PID=$!
echo "  ✓ Proxy web PID=$PROXY_PID → puerto $PROXY_PORT"

# 3. Esperar que OpenCode levante (hasta 40s)
echo "  Esperando que OpenCode arranque..."
for i in $(seq 1 20); do
  sleep 2
  if curl -sf "http://localhost:${OPENCODE_INTERNAL_PORT}/health" > /dev/null 2>&1; then
    echo "  ✓ OpenCode listo en $((i*2))s"
    break
  fi
done

# 4. DB Sync (PostgreSQL)
if [ -n "$DATABASE_URL" ]; then
  SYNC_API_PORT=$SYNC_PORT \
    node /app/db-sync.mjs &
  SYNC_PID=$!
  echo "  ✓ DB Sync PID=$SYNC_PID → puerto $SYNC_PORT"
else
  echo "  ⚠ DATABASE_URL no configurada — sync desactivado"
fi

echo ""
echo "============================================================"
echo "  🌐 Interfaz web:    http://0.0.0.0:${PROXY_PORT}"
echo "  🗄️  Historial API:  http://0.0.0.0:${SYNC_PORT}/api/sessions"
echo "  🔍 Buscar:          http://0.0.0.0:${SYNC_PORT}/api/search?q=texto"
echo "============================================================"

# ---- Graceful Shutdown & Auto-Sync ---- #
cleanup() {
  echo ""
  echo "🛑 Señal de apagado recibida. Sincronizando historial antes de salir..."
  curl -s -X POST "http://localhost:${PROXY_PORT}/api/sync-now" || true
  echo "✓ Sincronización final completada."
  kill $OC_PID 2>/dev/null
  kill $PROXY_PID 2>/dev/null
  kill $SYNC_PID 2>/dev/null
  exit 0
}

trap cleanup SIGINT SIGTERM

# Mantener vivo — si OpenCode muere, el contenedor se reinicia
wait $OC_PID
