import express from "express";
import { createProxyMiddleware } from "http-proxy-middleware";
import { createServer } from "http";
import path from "path";
import { fileURLToPath } from "url";
import https from "https";
import http from "http";
import { WebSocketServer } from "ws";
import { randomUUID } from "crypto";
import { existsSync } from "fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PORT            = parseInt(process.env.PORT || "21293");
const OPENCODE_PORT   = parseInt(process.env.OPENCODE_PORT || process.env.OPENCODE_INTERNAL_PORT || "21294");
const OPENCODE_TARGET = `http://localhost:${OPENCODE_PORT}`;

const API_SERVER_PORT = parseInt(process.env.API_SERVER_PORT || "21296");
const API_SERVER_TARGET = `http://localhost:${API_SERVER_PORT}`;

// ── Agentes PC conectados ─────────────────────────────────
const pcAgents = new Map(); // agentId → { ws, name, sysinfo, connectedAt }
const pendingCmds = new Map();

async function sendToAgent(agentId, cmd, timeout = 30000) {
  const agent = pcAgents.get(agentId);
  if (!agent) throw new Error(`Agente ${agentId} no conectado`);
  const requestId = randomUUID();
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => { pendingCmds.delete(requestId); reject(new Error("Timeout")); }, timeout);
    pendingCmds.set(requestId, { resolve: r => { clearTimeout(t); resolve(r); }, reject });
    agent.ws.send(JSON.stringify({ type: "command", requestId, cmd }));
  });
}


const app = express();

// ── Health check propio (responde siempre, aunque OpenCode no haya arrancado)
app.get("/health", (req, res) => res.json({ status: "ok", proxy: true, timestamp: Date.now() }));


// ── React App (frontend compilado) ─────────────────────────
const UI_DIR = '/app/ui';
const UI_INDEX = '/app/ui/index.html';
if (existsSync(UI_DIR)) {
  app.use(express.static(UI_DIR, { index: false }));
  // SPA catch-all: servir index.html para rutas que no son API ni archivos estáticos
  app.get('*', (req, res) => {
    if (!req.path.startsWith('/api') && !req.path.startsWith('/__') && !req.path.startsWith('/port')) {
      res.sendFile(UI_INDEX);
    }
  });
  console.log('[proxy] ✓ Sirviendo React app desde /app/ui/');
} else {
  console.log('[proxy] ⚠ React app no encontrada en /app/ui/ — usando OpenCode UI');
}

// ── Static shell files (CSS + JS personalizado) ──────────────
app.use("/__shell", express.static(path.join(__dirname, "public")));

// ── Túnel de Puertos de Desarrollo (Dev Port Tunnel) ──────
const devPortProxy = createProxyMiddleware({
  target: 'http://127.0.0.1:80', // Fallback seguro para evitar crash si router falla
  router: (req) => {
    // Cuando usamos app.use('/port', ...), req.originalUrl contiene '/port/5173'
    const match = req.originalUrl.match(/^\/port\/(\d+)/);
    if (match) {
      return `http://127.0.0.1:${match[1]}`;
    }
    return null;
  },
  pathRewrite: (path, req) => {
    // pathRewrite recibe la URL original cuando se usa router dinámico en v3
    const match = req.originalUrl.match(/^\/port\/\d+(.*)/);
    return match && match[1] !== "" ? match[1] : "/";
  },
  changeOrigin: true,
  ws: true,
  logLevel: 'silent'
});
app.use("/port", devPortProxy);

// ═══════════════════════════════════════════════════════════════
// ENDPOINT: /vision — Convierte imagen → texto descriptivo
// Permite que CUALQUIER modelo (Llama, Groq, Mistral, etc.)
// "vea" imágenes recibiendo una descripción detallada en texto.
// ═══════════════════════════════════════════════════════════════
app.post("/__vision", express.json({ limit: "20mb" }), async (req, res) => {
  const { image, mime = "image/jpeg", question = "Describe esta imagen en detalle completo en español. Incluye: qué muestra, textos visibles, colores, objetos, personas, código si hay, errores, gráficos, cualquier información relevante." } = req.body;

  if (!image) return res.status(400).json({ error: "Falta el campo 'image' (base64)" });

  // Limpiar base64 si viene con prefijo data:url
  const base64 = image.includes(",") ? image.split(",")[1] : image;

  const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY || process.env.AI_INTEGRATIONS_ANTHROPIC_API_KEY;
  const ANTHROPIC_URL = process.env.ANTHROPIC_BASE_URL || "https://api.anthropic.com";
  const OPENAI_KEY    = process.env.OPENAI_API_KEY || process.env.AI_INTEGRATIONS_OPENAI_API_KEY;
  const OPENAI_URL    = process.env.OPENAI_BASE_URL || "https://api.openai.com";
  const GEMINI_KEY    = process.env.GOOGLE_GENERATIVE_AI_API_KEY;

  // ── Intentar con Anthropic Claude ───────────────────────────
  if (ANTHROPIC_KEY) {
    try {
      const desc = await callAnthropicVision(ANTHROPIC_KEY, ANTHROPIC_URL, base64, mime, question);
      return res.json({ description: desc, model: "claude-haiku (visión)" });
    } catch (e) {
      console.error("[vision] Anthropic falló:", e.message);
    }
  }

  // ── Intentar con OpenAI GPT-4o ──────────────────────────────
  if (OPENAI_KEY) {
    try {
      const desc = await callOpenAIVision(OPENAI_KEY, OPENAI_URL, base64, mime, question);
      return res.json({ description: desc, model: "gpt-4o (visión)" });
    } catch (e) {
      console.error("[vision] OpenAI falló:", e.message);
    }
  }

  // ── Intentar con Gemini Flash ───────────────────────────────
  if (GEMINI_KEY) {
    try {
      const desc = await callGeminiVision(GEMINI_KEY, base64, mime, question);
      return res.json({ description: desc, model: "gemini-flash (visión)" });
    } catch (e) {
      console.error("[vision] Gemini falló:", e.message);
    }
  }

  // ── Sin API key de visión disponible ────────────────────────
  return res.status(503).json({
    error: "No hay API key de visión disponible",
    hint: "Agrega ANTHROPIC_API_KEY, OPENAI_API_KEY o GOOGLE_GENERATIVE_AI_API_KEY en las Variables de Entorno de EasyPanel"
  });
});

