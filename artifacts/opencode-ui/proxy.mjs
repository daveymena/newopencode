import express from "express";
import { createProxyMiddleware } from "http-proxy-middleware";
import { createServer } from "http";
import path from "path";
import { fileURLToPath } from "url";
import https from "https";
import http from "http";
import { existsSync } from "fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PORT            = parseInt(process.env.PORT || "21293");
const OPENCODE_PORT   = parseInt(process.env.OPENCODE_INTERNAL_PORT || "21294");
const OPENCODE_TARGET = `http://localhost:${OPENCODE_PORT}`;

const app = express();
app.use(express.json({ limit: "20mb" }));
app.use(express.urlencoded({ extended: false }));

// ═══════════════════════════════════════════════════════════════
// AUTENTICACIÓN — Login con cookie de sesión
// Variables: OPENCODE_USERNAME (default: opencode)
//            OPENCODE_SERVER_PASSWORD (secret)
// ═══════════════════════════════════════════════════════════════
const AUTH_USER   = process.env.OPENCODE_USERNAME       || "opencode";
const AUTH_PASS   = process.env.OPENCODE_SERVER_PASSWORD || "";
const SESSION_KEY = "oc_session";
// Token de sesión: hash simple del usuario+contraseña
const SESSION_TOKEN = AUTH_PASS
  ? Buffer.from(`${AUTH_USER}:${AUTH_PASS}`).toString("base64")
  : "";

function isAuthenticated(req) {
  if (!AUTH_PASS) return true; // sin contraseña = acceso libre
  const cookie = req.headers.cookie || "";
  const match  = cookie.match(/oc_session=([^;]+)/);
  return match && match[1] === SESSION_TOKEN;
}

const LOGIN_HTML = (error = "") => `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenCode Evolved — Acceso</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{
    min-height:100vh;display:flex;align-items:center;justify-content:center;
    background:#07070d;
    background-image:
      radial-gradient(ellipse 80% 50% at 20% -10%,rgba(124,58,237,.22) 0%,transparent 60%),
      radial-gradient(ellipse 60% 40% at 80% 110%,rgba(59,130,246,.14) 0%,transparent 60%);
    font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif;
  }
  .card{
    width:340px;padding:36px 32px;
    background:rgba(13,13,22,.92);
    border:1px solid rgba(124,58,237,.28);
    border-radius:20px;
    box-shadow:0 24px 64px rgba(0,0,0,.6),0 0 0 1px rgba(255,255,255,.04);
    backdrop-filter:blur(24px);
  }
  .logo{display:flex;align-items:center;gap:10px;margin-bottom:28px;justify-content:center}
  .logo svg{width:28px;height:28px}
  .logo-text{font-size:17px;font-weight:700;color:#fff;letter-spacing:.4px}
  .badge{
    font-size:9px;font-weight:700;letter-spacing:1.2px;
    color:#8b5cf6;background:rgba(124,58,237,.15);
    border:1px solid rgba(124,58,237,.3);border-radius:4px;padding:2px 7px;
    text-transform:uppercase;
  }
  h2{font-size:14px;color:rgba(200,200,240,.7);text-align:center;margin-bottom:24px;font-weight:400}
  label{display:block;font-size:11.5px;color:rgba(180,180,220,.75);margin-bottom:6px;font-weight:500}
  input{
    width:100%;padding:10px 13px;margin-bottom:16px;
    background:rgba(255,255,255,.05);
    border:1px solid rgba(255,255,255,.1);
    border-radius:9px;color:rgba(240,240,255,.92);
    font-size:13px;outline:none;transition:all .15s;
  }
  input:focus{border-color:rgba(124,58,237,.6);box-shadow:0 0 0 3px rgba(124,58,237,.15)}
  button{
    width:100%;padding:11px;margin-top:4px;
    background:linear-gradient(135deg,#7c3aed,#6d28d9);
    border:none;border-radius:9px;color:#fff;
    font-size:13px;font-weight:600;cursor:pointer;transition:all .15s;letter-spacing:.3px;
  }
  button:hover{background:linear-gradient(135deg,#8b5cf6,#7c3aed);transform:translateY(-1px)}
  .error{
    background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.3);
    border-radius:8px;padding:9px 12px;margin-bottom:16px;
    font-size:12px;color:#f87171;text-align:center;
  }
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <svg viewBox="0 0 24 24" fill="none">
      <path d="M12 2L2 7L12 12L22 7Z" stroke="#8b5cf6" stroke-width="1.8" stroke-linejoin="round"/>
      <path d="M2 17L12 22L22 17" stroke="#8b5cf6" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M2 12L12 17L22 12" stroke="#6d28d9" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <span class="logo-text">OpenCode</span>
    <span class="badge">EVOLVED</span>
  </div>
  <h2>Ingresa tus credenciales para continuar</h2>
  ${error ? `<div class="error">❌ ${error}</div>` : ""}
  <form method="POST" action="/__login">
    <label for="u">Usuario</label>
    <input id="u" name="username" type="text" value="opencode" autocomplete="username" required>
    <label for="p">Contraseña</label>
    <input id="p" name="password" type="password" autocomplete="current-password" required autofocus>
    <button type="submit">Entrar →</button>
  </form>
</div>
</body>
</html>`;

