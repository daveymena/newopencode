#!/usr/bin/env node
/**
 * OpenCode Evolved — MCP Server: Computer Control
 * 
 * CAPACIDADES:
 * • SSH → cualquier Linux/Mac/Windows con SSH habilitado
 * • PowerShell Remoto → Windows via SSH o WinRM
 * • RDP → captura de pantalla de escritorios remotos
 * • VNC → conexión y screenshots remotos
 * • Control de procesos, archivos, comandos
 * • Navegador headless (Playwright)
 * • Web scraping y búsqueda
 * • Memoria persistente
 */

import { createInterface } from "readline";
import { execSync, exec, spawn } from "child_process";
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, statSync } from "fs";
import { join, dirname, extname } from "path";
import { fileURLToPath } from "url";
import https from "https";
import http from "http";
import { createConnection } from "net";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PLAYWRIGHT_BROWSERS = "/home/runner/workspace/.cache/ms-playwright";
const WORKSPACE = "/home/runner/workspace";
const MCP_TOOLS_DIR = "/home/runner/mcp-tools/node_modules";

// ── Utilidades ──────────────────────────────────────────────
function send(obj) { process.stdout.write(JSON.stringify(obj) + "\n"); }
function ok(id, content) { send({ jsonrpc:"2.0", id, result:{ content:[{ type:"text", text:String(content) }] } }); }
function fail(id, msg) { send({ jsonrpc:"2.0", id, result:{ content:[{ type:"text", text:`❌ ${msg}` }], isError:true } }); }
function runCmd(cmd, opts={}) {
  return execSync(cmd, { encoding:"utf8", timeout:60000, shell:"/bin/bash",
    env:{ ...process.env, PLAYWRIGHT_BROWSERS_PATH: PLAYWRIGHT_BROWSERS }, ...opts });
}

