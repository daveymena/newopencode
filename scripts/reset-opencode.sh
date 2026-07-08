#!/usr/bin/env bash
set -euo pipefail

# ─── Colores ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; MAGENTA='\033[0;35m'; WHITE='\033[1;37m'
GRAY='\033[0;90m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}OK${NC}   $1"; }
skip() { echo -e "  ${GRAY}--${NC}   $1"; }
warn() { echo -e "  ${YELLOW}WARN${NC} $1"; }
err()  { echo -e "  ${RED}FAIL${NC} $1"; }
info() { echo -e "       ${GRAY}$1${NC}"; }
header() {
  clear 2>/dev/null || true
  echo ""
  echo "  ${CYAN}+------------------------------------------------------+${NC}"
  echo "  ${CYAN}|        OPENCODE  --  RESET DE PROYECTO  (Linux)      |${NC}"
  echo "  ${CYAN}+------------------------------------------------------+${NC}"
  echo ""
}

# ─── Rutas ──────────────────────────────────────────────────────────────────
PROJECT_PATH="${1:-}"
if [ -z "$PROJECT_PATH" ]; then
  echo -e "  ${YELLOW}Ruta del proyecto a resetear:${NC}"
  echo -e "  ${GRAY}(Enter para usar directorio actual)${NC}"
  echo ""
  read -r -p "  Ruta: " raw_path
  if [ -z "$raw_path" ]; then
    PROJECT_PATH="$PWD"
  else
    PROJECT_PATH="${raw_path%/}"
  fi
fi

if [ ! -d "$PROJECT_PATH" ]; then
  err "La ruta no existe: $PROJECT_PATH"
  exit 1
fi

PROJECT_PATH="$(cd "$PROJECT_PATH" && pwd)"
OPCODE_LOCAL="$PROJECT_PATH/.opencode"
SNAPSHOTS_ROOT="$HOME/.local/share/opencode/snapshot"
DATA_GLOBAL="$HOME/.local/share/opencode"
CONFIG_GLOBAL="$HOME/.config/opencode"
AGENT_GLOBAL="$HOME/.opencode-agent"
CACHE_GLOBAL="$HOME/.cache/opencode"

header
echo -e "  ${WHITE}Proyecto: $PROJECT_PATH${NC}"
echo ""

# ─── Hash SHA1 del proyecto (para snapshots) ────────────────────────────────
project_hash=""
if command -v sha1sum &>/dev/null; then
  norm=$(echo "$PROJECT_PATH" | tr '[:upper:]' '[:lower:]' | sed 's|\\|/|g')
  project_hash=$(echo -n "$norm" | sha1sum | cut -d' ' -f1)
elif command -v openssl &>/dev/null; then
  norm=$(echo "$PROJECT_PATH" | tr '[:upper:]' '[:lower:]' | sed 's|\\|/|g')
  project_hash=$(echo -n "$norm" | openssl sha1 | cut -d' ' -f2)
fi

snapshot_path=""
[ -n "$project_hash" ] && snapshot_path="$SNAPSHOTS_ROOT/$project_hash"

# ─── Inventario ─────────────────────────────────────────────────────────────
echo -e "  ${CYAN}Estado actual:${NC}"
echo ""

if [ -d "$OPCODE_LOCAL" ]; then
  n=$(find "$OPCODE_LOCAL" -type f 2>/dev/null | wc -l)
  echo -e "  ${YELLOW}[*] .opencode del proyecto  ($n archivos)${NC}"
else
  skip ".opencode del proyecto: no existe"
fi

if [ -n "$snapshot_path" ] && [ -d "$snapshot_path" ]; then
  n=$(find "$snapshot_path" -type f 2>/dev/null | wc -l)
  echo -e "  ${YELLOW}[*] Snapshots del proyecto  ($n archivos)${NC}"
else
  skip "Snapshots del proyecto: no existen"
fi

if [ -f "$DATA_GLOBAL/opencode.db" ]; then
  db_bytes=$(stat -c%s "$DATA_GLOBAL/opencode.db" 2>/dev/null || stat -f%z "$DATA_GLOBAL/opencode.db" 2>/dev/null)
  db_mb=$(echo "scale=1; $db_bytes / 1048576" | bc 2>/dev/null || echo "?")
  echo -e "  ${YELLOW}[*] Base de datos local  (opencode.db  ${db_mb} MB)${NC}"
  info "$DATA_GLOBAL"
else
  skip "Base de datos local: no existe"
fi

if [ -d "$AGENT_GLOBAL" ]; then
  echo -e "  ${YELLOW}[*] ID de Agente y Servidor (.opencode-agent)${NC}"
  info "$AGENT_GLOBAL"
fi

if [ -d "$CONFIG_GLOBAL" ]; then
  echo -e "  ${YELLOW}[*] Config global de OpenCode${NC}"
  info "$CONFIG_GLOBAL"
else
  skip "Config global: no existe"
fi

# ─── Menu ───────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${GRAY}+------------------------------------------------------+${NC}"
echo -e "  ${CYAN}Elige el tipo de reset:${NC}"
echo ""
echo -e "  ${WHITE}1  Solo el proyecto${NC}"
echo -e "     ${GRAY}Borra: .opencode + snapshots${NC}"
echo -e "     ${GRAY}Mantiene: DB de sesiones, tokens, config global${NC}"
echo ""
echo -e "  ${GREEN}2  Proyecto + sesiones locales  <-- RECOMENDADO${NC}"
echo -e "     ${GRAY}Borra: .opencode + snapshots + opencode.db + datos globales${NC}"
echo -e "     ${GRAY}OpenCode no recordara NADA. Como nuevo. Tokens se mantienen.${NC}"
echo ""
echo -e "  ${RED}3  Reset TOTAL de fabrica${NC}"
echo -e "     ${GRAY}Borra: TODO (proyecto + DB + config + tokens)${NC}"
echo -e "     ${GRAY}Deberas reconfigurar API keys al abrir OpenCode.${NC}"
echo ""
echo -e "  ${MAGENTA}4  Desinstalar y Reinstalar OpenCode${NC}"
echo -e "     ${GRAY}Borra TODO (opcion 3) y vuelve a instalar OpenCode via npm.${NC}"
echo ""
echo -e "  ${GRAY}0  Cancelar${NC}"
echo -e "  ${GRAY}+------------------------------------------------------+${NC}"
echo ""

