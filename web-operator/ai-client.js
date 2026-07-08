import http from 'http';
import https from 'https';
import { readFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ── Load .env (siempre sobreescribir) ──
function loadEnv() {
  const envPath = resolve(__dirname, '..', '.env');
  if (existsSync(envPath)) {
    const lines = readFileSync(envPath, 'utf-8').split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const eqIdx = trimmed.indexOf('=');
      if (eqIdx === -1) continue;
      const key = trimmed.slice(0, eqIdx).trim();
      const val = trimmed.slice(eqIdx + 1).trim().replace(/^['"]|['"]$/g, '');
      if (val) process.env[key] = val; // Siempre sobreescribir si hay valor
    }
  }
}
loadEnv();

// ── Configuración de prioridad de proveedores ──
const USE_COPILOT_FIRST = process.env.USE_COPILOT_FIRST === 'true' || process.env.GITHUB_COPILOT_ENABLED === 'true';
const COPILOT_MODEL = process.env.COPILOT_MODEL || 'gpt-4o'; // gpt-4o, claude-3.5-sonnet, gpt-4-turbo

console.log(`[AI Config] Copilot primario: ${USE_COPILOT_FIRST ? 'SI' : 'NO'}`);
console.log(`[AI Config] Modelo Copilot: ${COPILOT_MODEL}`);

const OPENCODE_PORT = parseInt(process.env.OPENCODE_INTERNAL_PORT || '21294');

// ═══════════════════════════════════════════════════════════════
//  OPENCODE ZEN — Para tareas de TEXTO (planificación, razonamiento)
// ═══════════════════════════════════════════════════════════════

function ocRequest(path, method, body, timeoutMs = 120000) {
  return new Promise((resolve, reject) => {
    const payload = body ? JSON.stringify(body) : '';
    const req = http.request({
      hostname: 'localhost', port: OPENCODE_PORT, path, method,
      headers: { 'Content-Type': 'application/json', ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}) },
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

async function sendToOpenCode(textContent, model = 'opencode/deepseek-v4-flash-free') {
  // Si Copilot está habilitado como primario, intentar primero
  if (USE_COPILOT_FIRST) {
    console.log(`  [AI] Copilot ${COPILOT_MODEL} (prioritario)...`);
    const copilotResult = await callCopilot(textContent, COPILOT_MODEL);
    if (copilotResult) {
      console.log(`  [AI] ✓ Copilot respondió (${copilotResult.length} chars)`);
      return copilotResult;
    }
    console.log(`  [AI] Copilot no disponible, usando OpenCode...`);
  }

  // Intentar OpenCode
  try {
    const sessRes = await ocRequest('/session', 'POST', {});
    if (sessRes.status !== 200 && sessRes.status !== 201) return null;
    const sessionId = JSON.parse(sessRes.data).id;

    const [providerID, modelID] = model.includes('/') ? model.split('/') : ['opencode', model];
    const startTime = Date.now();
    const res = await ocRequest(`/session/${sessionId}/message`, 'POST', {
      parts: [{ type: 'text', text: textContent }],
      model: { providerID, modelID },
    }, 180000);

    if (res.status !== 200) return null;
    const result = JSON.parse(res.data);
    let fullContent = '';
    if (result.parts && Array.isArray(result.parts)) {
      for (const part of result.parts) {
        if (part.type === 'text' && part.text) fullContent += part.text;
      }
    }
    console.log(`  [AI] OpenCode respondió en ${Date.now() - startTime}ms (${fullContent.length} chars)`);
    return fullContent || null;
  } catch (e) {
    console.error(`  [AI] OpenCode error: ${e.message}`);
  }

  // Fallback final: GitHub Copilot (si no estaba habilitado como primario)
  if (!USE_COPILOT_FIRST) {
    console.log(`  [AI] Fallback: GitHub Copilot...`);
    const copilotResult = await callCopilot(textContent, COPILOT_MODEL);
    if (copilotResult) {
      console.log(`  [AI] ✓ Copilot respondió (${copilotResult.length} chars)`);
      return copilotResult;
    }
  }

  return null;
}

async function callVisionAPIs(base64, question) {
  // ── PRIORIDAD 1: GitHub Copilot Vision (si está habilitado) ──
  if (USE_COPILOT_FIRST) {
    console.log(`  [Vision] Copilot ${COPILOT_MODEL} (prioritario)...`);
    const copilotResult = await callCopilotVision(base64, question, COPILOT_MODEL);
    if (copilotResult) {
      console.log(`  [Vision] ✓ Copilot OK (${copilotResult.length} chars)`);
      return copilotResult;
    }
    console.log(`  [Vision] Copilot no disponible, usando fallbacks...`);
  }

  // ── PRIORIDAD 2: OpenCode Zen mimo-v2.5-free ──
  console.log(`  [Vision] OpenCode Zen mimo-v2.5-free...`);
  try {
    const textContent = question + '\n\n[Analiza la imagen adjunta]';
    const result = await sendToOpenCode(textContent, 'opencode/mimo-v2.5-free');
    if (result) {
      console.log(`  [Vision] ✓ OpenCode OK (${result.length} chars)`);
      return result;
    }
  } catch (e) {
    console.error(`  [Vision] mimo-v2.5-free error: ${e.message}`);
  }

  // ── PRIORIDAD 3: Freemodel gpt-4o ──
  const key = process.env.FREEMODEL_API_KEY;
  const baseUrl = process.env.FREEMODEL_BASE_URL || 'https://api.freemodel.dev/v1';
  if (key) {
    try {
      console.log(`  [Vision] Freemodel gpt-4o...`);
      const resp = await fetch(`${baseUrl}/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${key}` },
        body: JSON.stringify({
          model: 'gpt-4o', max_tokens: 4096, temperature: 0.1,
          messages: [{ role: 'user', content: [
            { type: 'image_url', image_url: { url: `data:image/png;base64,${base64}`, detail: 'high' } },
            { type: 'text', text: question },
          ]}],
        }),
        signal: AbortSignal.timeout(90000),
      });
      const data = await resp.json();
      const result = data.choices?.[0]?.message?.content;
      if (result) {
        console.log(`  [Vision] ✓ Freemodel OK (${result.length} chars)`);
        return result;
      }
    } catch (e) {
      console.error(`  [Vision] Freemodel error: ${e.message}`);
    }
  }

  // ── ÚLTIMO FALLBACK: Copilot (si no estaba habilitado como primario) ──
  if (!USE_COPILOT_FIRST) {
    console.log(`  [Vision] Último fallback: Copilot...`);
    const copilotResult = await callCopilotVision(base64, question, COPILOT_MODEL);
    if (copilotResult) {
      console.log(`  [Vision] ✓ Copilot OK (${copilotResult.length} chars)`);
      return copilotResult;
    }
  }

  return null;
}

// ══════════════════════════════════════════════════════════════
//  GITHUB COPILOT - API DIRECTA (INDEPENDIENTE DE OPENCODE)
// ══════════════════════════════════════════════════════════════

let copilotTokenCache = null;
let copilotTokenExpiry = 0;

async function getCopilotToken() {
  // Usar token en cache si aún es válido
  if (copilotTokenCache && Date.now() < copilotTokenExpiry) {
    return copilotTokenCache;
  }

  const githubToken = process.env.GITHUB_COPILOT_TOKEN || process.env.GITHUB_TOKEN;
  if (!githubToken) {
    console.log('  [Copilot] No hay GITHUB_TOKEN configurado');
    return null;
  }

  // Intentar diferentes endpoints de Copilot
  const endpoints = [
    'https://api.github.com/copilot_internal/v2/token',
    'https://api.github.com/copilot_internal/token',
  ];

  for (const endpoint of endpoints) {
    try {
      const resp = await fetch(endpoint, {
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'Accept': 'application/json',
          'User-Agent': 'GitHub-Copilot-Client/1.0',
          'Editor-Version': 'vscode/1.85.0',
        },
        signal: AbortSignal.timeout(10000),
      });

      if (resp.ok) {
        const data = await resp.json();
        if (data.token) {
          copilotTokenCache = data.token;
          // Cachear por 50 minutos (tokens duran 1 hora)
          copilotTokenExpiry = Date.now() + (50 * 60 * 1000);
          console.log('  [Copilot] ✓ Token obtenido y cacheado');
          return data.token;
        }
      }
    } catch (e) {
      // Continuar al siguiente endpoint
    }
  }

  console.log('  [Copilot] ✗ No se pudo obtener token (¿tienes Copilot activo?)');
  return null;
}

async function callCopilot(textContent, model = 'gpt-4o') {
  const copilotToken = await getCopilotToken();
  if (!copilotToken) {
    console.log('  [Copilot] Sin token, saltando...');
    return null;
  }

  try {
    console.log(`  [Copilot] Usando modelo ${model}...`);
    const resp = await fetch('https://api.githubcopilot.com/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${copilotToken}`,
        'Content-Type': 'application/json',
        'Editor-Version': 'vscode/1.85.0',
        'Editor-Plugin-Version': 'copilot-chat/0.11.0',
      },
      body: JSON.stringify({
        model,
        max_tokens: 4096,
        temperature: 0.1,
        messages: [{ role: 'user', content: textContent }],
        stream: false,
      }),
      signal: AbortSignal.timeout(60000),
    });

    if (!resp.ok) {
      const errorText = await resp.text();
      console.log(`  [Copilot] Error ${resp.status}: ${errorText.substring(0, 200)}`);
      return null;
    }

    const data = await resp.json();
    const content = data.choices?.[0]?.message?.content;
    
    if (content) {
      console.log(`  [Copilot] ✓ Respuesta OK (${content.length} chars)`);
      return content;
    }

    return null;
  } catch (e) {
    console.log(`  [Copilot] Error: ${e.message}`);
    return null;
  }
}

