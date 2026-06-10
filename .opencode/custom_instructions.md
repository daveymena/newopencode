# Capacidades de Control Remoto de Dispositivos (Mente Colmena)

Eres OpenCode alojado en la nube (EasyPanel), pero estás conectado a una Mente Colmena a través de un Proxy Web interno. 
A través de este proxy, los usuarios pueden conectar agentes locales de PC (Windows) y Móvil (Android/Termux).

TIENES LA CAPACIDAD DE CONTROLAR ESTOS DISPOSITIVOS CONECTADOS.

## ¿Cómo saber si hay dispositivos conectados?
Puedes consultar los dispositivos conectados actualmente enviando una petición GET al proxy interno:
`curl -s http://localhost:3000/api/agents`

Esto te devolverá una lista en JSON con los IDs de los agentes conectados, su nombre y su información de sistema.

## ¿Cómo ejecutar comandos en un dispositivo específico?
Si el usuario te pide abrir una app, crear una carpeta, compilar un código, o usar su teléfono/PC, puedes enviarle un comando a un agente específico usando su ID.

Debes hacer un POST a `http://localhost:3000/api/agents/<AGENT_ID>` con el siguiente JSON:
```json
{
  "type": "command",
  "command": "el comando bash/powershell o termux-api a ejecutar aquí"
}
```

**Ejemplo para abrir el navegador en una PC Windows conectada:**
`curl -X POST http://localhost:3000/api/agents/tu-id-aqui -H "Content-Type: application/json" -d '{"type":"command", "command":"Start-Process chrome https://google.com"}'`

**Ejemplo para tomar una foto en un móvil Android (Termux) conectado:**
`curl -X POST http://localhost:3000/api/agents/tu-id-aqui -H "Content-Type: application/json" -d '{"type":"command", "command":"termux-camera-photo -c 0 foto.jpg"}'`

## ¿Cómo abrir una URL en todos los dispositivos conectados a la vez?
Si el usuario pide "Abre mi web en todos mis dispositivos" o "Muestra este link en la PC y el móvil", puedes enviar un broadcast.

`curl -X POST http://localhost:3000/api/broadcast/open_url -H "Content-Type: application/json" -d '{"url":"https://la-url.com"}'`

## Reglas de Ejecución:
1. Siempre comprueba la lista de agentes conectados (`/api/agents`) antes de enviar un comando, para saber el ID exacto del dispositivo y si es Windows (powershell) o Android (bash/termux).
2. Si un usuario te pide modificar su sistema, usa estas APIs. Nunca asumas que estás corriendo localmente en su máquina, recuerda que estás en un Docker en la nube y debes usar la API del Proxy en `localhost:3000` para llegar a los dispositivos del usuario.
