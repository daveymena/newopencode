#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════
#  Push OpenCode Evolved → GitHub
#  Uso: bash bin/push-to-github.sh
# ════════════════════════════════════════════════════════════
set -e

REPO_URL="https://github.com/daveymena/epncode-evolution.git"
BRANCH="master"

if [ -z "$GITHUB_PERSONAL_ACCESS_TOKEN" ]; then
  echo "❌  Falta el secret GITHUB_PERSONAL_ACCESS_TOKEN"
  echo "    Agrégalo en Replit → Secrets y vuelve a correr este script."
  exit 1
fi

echo "🔧  Configurando remote 'github'..."
git remote remove github 2>/dev/null || true
git remote add github "https://daveymena:${GITHUB_PERSONAL_ACCESS_TOKEN}@github.com/daveymena/epncode-evolution.git"

echo "📋  Commits a subir:"
git log --oneline -5

echo ""
echo "🚀  Haciendo push a GitHub..."
git push github "${BRANCH}":main --force-with-lease 2>&1 | grep -v "GITHUB_PERSONAL_ACCESS_TOKEN" || \
git push github "${BRANCH}":main --force 2>&1 | grep -v "GITHUB_PERSONAL_ACCESS_TOKEN"

echo ""
echo "✅  ¡Push exitoso!"
echo "    Repo: ${REPO_URL}"

git remote remove github 2>/dev/null || true