// GET /__login → muestra el formulario
app.get("/__login", (req, res) => {
  if (isAuthenticated(req)) return res.redirect("/");
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(LOGIN_HTML());
});

// POST /__login → valida credenciales
app.post("/__login", (req, res) => {
  const { username, password } = req.body;
  if (username === AUTH_USER && password === AUTH_PASS) {
    res.setHeader("Set-Cookie",
      `${SESSION_KEY}=${SESSION_TOKEN}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400`
    );
    return res.redirect("/");
  }
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(LOGIN_HTML("Usuario o contraseña incorrectos"));
});

// GET /__logout → cierra sesión
app.get("/__logout", (req, res) => {
  res.setHeader("Set-Cookie", `${SESSION_KEY}=; Path=/; Max-Age=0`);
  res.redirect("/__login");
});

// Middleware de protección global
if (AUTH_PASS) {
  app.use((req, res, next) => {
    if (req.path.startsWith("/__shell") || req.path === "/__vision" ||
        req.path === "/__login" || req.path === "/__logout") return next();
    if (!isAuthenticated(req)) return res.redirect("/__login");
    next();
  });
}

// ── Static shell files (CSS + JS personalizado) ──────────────
app.use("/__shell", express.static(path.join(__dirname, "public")));

// ═══════════════════════════════════════════════════════════════
// ENDPOINT: /vision — Convierte imagen → texto descriptivo
// Permite que CUALQUIER modelo (Llama, Groq, Mistral, etc.)
// "vea" imágenes recibiendo una descripción detallada en texto.
// ═══════════════════════════════════════════════════════════════
app.post("/__vision", async (req, res) => {
  const { image, mime = "image/jpeg", question = "Describe esta imagen en detalle completo en español. Incluye: qué muestra, textos visibles, colores, objetos, personas, código si hay, errores, gráficos, cualquier información relevante." } = req.body;

  if (!image) return res.status(400).json({ error: "Falta el campo 'image' (base64)" });

  // Limpiar base64 si viene con prefijo data:url
  const base64 = image.includes(",") ? image.split(",")[1] : image;

  const FREEMODEL_KEY  = process.env.FREEMODEL_API_KEY;
  const FREEMODEL_URL  = process.env.FREEMODEL_BASE_URL || "https://api.freemodel.dev/v1";
  const FREEMODEL_MDL  = process.env.FREEMODEL_MODEL    || "gpt-4o";
  const ANTHROPIC_KEY  = process.env.ANTHROPIC_API_KEY  || process.env.AI_INTEGRATIONS_ANTHROPIC_API_KEY;
  const ANTHROPIC_URL  = process.env.ANTHROPIC_BASE_URL || "https://api.anthropic.com";
  const OPENAI_KEY     = process.env.OPENAI_API_KEY     || process.env.AI_INTEGRATIONS_OPENAI_API_KEY;
  const OPENAI_URL     = "https://api.openai.com";  // siempre usar OpenAI real, no FreeModel aquí
  const GEMINI_KEY     = process.env.GOOGLE_GENERATIVE_AI_API_KEY;

  // ── 1. FreeModel GPT-4o (gratis, prioridad alta) ─────────────
  if (FREEMODEL_KEY) {
    try {
      const desc = await callOpenAIVision(FREEMODEL_KEY, FREEMODEL_URL, base64, mime, question, FREEMODEL_MDL);
      return res.json({ description: desc, model: `freemodel/${FREEMODEL_MDL} (visión gratis)` });
    } catch (e) {
      console.error("[vision] FreeModel falló:", e.message);
    }
  }

  // ── 2. Anthropic Claude Haiku ────────────────────────────────
  if (ANTHROPIC_KEY) {
    try {
      const desc = await callAnthropicVision(ANTHROPIC_KEY, ANTHROPIC_URL, base64, mime, question);
      return res.json({ description: desc, model: "claude-haiku (visión)" });
    } catch (e) {
      console.error("[vision] Anthropic falló:", e.message);
    }
  }

  // ── 3. OpenAI GPT-4o ─────────────────────────────────────────
  if (OPENAI_KEY) {
    try {
      const desc = await callOpenAIVision(OPENAI_KEY, OPENAI_URL, base64, mime, question, "gpt-4o-mini");
      return res.json({ description: desc, model: "gpt-4o (visión)" });
    } catch (e) {
      console.error("[vision] OpenAI falló:", e.message);
    }
  }

  // ── 4. Gemini Flash ──────────────────────────────────────────
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
    hint: "FREEMODEL_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY o GOOGLE_GENERATIVE_AI_API_KEY"
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

async function callOpenAIVision(key, baseUrl, base64, mime, question, model = "gpt-4o-mini") {
  const url = baseUrl.endsWith("/v1") ? `${baseUrl}/chat/completions` : `${baseUrl}/v1/chat/completions`;
  const res = await httpsPost(
    url,
    { "Authorization": `Bearer ${key}` },
    {
      model,
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
// FRONTEND STANDALONE — Sirve UI local si existe
// ═══════════════════════════════════════════════════════════════
const UI_DIR_DOCKER = '/app/ui';
const UI_DIR_LOCAL  = path.join(__dirname, 'ui');
const UI_DIR        = existsSync(UI_DIR_DOCKER) ? UI_DIR_DOCKER : UI_DIR_LOCAL;
const UI_INDEX      = path.join(UI_DIR, 'index.html');
const hasStandalone = existsSync(UI_INDEX);

if (hasStandalone) {
  app.use(express.static(UI_DIR, { index: false }));
  console.log(`✦ Frontend standalone cargado desde ${UI_DIR}`);
} else {
  console.log(`✦ Frontend standalone no encontrado en ${UI_INDEX} — usando UI de OpenCode`);
}

// ═══════════════════════════════════════════════════════════════
// Shell injection HTML
// ═══════════════════════════════════════════════════════════════
const shellCSS = `<link rel="stylesheet" href="/__shell/shell.css">`;
const shellJS  = `<script src="/__shell/shell.js"></script>`;

// ── Proxy principal → OpenCode ──────────────────────────────
const proxyOptions = {
  target: OPENCODE_TARGET,
  changeOrigin: true,
  selfHandleResponse: true,
  onProxyReq: (proxyReq, req) => {
    if (AUTH_PASS) {
      const reqCookie = req.headers.cookie || "";
      if (!reqCookie.includes("oc_session=")) {
        proxyReq.setHeader("Cookie", `oc_session=${SESSION_TOKEN}`);
      }
    }
  },
  on: {
    proxyRes: (proxyRes, req, res) => {
      const contentType = proxyRes.headers["content-type"] || "";
      const isHTML = contentType.includes("text/html");

      delete proxyRes.headers["content-security-policy"];
      delete proxyRes.headers["x-frame-options"];
      delete proxyRes.headers["content-length"];

      if (proxyRes.statusCode === 401 || proxyRes.statusCode === 403) {
        if (AUTH_PASS) {
          const injectUrl = proxyRes.headers["location"] || "";
          if (injectUrl.includes("login") || injectUrl.includes("auth")) {
            const reqCookie = req.headers.cookie || "";
            if (!reqCookie.includes("oc_session=")) {
              res.setHeader("Set-Cookie",
                `${SESSION_KEY}=${SESSION_TOKEN}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400`
              );
            }
          }
        }
      }

      Object.entries(proxyRes.headers).forEach(([key, val]) => res.setHeader(key, val));
      res.statusCode = proxyRes.statusCode;

      if (!isHTML) { proxyRes.pipe(res); return; }

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
<html lang="es"><head><meta charset="utf-8"><title>OpenCode Evolved</title>
<style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#0f0f1a;color:#e2e8f0}.card{text-align:center;padding:2rem;border-radius:12px;background:#1e1e2e;border:1px solid #334155;max-width:400px}h1{color:#8b5cf6;margin:0 0 .5rem}p{color:#94a3b8;margin:0 0 1.5rem}button{background:#8b5cf6;color:#fff;border:none;padding:.75rem 1.5rem;border-radius:8px;font-size:1rem;cursor:pointer}button:hover{background:#7c3aed}</style></head>
<body><div class="card"><h1>OpenCode</h1><p>Iniciando servidor...</p><button onclick="location.reload()">Reintentar</button></div></body></html>`);
      }
    },
  },
};

// Solo proxiar a OpenCode si NO hay frontend standalone
// o si la ruta es una API/asset que no existe localmente
if (hasStandalone) {
  // Con frontend standalone: solo proxiar /api/* y assets no encontrados
  app.use("/api", createProxyMiddleware({ ...proxyOptions, pathRewrite: undefined }));
  app.use("/__shell", createProxyMiddleware({ ...proxyOptions, pathRewrite: undefined }));
  // SPA catch-all: servir index.html para rutas que no son API
  app.use((req, res, next) => {
    if (req.method === 'GET' && !req.path.startsWith('/api') && !req.path.startsWith('/__')) {
      res.sendFile(UI_INDEX);
    } else {
      next();
    }
  });
} else {
  // Sin frontend standalone: proxy completo a OpenCode
  app.use("/", createProxyMiddleware(proxyOptions));
}

// ── Servidor HTTP con soporte WebSocket ─────────────────────
const server = createServer(app);
const wsProxy = createProxyMiddleware({ target: OPENCODE_TARGET, changeOrigin: true, ws: true });
server.on("upgrade", (req, socket, head) => wsProxy.upgrade(req, socket, head));

server.listen(PORT, "0.0.0.0", () => {
  console.log(`✦ OpenCode Evolved shell corriendo en http://0.0.0.0:${PORT}`);
  console.log(`  → Proxying a OpenCode en ${OPENCODE_TARGET}`);
});
