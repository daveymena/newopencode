#!/bin/bash
set -e

echo "================================================"
echo "  EXNOVA TRADING BOT - EasyPanel Deployment"
echo "================================================"
echo ""

# ── Crear .env desde variables de entorno ─────────────────────────────
if [ -n "$EXNOVA_EMAIL" ] && [ -n "$EXNOVA_PASSWORD" ]; then
    cat > /app/.env <<EOF
EXNOVA_EMAIL=${EXNOVA_EMAIL}
EXNOVA_PASSWORD=${EXNOVA_PASSWORD}
ACCOUNT_TYPE=${ACCOUNT_TYPE:-PRACTICE}
CAPITAL_PER_TRADE=${CAPITAL_PER_TRADE:-10.0}
INITIAL_BALANCE=${INITIAL_BALANCE:-749.79}
EXPIRATION_TIME=${EXPIRATION_TIME:-120}
BROKER_NAME=${BROKER_NAME:-exnova}
BROKER=${BROKER:-exnova}
DEFAULT_ASSET=${DEFAULT_ASSET:-AUDUSD-OTC}
USE_LLM=${USE_LLM:-false}
OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
OPENROUTER_MODEL=${OPENROUTER_MODEL:-google/gemini-2.0-flash-exp:free}
NVIDIA_NIM_BRIDGE_URL=${NVIDIA_NIM_BRIDGE_URL:-}
NVIDIA_NIM_BRIDGE_API_KEY=${NVIDIA_NIM_BRIDGE_API_KEY:-}
NVIDIA_NIM_BRIDGE_MODEL=${NVIDIA_NIM_BRIDGE_MODEL:-meta/llama-3.1-8b-instruct}
GITHUB_TOKEN=${GITHUB_TOKEN:-}
GITHUB_MODEL=${GITHUB_MODEL:-gpt-4o}
EOF
    echo "[OK] .env creado desde variables de entorno"
else
    echo "[WARN] EXNOVA_EMAIL o EXNOVA_PASSWORD no configurados"
    echo "[INFO] Usando .env existente si existe"
fi

# ── Verificar configuración ───────────────────────────────────────────
echo ""
echo "  Email:     ${EXNOVA_EMAIL:-usar .env}"
echo "  Cuenta:    ${ACCOUNT_TYPE:-PRACTICE}"
echo "  Capital:   \$${CAPITAL_PER_TRADE:-10.0}/trade"
echo "  LLM:       ${USE_LLM:-false}"
echo "  Assets:    ${ASSETS:-AUDUSD-OTC, EURUSD-OTC, GBPUSD-OTC}"
echo ""

# ── Crear bot_config.json override si se especificaron assets ────────
if [ -n "$ASSETS" ]; then
    IFS=',' read -ra ASSET_ARRAY <<< "$ASSETS"
    python3 -c "
import json
path = 'bot_config.json'
try:
    with open(path) as f:
        cfg = json.load(f)
except:
    cfg = {}
cfg['assets'] = [a.strip() for a in '$ASSETS'.split(',')]
with open(path, 'w') as f:
    json.dump(cfg, f, indent=2)
print('[OK] assets configurados:', cfg['assets'])
"
fi

# ── Iniciar bot ──────────────────────────────────────────────────────
echo ""
echo "================================================"
echo "  Iniciando bot..."
echo "================================================"
echo ""

cd /app/bot
exec python3 main.py 2>&1
