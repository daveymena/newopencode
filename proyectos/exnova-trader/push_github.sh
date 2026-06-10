#!/bin/bash
# Script para subir el código a GitHub
# Uso: bash push_github.sh

set -e

REPO_URL="https://daveymena:${GITHUB_TOKEN}@github.com/daveymena/bot-reversiones-iq.git"

echo "Configurando remote de GitHub..."
git remote remove github 2>/dev/null || true
git remote add github "$REPO_URL"

echo "Subiendo código a GitHub (branch: main)..."
git push github main --force

echo ""
echo "✓ Código subido exitosamente a:"
echo "  https://github.com/daveymena/bot-reversiones-iq"

# Limpiar token de la URL del remote por seguridad
git remote set-url github "https://github.com/daveymena/bot-reversiones-iq.git"
echo "✓ Token limpiado del remote por seguridad."
