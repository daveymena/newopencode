// ============================================================
// OpenCode Mobile Agent - Agente local para Android (Termux)
// Conecta tu Móvil a OpenCode en EasyPanel via WebSocket
// Requiere: Termux y Termux:API
// ============================================================

import { WebSocket } from 'ws';
import { exec } from 'child_process';
import { promisify } from 'util';
import os from 'os';
import fs from 'fs';
import path from 'path';

const execAsync = promisify(exec);

// ── Configuración ─────────────────────────────────────────
const CONFIG_FILE = path.join(os.homedir(), '.opencode-agent', 'config.json');
let config = {
  serverUrl: process.env.EASYPANEL_URL || 'wss://opencode.tu-dominio.com',
  agentName: 'Android-' + os.hostname(),
  agentId: null,
  reconnectDelay: 5000,
};

if (fs.existsSync(CONFIG_FILE)) {
  try {
    const saved = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
    config = { ...config, ...saved };
  } catch {}
}

function saveConfig() {
  const dir = path.dirname(CONFIG_FILE);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

// ── Helpers Termux ─────────────────────────────────────────
async function runTermux(command) {
  try {
    const { stdout, stderr } = await execAsync(command, { timeout: 30000 });
    return { ok: true, stdout, stderr };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

// ── Información del sistema ────────────────────────────────
async function getSystemInfo() {
  let battery = 'desconocida';
  try {
    const { stdout } = await execAsync('termux-battery-status');
    const batInfo = JSON.parse(stdout);
    battery = `${batInfo.percentage}% (${batInfo.status})`;
  } catch {}

  return {
    hostname:  os.hostname(),
    platform:  'android',
    arch:      os.arch(),
    battery,
    memory:    `${Math.round(os.freemem()/1024/1024)}MB libre`,
    uptime:    `${Math.round(os.uptime()/3600)}h`,
  };
}

// ── Ejecutor de comandos (Android/Termux) ─────────────────
async function executeCommand(cmd) {
  const type = cmd.type;
  
  try {
    // Abrir URL en navegador (Chrome/Default)
    if (type === 'open_url' || type === 'browser') {
      const url = cmd.url || cmd.data;
      await runTermux(`termux-open-url "${url}"`);
      return { ok: true, message: `✓ URL abierta en Android: ${url}` };
    }

    // Enviar notificación
    if (type === 'notify') {
      const msg = cmd.message || cmd.data;
      const title = cmd.title || 'OpenCode';
      await runTermux(`termux-notification --title "${title}" --content "${msg}"`);
      return { ok: true, message: '✓ Notificación enviada' };
    }

    // Hacer vibrar
    if (type === 'vibrate') {
      const duration = cmd.duration || 1000;
      await runTermux(`termux-vibrate -d ${duration}`);
      return { ok: true, message: `✓ Teléfono vibrando (${duration}ms)` };
    }

    // Tomar foto silenciosa (cámara trasera o frontal)
    if (type === 'photo') {
      const camId = cmd.camera || 0; // 0=trasera, 1=frontal
      const outPath = path.join(os.tmpdir(), `photo_${Date.now()}.jpg`);
      await runTermux(`termux-camera-photo -c ${camId} "${outPath}"`);
      const imgData = fs.readFileSync(outPath);
      const base64 = imgData.toString('base64');
      fs.unlinkSync(outPath);
      return { ok: true, base64, mime: 'image/jpeg' };
    }

    // Obtener ubicación GPS
    if (type === 'location') {
      const loc = await runTermux(`termux-location -p network`);
      if (loc.ok) {
        return { ok: true, data: JSON.parse(loc.stdout) };
      }
      return loc;
    }

    // Reproducir audio/media
    if (type === 'play_media') {
      const file = cmd.file;
      await runTermux(`termux-media-player play "${file}"`);
      return { ok: true, message: `✓ Reproduciendo media` };
    }

    // Ejecutar comando bash nativo
    if (type === 'cmd' || type === 'shell' || type === 'bash') {
      const command = cmd.command || cmd.data;
      return await runTermux(command);
    }

    // Info del sistema
    if (type === 'sysinfo') {
      return { ok: true, info: await getSystemInfo() };
    }

    return { ok: false, error: `Tipo de comando desconocido para Android: ${type}` };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

// ── WebSocket Client ───────────────────────────────────────
let ws = null;

async function connect() {
  const url = config.serverUrl.replace(/^http/, 'ws') + '/agent';
  console.log(`[mobile] Conectando a ${url}...`);

  ws = new WebSocket(url, {
    headers: {
      'x-agent-name': config.agentName,
      'x-agent-id':   config.agentId || '',
      'x-agent-os':   'android',
    }
  });

  ws.on('open', async () => {
    console.log('[mobile] ✓ Conectado a EasyPanel');
    ws.send(JSON.stringify({
      type: 'register',
      agentName: config.agentName,
      agentId: config.agentId,
      sysinfo: await getSystemInfo(),
    }));
  });

  ws.on('message', async (data) => {
    try {
      const msg = JSON.parse(data.toString());
      
      if (msg.type === 'registered') {
        config.agentId = msg.agentId;
        saveConfig();
        console.log(`[mobile] ✓ Registrado como: ${msg.agentId}`);
        // Vibrar cortito para confirmar conexión exitosa
        runTermux('termux-vibrate -d 100');
        return;
      }

      if (msg.type === 'command') {
        console.log(`[mobile] → Comando: ${msg.cmd?.type}`);
        // Vibrar al recibir comando (opcional, ayuda a depurar)
        runTermux('termux-vibrate -d 50 -f');
        const result = await executeCommand(msg.cmd);
        ws.send(JSON.stringify({ type: 'result', requestId: msg.requestId, result }));
      }

      if (msg.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong', ts: Date.now() }));
      }
    } catch (err) {
      console.error('[mobile] Error:', err.message);
    }
  });

  ws.on('close', () => {
    console.log(`[mobile] Desconectado. Reconectando en ${config.reconnectDelay/1000}s...`);
    setTimeout(connect, config.reconnectDelay);
  });

  ws.on('error', (err) => {
    console.error('[mobile] WS Error:', err.message);
  });
}

// Prevenir que Android mate el proceso usando wakelock
console.log('Activando Wakelock para mantener el agente vivo...');
exec('termux-wake-lock', () => {
  connect();
});
