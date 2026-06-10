#!/usr/bin/env node
/**
 * OpenCode Evolved — Telegram Agent
 * API directa de Telegram via HTTPS (sin dependencias externas)
 *
 * Capacidades:
 * • Ejecutar comandos del sistema
 * • Controlar PCs remotos via SSH (Linux, Mac, Windows)
 * • PowerShell remoto en Windows
 * • Navegar internet, tomar screenshots
 * • Analizar imágenes enviadas al bot
 * • Correr Python y JavaScript
 * • Agente autónomo con tareas largas
 *
 * Comandos Telegram:
 *   /start  — bienvenida
 *   /ayuda  — capacidades
 *   /nuevo  — nueva sesión
 *   /estado — info del sistema
 *   /stop   — detener tarea
 */

import https from "https";
import http from "http";
import { execSync } from "child_process";
import { readFileSync, writeFileSync, existsSync, mkdirSync, statSync, createReadStream } from "fs";
import { dirname } from "path";

const TOKEN     = process.env.TELEGRAM_BOT_TOKEN;
const API_KEY   = process.env.ANTHROPIC_API_KEY || process.env.AI_INTEGRATIONS_ANTHROPIC_API_KEY;
const API_URL   = process.env.ANTHROPIC_BASE_URL || "https://api.anthropic.com";
const WORKSPACE = "/home/runner/workspace";
const PW_CACHE  = "/home/runner/workspace/.cache/ms-playwright";

if (!TOKEN) {
  console.error("❌ TELEGRAM_BOT_TOKEN no encontrado. Agrégalo en Replit Secrets.");
  process.exit(0); // salir limpiamente sin crashear el proceso principal
}

// ── HTTP helper ───────────────────────────────────────────────
function request(url, opts = {}, body = null) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const options = {
      hostname: u.hostname,
      port:     u.port || (u.protocol === "https:" ? 443 : 80),
      path:     u.pathname + u.search,
      method:   opts.method || (body ? "POST" : "GET"),
      headers:  opts.headers || {},
      timeout:  opts.timeout || 120000
    };
    if (body) {
      const buf = Buffer.isBuffer(body) ? body : Buffer.from(JSON.stringify(body));
      options.headers["Content-Type"] = options.headers["Content-Type"] || "application/json";
      options.headers["Content-Length"] = buf.length;
    }
    const mod = u.protocol === "https:" ? https : http;
    let data = Buffer.alloc(0);
    const req = mod.request(options, res => {
      res.on("data", c => { data = Buffer.concat([data, c]); });
      res.on("end", () => {
        try { resolve(JSON.parse(data.toString())); }
        catch { resolve(data.toString()); }
      });
    });
    req.on("error", reject);
    req.on("timeout", () => { req.destroy(); reject(new Error("Timeout")); });
    if (body) req.write(Buffer.isBuffer(body) ? body : JSON.stringify(body));
    req.end();
  });
}

// ── Telegram API ──────────────────────────────────────────────
const TG = `https://api.telegram.org/bot${TOKEN}`;
const TG_FILE = `https://api.telegram.org/file/bot${TOKEN}`;

async function tgCall(method, params = {}) {
  try {
    const res = await request(`${TG}/${method}`, { method:"POST" }, params);
    return res;
  } catch(e) { return { ok:false, error: e.message }; }
}

async function sendMsg(chatId, text, extra = {}) {
  const MAX = 4000;
  for (let i = 0; i < text.length; i += MAX) {
    const chunk = text.slice(i, i + MAX);
    await tgCall("sendMessage", { chat_id:chatId, text:chunk, ...extra });
    if (text.length > MAX) await sleep(300);
  }
}

async function sendPhoto(chatId, filePath, caption = "") {
  // Usar sendPhoto via URL o file_id no disponible sin multipart — enviar vía link
  // Como alternativa, informamos que el screenshot está guardado
  await sendMsg(chatId, `📸 Screenshot guardado en: ${filePath}\n${caption}`);
}

async function sendAction(chatId, action = "typing") {
  await tgCall("sendChatAction", { chat_id:chatId, action });
}