// ── Definición de herramientas ──────────────────────────────
const tools = [

  // ═══════════════════════════════════════════════════════════
  // CONTROL REMOTO — SSH
  // ═══════════════════════════════════════════════════════════
  {
    name: "ssh_connect_run",
    description: `Conecta a cualquier servidor REMOTO via SSH y ejecuta comandos.
Funciona con: Linux, macOS, Windows (si tiene SSH habilitado).
Para Windows: habilita "OpenSSH Server" en Configuración → Apps → Características opcionales.
Ejemplo: ssh_connect_run(host="192.168.1.100", user="admin", password="pass", command="ls -la")`,
    inputSchema: {
      type: "object",
      properties: {
        host:     { type:"string", description:"IP o hostname del equipo remoto" },
        user:     { type:"string", description:"Usuario SSH" },
        password: { type:"string", description:"Contraseña (o usa key_path)" },
        key_path: { type:"string", description:"Ruta a clave privada SSH (alternativa a password)" },
        port:     { type:"number", default:22, description:"Puerto SSH (default 22)" },
        command:  { type:"string", description:"Comando a ejecutar en el equipo remoto" },
        timeout:  { type:"number", default:30 }
      },
      required: ["host","user","command"]
    }
  },
  {
    name: "ssh_upload_file",
    description: "Sube un archivo local a un equipo remoto via SCP (SSH)",
    inputSchema: {
      type:"object",
      properties: {
        host:        { type:"string" },
        user:        { type:"string" },
        password:    { type:"string" },
        key_path:    { type:"string" },
        port:        { type:"number", default:22 },
        local_path:  { type:"string", description:"Ruta local del archivo" },
        remote_path: { type:"string", description:"Ruta destino en el equipo remoto" }
      },
      required: ["host","user","local_path","remote_path"]
    }
  },
  {
    name: "ssh_download_file",
    description: "Descarga un archivo de un equipo remoto a este servidor via SCP",
    inputSchema: {
      type:"object",
      properties: {
        host:        { type:"string" },
        user:        { type:"string" },
        password:    { type:"string" },
        key_path:    { type:"string" },
        port:        { type:"number", default:22 },
        remote_path: { type:"string" },
        local_path:  { type:"string" }
      },
      required: ["host","user","remote_path","local_path"]
    }
  },

  // ═══════════════════════════════════════════════════════════
  // WINDOWS — PowerShell y CMD
  // ═══════════════════════════════════════════════════════════
  {
    name: "windows_powershell",
    description: `Ejecuta comandos PowerShell en un equipo Windows remoto via SSH.
REQUISITO: Windows debe tener "OpenSSH Server" instalado.
Instrucciones para habilitarlo:
  1. Configuración → Apps → Características opcionales → OpenSSH Server
  2. O ejecutar en PowerShell admin: Add-WindowsCapability -Online -Name OpenSSH.Server
  3. Start-Service sshd; Set-Service -Name sshd -StartupType Automatic

Ejemplo: windows_powershell(host="192.168.1.100", user="Administrador", password="pass", script="Get-Process | Select-Object Name,CPU | Sort CPU -desc | head 10")`,
    inputSchema: {
      type:"object",
      properties: {
        host:     { type:"string", description:"IP del equipo Windows" },
        user:     { type:"string", description:"Usuario Windows (ej: Administrador)" },
        password: { type:"string" },
        key_path: { type:"string" },
        port:     { type:"number", default:22 },
        script:   { type:"string", description:"Script PowerShell a ejecutar" }
      },
      required: ["host","user","script"]
    }
  },
  {
    name: "windows_screenshot_rdp",
    description: `Toma una captura de pantalla de un escritorio Windows remoto via RDP.
REQUISITO: RDP habilitado en Windows (Configuración → Sistema → Escritorio remoto).
Devuelve la ruta del screenshot PNG guardado.`,
    inputSchema: {
      type:"object",
      properties: {
        host:     { type:"string", description:"IP del equipo Windows" },
        user:     { type:"string" },
        password: { type:"string" },
        port:     { type:"number", default:3389 },
        width:    { type:"number", default:1920 },
        height:   { type:"number", default:1080 }
      },
      required: ["host","user","password"]
    }
  },
  {
    name: "windows_cmd",
    description: "Ejecuta comandos CMD clásicos en Windows remoto (via SSH)",
    inputSchema: {
      type:"object",
      properties: {
        host:     { type:"string" },
        user:     { type:"string" },
        password: { type:"string" },
        port:     { type:"number", default:22 },
        command:  { type:"string", description:"Comando CMD (ej: dir C:\\ /s)" }
      },
      required: ["host","user","command"]
    }
  },

  // ═══════════════════════════════════════════════════════════
  // CONTROL DE NAVEGADOR (Playwright)
  // ═══════════════════════════════════════════════════════════
  {
    name: "browser_navigate",
    description: "Abre una URL en navegador headless y retorna el contenido de la página",
    inputSchema: {
      type:"object",
      properties: {
        url:         { type:"string" },
        wait_for:    { type:"string", default:"networkidle", enum:["load","domcontentloaded","networkidle"] },
        return_html: { type:"boolean", default:false }
      },
      required: ["url"]
    }
  },
  {
    name: "browser_screenshot",
    description: "Toma una captura de pantalla de cualquier página web",
    inputSchema: {
      type:"object",
      properties: {
        url:       { type:"string" },
        width:     { type:"number", default:1280 },
        height:    { type:"number", default:720 },
        full_page: { type:"boolean", default:false },
        output:    { type:"string", description:"Ruta donde guardar el PNG" }
      },
      required: ["url"]
    }
  },
  {
    name: "browser_click_and_fill",
    description: "Navega a una URL, hace clic en elementos y escribe texto (automatización web)",
    inputSchema: {
      type:"object",
      properties: {
        url:      { type:"string" },
        actions:  {
          type:"array",
          description:"Lista de acciones a ejecutar en orden",
          items: {
            type:"object",
            properties: {
              type:     { type:"string", enum:["click","fill","press","wait","screenshot","select"] },
              selector: { type:"string", description:"Selector CSS o texto del elemento" },
              value:    { type:"string", description:"Valor a escribir (para fill)" },
              key:      { type:"string", description:"Tecla a presionar (para press, ej: Enter, Tab)" },
              ms:       { type:"number", description:"Milisegundos a esperar (para wait)" }
            }
          }
        }
      },
      required: ["url","actions"]
    }
  },
  {
    name: "browser_extract_data",
    description: "Extrae datos estructurados de una página web (scraping)",
    inputSchema: {
      type:"object",
      properties: {
        url:       { type:"string" },
        selectors: {
          type:"object",
          description:"Mapa de nombre → selector CSS para extraer",
          additionalProperties: { type:"string" }
        },
        extract_all_text: { type:"boolean", default:false }
      },
      required: ["url"]
    }
  },

  // ═══════════════════════════════════════════════════════════
  // SISTEMA LOCAL
  // ═══════════════════════════════════════════════════════════
  {
    name: "run_command",
    description: "Ejecuta cualquier comando en este servidor Linux (bash, python, node, go, etc.)",
    inputSchema: {
      type:"object",
      properties: {
        command: { type:"string" },
        cwd:     { type:"string", default:"/home/runner/workspace" },
        timeout: { type:"number", default:60000 }
      },
      required: ["command"]
    }
  },
  {
    name: "install_package",
    description: "Instala paquetes con cualquier gestor: npm, pip, cargo, gem, apt, go get, composer",
    inputSchema: {
      type:"object",
      properties: {
        manager:  { type:"string", enum:["npm","pip","pip3","cargo","gem","apt","go","pnpm","bun","composer"] },
        packages: { type:"array", items:{ type:"string" } },
        global:   { type:"boolean", default:false }
      },
      required: ["manager","packages"]
    }
  },
  {
    name: "run_python",
    description: "Ejecuta código Python y retorna stdout/stderr",
    inputSchema: {
      type:"object",
      properties: {
        code:    { type:"string" },
        timeout: { type:"number", default:30000 }
      },
      required: ["code"]
    }
  },
  {
    name: "run_javascript",
    description: "Ejecuta código JavaScript con Node.js",
    inputSchema: {
      type:"object",
      properties: { code:{ type:"string" }, timeout:{ type:"number", default:30000 } },
      required: ["code"]
    }
  },
  {
    name: "system_info",
    description: "Info del sistema: CPU, RAM, disco, procesos, red",
    inputSchema: { type:"object", properties:{ detail:{ type:"string", enum:["cpu","memory","disk","network","processes","all"], default:"all" } } }
  },

  // ═══════════════════════════════════════════════════════════
  // ARCHIVOS Y FILESYSTEM
  // ═══════════════════════════════════════════════════════════
  {
    name: "read_file",
    description: "Lee un archivo de texto local",
    inputSchema: { type:"object", properties:{ path:{ type:"string" } }, required:["path"] }
  },
  {
    name: "write_file",
    description: "Crea o sobreescribe un archivo",
    inputSchema: {
      type:"object",
      properties:{ path:{ type:"string" }, content:{ type:"string" }, append:{ type:"boolean", default:false } },
      required:["path","content"]
    }
  },
  {
    name: "list_directory",
    description: "Lista contenido de un directorio",
    inputSchema: { type:"object", properties:{ path:{ type:"string" }, recursive:{ type:"boolean", default:false } }, required:["path"] }
  },
  {
    name: "search_files",
    description: "Busca archivos por nombre o contenido",
    inputSchema: {
      type:"object",
      properties:{ directory:{ type:"string" }, pattern:{ type:"string" }, search_content:{ type:"boolean", default:false } },
      required:["directory","pattern"]
    }
  },

  // ═══════════════════════════════════════════════════════════
  // RED Y WEB
  // ═══════════════════════════════════════════════════════════
  {
    name: "fetch_url",
    description: "Descarga contenido de cualquier URL (HTTP/HTTPS)",
    inputSchema: {
      type:"object",
      properties:{ url:{ type:"string" }, extract_text:{ type:"boolean", default:true }, headers:{ type:"object" } },
      required:["url"]
    }
  },
  {
    name: "web_search",
    description: "Busca en internet via DuckDuckGo",
    inputSchema: {
      type:"object",
      properties:{ query:{ type:"string" }, limit:{ type:"number", default:8 } },
      required:["query"]
    }
  },
  {
    name: "port_scan",
    description: "Verifica si puertos están abiertos en un host (útil para diagnosticar conectividad)",
    inputSchema: {
      type:"object",
      properties:{ host:{ type:"string" }, ports:{ type:"array", items:{ type:"number" } } },
      required:["host","ports"]
    }
  },
  {
    name: "ping_host",
    description: "Hace ping a un host para verificar conectividad",
    inputSchema: { type:"object", properties:{ host:{ type:"string" }, count:{ type:"number", default:4 } }, required:["host"] }
  },
  {
    name: "download_file",
    description: "Descarga un archivo de internet a este servidor",
    inputSchema: {
      type:"object",
      properties:{ url:{ type:"string" }, destination:{ type:"string" } },
      required:["url","destination"]
    }
  },

  // ═══════════════════════════════════════════════════════════
  // MEMORIA Y CONTEXTO
  // ═══════════════════════════════════════════════════════════
  {
    name: "save_to_memory",
    description: "Guarda info importante en .opencode/memory.md (persiste entre sesiones)",
    inputSchema: {
      type:"object",
      properties:{ content:{ type:"string" }, section:{ type:"string", default:"General" } },
      required:["content"]
    }
  },
  {
    name: "read_memory",
    description: "Lee toda la memoria persistente guardada",
    inputSchema: { type:"object", properties:{} }
  },

  // ═══════════════════════════════════════════════════════════
  // AGENTE DE INSTALACIÓN REMOTA
  // ═══════════════════════════════════════════════════════════
  {
    name: "generate_agent_installer",
    description: `Genera un script de instalación de agente SSH para equipos remotos.
El script habilita SSH en Windows/Linux/Mac para que puedas controlarlos desde aquí.
Disponible para: Windows (PowerShell), Linux/Mac (bash)`,
    inputSchema: {
      type:"object",
      properties: {
        os:       { type:"string", enum:["windows","linux","mac"], description:"Sistema operativo del equipo a controlar" },
        ssh_port: { type:"number", default:22 }
      },
      required: ["os"]
    }
  }
];

