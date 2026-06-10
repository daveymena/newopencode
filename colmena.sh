#!/bin/bash

# ==============================================================================
# MENTE COLMENA (Hive Mind) - Herramienta de Control de Agentes
# Este script permite a OpenCode enviar comandos a dispositivos PC/Móviles conectados.
# ==============================================================================

if [ -z "$1" ]; then
  echo "Uso:"
  echo "  ./colmena.sh list                   -> Lista los dispositivos conectados y sus IDs"
  echo "  ./colmena.sh open <ID> <URL>        -> Abre una página web en el navegador del dispositivo"
  echo "  ./colmena.sh notify <ID> <Mensaje>  -> Muestra una notificación push/Windows en el dispositivo"
  echo "  ./colmena.sh cmd <ID> <Comando>     -> Ejecuta un comando de consola (CMD) en la PC"
  exit 1
fi

ACTION=$1
AGENT_ID=$2

if [ "$ACTION" == "list" ]; then
  echo "Dispositivos conectados:"
  curl -s "http://localhost:3000/api/agents"
  echo ""
  exit 0
fi

if [ -z "$AGENT_ID" ]; then
  echo "Error: Necesitas proporcionar el ID del agente."
  exit 1
fi

# =======================
# Acciones
# =======================

if [ "$ACTION" == "open" ]; then
  URL=$3
  curl -s -X POST "http://localhost:3000/api/agents/$AGENT_ID" \
       -H "Content-Type: application/json" \
       -d "{\"type\":\"open_url\", \"url\":\"$URL\"}"
  echo ""
  exit 0
fi

if [ "$ACTION" == "notify" ]; then
  MSG=$3
  curl -s -X POST "http://localhost:3000/api/agents/$AGENT_ID" \
       -H "Content-Type: application/json" \
       -d "{\"type\":\"notify\", \"message\":\"$MSG\", \"title\":\"OpenCode HiveMind\"}"
  echo ""
  exit 0
fi

if [ "$ACTION" == "cmd" ]; then
  CMD=$3
  curl -s -X POST "http://localhost:3000/api/agents/$AGENT_ID" \
       -H "Content-Type: application/json" \
       -d "{\"type\":\"cmd\", \"command\":\"$CMD\"}"
  echo ""
  exit 0
fi

echo "Acción no reconocida."