async function callCopilotVision(base64, question, model = 'gpt-4o') {
  const copilotToken = await getCopilotToken();
  if (!copilotToken) {
    console.log('  [Copilot Vision] Sin token, saltando...');
    return null;
  }

  try {
    console.log(`  [Copilot Vision] Usando modelo ${model}...`);
    const resp = await fetch('https://api.githubcopilot.com/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${copilotToken}`,
        'Content-Type': 'application/json',
        'Editor-Version': 'vscode/1.85.0',
        'Editor-Plugin-Version': 'copilot-chat/0.11.0',
      },
      body: JSON.stringify({
        model,
        max_tokens: 4096,
        temperature: 0.1,
        messages: [{
          role: 'user',
          content: [
            { type: 'image_url', image_url: { url: `data:image/png;base64,${base64}`, detail: 'high' } },
            { type: 'text', text: question },
          ]
        }],
        stream: false,
      }),
      signal: AbortSignal.timeout(60000),
    });

    if (!resp.ok) {
      const errorText = await resp.text();
      console.log(`  [Copilot Vision] Error ${resp.status}: ${errorText.substring(0, 200)}`);
      return null;
    }

    const data = await resp.json();
    const content = data.choices?.[0]?.message?.content;
    
    if (content) {
      console.log(`  [Copilot Vision] ✓ Respuesta OK (${content.length} chars)`);
      return content;
    }

    return null;
  } catch (e) {
    console.log(`  [Copilot Vision] Error: ${e.message}`);
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════
//  FUNCIÓN PRINCIPAL
// ═══════════════════════════════════════════════════════════════

export async function callBestModel(taskType, messages, maxTokens = 4096) {
  // Verificar si hay imágenes en los mensajes
  const hasImages = messages.some(m =>
    Array.isArray(m.content) && m.content.some(c => c.type === 'image_url')
  );

  if (hasImages) {
    // ── VISION: Llamar APIs directamente ──
    console.log(`  [AI] Enviando ${taskType} a APIs de visión...`);

    // Extraer imagen y pregunta
    let base64 = '';
    let question = '';
    for (const m of messages) {
      if (Array.isArray(m.content)) {
        for (const c of m.content) {
          if (c.type === 'image_url' && c.image_url?.url) {
            base64 = c.image_url.url.split(',')[1] || '';
          }
          if (c.type === 'text') question += c.text + '\n';
        }
      } else if (typeof m.content === 'string') {
        question = m.content;
      }
    }

    if (!base64) {
      console.error('  [AI] No se encontró imagen base64');
  // Fallback: GitHub Copilot vision
  console.log(`  [Vision] Fallback: Copilot vision...`);
  const copilotResult = await callCopilotVision(base64, question);
  if (copilotResult) {
    console.log(`  [Vision] ✓ Copilot OK (${copilotResult.length} chars)`);
    return copilotResult;
  }

  return null;
}

    return await callVisionAPIs(base64, question);
  }

  // ── TEXTO: Usar OpenCode Zen ──
  console.log(`  [AI] Enviando ${taskType} a OpenCode Zen...`);

  // Construir texto completo
  let textContent = '';
  const systemMsg = messages.find(m => m.role === 'system');
  const lastUserMsg = messages.filter(m => m.role === 'user').pop();

  if (systemMsg) textContent = systemMsg.content + '\n\n';
  if (lastUserMsg) {
    if (typeof lastUserMsg.content === 'string') textContent += lastUserMsg.content;
    else if (Array.isArray(lastUserMsg.content)) {
      for (const c of lastUserMsg.content) {
        if (c.type === 'text') textContent += c.text + '\n';
      }
    }
  }

  // Seleccionar modelo por tarea — todos gratis vía OpenCode Zen
  const modelMap = {
    planning: 'opencode/deepseek-v4-flash-free',      // Razonamiento profundo
    reasoning: 'opencode/deepseek-v4-flash-free',     // Verificar y replanificar
    fast: 'opencode/deepseek-v4-flash-free',          // Acciones rápidas
    multitool: 'opencode/mimo-v2.5-free',             // Tools + razonamiento
    vision: 'opencode/mimo-v2.5-free',                // Vision (via describe)
    captcha: 'opencode/mimo-v2.5-free',               // Vision para captcha
  };

  // Fallback chain por si el modelo principal falla
  const fallbackChain = {
    planning: ['opencode/deepseek-v4-flash-free', 'opencode/big-pickle', 'opencode/nemotron-3-ultra-free'],
    reasoning: ['opencode/deepseek-v4-flash-free', 'opencode/big-pickle', 'opencode/hy3-free'],
    fast: ['opencode/deepseek-v4-flash-free', 'opencode/north-mini-code-free', 'opencode/big-pickle'],
    multitool: ['opencode/mimo-v2.5-free', 'opencode/deepseek-v4-flash-free', 'opencode/big-pickle'],
    vision: ['opencode/mimo-v2.5-free', 'opencode/deepseek-v4-flash-free'],
    captcha: ['opencode/mimo-v2.5-free', 'opencode/deepseek-v4-flash-free'],
  };

  const model = modelMap[taskType] || 'opencode/deepseek-v4-flash-free';
  let result = await sendToOpenCode(textContent, model);

  // Si falla, probar fallback chain
  if (!result && fallbackChain[taskType]) {
    for (const fb of fallbackChain[taskType]) {
      if (fb === model) continue;
      console.log(`  [AI] Fallback: ${fb}...`);
      result = await sendToOpenCode(textContent, fb);
      if (result) break;
    }
  }

  // Último fallback: GitHub Copilot
  if (!result) {
    console.log(`  [AI] Último fallback: Copilot...`);
    result = await callCopilot(textContent);
  }

  return result;
}

// ═══════════════════════════════════════════════════════════════
//  FUNCIONES DE ANÁLISIS
// ═══════════════════════════════════════════════════════════════

export async function analyzeScreenshot(screenshotBase64, task, pageInfo) {
  const messages = [
    { role: 'system', content: `Eres un agente de automatización de navegador. Ves capturas de pantalla y decides acciones.\nACCIONES: CLICK "texto", TYPE "texto" INTO "campo", SELECT "opción" FROM "dropdown", SCROLL_DOWN, SCROLL_UP, WAIT, NAVIGATE "url", TASK_COMPLETE, TASK_FAILED "razón"\nResponde con SOLO UNA acción.` },
    { role: 'user', content: [
      { type: 'text', text: `TAREA: ${task}\nURL: ${pageInfo.url}\nTÍTULO: ${pageInfo.title}\n\n¿Qué hacer?` },
      { type: 'image_url', image_url: { url: `data:image/png;base64,${screenshotBase64}`, detail: 'high' } },
    ]},
  ];
  return await callBestModel('vision', messages, 2048);
}

export async function analyzeWithContext(screenshotBase64, task, context, pageInfo) {
  const messages = [
    { role: 'system', content: `Eres un agente de automatización. Ves capturas de pantalla y decides acciones.\nACCIONES: CLICK "texto", TYPE "texto" INTO "campo", SELECT "opción" FROM "dropdown", SCROLL_DOWN, SCROLL_UP, WAIT, NAVIGATE "url", TASK_COMPLETE, TASK_FAILED "razón"\nResponde con SOLO UNA acción.` },
    { role: 'user', content: [
      { type: 'text', text: `TAREA: ${task}\nHISTORIAL: ${context}\nURL: ${pageInfo.url}\nTÍTULO: ${pageInfo.title}\n\n¿Qué hacer ahora?` },
      { type: 'image_url', image_url: { url: `data:image/png;base64,${screenshotBase64}`, detail: 'high' } },
    ]},
  ];
  return await callBestModel('vision', messages, 2048);
}

export async function extractPageContent(screenshotBase64, extractionDesc) {
  const messages = [
    { role: 'user', content: [
      { type: 'text', text: `Extrae la información solicitada: ${extractionDesc}` },
      { type: 'image_url', image_url: { url: `data:image/png;base64,${screenshotBase64}`, detail: 'high' } },
    ]},
  ];
  return await callBestModel('vision', messages, 4096);
}

export async function solveCaptchaVision(screenshotBase64) {
  const messages = [
    { role: 'user', content: [
      { type: 'text', text: 'Analiza este captcha. ¿Qué debo hacer para pasarlo? Responde con UNA acción.' },
      { type: 'image_url', image_url: { url: `data:image/png;base64,${screenshotBase64}`, detail: 'high' } },
    ]},
  ];
  return await callBestModel('captcha', messages, 1024);
}