async function getFileUrl(fileId) {
  const r = await tgCall("getFile", { file_id: fileId });
  if (r.ok) return `${TG_FILE}/${r.result.file_path}`;
  return null;
}

async function downloadAsBase64(url) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    https.get(url, res => {
      res.on("data", c => chunks.push(c));
      res.on("end", () => resolve(Buffer.concat(chunks).toString("base64")));
    }).on("error", reject);
  });
}

// ── Estado ────────────────────────────────────────────────────
const sessions = new Map(); // chatId → { history, busy }
function sess(chatId) {
  if (!sessions.has(chatId)) sessions.set(chatId, { history:[], busy:false });
  return sessions.get(chatId);
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

// ── Herramientas para Claude ──────────────────────────────────
const TOOLS = [
  { name:"run_command",
    description:"Ejecuta cualquier comando bash en el servidor Linux",
    input_schema:{ type:"object", properties:{ command:{type:"string"}, cwd:{type:"string"} }, required:["command"] } },
  { name:"run_python",
    description:"Ejecuta código Python 3 y retorna stdout/stderr",
    input_schema:{ type:"object", properties:{ code:{type:"string"} }, required:["code"] } },
  { name:"run_javascript",
    description:"Ejecuta código JavaScript con Node.js",
    input_schema:{ type:"object", properties:{ code:{type:"string"} }, required:["code"] } },
  { name:"ssh_run",
    description:"Ejecuta comandos en PC remoto via SSH (Linux, Mac, Windows con SSH habilitado)",
    input_schema:{ type:"object",
      properties:{ host:{type:"string"}, user:{type:"string"}, password:{type:"string"}, command:{type:"string"}, port:{type:"number"} },
      required:["host","user","command"] } },
  { name:"windows_powershell",
    description:"Ejecuta PowerShell en Windows remoto via SSH",
    input_schema:{ type:"object",
      properties:{ host:{type:"string"}, user:{type:"string"}, password:{type:"string"}, script:{type:"string"} },
      required:["host","user","script"] } },
  { name:"web_browse",
    description:"Abre una URL y extrae el texto de la página",
    input_schema:{ type:"object", properties:{ url:{type:"string"} }, required:["url"] } },
  { name:"web_search",
    description:"Busca en internet via DuckDuckGo",
    input_schema:{ type:"object", properties:{ query:{type:"string"} }, required:["query"] } },
  { name:"screenshot_url",
    description:"Toma screenshot de una URL web con Playwright headless",
    input_schema:{ type:"object", properties:{ url:{type:"string"} }, required:["url"] } },
  { name:"read_file",
    description:"Lee un archivo de texto del servidor",
    input_schema:{ type:"object", properties:{ path:{type:"string"} }, required:["path"] } },
  { name:"write_file",
    description:"Crea o sobreescribe un archivo en el servidor",
    input_schema:{ type:"object",
      properties:{ path:{type:"string"}, content:{type:"string"} }, required:["path","content"] } },
  { name:"system_status",
    description:"CPU, RAM, disco y procesos del servidor",
    input_schema:{ type:"object", properties:{} } },
  { name:"download_file",
    description:"Descarga archivo de internet al servidor",
    input_schema:{ type:"object",
      properties:{ url:{type:"string"}, destination:{type:"string"} }, required:["url","destination"] } },
  { name:"list_directory",
    description:"Lista el contenido de un directorio",
    input_schema:{ type:"object", properties:{ path:{type:"string"} }, required:["path"] } }
];

// ── Ejecutores de herramientas ────────────────────────────────
function run(cmd, opts = {}) {
  return execSync(cmd, {
    encoding:"utf8", timeout:60000, shell:"/bin/bash",
    env:{ ...process.env, PLAYWRIGHT_BROWSERS_PATH:PW_CACHE },
    cwd: opts.cwd || WORKSPACE, ...opts
  });
}

async function fetchText(url) {
  return new Promise(r => {
    const mod = url.startsWith("https") ? https : http;
    let d = "";
    const req = mod.get(url, { headers:{"User-Agent":"Mozilla/5.0"} }, res => {
      res.on("data", c => { d += c; });
      res.on("end", () => {
        d = d.replace(/<script[^>]*>[\s\S]*?<\/script>/gi,"")
             .replace(/<style[^>]*>[\s\S]*?<\/style>/gi,"")
             .replace(/<[^>]+>/g," ").replace(/\s+/g," ").trim().slice(0,6000);
        r(d);
      });
    });
    req.on("error", e => r(`Error: ${e.message}`));
    req.setTimeout(20000, () => { req.destroy(); r("Timeout"); });
  });
}

async function execTool(name, args, chatId) {
  try {
    switch(name) {

      case "run_command":
        return run(args.command, { cwd: args.cwd || WORKSPACE });

      case "run_python": {
        const f = `/tmp/tg-py-${Date.now()}.py`;
        writeFileSync(f, args.code);
        return run(`python3 "${f}"`);
      }

      case "run_javascript": {
        const f = `/tmp/tg-js-${Date.now()}.mjs`;
        writeFileSync(f, args.code);
        return run(`node "${f}"`);
      }

      case "ssh_run": {
        const pass = args.password ? `sshpass -p '${args.password.replace(/'/g,"'\\''")}'` : "";
        const port = args.port ? `-p ${args.port}` : "";
        return run(`${pass} ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 ${port} ${args.user}@${args.host} '${args.command.replace(/'/g,"'\\''")}'`);
      }

      case "windows_powershell": {
        const pass = args.password ? `sshpass -p '${args.password.replace(/'/g,"'\\''")}'` : "";
        const ps = `powershell.exe -NonInteractive -Command "${args.script.replace(/"/g,'\\"')}"`;
        return run(`${pass} ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 ${args.user}@${args.host} '${ps.replace(/'/g,"'\\''")}'`);
      }

      case "web_browse":
        return await fetchText(args.url);

      case "web_search":
        return await fetchText(`https://html.duckduckgo.com/html/?q=${encodeURIComponent(args.query)}`);

      case "screenshot_url": {
        const out = `/tmp/tg-ss-${Date.now()}.png`;
        const script = `
import('file:///home/runner/mcp-tools/node_modules/playwright/index.mjs').then(async ({chromium})=>{
  const b = await chromium.launch({headless:true,args:['--no-sandbox']});
  const p = await b.newPage();
  await p.setViewportSize({width:1280,height:720});
  await p.goto(${JSON.stringify(args.url)},{waitUntil:'networkidle',timeout:30000});
  await p.screenshot({path:${JSON.stringify(out)}});
  await b.close();
  console.log('OK:${out}');
}).catch(e=>{console.error(e.message);process.exit(1)});`;
        const tf = `/tmp/tg-pw-${Date.now()}.mjs`;
        writeFileSync(tf, script);
        run(`PLAYWRIGHT_BROWSERS_PATH="${PW_CACHE}" node "${tf}"`, { timeout:45000 });
        if (existsSync(out)) {
          await sendMsg(chatId, `📸 Screenshot listo: ${out} (${(statSync(out).size/1024).toFixed(1)}KB)\nℹ️  Archivo guardado en el servidor. Puedes pedirme que lo lea o lo procese.`);
          return `Screenshot guardado en ${out}`;
        }
        return "Screenshot procesado (chromium no disponible en este entorno)";
      }

      case "read_file":
        return existsSync(args.path) ? readFileSync(args.path,"utf8").slice(0,4000) : `No existe: ${args.path}`;

      case "write_file": {
        const dir = dirname(args.path);
        if (!existsSync(dir)) mkdirSync(dir,{recursive:true});
        writeFileSync(args.path, args.content);
        return `✅ Guardado: ${args.path} (${args.content.length} bytes)`;
      }

      case "system_status":
        return run("echo '=CPU=' && nproc && echo '=RAM=' && free -h && echo '=DISCO=' && df -h / | tail -1 && echo '=TOP PROCESOS=' && ps aux --sort=-%cpu | head -8");

      case "download_file": {
        const dir = dirname(args.destination);
        if (!existsSync(dir)) mkdirSync(dir,{recursive:true});
        return run(`curl -L -# -o "${args.destination}" "${args.url}"`, {timeout:120000});
      }

      case "list_directory":
        return existsSync(args.path)
          ? run(`ls -lah "${args.path}" | head -40`)
          : `No existe: ${args.path}`;

      default:
        return `Herramienta desconocida: ${name}`;
    }
  } catch(e) {
    return `❌ Error (${name}): ${e.message.slice(0,400)}`;
  }
}

// ── Claude API (agentic loop) ─────────────────────────────────
const SYSTEM = `Eres OpenCode Evolved Agent, un asistente AI con control total del sistema.
Herramientas disponibles: ejecutar comandos bash, Python, JavaScript, controlar PCs remotos via SSH, PowerShell en Windows, navegar internet, leer/escribir archivos, tomar screenshots.
Responde SIEMPRE en español. Sé conciso. Cuando uses una herramienta, describe brevemente lo que estás haciendo en una línea antes.
Si ves una imagen, analízala en detalle.`;

async function claudeChat(messages) {
  if (!API_KEY) return null;
  const urlObj = new URL(`${API_URL}/v1/messages`);
  const body = { model:"claude-sonnet-4-5", max_tokens:4096, system:SYSTEM, tools:TOOLS, messages };
  const res = await request(urlObj.href, {
    method:"POST",
    headers:{ "Content-Type":"application/json", "anthropic-version":"2023-06-01", "x-api-key":API_KEY },
    timeout:120000
  }, body);
  return res;
}

async function runAgent(chatId, userText, imageBase64 = null) {
  const s = sess(chatId);
  s.busy = true;

  const userContent = [];
  if (imageBase64) {
    userContent.push({ type:"image", source:{ type:"base64", media_type:"image/jpeg", data:imageBase64 } });
  }
  userContent.push({ type:"text", text: userText });
  s.history.push({ role:"user", content: userContent });

  await sendAction(chatId, "typing");

  if (!API_KEY) {
    // Sin IA — modo comando directo
    await sendMsg(chatId, "⚠️ Sin clave ANTHROPIC_API_KEY. Ejecutando como comando directo...");
    try {
      const result = run(userText, { cwd: WORKSPACE });
      await sendMsg(chatId, `\`\`\`\n${result.slice(0,3000)}\n\`\`\``, { parse_mode:"Markdown" });
    } catch(e) {
      await sendMsg(chatId, `❌ ${e.message.slice(0,500)}`);
    }
    s.busy = false;
    return;
  }

  let loops = 0;
  while (s.busy && loops++ < 15) {
    let resp;
    try { resp = await claudeChat(s.history); }
    catch(e) { await sendMsg(chatId, `❌ Error API: ${e.message}`); break; }

    if (!resp || resp.error || !resp.content) {
      await sendMsg(chatId, `❌ Error: ${JSON.stringify(resp).slice(0,200)}`);
      break;
    }

    s.history.push({ role:"assistant", content: resp.content });

    const toolResults = [];
    let hasTools = false;

    for (const block of resp.content) {
      if (block.type === "text" && block.text?.trim()) {
        await sendMsg(chatId, block.text);
      }
      if (block.type === "tool_use") {
        hasTools = true;
        await sendAction(chatId, "typing");
        const argsStr = JSON.stringify(block.input || {}).slice(0,150);
        await sendMsg(chatId, `🔧 \`${block.name}\`: ${argsStr}`, { parse_mode:"Markdown" });
        const result = await execTool(block.name, block.input || {}, chatId);
        const resStr = String(result).slice(0,2000);
        if (resStr.length > 100) {
          await sendMsg(chatId, `\`\`\`\n${resStr}\n\`\`\``, { parse_mode:"Markdown" });
        }
        toolResults.push({ type:"tool_result", tool_use_id:block.id, content:resStr });
      }
    }

    if (hasTools) {
      s.history.push({ role:"user", content:toolResults });
      await sendAction(chatId, "typing");
      continue;
    }
    break; // respuesta final sin herramientas
  }

  s.busy = false;
}

// ── Long-polling Telegram ─────────────────────────────────────
let offset = 0;

async function processUpdate(update) {
  const msg = update.message || update.edited_message;
  if (!msg) return;

  const chatId  = msg.chat.id;
  const text    = msg.text || "";
  const s       = sess(chatId);

  // Comandos
  if (text === "/start" || text.startsWith("/start ")) {
    const name = msg.from?.first_name || "usuario";
    return sendMsg(chatId,
`🚀 *OpenCode Evolved Agent*

Hola ${name}! Soy tu agente AI con control total del sistema.

Puedo hacer:
🖥 Ejecutar comandos bash en el servidor
🌐 Conectarme via SSH a cualquier PC remoto
🪟 Controlar Windows via PowerShell
🤖 Correr Python y JavaScript
📷 Analizar imágenes (manda fotos directamente)
🔍 Buscar en internet y tomar screenshots
📁 Leer y crear archivos

*Comandos:*
/nuevo — nueva sesión
/estado — info del sistema  
/stop — detener tarea en curso
/ayuda — más detalles

¡Escribe lo que necesitas en español! 💪`, { parse_mode:"Markdown" });
  }

  if (text === "/ayuda") {
    return sendMsg(chatId,
`🛠 *Ejemplos de uso:*

• "ejecuta df -h para ver el disco"
• "conectate via SSH a 192.168.1.50 como admin con pass mipass y muestra los procesos"
• "corre este Python: print(2+2)"
• "busca en internet las últimas noticias de IA"
• "toma un screenshot de github.com"
• "lee el archivo /home/runner/workspace/package.json"
• "crea un archivo /tmp/test.txt con el texto Hola mundo"
• (manda una foto) → la analizo automáticamente

*Control Windows:*
• "ejecuta en Windows 192.168.1.100 user Admin pass 1234: Get-Process | head 10"

Todo en lenguaje natural 🗣`, { parse_mode:"Markdown" });
  }

  if (text === "/nuevo") {
    sessions.delete(chatId);
    return sendMsg(chatId, "🆕 Nueva sesión iniciada. ¿Qué necesitas?");
  }

  if (text === "/estado") {
    try {
      const info = run("echo 'CPU:' && nproc && echo 'RAM:' && free -h | grep Mem && echo 'DISCO:' && df -h / | tail -1", {timeout:5000});
      return sendMsg(chatId, `📊 *Estado:*\n\`\`\`\n${info}\`\`\``, { parse_mode:"Markdown" });
    } catch(e) { return sendMsg(chatId, `❌ ${e.message}`); }
  }

  if (text === "/stop") {
    s.busy = false;
    return sendMsg(chatId, "🛑 Tarea detenida.");
  }

  // Foto → análisis de imagen
  if (msg.photo) {
    if (s.busy) return sendMsg(chatId, "⏳ Hay una tarea en curso. Usa /stop para detenerla.");
    await sendMsg(chatId, "📷 Imagen recibida, analizando...");
    try {
      const best = msg.photo[msg.photo.length - 1];
      const fileUrl = await getFileUrl(best.file_id);
      const b64 = fileUrl ? await downloadAsBase64(fileUrl) : null;
      const caption = msg.caption || "Describe esta imagen en detalle";
      await runAgent(chatId, caption, b64);
    } catch(e) { await sendMsg(chatId, `❌ Error con imagen: ${e.message}`); }
    return;
  }

  // Mensaje de texto normal
  if (!text || text.startsWith("/")) return;
  if (s.busy) return sendMsg(chatId, "⏳ Tarea en curso. Usa /stop para detenerla.");

  runAgent(chatId, text).catch(async e => {
    await sendMsg(chatId, `❌ ${e.message}`);
    s.busy = false;
  });
}

async function poll() {
  while (true) {
    try {
      const res = await request(`${TG}/getUpdates`, {
        method: "POST",
        headers: { "Content-Type":"application/json" },
        timeout: 35000
      }, { offset, timeout: 30, allowed_updates:["message","edited_message"] });

      if (res.ok && res.result?.length) {
        for (const upd of res.result) {
          offset = upd.update_id + 1;
          processUpdate(upd).catch(e => console.error("[upd error]", e.message));
        }
      }
    } catch(e) {
      if (!e.message.includes("Timeout")) {
        console.error("[poll]", e.message);
      }
      await sleep(3000);
    }
  }
}

// ── Arrancar ──────────────────────────────────────────────────
console.log("🤖 OpenCode Evolved — Telegram Agent arrancando...");
poll().catch(e => console.error("Poll fatal:", e.message));