// ── Llamadas a APIs de visión ────────────────────────────────

function httpsPost(urlStr, headers, body) {
  return new Promise((resolve, reject) => {
    const u = new URL(urlStr);
    const buf = Buffer.from(JSON.stringify(body));
    const opts = {
      hostname: u.hostname,
      port:     u.port || 443,
      path:     u.pathname + u.search,
      method:   "POST",
      headers:  { "Content-Type":"application/json", "Content-Length":buf.length, ...headers }
    };
    const mod = u.protocol === "https:" ? https : http;
    let data = "";
    const req = mod.request(opts, r => {
      r.on("data", c => { data += c; });
      r.on("end", () => {
        try { resolve(JSON.parse(data)); }
        catch { resolve({ _raw: data }); }
      });
    });
    req.on("error", reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error("Timeout")); });
    req.write(buf);
    req.end();
  });
}

async function callAnthropicVision(key, baseUrl, base64, mime, question) {
  const res = await httpsPost(
    `${baseUrl}/v1/messages`,
    { "x-api-key": key, "anthropic-version": "2023-06-01" },
    {
      model: "claude-haiku-4-5",
      max_tokens: 1024,
      messages: [{
        role: "user",
        content: [
          { type: "image", source: { type: "base64", media_type: mime, data: base64 } },
          { type: "text",  text: question }
        ]
      }]
    }
  );
  if (res.error) throw new Error(res.error.message || JSON.stringify(res.error));
  return res.content?.[0]?.text || JSON.stringify(res);
}

async function callOpenAIVision(key, baseUrl, base64, mime, question) {
  const res = await httpsPost(
    `${baseUrl}/v1/chat/completions`,
    { "Authorization": `Bearer ${key}` },
    {
      model: "gpt-4o-mini",
      max_tokens: 1024,
      messages: [{
        role: "user",
        content: [
          { type: "image_url", image_url: { url: `data:${mime};base64,${base64}` } },
          { type: "text", text: question }
        ]
      }]
    }
  );
  if (res.error) throw new Error(res.error.message || JSON.stringify(res.error));
  return res.choices?.[0]?.message?.content || JSON.stringify(res);
}