read -r -p "  Elige (1/2/3/4/0): " op
echo ""

if [ "$op" = "0" ] || [ -z "$op" ]; then
  warn "Cancelado."
  exit 0
fi

# ─── Backup ─────────────────────────────────────────────────────────────────
echo -e "  ${CYAN}Creando backup...${NC}"

ts=$(date +%Y%m%d_%H%M%S)
bak="$CONFIG_GLOBAL/../opencode_backup_$ts"
bak="$(cd "$(dirname "$bak")" && pwd)/opencode_backup_$ts"
mkdir -p "$bak"

backup_item() {
  local src="$1" dst="$2"
  if [ -e "$src" ]; then
    cp -a "$src" "$bak/$dst" 2>/dev/null && ok "Backup: $dst" || warn "No se pudo respaldar $dst"
  fi
}

backup_item "$OPCODE_LOCAL" "project_opencode"

if [ "$op" = "2" ] || [ "$op" = "3" ] || [ "$op" = "4" ]; then
  backup_item "$DATA_GLOBAL"   "data_global"
  backup_item "$CONFIG_GLOBAL" "config_global"
  backup_item "$AGENT_GLOBAL"  "agent_global"
fi

info "Backup en: $bak"
echo ""

# ─── Borrar segun opcion ───────────────────────────────────────────────────
echo -e "  ${CYAN}Ejecutando reset...${NC}"
echo ""

# Siempre: .opencode del proyecto
if [ -d "$OPCODE_LOCAL" ]; then
  rm -rf "$OPCODE_LOCAL" 2>/dev/null && ok ".opencode del proyecto eliminado." || err "Error borrando .opencode"
else
  skip ".opencode no existia."
fi

# Siempre: snapshots del proyecto
if [ -n "$snapshot_path" ] && [ -d "$snapshot_path" ]; then
  rm -rf "$snapshot_path" 2>/dev/null && ok "Snapshots del proyecto eliminados." || warn "No se pudieron borrar snapshots."
else
  skip "Sin snapshots que borrar."
fi

# Opcion 2, 3 y 4: borrar datos globales + agent + cache
if [[ "$op" =~ ^[234]$ ]]; then
  for p in "$DATA_GLOBAL" "$AGENT_GLOBAL" "$CACHE_GLOBAL"; do
    if [ -e "$p" ]; then
      rm -rf "$p" 2>/dev/null && ok "$(basename "$p") eliminado." || err "Error borrando $p"
    else
      skip "$(basename "$p") no existia."
    fi
  done
fi

# Opcion 3 y 4: tambien borrar config global (tokens, API keys)
if [ "$op" = "3" ] || [ "$op" = "4" ]; then
  if [ -d "$CONFIG_GLOBAL" ]; then
    rm -rf "$CONFIG_GLOBAL" 2>/dev/null && ok "Config global eliminada." || err "Error borrando config global"
  else
    skip "Config global no existia."
  fi
fi

# Opcion 4: Reinstalar OpenCode
if [ "$op" = "4" ]; then
  echo ""
  echo -e "  ${MAGENTA}Reinstalando OpenCode globalmente...${NC}"
  
  if command -v opencode &>/dev/null; then
    echo -e "  ${GRAY}-- Cerrando procesos OpenCode...${NC}"
    pkill -f opencode 2>/dev/null || true
    sleep 1
  fi

  echo -e "  ${GRAY}-- Desinstalando version anterior...${NC}"
  npm uninstall -g opencode-ai 2>/dev/null || true

  echo -e "  ${GRAY}-- Limpiando cache de npm...${NC}"
  npm cache clean --force 2>/dev/null || true

  echo -e "  ${YELLOW}-- Descargando e instalando nueva version (espera)...${NC}"
  if npm install -g opencode-ai; then
    ok "OpenCode se reinstalo correctamente."
  else
    warn "La instalacion parece haber fallado."
    info "Ejecuta manualmente: npm install -g opencode-ai"
  fi
fi

# ─── Resultado ──────────────────────────────────────────────────────────────
echo ""
echo -e "  ${GRAY}+------------------------------------------------------+${NC}"
echo ""

if [ ! -d "$OPCODE_LOCAL" ]; then
  ok "RESET COMPLETADO."
  echo ""
  case "$op" in
    1) info "OpenCode no recordara el contexto de este proyecto."
       info "DB de sesiones y tokens: intactos." ;;
    2) info "OpenCode arranca como nuevo en este proyecto."
       info "Sin historial, sin sesiones previas."
       info "Tus API keys siguen configuradas." ;;
    4) info "Reinstalacion limpia de OpenCode completada."
       info "Deberas reconfigurar tu API key al abrir OpenCode." ;;
    *) info "Reset total de fabrica completado."
       info "Deberas reconfigurar tu API key al abrir OpenCode." ;;
  esac
else
  err "Algunos archivos no se pudieron eliminar."
  warn "Verifica permisos o ejecuta con sudo."
fi

echo ""
info "Backup en: $bak"
echo ""
