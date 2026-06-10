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
  echo "  ./colmena.sh screenshot <ID>        -> Toma una captura de pantalla del PC y la guarda como screenshot.png"
  echo "  ./colmena.sh mouse_move <ID> <X> <Y>-> Mueve el ratón a las coordenadas X Y"
  echo "  ./colmena.sh mouse_click <ID> [btn] -> Hace clic (btn: left o right)"
  echo "  ./colmena.sh type <ID> <texto>      -> Escribe texto usando el teclado"
  echo "  ./colmena.sh key <ID> <tecla>       -> Presiona tecla especial (ej: {ENTER}, ^{c})"
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

if [ "$ACTION" == "screenshot" ]; then
  echo "Tomando captura de pantalla de la PC remota..."
  # Descargamos el JSON con la captura en base64 al temporal
  curl -s -X POST "http://localhost:3000/api/agents/$AGENT_ID" \
       -H "Content-Type: application/json" \
       -d "{\"type\":\"screenshot\"}" > /tmp/screenshot.json
  
  # Extraemos el base64 y guardamos como screenshot.png para que OpenCode pueda verlo
  node -e "const fs=require('fs'); const j=JSON.parse(fs.readFileSync('/tmp/screenshot.json')); if(j.base64){ fs.writeFileSync('screenshot.png', Buffer.from(j.base64, 'base64')); console.log('✓ Captura guardada exitosamente en screenshot.png en la raiz del proyecto.'); } else { console.log('Error tomando captura:', j.error || 'Desconocido'); }"
  exit 0
fi

if [ "$ACTION" == "mouse_move" ]; then
  curl -s -X POST "http://localhost:3000/api/agents/$AGENT_ID" \
       -H "Content-Type: application/json" \
       -d "{\"type\":\"mouse_move\", \"x\":\"$3\", \"y\":\"$4\"}"
  echo ""
  exit 0
fi

if [ "$ACTION" == "mouse_click" ]; then
  BTN=${3:-left}
  curl -s -X POST "http://localhost:3000/api/agents/$AGENT_ID" \
       -H "Content-Type: application/json" \
       -d "{\"type\":\"mouse_click\", \"button\":\"$BTN\"}"
  echo ""
  exit 0
fi

if [ "$ACTION" == "type" ]; then
  TEXT=$3
  curl -s -X POST "http://localhost:3000/api/agents/$AGENT_ID" \
       -H "Content-Type: application/json" \
       -d "{\"type\":\"keyboard_type\", \"text\":\"$TEXT\"}"
  echo ""
  exit 0
fi

if [ "$ACTION" == "key" ]; then
  KEY=$3
  curl -s -X POST "http://localhost:3000/api/agents/$AGENT_ID" \
       -H "Content-Type: application/json" \
       -d "{\"type\":\"keyboard_press\", \"key\":\"$KEY\"}"
  echo ""
  exit 0
fi

echo "Acción no reconocida."
