// ============================================================
// OpenCode Agent Server - Corre en EasyPanel
// Gestiona los agentes PC conectados y permite a OpenCode
// enviarles comandos para controlar PCs remotos
// ============================================================

import { WebSocketServer } from 'ws';
import http from 'http';
import { randomUUID } from 'crypto';

// ── Almacén de agentes conectados ─────────────────────────
const agents = new Map(); // agentId → { ws, info, connectedAt }

// ── WebSocket Server para agentes ─────────────────────────
const WS_PORT = parseInt(process.env.AGENT_WS_PORT || '21291');

const wss = new WebSocketServer({ noServer: true });

wss.on('connection', (ws, req) => {
  const agentName = req.headers['x-agent-name'] || 'PC-Desconocido';
  const agentIdHeader = req.headers['x-agent-id'] || '';
  let agentId = agentIdHeader || randomUUID();

  console.log(`[agent-server] ← Nuevo agente conectado: ${agentName}`);

  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data.toString());

      if (msg.type === 'register') {
        // Usar el ID proporcionado o mantener el generado
        if (msg.agentId) agentId = msg.agentId;
        else agentId = randomUUID();

        agents.set(agentId, {
          ws,
          name: msg.agentName || agentName,
          sysinfo: msg.sysinfo || {},
          connectedAt: new Date(),
        });

        ws.send(JSON.stringify({ type: 'registered', agentId }));
        console.log(`[agent-server] ✓ Agente registrado: ${agentId} (${msg.agentName})`);
      }

      if (msg.type === 'result') {
        // El resultado de un comando ejecutado en el PC
        // Se reenvía al solicitante (OpenCode o API)
        const pending = pendingRequests.get(msg.requestId);
        if (pending) {
          pending.resolve(msg.result);
          pendingRequests.delete(msg.requestId);
        }
      }

      if (msg.type === 'pong') {
        // Keepalive OK
      }
    } catch (err) {
      console.error('[agent-server] Error:', err.message);
    }
  });

  ws.on('close', () => {
    agents.delete(agentId);
    console.log(`[agent-server] ✗ Agente desconectado: ${agentId}`);
  });

  // Keepalive ping cada 30s
  const pingInterval = setInterval(() => {
    if (ws.readyState === ws.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
    } else {
      clearInterval(pingInterval);
    }
  }, 30000);
});

// ── Solicitudes pendientes (comando enviado, esperando respuesta) ──
const pendingRequests = new Map();

async function sendCommandToAgent(agentId, cmd, timeoutMs = 30000) {
  const agent = agents.get(agentId);
  if (!agent) throw new Error(`Agente no encontrado: ${agentId}`);

  const requestId = randomUUID();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pendingRequests.delete(requestId);
      reject(new Error(`Timeout esperando respuesta del agente ${agentId}`));
    }, timeoutMs);

    pendingRequests.set(requestId, {
      resolve: (result) => { clearTimeout(timer); resolve(result); },
      reject,
    });

    agent.ws.send(JSON.stringify({ type: 'command', requestId, cmd }));
  });
}

// ── API HTTP para OpenCode / proxy ────────────────────────
const apiServer = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${WS_PORT}`);
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(200); res.end(); return; }

  try {
    // Lista de agentes conectados
    if (url.pathname === '/agents' && req.method === 'GET') {
      const list = [...agents.entries()].map(([id, a]) => ({
        id, name: a.name, sysinfo: a.sysinfo, connectedAt: a.connectedAt,
      }));
      res.writeHead(200);
      res.end(JSON.stringify(list));
      return;
    }

    // Ejecutar comando en un agente
    if (url.pathname.startsWith('/agents/') && req.method === 'POST') {
      const agentId = url.pathname.split('/')[2];
      let body = '';
      req.on('data', d => body += d);
      await new Promise(r => req.on('end', r));
      const cmd = JSON.parse(body);
      const result = await sendCommandToAgent(agentId, cmd);
      res.writeHead(200);
      res.end(JSON.stringify(result));
      return;
    }

    // Abrir URL en TODOS los agentes conectados
    if (url.pathname === '/broadcast/open_url' && req.method === 'POST') {
      let body = '';
      req.on('data', d => body += d);
      await new Promise(r => req.on('end', r));
      const { url: targetUrl } = JSON.parse(body);
      const results = await Promise.allSettled(
        [...agents.keys()].map(id => sendCommandToAgent(id, { type: 'open_url', url: targetUrl }, 10000))
      );
      res.writeHead(200);
      res.end(JSON.stringify({ agents: agents.size, results: results.map(r => r.status) }));
      return;
    }

    // Health
    if (url.pathname === '/health') {
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true, agents: agents.size }));
      return;
    }

    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Not found' }));
  } catch (err) {
    res.writeHead(500);
    res.end(JSON.stringify({ error: err.message }));
  }
});

// ── Upgrade HTTP → WebSocket para /agent ─────────────────
apiServer.on('upgrade', (req, socket, head) => {
  if (req.url === '/agent') {
    wss.handleUpgrade(req, socket, head, (ws) => {
      wss.emit('connection', ws, req);
    });
  } else {
    socket.destroy();
  }
});

apiServer.listen(WS_PORT, '0.0.0.0', () => {
  console.log(`[agent-server] ✓ Servidor de agentes en puerto ${WS_PORT}`);
  console.log(`[agent-server]   GET  /agents              → agentes conectados`);
  console.log(`[agent-server]   POST /agents/:id          → enviar comando a PC`);
  console.log(`[agent-server]   WS   /agent               → conexión de agentes`);
});

export { sendCommandToAgent, agents };
