// ============================================================
// OpenCode PC Agent - Agente local para Windows
// Conecta tu PC a OpenCode en EasyPanel via WebSocket
// Permite control remoto: navegador, archivos, PowerShell, apps
// ============================================================

import { WebSocket } from 'ws';
import { execSync, exec } from 'child_process';
import { promisify } from 'util';
import os from 'os';
import fs from 'fs';
import path from 'path';
import http from 'http';

const execAsync = promisify(exec);

// ── Configuración ─────────────────────────────────────────
const CONFIG_FILE = path.join(os.homedir(), '.opencode-agent', 'config.json');
let config = {
  serverUrl: process.env.EASYPANEL_URL || 'wss://opencode.tu-dominio.com',
  agentName: os.hostname(),
  agentId: null,
  reconnectDelay: 5000,
};

// Cargar configuración guardada
if (fs.existsSync(CONFIG_FILE)) {
  try {
    const saved = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
    config = { ...config, ...saved };
  } catch {}
}

// Variables de entorno siempre tienen prioridad
const envUrl = process.env.EASYPANEL_URL || process.env.AGENT_SERVER_URL;
if (envUrl) {
  config.serverUrl = envUrl;
}

function saveConfig() {
  const dir = path.dirname(CONFIG_FILE);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

// ── Información del sistema ────────────────────────────────
function getSystemInfo() {
  return {
    hostname:  os.hostname(),
    platform:  os.platform(),
    arch:      os.arch(),
    username:  os.userInfo().username,
    homedir:   os.homedir(),
    memory:    `${Math.round(os.freemem()/1024/1024)}MB libre / ${Math.round(os.totalmem()/1024/1024)}MB total`,
    uptime:    `${Math.round(os.uptime()/3600)}h`,
    cpus:      os.cpus()[0]?.model || 'desconocido',
    ip:        Object.values(os.networkInterfaces()).flat().find(i => !i.internal && i.family === 'IPv4')?.address || 'desconocida',
  };
}

// ── Ejecutor de comandos ───────────────────────────────────
async function executeCommand(cmd) {
  const type = cmd.type;
  
  try {
    // Abrir URL en navegador
    if (type === 'open_url' || type === 'browser') {
      const url = cmd.url || cmd.data;
      execSync(`start "" "${url}"`, { shell: 'cmd.exe' });
      return { ok: true, message: `✓ Abierto en navegador: ${url}` };
    }

    // Ejecutar PowerShell
    if (type === 'powershell' || type === 'ps') {
      const script = cmd.script || cmd.data;
      const { stdout, stderr } = await execAsync(`powershell.exe -NoProfile -Command "${script.replace(/"/g, '\\"')}"`, { timeout: 30000 });
      return { ok: true, stdout, stderr };
    }

    // Ejecutar CMD
    if (type === 'cmd' || type === 'shell') {
      const command = cmd.command || cmd.data;
      const { stdout, stderr } = await execAsync(command, { shell: 'cmd.exe', timeout: 30000 });
      return { ok: true, stdout, stderr };
    }

    // Abrir archivo o carpeta
    if (type === 'open_file' || type === 'explorer') {
      const filePath = cmd.path || cmd.data;
      execSync(`explorer.exe "${filePath}"`, { shell: 'cmd.exe' });
      return { ok: true, message: `✓ Abierto: ${filePath}` };
    }

    // Leer archivo
    if (type === 'read_file') {
      const filePath = cmd.path;
      const content = fs.readFileSync(filePath, 'utf8');
      return { ok: true, content, size: content.length };
    }

    // Escribir archivo
    if (type === 'write_file') {
      const filePath = cmd.path;
      fs.mkdirSync(path.dirname(filePath), { recursive: true });
      fs.writeFileSync(filePath, cmd.content || '');
      return { ok: true, message: `✓ Archivo guardado: ${filePath}` };
    }

    // Listar directorio
    if (type === 'list_dir') {
      const dirPath = cmd.path || os.homedir();
      const items = fs.readdirSync(dirPath, { withFileTypes: true });
      return { ok: true, items: items.map(i => ({ name: i.name, isDir: i.isDirectory() })) };
    }

    // Captura de pantalla (requiere PowerShell)
    if (type === 'screenshot') {
      const outPath = cmd.path || path.join(os.tmpdir(), `screenshot_${Date.now()}.png`);
      const ps = `Add-Type -AssemblyName System.Windows.Forms; $screen=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds; $bmp=New-Object System.Drawing.Bitmap($screen.Width,$screen.Height); $g=[System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($screen.Location,[System.Drawing.Point]::Empty,$screen.Size); $bmp.Save('${outPath}'); Write-Output '${outPath}'`;
      await execAsync(`powershell.exe -Command "${ps}"`, { timeout: 10000 });
      const imgData = fs.readFileSync(outPath);
      const base64 = imgData.toString('base64');
      return { ok: true, path: outPath, base64, mime: 'image/png' };
    }

    // Notificación de Windows
    if (type === 'notify') {
      const msg = cmd.message || cmd.data;
      const title = cmd.title || 'OpenCode';
      const ps = `[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); [System.Windows.Forms.MessageBox]::Show('${msg}','${title}')`;
      exec(`powershell.exe -Command "${ps}"`);
      return { ok: true, message: '✓ Notificación enviada' };
    }

    // Info del sistema
    if (type === 'sysinfo') {
      return { ok: true, info: getSystemInfo() };
    }

    return { ok: false, error: `Tipo de comando desconocido: ${type}` };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

// ── WebSocket Client ───────────────────────────────────────
let ws = null;
let reconnectTimer = null;

function connect() {
  const url = config.serverUrl.replace(/^http/, 'ws') + '/agent';
  console.log(`[agent] Conectando a ${url}...`);

  ws = new WebSocket(url, {
    headers: {
      'x-agent-name': config.agentName,
      'x-agent-id':   config.agentId || '',
      'x-agent-os':   os.platform(),
    }
  });

  ws.on('open', () => {
    console.log('[agent] ✓ Conectado a EasyPanel');
    // Registrar agente
    ws.send(JSON.stringify({
      type: 'register',
      agentName: config.agentName,
      agentId: config.agentId,
      sysinfo: getSystemInfo(),
    }));
  });

  ws.on('message', async (data) => {
    try {
      const msg = JSON.parse(data.toString());
      
      // Guardar ID asignado por el servidor
      if (msg.type === 'registered') {
        config.agentId = msg.agentId;
        saveConfig();
        console.log(`[agent] ✓ Registrado como: ${msg.agentId}`);
        return;
      }

      // Ejecutar comando recibido
      if (msg.type === 'command') {
        console.log(`[agent] → Comando: ${msg.cmd?.type}`);
        const result = await executeCommand(msg.cmd);
        ws.send(JSON.stringify({
          type: 'result',
          requestId: msg.requestId,
          result,
        }));
      }

      // Ping
      if (msg.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong', ts: Date.now() }));
      }
    } catch (err) {
      console.error('[agent] Error procesando mensaje:', err.message);
    }
  });

  ws.on('close', () => {
    console.log(`[agent] Desconectado. Reconectando en ${config.reconnectDelay/1000}s...`);
    reconnectTimer = setTimeout(connect, config.reconnectDelay);
  });

  ws.on('error', (err) => {
    console.error('[agent] Error WebSocket:', err.message);
  });
}

// ── API Local (para configurar desde INICIAR-WINDOWS.bat) ──
const localServer = http.createServer((req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');

  if (req.url === '/status') {
    res.writeHead(200);
    res.end(JSON.stringify({
      connected: ws?.readyState === 1,
      agentId: config.agentId,
      agentName: config.agentName,
      serverUrl: config.serverUrl,
      sysinfo: getSystemInfo(),
    }));
  } else if (req.url === '/config' && req.method === 'POST') {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const newCfg = JSON.parse(body);
        config = { ...config, ...newCfg };
        saveConfig();
        // Reconectar con nueva URL
        if (ws) ws.close();
        res.writeHead(200);
        res.end(JSON.stringify({ ok: true }));
      } catch (e) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: e.message }));
      }
    });
  } else {
    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Not found' }));
  }
});

// ── Inicio ────────────────────────────────────────────────
const AGENT_LOCAL_PORT = parseInt(process.env.AGENT_PORT || '21290');
localServer.listen(AGENT_LOCAL_PORT, '127.0.0.1', () => {
  console.log(`
╔═══════════════════════════════════════════════╗
║     OpenCode PC Agent - Windows               ║
║     Control remoto desde EasyPanel            ║
╠═══════════════════════════════════════════════╣
║  Estado local: http://localhost:${AGENT_LOCAL_PORT}/status ║
║  Servidor:     ${config.serverUrl.padEnd(31)}║
╚═══════════════════════════════════════════════╝`);
  connect();
});

// Mantener vivo
process.on('SIGINT', () => {
  console.log('\n[agent] Deteniendo...');
  if (ws) ws.close();
  localServer.close();
  process.exit(0);
});