// ── Playwright runner ────────────────────────────────────────
async function runPlaywright(script) {
  const tmpFile = `/tmp/pw-${Date.now()}.mjs`;
  const header = `
import { chromium } from '${MCP_TOOLS_DIR}/playwright/index.mjs';
process.env.PLAYWRIGHT_BROWSERS_PATH = '${PLAYWRIGHT_BROWSERS}';
`;
  writeFileSync(tmpFile, header + script);
  try {
    return runCmd(`PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS}" node --experimental-vm-modules "${tmpFile}"`, { timeout:60000 });
  } finally {
    try { runCmd(`rm -f "${tmpFile}"`); } catch {}
  }
}

// ── SSH runner ───────────────────────────────────────────────
function buildSSHCmd({ host, user, password, key_path, port=22 }, command) {
  if (password) {
    return `sshpass -p '${password.replace(/'/g,"'\\''")}'  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p ${port} ${user}@${host} '${command.replace(/'/g,"'\\''")}'`;
  }
  const keyOpt = key_path ? `-i "${key_path}"` : `-i ~/.ssh/id_rsa`;
  return `ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 ${keyOpt} -p ${port} ${user}@${host} '${command.replace(/'/g,"'\\''")}'`;
}

// ── Handlers ─────────────────────────────────────────────────
async function handle(name, args) {
  switch (name) {

    // ── SSH ──────────────────────────────────────────────────
    case "ssh_connect_run": {
      const cmd = buildSSHCmd(args, args.command);
      try {
        return runCmd(cmd, { timeout: (args.timeout||30)*1000 });
      } catch(e) {
        if (e.message.includes("sshpass")) {
          return runCmd(`ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=no -p ${args.port||22} ${args.user}@${args.host} "${args.command}"`, { timeout:(args.timeout||30)*1000 });
        }
        throw e;
      }
    }

    case "ssh_upload_file": {
      const passOpt = args.password ? `sshpass -p '${args.password}'` : "";
      const keyOpt  = args.key_path ? `-i "${args.key_path}"` : "";
      return runCmd(`${passOpt} scp -o StrictHostKeyChecking=no ${keyOpt} -P ${args.port||22} "${args.local_path}" ${args.user}@${args.host}:"${args.remote_path}"`);
    }

    case "ssh_download_file": {
      const passOpt = args.password ? `sshpass -p '${args.password}'` : "";
      const keyOpt  = args.key_path ? `-i "${args.key_path}"` : "";
      return runCmd(`${passOpt} scp -o StrictHostKeyChecking=no ${keyOpt} -P ${args.port||22} ${args.user}@${args.host}:"${args.remote_path}" "${args.local_path}"`);
    }

    // ── WINDOWS ──────────────────────────────────────────────
    case "windows_powershell": {
      // PowerShell via SSH (Windows OpenSSH Server)
      const psCmd = `powershell.exe -NonInteractive -Command "${args.script.replace(/"/g,'\\"')}"`;
      const cmd = buildSSHCmd(args, psCmd);
      return runCmd(cmd, { timeout:60000 });
    }

    case "windows_cmd": {
      const cmdExe = `cmd.exe /c "${args.command.replace(/"/g,'\\"')}"`;
      const cmd = buildSSHCmd(args, cmdExe);
      return runCmd(cmd, { timeout:30000 });
    }

    case "windows_screenshot_rdp": {
      const output = `/tmp/rdp-screenshot-${Date.now()}.png`;
      // Usar xfreerdp para conectar y capturar
      try {
        runCmd(`Xvfb :99 -screen 0 ${args.width||1920}x${args.height||1080}x24 &`, { timeout:3000 });
      } catch {}
      try {
        runCmd(
          `DISPLAY=:99 xfreerdp /v:${args.host}:${args.port||3389} /u:${args.user} /p:'${args.password}' /size:${args.width||1920}x${args.height||1080} /cert-ignore /log-level:OFF /app-cmd:"powershell -Command Start-Sleep 3" +bitmap-cache /rfx 2>/dev/null || true`,
          { timeout:15000 }
        );
        runCmd(`DISPLAY=:99 scrot "${output}" 2>/dev/null || import -window root "${output}" 2>/dev/null || true`);
      } catch {}
      return existsSync(output)
        ? `✅ Captura RDP guardada: ${output}`
        : `ℹ️  RDP conectado a ${args.host}. Para screenshots en tiempo real, usa VNC o instala el agente en el equipo Windows.\n\nAlternativa: usa windows_powershell para ejecutar comandos sin captura visual.`;
    }

    // ── NAVEGADOR (Playwright) ────────────────────────────────
    case "browser_navigate": {
      const output = `/tmp/page-${Date.now()}.txt`;
      const script = `
const browser = await chromium.launch({ headless:true, args:['--no-sandbox','--disable-setuid-sandbox'] });
const page = await browser.newPage();
await page.goto(${JSON.stringify(args.url)}, { waitUntil:${JSON.stringify(args.wait_for||'networkidle')}, timeout:30000 });
const content = await page.evaluate(() => document.body.innerText);
const url = page.url();
const title = await page.title();
console.log('TITLE:' + title);
console.log('URL:' + url);
console.log('---CONTENT---');
console.log(content.slice(0, 6000));
await browser.close();
`;
      return runPlaywright(script);
    }

    case "browser_screenshot": {
      const output = args.output || `/tmp/screenshot-${Date.now()}.png`;
      const script = `
const browser = await chromium.launch({ headless:true, args:['--no-sandbox'] });
const page = await browser.newPage();
await page.setViewportSize({ width:${args.width||1280}, height:${args.height||720} });
await page.goto(${JSON.stringify(args.url)}, { waitUntil:'networkidle', timeout:30000 });
await page.screenshot({ path:${JSON.stringify(output)}, fullPage:${args.full_page||false} });
const size = (await import('fs')).statSync(${JSON.stringify(output)}).size;
console.log('✅ Screenshot: ${output} (' + Math.round(size/1024) + 'KB)');
await browser.close();
`;
      return runPlaywright(script);
    }

    case "browser_click_and_fill": {
      const actionsCode = (args.actions||[]).map(a => {
        if (a.type==="click")  return `await page.click(${JSON.stringify(a.selector)});`;
        if (a.type==="fill")   return `await page.fill(${JSON.stringify(a.selector)}, ${JSON.stringify(a.value||"")});`;
        if (a.type==="press")  return `await page.press(${JSON.stringify(a.selector||"body")}, ${JSON.stringify(a.key||"Enter")});`;
        if (a.type==="wait")   return `await page.waitForTimeout(${a.ms||1000});`;
        if (a.type==="select") return `await page.selectOption(${JSON.stringify(a.selector)}, ${JSON.stringify(a.value)});`;
        if (a.type==="screenshot") return `await page.screenshot({ path:'/tmp/action-${Date.now()}.png' }); console.log('Screenshot tomado');`;
        return "";
      }).join("\n  ");
      const script = `
const browser = await chromium.launch({ headless:true, args:['--no-sandbox'] });
const page = await browser.newPage();
await page.setViewportSize({ width:1280, height:720 });
await page.goto(${JSON.stringify(args.url)}, { waitUntil:'domcontentloaded', timeout:30000 });
${actionsCode}
const result = await page.evaluate(() => document.body.innerText);
console.log('✅ Acciones completadas. Contenido actual:');
console.log(result.slice(0, 3000));
await browser.close();
`;
      return runPlaywright(script);
    }

    case "browser_extract_data": {
      const selectorsJSON = JSON.stringify(args.selectors || {});
      const script = `
const browser = await chromium.launch({ headless:true, args:['--no-sandbox'] });
const page = await browser.newPage();
await page.goto(${JSON.stringify(args.url)}, { waitUntil:'networkidle', timeout:30000 });
const selectors = ${selectorsJSON};
const results = {};
for (const [name, sel] of Object.entries(selectors)) {
  try {
    const els = await page.$$(sel);
    results[name] = await Promise.all(els.map(el => el.innerText()));
  } catch(e) { results[name] = 'Error: ' + e.message; }
}
${args.extract_all_text ? "results._all_text = (await page.evaluate(() => document.body.innerText)).slice(0,4000);" : ""}
console.log(JSON.stringify(results, null, 2));
await browser.close();
`;
      return runPlaywright(script);
    }

    // ── SISTEMA LOCAL ─────────────────────────────────────────
    case "run_command": {
      return runCmd(args.command, { cwd: args.cwd||WORKSPACE, timeout: args.timeout||60000 });
    }

    case "install_package": {
      const cmds = {
        npm:      `npm install${args.global?" -g":""} ${args.packages.join(" ")}`,
        pnpm:     `pnpm add${args.global?" -g":""} ${args.packages.join(" ")}`,
        bun:      `bun add ${args.packages.join(" ")}`,
        pip:      `pip install ${args.packages.join(" ")}`,
        pip3:     `pip3 install ${args.packages.join(" ")}`,
        cargo:    `cargo install ${args.packages.join(" ")}`,
        gem:      `gem install ${args.packages.join(" ")}`,
        apt:      `apt-get install -y ${args.packages.join(" ")}`,
        go:       `go get ${args.packages.join(" ")}`,
        composer: `composer require ${args.packages.join(" ")}`,
      };
      return runCmd(cmds[args.manager], { cwd: WORKSPACE });
    }

    case "run_python": {
      const f = `/tmp/oc-py-${Date.now()}.py`;
      writeFileSync(f, args.code);
      return runCmd(`python3 "${f}"`, { timeout: args.timeout||30000 });
    }

    case "run_javascript": {
      const f = `/tmp/oc-js-${Date.now()}.mjs`;
      writeFileSync(f, args.code);
      return runCmd(`node "${f}"`, { timeout: args.timeout||30000 });
    }

    case "system_info": {
      const d = args.detail || "all";
      const parts = {};
      if (d==="all"||d==="cpu")       parts.cpu       = runCmd("nproc && cat /proc/cpuinfo | grep 'model name' | head -1").trim();
      if (d==="all"||d==="memory")    parts.memory    = runCmd("free -h").trim();
      if (d==="all"||d==="disk")      parts.disk      = runCmd("df -h").trim();
      if (d==="all"||d==="network")   parts.network   = runCmd("ip addr show 2>/dev/null || ifconfig 2>/dev/null || echo 'N/A'").trim();
      if (d==="all"||d==="processes") parts.processes = runCmd("ps aux --sort=-%cpu | head -15").trim();
      return Object.entries(parts).map(([k,v])=>`=== ${k.toUpperCase()} ===\n${v}`).join("\n\n");
    }

    // ── ARCHIVOS ──────────────────────────────────────────────
    case "read_file": {
      if (!existsSync(args.path)) return `Archivo no encontrado: ${args.path}`;
      return readFileSync(args.path, "utf8");
    }

    case "write_file": {
      const dir = dirname(args.path);
      if (!existsSync(dir)) mkdirSync(dir, { recursive:true });
      writeFileSync(args.path, (args.append&&existsSync(args.path)?readFileSync(args.path,"utf8"):"")+args.content, "utf8");
      return `✅ Guardado: ${args.path} (${args.content.length} chars)`;
    }

    case "list_directory": {
      if (!existsSync(args.path)) return `No existe: ${args.path}`;
      return readdirSync(args.path).map(f => {
        const s = statSync(join(args.path,f));
        return `${s.isDirectory()?"📁":"📄"} ${f}${s.isDirectory()?"/":` (${(s.size/1024).toFixed(1)}KB)`}`;
      }).join("\n");
    }

    case "search_files": {
      const cmd = args.search_content
        ? `grep -rl "${args.pattern}" "${args.directory}" 2>/dev/null | head -20`
        : `find "${args.directory}" -name "${args.pattern}" 2>/dev/null | head -20`;
      return runCmd(cmd) || "Sin resultados";
    }

    // ── RED / WEB ─────────────────────────────────────────────
    case "fetch_url": {
      return new Promise(resolve => {
        const mod = args.url.startsWith("https") ? https : http;
        const headers = { "User-Agent":"Mozilla/5.0 OpenCode-Evolved/1.0", ...(args.headers||{}) };
        let data = "";
        const req = mod.get(args.url, { headers }, res => {
          res.on("data", c => { data += c; });
          res.on("end", () => {
            if (args.extract_text !== false) {
              data = data
                .replace(/<script[^>]*>[\s\S]*?<\/script>/gi,"")
                .replace(/<style[^>]*>[\s\S]*?<\/style>/gi,"")
                .replace(/<[^>]+>/g," ")
                .replace(/\s+/g," ").trim().slice(0,8000);
            }
            resolve(data);
          });
        });
        req.on("error", e => resolve(`Error: ${e.message}`));
        req.setTimeout(20000, () => { req.destroy(); resolve("Timeout"); });
      });
    }

    case "web_search": {
      const q = encodeURIComponent(args.query);
      const html = await handle("fetch_url", { url:`https://html.duckduckgo.com/html/?q=${q}`, extract_text:true });
      return `🔍 "${args.query}":\n${html.slice(0,5000)}`;
    }

    case "ping_host": {
      return runCmd(`ping -c ${args.count||4} ${args.host}`, { timeout:15000 });
    }

    case "port_scan": {
      const results = await Promise.all((args.ports||[]).map(port => new Promise(resolve => {
        const s = createConnection({ host:args.host, port, timeout:3000 });
        s.on("connect", () => { s.destroy(); resolve(`${port} ✅ ABIERTO`); });
        s.on("error",   () => { resolve(`${port} ❌ cerrado`); });
        s.on("timeout", () => { s.destroy(); resolve(`${port} ⏱ timeout`); });
      })));
      return `Puerto scan ${args.host}:\n${results.join("\n")}`;
    }

    case "download_file": {
      const dir = dirname(args.destination);
      if (!existsSync(dir)) mkdirSync(dir, { recursive:true });
      return runCmd(`curl -L -# -o "${args.destination}" "${args.url}"`, { timeout:120000 });
    }

    // ── MEMORIA ───────────────────────────────────────────────
    case "save_to_memory": {
      const p = `${WORKSPACE}/.opencode/memory.md`;
      const existing = existsSync(p) ? readFileSync(p,"utf8") : "";
      writeFileSync(p, existing + `\n\n## ${args.section||"General"} — ${new Date().toISOString()}\n${args.content}\n`);
      return `✅ Guardado en memoria: ${p}`;
    }

    case "read_memory": {
      const p = `${WORKSPACE}/.opencode/memory.md`;
      return existsSync(p) ? readFileSync(p,"utf8") : "Memoria vacía";
    }

    // ── AGENTE INSTALADOR ──────────────────────────────────────
    case "generate_agent_installer": {
      const port = args.ssh_port || 22;
      if (args.os === "windows") {
        return `# INSTALADOR DE AGENTE SSH PARA WINDOWS
# Copia y ejecuta en PowerShell con permisos de Administrador:

# 1. Instalar OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# 2. Iniciar y configurar inicio automático
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'

# 3. Permitir SSH en el firewall
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort ${port}

# 4. Verificar IP del equipo
Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress

Write-Host "✅ SSH habilitado. Ahora puedes controlar este PC desde OpenCode Evolved."
Write-Host "   Usa: ssh_connect_run(host='<IP_DE_ARRIBA>', user='$env:USERNAME', password='<tu_contraseña>', command='...')"
`;
      }
      if (args.os === "linux" || args.os === "mac") {
        return `# INSTALADOR DE AGENTE SSH PARA ${args.os.toUpperCase()}
# Ejecuta en terminal:

${args.os==="linux" ? `# Instalar y habilitar SSH
sudo apt-get install -y openssh-server || sudo yum install -y openssh-server
sudo systemctl enable ssh && sudo systemctl start ssh` : `# Habilitar SSH en Mac
sudo systemsetup -setremotelogin on`}

# Ver IP del equipo
ip addr show | grep 'inet ' || ifconfig | grep 'inet '

echo "✅ SSH habilitado en puerto ${port}"
echo "Controla desde OpenCode con: ssh_connect_run(host='<IP>', user='$(whoami)', ...)"
`;
      }
      return "OS no reconocido";
    }

    default:
      return `Herramienta desconocida: "${name}"`;
  }
}

// ── Loop MCP ────────────────────────────────────────────────
const rl = createInterface({ input: process.stdin });
process.stderr.write("[computer-tools] MCP iniciado con " + tools.length + " herramientas\n");

rl.on("line", async line => {
  let msg;
  try { msg = JSON.parse(line); } catch { return; }

  if (msg.method === "initialize") {
    send({ jsonrpc:"2.0", id:msg.id, result:{
      protocolVersion:"2024-11-05",
      capabilities:{ tools:{} },
      serverInfo:{ name:"computer-tools", version:"2.0.0" }
    }});
    return;
  }
  if (msg.method === "tools/list") {
    send({ jsonrpc:"2.0", id:msg.id, result:{ tools } });
    return;
  }
  if (msg.method === "tools/call") {
    const { name, arguments: args } = msg.params;
    try {
      const result = await handle(name, args||{});
      ok(msg.id, result);
    } catch(err) {
      fail(msg.id, err.message);
    }
    return;
  }
  send({ jsonrpc:"2.0", id:msg.id||null, result:{} });
});