async function callGeminiVision(key, base64, mime, question) {
  const res = await httpsPost(
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${key}`,
    {},
    {
      contents: [{
        parts: [
          { inline_data: { mime_type: mime, data: base64 } },
          { text: question }
        ]
      }]
    }
  );
  if (res.error) throw new Error(res.error.message || JSON.stringify(res.error));
  return res.candidates?.[0]?.content?.parts?.[0]?.text || JSON.stringify(res);
}

// ═══════════════════════════════════════════════════════════════
// Shell injection HTML
// ═══════════════════════════════════════════════════════════════
const shellCSS = `<link rel="stylesheet" href="/__shell/shell.css">`;
const shellJS  = `<script src="/__shell/shell.js"></script>`;

// ── Proxy principal → OpenCode ──────────────────────────────
const htmlProxy = createProxyMiddleware({
  target: OPENCODE_TARGET,
  changeOrigin: true,
  selfHandleResponse: true,
  on: {
    proxyReq: (proxyReq, req, res) => {
      proxyReq.removeHeader('accept-encoding');
    },
    proxyRes: (proxyRes, req, res) => {
      const contentType = proxyRes.headers["content-type"] || "";
      const isHTML = contentType.includes("text/html");

      if (!isHTML) {
        Object.entries(proxyRes.headers).forEach(([key, val]) => res.setHeader(key, val));
        res.statusCode = proxyRes.statusCode;
        proxyRes.pipe(res);
        return;
      }

      delete proxyRes.headers["content-security-policy"];
      delete proxyRes.headers["x-frame-options"];
      delete proxyRes.headers["content-length"];

      Object.entries(proxyRes.headers).forEach(([key, val]) => res.setHeader(key, val));
      res.statusCode = proxyRes.statusCode;

      let body = "";
      proxyRes.setEncoding("utf8");
      proxyRes.on("data", chunk => { body += chunk; });
      proxyRes.on("end", () => {
        body = body.replace("</head>", `${shellCSS}\n</head>`);
        body = body.replace("</body>", `${shellJS}\n</body>`);
        res.end(body);
      });
    },
    error: (err, req, res) => {
      if (!res.headersSent) {
        res.writeHead(502, { "Content-Type": "text/html; charset=utf-8" });
        res.end(`<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="5">
  <title>OpenCode — Iniciando...</title>
  <style>
    body { margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center; background:#07070d; font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif; color:#f0f0ff; }
    .box { text-align:center; padding:3rem; background:rgba(255,255,255,0.03); border:1px solid rgba(124,58,237,0.25); border-radius:16px; backdrop-filter:blur(20px); max-width:420px; }
    h1 { margin:0 0 .5rem; font-size:1.6rem; }
    .badge { display:inline-block; font-size:.7rem; font-weight:700; letter-spacing:1px; color:#8b5cf6; background:rgba(124,58,237,0.15); border:1px solid rgba(124,58,237,0.3); border-radius:4px; padding:2px 8px; text-transform:uppercase; margin-bottom:1.2rem; }
    p { color:rgba(200,200,230,0.7); line-height:1.6; font-size:.95rem; }
    .spinner { width:36px; height:36px; border:3px solid rgba(124,58,237,0.25); border-top-color:#7c3aed; border-radius:50%; animation:spin .7s linear infinite; margin:0 auto 1.5rem; }
    @keyframes spin { to { transform:rotate(360deg); } }
    .hint { font-size:.8rem; color:rgba(160,160,200,0.5); margin-top:1.5rem; }
  </style>
</head>
<body>
  <div class="box">
    <div class="spinner"></div>
    <h1>OpenCode</h1>
    <div class="badge">EVOLVED</div>
    <p>El motor de IA está iniciando...<br>La página se recargará automáticamente.</p>
    <p class="hint">Esto puede tomar hasta 40 segundos en el primer arranque.</p>
  </div>
</body>
</html>`);
      }
    },
  },
});

const apiProxy = createProxyMiddleware({
  target: OPENCODE_TARGET,
  changeOrigin: true,
});

// ── API para gestionar Agentes ────────────────────────────
const customApi = express.Router();

// ── UI Clients (SSE) ──────────────────────────────────────
const uiClients = new Set();

customApi.get("/ui-events", (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();

  uiClients.add(res);

  const pingInterval = setInterval(() => {
    res.write(':\n\n');
  }, 20000);

  req.on("close", () => {
    clearInterval(pingInterval);
    uiClients.delete(res);
  });
});

function broadcastToUI(eventType, data) {
  const message = `event: ${eventType}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const client of uiClients) {
    client.write(message);
  }
}

customApi.get("/agents", (req, res) => {
  const list = [...pcAgents.entries()].map(([id, a]) => ({ id, name: a.name, sysinfo: a.sysinfo, connectedAt: a.connectedAt }));
  res.json(list);
});

customApi.post("/agents/:id", express.json(), async (req, res) => {
  try {
    const result = await sendToAgent(req.params.id, req.body);
    res.json(result);
  } catch(e) {
    res.status(500).json({ error: e.message });
  }
});

customApi.post("/broadcast/open_url", express.json(), async (req, res) => {
  try {
    const { url: targetUrl } = req.body;
    
    // Broadcast to internal UI browser
    broadcastToUI("open_url", { url: targetUrl });

    // Broadcast to external PC agents
    const results = await Promise.allSettled([...pcAgents.keys()].map(id => sendToAgent(id, { type: "open_url", url: targetUrl }, 10000)));
    res.json({ agents: pcAgents.size, uiClients: uiClients.size, results: results.map(r => r.status) });
  } catch(e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Endpoint para disparar sincronización manual ────────────
customApi.post("/sync-now", express.json(), async (req, res) => {
  try {
    const SYNC_PORT = process.env.SYNC_API_PORT || 21295;
    const resp = await fetch(`http://localhost:${SYNC_PORT}/api/sync`, { method: 'POST' });
    const data = await resp.json();
    res.json({ ok: true, ...data });
  } catch(e) {
    res.status(500).json({ error: e.message });
  }
});

app.use("/api", customApi);

// ── Dashboard de Mente Colmena ──────────────────────────────
app.get("/colmena", (req, res) => {
  const host = req.headers.host;
  const wssUrl = `wss://${host}`;
  
  const html = `
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Mente Colmena - OpenCode</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .container { background: #1e293b; padding: 2rem; border-radius: 12px; max-width: 600px; width: 90%; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        h1 { margin-top: 0; color: #38bdf8; text-align: center; }
        p { color: #cbd5e1; line-height: 1.6; }
        .box { background: #0f172a; border: 1px solid #334155; padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem; }
        h2 { font-size: 1.2rem; color: #f1f5f9; margin-top: 0; }
        .btn { display: inline-block; background: #38bdf8; color: #0f172a; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: bold; transition: background 0.2s; }
        .btn:hover { background: #0ea5e9; }
        code { background: #000; color: #10b981; padding: 10px; border-radius: 4px; display: block; overflow-x: auto; font-family: monospace; }
        .back-link { display: block; text-align: center; margin-top: 2rem; color: #94a3b8; text-decoration: none; }
        .back-link:hover { color: #f8fafc; }
      </style>
    </head>
    <body>
      <div class="container">
        <h1>🐝 Mente Colmena</h1>
        <p>Conecta tus dispositivos para que OpenCode pueda controlarlos de forma remota.</p>
        
        <div class="box">
          <h2>💻 Agente para PC (Windows)</h2>
          <p>Descarga el ejecutable preconfigurado, dale doble clic y mantenlo abierto para conectar esta PC.</p>
          <a href="/download-pc-agent" class="btn">📥 Descargar INSTALAR-AGENTE.bat</a>
        </div>

        <div class="box">
          <h2>📱 Agente para Android (Termux)</h2>
          <p>Abre la app <strong>Termux</strong> en tu celular, copia y pega el siguiente comando. Ya está preconfigurado con tu URL:</p>
          <code>curl -fsSL -o agente.sh "https://raw.githubusercontent.com/daveymena/openco/main/agent-local/instalar-movil.sh" && bash agente.sh "${wssUrl}"</code>
        </div>
        
        <a href="/" class="back-link">← Volver a OpenCode</a>
      </div>
    </body>
    </html>
  `;
  res.send(html);
});

app.get("/download-pc-agent", (req, res) => {
  const host = req.headers.host;
  const wssUrl = `wss://${host}`;
  
  const batContent = `@echo off
title OpenCode PC Agent
echo ========================================
echo Iniciando Agente Local de OpenCode (PC)
echo ========================================
echo.

node -v >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js no esta instalado.
    pause
    exit /b
)

IF NOT EXIST "pc-agent.mjs" (
    echo Descargando agente...
    curl -fsSL -o pc-agent.mjs "https://raw.githubusercontent.com/daveymena/openco/main/agent-local/pc-agent.mjs"
)

echo Instalando libreria 'ws'...
call npm install ws --no-save >nul 2>&1

echo Conectando a la colmena...
set AGENT_SERVER_URL=${wssUrl}

:loop
node pc-agent.mjs
echo.
echo [AGENT] El agente se ha cerrado. Reiniciando automaticamente en 3 segundos para mantener la conexion estable...
timeout /t 3
goto loop
`;

  res.setHeader('Content-disposition', 'attachment; filename=INSTALAR-AGENTE.bat');
  res.setHeader('Content-type', 'application/x-bat');
  res.send(batContent);
});

// (Duplicado eliminado — /api ya registrado en línea 331)

// ── Proxy dinámico al API Server (modelos, sesiones, archivos, terminal, chat) ──
const apiServerProxy = createProxyMiddleware({
  target: API_SERVER_TARGET,
  changeOrigin: true,
  ws: true,
  on: {
    error: (err, req, res) => {
      if (!res.headersSent) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'API Server no disponible', detail: err.message }));
      }
    }
  }
});

// ═══════════════════════════════════════════════════════════════
// SISTEMA DE CHAT COMPLETO — Session persistence + Multi-provider
// ═══════════════════════════════════════════════════════════════

// Mapa de sesiones: frontendSessionId → { ocSessionId, model, createdAt }
const sessionMap = new Map();

// Solicitudes activas (para poder cancelar)
const activeRequests = new Map();

// ── FREEMODEL API (bridge directo) ────────────────────────────
const FREEMODEL_KEY = process.env.FREEMODEL_API_KEY || 'fe_oa_db8434da9d092b657e26dba8e2cdbf5cc460848f7e3b490c';
const FREEMODEL_URL = process.env.FREEMODEL_BASE_URL || 'https://api.freemodel.dev/v1';

function callFreemodel(model, message, systemPrompt) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      model,
      messages: [
        ...(systemPrompt ? [{ role: 'system', content: systemPrompt }] : []),
        { role: 'user', content: message }
      ],
      max_tokens: 4096,
    });

    const url = new URL(`${FREEMODEL_URL}/chat/completions`);
    const req = https.request({
      hostname: url.hostname,
      port: url.port || 443,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${FREEMODEL_KEY}`,
        'Content-Length': Buffer.byteLength(payload),
      },
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            reject(new Error(parsed.error.message || JSON.stringify(parsed.error)));
          } else {
            resolve(parsed.choices?.[0]?.message?.content || '(sin respuesta)');
          }
        } catch (e) {
          reject(new Error('Error parseando respuesta Freemodel'));
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(60000, () => { req.destroy(); reject(new Error('Timeout Freemodel')); });
    req.write(payload);
    req.end();
  });
}

function ocRequest(path, method, body, timeoutMs = 120000) {
  return new Promise((resolve, reject) => {
    const payload = body ? JSON.stringify(body) : '';
    const req = http.request({
      hostname: 'localhost',
      port: OPENCODE_PORT,
      path,
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
      },
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => resolve({ status: res.statusCode || 0, data }));
    });
    req.on('error', reject);
    req.setTimeout(timeoutMs, () => { req.destroy(); reject(new Error('Timeout')); });
    if (payload) req.write(payload);
    req.end();
  });
}

// Crear o reusar sesión en OpenCode
async function getOrCreateSession(frontendSessionId) {
  const existing = sessionMap.get(frontendSessionId);
  if (existing) {
    // Verificar que la sesión aún existe en OpenCode
    try {
      const check = await ocRequest(`/session/${existing.ocSessionId}`, 'GET', null, 5000);
      if (check.status === 200) return existing.ocSessionId;
    } catch {}
    // Si no existe, eliminar del mapa y crear nueva
    sessionMap.delete(frontendSessionId);
  }

  // Crear nueva sesión en OpenCode
  try {
    const createRes = await ocRequest('/session', 'POST', {});
    if (createRes.status === 200 || createRes.status === 201) {
      const created = JSON.parse(createRes.data);
      const ocId = created.id || created.sessionID;
      sessionMap.set(frontendSessionId, { ocSessionId: ocId, createdAt: Date.now() });
      console.log(`[chat] Sesión mapeada: ${frontendSessionId} → ${ocId}`);
      return ocId;
    }
  } catch (e) {
    console.error('[chat] Error creando sesión:', e.message);
  }
  return frontendSessionId;
}

// Parsear modelo "provider/modelID" → { providerID, modelID }
function parseModel(modelStr) {
  const raw = modelStr || 'opencode/big-pickle';
  const slashIdx = raw.indexOf('/');
  if (slashIdx > 0) {
    return { providerID: raw.substring(0, slashIdx), modelID: raw.substring(slashIdx + 1) };
  }
  return { providerID: 'opencode', modelID: raw };
}

// ── POST /api/chat — Envía mensaje y recibe respuesta SSE ──
app.post('/api/chat', express.json(), async (req, res) => {
  const { sessionId, message, model, systemPrompt } = req.body;
  const requestId = randomUUID();

  if (!sessionId || !message) {
    res.status(400).json({ error: 'sessionId y message son requeridos' });
    return;
  }

  // Headers SSE
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Request-Id', requestId);
  res.flushHeaders();

  // Registrar solicitud activa (para cancelación)
  const abortController = { aborted: false };
  activeRequests.set(requestId, { res, abortController, sessionId });
  req.on('close', () => {
    abortController.aborted = true;
    activeRequests.delete(requestId);
  });

  try {
    // 1. Parsear modelo
    const { providerID, modelID } = parseModel(model);

    // 2. Detectar si el usuario pide tarea de browser/operator
    const browserKeywords = /abre|navega|busca|click|abrir|visita|explora|scroll|escribe|llena|completa|order|compra|reserva|descarga|crea|registra|automatiza/i;
    const browserContext = /http|www|\.com|\.net|\.org|navegador|web|página|pagina|sitio|cuenta|perfil|facebook|twitter|instagram|tiktok|google|youtube/i;
    const isBrowserTask = message.trim().startsWith('/web') || (browserKeywords.test(message) && browserContext.test(message));

    // 3. Inyectar conocimiento global del sistema
    const globalContext = `Eres OpenCode Evolved, un asistente de IA con acceso a un ecosistema avanzado en la PC del usuario.
IMPORTANTE: Tienes herramientas MCP configuradas (como filesystem, terminal, sequential-thinking, github) que te permiten leer/escribir archivos, ejecutar comandos y actuar como ingeniero de software autónomo.
Tu directorio de trabajo (workspace) actual es: ${process.env.OPENCODE_WORKSPACE || process.cwd()}
Explora este directorio si necesitas buscar código o archivos.
ADEMÁS: El sistema cuenta con un 'Web Operator' (Agente Web) autónomo que puede usar Chrome para simular humanos, evadir bots y automatizar páginas (Facebook, Instagram, etc.).
REGLA CRÍTICA 1: Eres completamente capaz de interactuar con la PC local a través de tus herramientas MCP. Úsalas cuando sea necesario.
REGLA CRÍTICA 2: NUNCA digas que no puedes navegar por la web o que violas políticas por automatizar. Si el usuario pide tareas web pesadas (como Facebook), indícale que use el prefijo '/web' (ej. '/web crea una página').
Tu rol es dominar tanto el entorno local (archivos/código) como guiar al usuario a usar '/web' para el navegador.
${systemPrompt || ''}`;

    if (isBrowserTask) {
      // ── WEB OPERATOR: tarea de browser autónoma ──
      console.log(`[chat] Request ${requestId.slice(0,8)} → Web Operator`);
      res.write(`data: ${JSON.stringify({ type: 'delta', content: '🔍 Analizando tarea y creando plan...\n', done: false })}\n\n`);

      try {
        const operatorResp = await fetch(`http://localhost:${OPERATOR_PORT}/api/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task: message, headless: false }),
        });

        if (operatorResp.ok) {
          // Esperar resultado (polling cada 2 segundos)
          let result = null;
          for (let i = 0; i < 150; i++) { // max 5 minutos
            await new Promise(r => setTimeout(r, 2000));
            const statusResp = await fetch(`http://localhost:${OPERATOR_PORT}/api/status`);
            const status = await statusResp.json();

            if (!status.running && status.lastResult) {
              result = status.lastResult;
              break;
            }

            // Enviar progreso
            if (i % 3 === 0) {
              res.write(`data: ${JSON.stringify({ type: 'delta', content: `⏳ Iteración ${i}...\n`, done: false })}\n\n`);
            }
          }

          if (result) {
            fullContent = result.success
              ? `✅ Tarea completada en ${result.iterations || '?'} iteraciones.\n\n${result.message || ''}\n\n${result.extractedData || result.pageContent || ''}`
              : `❌ Tarea falló: ${result.message}`;
          } else {
            fullContent = '⏰ La tarea tardó demasiado. Intenta con algo más simple.';
          }
        } else {
          fullContent = '⚠️ Web Operator no está disponible. Asegúrate de que esté corriendo en puerto 3001.';
        }
      } catch (err) {
        fullContent = `⚠️ Error al ejecutar tarea de browser: ${err.message}`;
      }

    } else if (providerID === 'freemodel') {
      // ── FREEMODEL: llamada directa a la API ──
      console.log(`[chat] Request ${requestId.slice(0,8)} → Freemodel ${modelID}`);
      fullContent = await callFreemodel(modelID, message, globalContext);
    } else {
      // ── OPENCODE: sesión + mensaje ──
      const ocSessionId = await getOrCreateSession(sessionId);
      console.log(`[chat] Request ${requestId.slice(0,8)} → OpenCode ${providerID}/${modelID} session ${ocSessionId}`);

      const promptBody = {
        parts: [{ type: 'text', text: message + "\n\n" + globalContext }],
        model: { providerID, modelID },
        ...(systemPrompt ? { system: systemPrompt } : {}),
      };

      const promptRes = await ocRequest(`/session/${ocSessionId}/message`, 'POST', promptBody, 180000);

      if (promptRes.status !== 200) {
        let errMsg = 'Error al enviar mensaje';
        try {
          const errData = JSON.parse(promptRes.data);
          errMsg = errData.error?.data?.message || errData.error?.message || errMsg;
        } catch { errMsg = promptRes.data?.substring(0, 200) || errMsg; }
        console.error(`[chat] Error ${promptRes.status}:`, errMsg);
        res.write(`data: ${JSON.stringify({ type: 'error', content: errMsg, done: true })}\n\n`);
        res.end();
        activeRequests.delete(requestId);
        return;
      }

      const result = JSON.parse(promptRes.data);
      if (result.parts && Array.isArray(result.parts)) {
        for (const part of result.parts) {
          if (part.type === 'text' && part.text) fullContent += part.text;
        }
      }
    }

    if (!fullContent) fullContent = '(sin respuesta)';

    // 5. Enviar respuesta como streaming simulado (fragmentos progresivos)
    const CHUNK_SIZE = 3; // caracteres por chunk
    const DELAY_MS = 10;  // milisegundos entre chunks

    for (let i = 0; i < fullContent.length; i += CHUNK_SIZE) {
      if (abortController.aborted) break;
      const chunk = fullContent.slice(0, i + CHUNK_SIZE);
      res.write(`data: ${JSON.stringify({ type: 'delta', content: chunk, done: false })}\n\n`);
      await new Promise(r => setTimeout(r, DELAY_MS));
    }

    // 6. Enviar respuesta final completa
    res.write(`data: ${JSON.stringify({ type: 'done', content: fullContent, done: true })}\n\n`);
    res.end();
    activeRequests.delete(requestId);

    console.log(`[chat] Request ${requestId.slice(0,8)} completado (${fullContent.length} chars)`);

  } catch (err) {
    console.error('[chat] Error:', err.message);
    if (!res.destroyed) {
      res.write(`data: ${JSON.stringify({ type: 'error', content: `Error: ${err.message}`, done: true })}\n\n`);
      res.end();
    }
    activeRequests.delete(requestId);
  }
});

// ── POST /api/chat/cancel — Cancela una solicitud activa ──
app.post('/api/chat/cancel', express.json(), (req, res) => {
  const { requestId } = req.body;
  const active = activeRequests.get(requestId);
  if (active) {
    active.abortController.aborted = true;
    active.res.end();
    activeRequests.delete(requestId);
    res.json({ ok: true, message: 'Solicitud cancelada' });
  } else {
    res.json({ ok: false, message: 'Solicitud no encontrada' });
  }
});

// ═══════════════════════════════════════════════════════════════
// WEB OPERATOR — Integración con chat
// ═══════════════════════════════════════════════════════════════
const OPERATOR_PORT = process.env.OPERATOR_PORT || 3001;
let operatorWs = null;
let operatorLogs = [];
let operatorActive = false;

// Conectar al Web Operator via WebSocket
function connectOperator() {
  // Will be connected on demand
}

// ── POST /api/operator/run — Ejecutar tarea de browser ──
app.post('/api/operator/run', express.json(), async (req, res) => {
  const { task, url, headless } = req.body;
  if (!task) return res.status(400).json({ error: 'task es requerido' });

  try {
    const resp = await fetch(`http://localhost:${OPERATOR_PORT}/api/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, url, headless: headless !== false }),
    });
    const data = await resp.json();
    res.json(data);
  } catch (err) {
    res.status(503).json({ error: 'Web Operator no disponible', detail: err.message });
  }
});

// ── GET /api/operator/status — Estado del operator ──
app.get('/api/operator/status', async (req, res) => {
  try {
    const resp = await fetch(`http://localhost:${OPERATOR_PORT}/api/status`);
    const data = await resp.json();
    res.json(data);
  } catch {
    res.json({ running: false, task: null, lastResult: null });
  }
});

// ── POST /api/operator/cancel — Cancelar tarea ──
app.post('/api/operator/cancel', async (req, res) => {
  try {
    const resp = await fetch(`http://localhost:${OPERATOR_PORT}/api/cancel`, { method: 'POST' });
    const data = await resp.json();
    res.json(data);
  } catch {
    res.json({ error: 'No disponible' });
  }
});

// ── GET /api/operator/screenshot — Último screenshot ──
app.get('/api/operator/screenshot', async (req, res) => {
  try {
    const resp = await fetch(`http://localhost:${OPERATOR_PORT}/api/screenshot`);
    if (resp.ok) {
      const buf = Buffer.from(await resp.arrayBuffer());
      res.writeHead(200, { 'Content-Type': 'image/png', 'Content-Length': buf.length });
      res.end(buf);
    } else {
      res.status(404).json({ error: 'Sin screenshot' });
    }
  } catch {
    res.status(503).json({ error: 'Operator no disponible' });
  }
});

// ── GET /api/sessions — Lista sesiones de OpenCode ──
app.get('/api/sessions', async (req, res) => {
  try {
    const result = await ocRequest('/session', 'GET');
    if (result.status === 200) {
      const data = JSON.parse(result.data);
      res.json({ sessions: data.sessions || data || [] });
    } else {
      res.json({ sessions: [] });
    }
  } catch (err) {
    res.json({ sessions: [] });
  }
});

// ── POST /api/sessions — Crear sesión ──
app.post('/api/sessions', express.json(), async (req, res) => {
  try {
    const result = await ocRequest('/session', 'POST', {});
    if (result.status === 200 || result.status === 201) {
      const data = JSON.parse(result.data);
      res.json(data);
    } else {
      res.status(500).json({ error: 'No se pudo crear la sesión' });
    }
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── DELETE /api/sessions/:id — Eliminar sesión ──
app.delete('/api/sessions/:id', async (req, res) => {
  try {
    const result = await ocRequest(`/session/${req.params.id}`, 'DELETE');
    // Limpiar del mapa
    for (const [key, val] of sessionMap.entries()) {
      if (val.ocSessionId === req.params.id || key === req.params.id) {
        sessionMap.delete(key);
      }
    }
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/sessions/:id/messages — Historial de mensajes ──
app.get('/api/sessions/:id/messages', async (req, res) => {
  try {
    const result = await ocRequest(`/session/${req.params.id}/message`, 'GET');
    if (result.status === 200) {
      const data = JSON.parse(result.data);
      // Formatear para el frontend
      const messages = [];
      if (Array.isArray(data)) {
        for (const msg of data) {
          if (msg.info?.role === 'user' || msg.info?.role === 'assistant') {
            let content = '';
            if (msg.parts) {
              for (const part of msg.parts) {
                if (part.type === 'text' && part.text) content += part.text;
              }
            }
            messages.push({
              id: msg.info.id,
              role: msg.info.role,
              content,
              model: msg.info.modelID,
              createdAt: new Date(msg.info.time?.created).toISOString(),
            });
          }
        }
      }
      res.json({ messages });
    } else {
      res.json({ messages: [] });
    }
  } catch (err) {
    res.json({ messages: [] });
  }
});

// ── Modelos endpoint ──
app.get('/api/models', (req, res) => {
  res.json({
    models: [
      // ── OPENCODE ZEN (GRATUITOS) ──
      { id: 'opencode/big-pickle', name: 'Big Pickle - Código general', provider: 'OpenCode Zen', caps: ['tools', 'reasoning'] },
      { id: 'opencode/north-mini-code-free', name: 'North Mini Code - Código rápido', provider: 'OpenCode Zen', caps: ['tools'] },
      { id: 'opencode/mimo-v2.5-free', name: 'MiMo V2.5 - Vision+Audio', provider: 'OpenCode Zen', caps: ['vision', 'audio', 'tools', 'reasoning'] },
      { id: 'opencode/nemotron-3-ultra-free', name: 'Nemotron Ultra - 1M contexto', provider: 'OpenCode Zen', caps: ['tools', 'reasoning'], context: 1000000 },
      { id: 'opencode/hy3-free', name: 'Hy3 - 256K contexto', provider: 'OpenCode Zen', caps: ['tools', 'reasoning'] },
      { id: 'opencode/deepseek-v4-flash-free', name: 'DeepSeek V4 Flash - Rápido', provider: 'OpenCode Zen', caps: ['tools'] },

      // ── FREEMODEL ($300 crédito gratis) ──
      { id: 'freemodel/gpt-5.5', name: 'GPT-5.5 - Más capaz', provider: 'Freemodel', caps: ['vision', 'tools', 'reasoning'], credits: '$300 free' },
      { id: 'freemodel/gpt-5.4', name: 'GPT-5.4 - General potente', provider: 'Freemodel', caps: ['vision', 'tools', 'reasoning'], credits: '$300 free' },
      { id: 'freemodel/gpt-5.4-mini', name: 'GPT-5.4 Mini - Rápido y barato', provider: 'Freemodel', caps: ['vision', 'tools', 'reasoning'], credits: '$300 free' },
      { id: 'freemodel/gpt-5.3-codex', name: 'GPT-5.3 Codex - Código', provider: 'Freemodel', caps: ['vision', 'tools', 'reasoning'], credits: '$300 free' },
    ]
  });
});

// ── Bridge para Modelos Freemodel (OpenAI Compatible) ──
const freemodelBridge = createProxyMiddleware({
  target: process.env.FREEMODEL_BASE_URL || 'https://api.freemodel.dev/v1',
  changeOrigin: true,
  pathRewrite: {
    '^/api/bridge/v1': ''
  },
  on: {
    proxyReq: (proxyReq) => {
      proxyReq.setHeader('Authorization', `Bearer ${process.env.FREEMODEL_API_KEY || 'fe_oa_db8434da9d092b657e26dba8e2cdbf5cc460848f7e3b490c'}`);
    }
  }
});
app.use('/api/bridge/v1', freemodelBridge);

app.use((req, res, next) => {
  const isApi = req.url.startsWith('/api');
  const acceptsHtml = req.headers.accept?.includes('text/html');

  if (isApi) {
    // Peticiones /api/* → api-server (ya manejadas por customApi si coinciden,
    // las que no coincidieron caen aquí)
    apiServerProxy(req, res, next);
  } else if (acceptsHtml || (!isApi && !req.url.includes('.'))) {
    // Rutas de la SPA React (sin extensión de archivo = ruta de cliente)
    if (existsSync(UI_INDEX)) {
      res.sendFile(UI_INDEX);
    } else {
      // Fallback al UI de OpenCode si no está compilado el frontend
      htmlProxy(req, res, next);
    }
  } else {
    // Assets estáticos no encontrados, ficheros JS/CSS → OpenCode proxy
    apiProxy(req, res, next);
  }
});

// ── Servidor HTTP con soporte WebSocket ─────────────────────
const server = createServer(app);

const wss = new WebSocketServer({ noServer: true });
wss.on('connection', (ws, req) => {
  const agentName = req.headers['x-agent-name'] || 'PC-Desconocido';
  let agentId = req.headers['x-agent-id'] || randomUUID();
  console.log(`[agent-server] ← Nuevo agente conectado: ${agentName}`);
  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data.toString());
      if (msg.type === 'register') {
        if (msg.agentId) agentId = msg.agentId; else agentId = randomUUID();
        pcAgents.set(agentId, { ws, name: msg.agentName || agentName, sysinfo: msg.sysinfo || {}, connectedAt: new Date() });
        ws.send(JSON.stringify({ type: 'registered', agentId }));
        console.log(`[agent-server] ✓ Agente registrado: ${agentId} (${msg.agentName})`);
      }
      if (msg.type === 'result') {
        const pending = pendingCmds.get(msg.requestId);
        if (pending) { pending.resolve(msg.result); pendingCmds.delete(msg.requestId); }
      }
    } catch (err) {
      console.error('[agent-server] Error:', err.message);
    }
  });
  ws.on('close', () => { pcAgents.delete(agentId); console.log(`[agent-server] ✗ Agente desconectado: ${agentId}`); });
  const pingInterval = setInterval(() => {
    if (ws.readyState === ws.OPEN) ws.send(JSON.stringify({ type: 'ping' })); else clearInterval(pingInterval);
  }, 30000);
});

const wsProxy = createProxyMiddleware({ target: OPENCODE_TARGET, changeOrigin: true, ws: true });
server.on("upgrade", (req, socket, head) => {
  if (req.url === '/agent') {
    wss.handleUpgrade(req, socket, head, (ws) => {
      wss.emit('connection', ws, req);
    });
  } else if (req.url.startsWith('/api')) {
    apiServerProxy.upgrade(req, socket, head);
  } else {
    wsProxy.upgrade(req, socket, head);
  }
});

server.listen(PORT, () => {
  console.log(`[proxy] Proxy UI escuchando en puerto ${PORT}`);
  console.log(`  → Proxying a OpenCode en http://localhost:${OPENCODE_PORT}`);
});

// También escuchar en puerto 80 para EasyPanel
if (PORT !== 80) {
  const server80 = createServer(app);
  server80.on('upgrade', (req, socket, head) => {
    if (req.url === '/agent') {
      wss.handleUpgrade(req, socket, head, (ws) => {
        wss.emit('connection', ws, req);
      });
    } else if (req.url.startsWith('/api')) {
      apiServerProxy.upgrade(req, socket, head);
    } else {
      wsProxy.upgrade(req, socket, head);
    }
  });
  server80.listen(80, () => {
    console.log(`[proxy] Proxy UI también escuchando en puerto 80`);
  });
}
