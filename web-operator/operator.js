import { BrowserManager } from './browser.js';
import { analyzeScreenshot, analyzeWithContext, extractPageContent, solveCaptchaVision, callBestModel } from './ai-client.js';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ── Site Memory ──────────────────────────────────────────────
const MEMORY_DIR = resolve(__dirname, '.site-memory');
if (!existsSync(MEMORY_DIR)) mkdirSync(MEMORY_DIR, { recursive: true });

export function loadSiteMemory(domain) {
  const file = resolve(MEMORY_DIR, `${domain.replace(/[^a-z0-9]/gi, '_')}.json`);
  if (existsSync(file)) {
    try { return JSON.parse(readFileSync(file, 'utf-8')); } catch {}
  }
  return { domain, instructions: [], preferences: {}, loginSaved: false, visitCount: 0, lastVisit: null };
}

function saveSiteMemory(domain, data) {
  const file = resolve(MEMORY_DIR, `${domain.replace(/[^a-z0-9]/gi, '_')}.json`);
  data.lastVisit = new Date().toISOString();
  data.visitCount = (data.visitCount || 0) + 1;
  writeFileSync(file, JSON.stringify(data, null, 2));
}

export function addSiteInstruction(domain, instruction) {
  const memory = loadSiteMemory(domain);
  if (!memory.instructions) memory.instructions = [];
  memory.instructions.push({ text: instruction, added: new Date().toISOString() });
  saveSiteMemory(domain, memory);
}

// ═══════════════════════════════════════════════════════════════
//  MOTOR DE RAZONAMIENTO — Piensa como ChatGPT Operator
// ═══════════════════════════════════════════════════════════════
class ReasoningEngine {
  constructor(operator) {
    this.op = operator;
    this.plan = null;
    this.currentStep = 0;
    this.verificationHistory = [];
    this.replanCount = 0;
    this.maxReplans = 5;
    this.stuckStrategies = [];
  }

  // ── FASE 1: ANALIZAR TAREA y crear plan ──
  async analyzeAndPlan(task, startUrl) {
    this.op.log('  [Razonamiento] Analizando tarea en profundidad...');

    const messages = [
      {
        role: 'system',
        content: `Eres un agente de automatización inteligente como ChatGPT Operator. Tu trabajo es ANALIZAR, PLANIFICAR y EJECUTAR tareas en un navegador web.

REGLAS DE RAZONAMIENTO:
1. PRIMERO analiza qué se pide, qué información tienes, qué obstáculos puede haber
2. SEGUNDO crea un plan paso a paso con estrategias de respaldo
3. TERCERO considera si es mejor usar API en lugar de navegador (Facebook → Graph API, etc.)
4. CUARTO identifica riesgos: CAPTCHA, login requerido, detección de bots
5. QUINTO si algo falla, piensa en ALTERNATIVAS completamente diferentes, no repitas lo mismo

FORMATO DE RESPUESTA (JSON):
{
  "analysis": "Análisis profundo de la tarea: qué se pide, qué implica, qué riesgos hay",
  "strategy": "browser" o "api",
  "apiAlternative": "si recomiendas API, cuál y cómo (ej: Facebook Graph API para crear página)",
  "risks": ["riesgo 1", "riesgo 2"],
  "plan": [
    {"step": 1, "action": "descripción", "fallback": "qué hacer si falla"},
    {"step": 2, "action": "descripción", "fallback": "alternativa"}
  ],
  "estimatedTime": "tiempo estimado",
  "humanIntervention": true/false,
  "humanReason": "si se necesita intervención humana, por qué"
}`,
      },
      {
        role: 'user',
        content: `TAREA: ${task}\nURL INICIAL: ${startUrl || 'ninguna'}\n\nAnaliza esta tarea a fondo. Piensa en qué implica, qué riesgos hay, y cuál es la mejor estrategia. Si recomiendas API en lugar de navegador, explica por qué.`,
      },
    ];

    const response = await callBestModel('planning', messages, 2048);
    if (!response) return null;

    try {
      const jsonMatch = response.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        this.plan = JSON.parse(jsonMatch[0]);
        this.op.log(`  [Razonamiento] Análisis: ${this.plan.analysis || 'N/A'}`);
        this.op.log(`  [Razonamiento] Estrategia: ${this.plan.strategy || 'browser'}`);
        if (this.plan.apiAlternative) {
          this.op.log(`  [Razonamiento] API recomendada: ${this.plan.apiAlternative}`);
        }
        if (this.plan.risks?.length) {
          this.op.log(`  [Razonamiento] Riesgos: ${this.plan.risks.join(', ')}`);
        }
        if (this.plan.plan?.length) {
          this.op.log(`  [Razonamiento] Plan (${this.plan.plan.length} pasos):`);
          this.plan.plan.forEach((p, i) => this.op.log(`    ${i + 1}. ${p.action} → fallback: ${p.fallback}`));
        }
        if (this.plan.humanIntervention) {
          this.op.log(`  [Razonamiento] ⚠️ Intervención humana sugerida: ${this.plan.humanReason}`);
        }
        return this.plan;
      }
    } catch (e) {
      this.op.log(`  [Razonamiento] Error parseando plan: ${e.message}`);
    }
    return null;
  }

  // ── FASE 2: PENSAR ANTES DE CADA ACCIÓN ──
  async thinkBeforeAct(screenshot, task, pageInfo, history) {
    const recentHistory = history.slice(-8).map(h =>
      `${h.action.type}("${h.action.target || h.action.value || ''}") → ${h.result.success ? 'OK' : 'FAIL: ' + h.result.message}`
    ).join('\n');

    const planContext = this.plan?.plan ? `\nPlan actual: ${this.plan.plan.map((p, i) => `${i + 1}. ${p.action}`).join(', ')}` : '';

    const messages = [
      {
        role: 'system',
        content: `Eres un agente de automatización inteligente. Estás viendo una captura de pantalla de un navegador web.

TU TRABAJO:
1. ANALIZA lo que ves en la pantalla (botones, formularios, texto, menús)
2. RECuerda el objetivo final de la tarea
3. EVALúa qué pasos ya completaste y qué falta
4. DECIDE la MEJOR acción siguiente
5. Si algo falló antes, piensa en una ALTERNATIVA diferente
6. NUNCA repitas la misma acción que falló

IMPORTANTE: No solo mires el elemento más obvio. Piensa estratégicamente:
- ¿Estoy en la página correcta?
- ¿Necesito hacer scroll para ver más opciones?
- ¿Hay un botón o menú que me lleva más cerca del objetivo?
- ¿Debo llenar un formulario, seleccionar algo, o navegar a otra página?
- Si fallé antes, ¿qué podría funcionar diferente?

RESPONDE CON UNA ACCIÓN en este formato exacto:
ANALISIS: [qué ves en la pantalla y qué implica]
DECISIÓN: [por qué esta acción es la mejor]
ACCIÓN: [la acción en formato CLICK/TYPE/SELECT/SCROLL/WAIT/NAVIGATE]`,
      },
      {
        role: 'user',
        content: `TAREA OBJETIVO: ${task}
${planContext}

HISTORIAL RECIENTE:
${recentHistory || '(primera iteración)'}

URL ACTUAL: ${pageInfo.url}
TÍTULO: ${pageInfo.title}

Analiza la captura de pantalla y decide la MEJOR acción siguiente. Piensa estratégicamente.`,
      },
      {
        role: 'user',
        content: [
          { type: 'text', text: 'Captura de pantalla actual:' },
          { type: 'image_url', image_url: { url: `data:image/png;base64,${screenshot}`, detail: 'high' } },
        ],
      },
    ];

    return await callBestModel('reasoning', messages, 2048);
  }

  // ── FASE 3: VERIFICAR RESULTADO ──
  async verifyActionResult(action, screenshotBefore, screenshotAfter, task, pageInfo) {
    const messages = [
      {
        role: 'system',
        content: `Eres un verificador de acciones de automatización. Tu trabajo es determinar si una acción tuvo éxito.

Analiza:
1. ¿La página cambió después de la acción?
2. ¿Se abrió un formulario, menú, o nueva página?
3. ¿Apareció un mensaje de error?
4. ¿Se cargó contenido nuevo?
5. ¿Estamos más cerca del objetivo?

RESPONDE EN JSON:
{
  "success": true/false,
  "progressMade": true/false,
  "whatChanged": "descripción de qué cambió en la pantalla",
  "pageState": "login_required/captcha/form_page/dashboard/content_loaded/error",
  "suggestion": "si falló, qué intentar diferente"
}`,
      },
      {
        role: 'user',
        content: [
          {
            type: 'text',
            text: `Acción ejecutada: ${action.type} ${action.target || action.value || action.url || ''}
URL actual: ${pageInfo.url}
Título: ${pageInfo.title}

¿Tuvo éxito la acción? ¿Qué cambió en la pantalla?`,
          },
          { type: 'image_url', image_url: { url: `data:image/png;base64,${screenshotAfter}`, detail: 'high' } },
        ],
      },
    ];

    const response = await callBestModel('reasoning', messages, 1024);
    if (!response) return { success: false, progressMade: false, suggestion: 'No se pudo verificar' };

    try {
      const jsonMatch = response.match(/\{[\s\S]*\}/);
      if (jsonMatch) return JSON.parse(jsonMatch[0]);
    } catch {}

    return { success: true, progressMade: true, suggestion: response.slice(0, 200) };
  }

  // ── FASE 4: REPLANIFICAR cuando está stuck ──
  async replan(task, pageInfo, history, reason) {
    this.replanCount++;
    if (this.replanCount > this.maxReplans) {
      this.op.log('  [Razonamiento] Máximo de replanificaciones alcanzado');
      return null;
    }

    this.op.log(`  [Razonamiento] REPLANIFICANDO (intento ${this.replanCount}/${this.maxReplans}): ${reason}`);

    const failureHistory = history.slice(-10).map(h =>
      `${h.action.type}("${h.action.target || h.action.value || ''}") → ${h.result.success ? 'OK' : 'FAIL'}`
    ).join('\n');

    const messages = [
      {
        role: 'system',
        content: `Eres un agente de automatización que está ATASCADO. La tarea no va bien y necesitas un plan completamente nuevo.

REGLAS PARA REPLANIFICAR:
1. NO repitas acciones que ya fallaron
2. Piensa en ENFOQUES COMPLETAMENTE DIFERENTES
3. Si el navegador no funciona, considera: ¿hay una URL alternativa? ¿un botón diferente? ¿un atajo de teclado?
4. Si es una tarea de Facebook/Twitter/Instagram, considera usar la API en lugar del navegador
5. Si necesitas login, pide al usuario que lo haga manualmente
6. Si el CAPTCHA aparece, es porque el sitio detecta bots — cambia de estrategia

RESPONDE CON JSON:
{
  "newStrategy": "nueva estrategia completa",
  "abandonCurrentApproach": true/false,
  "alternativeActions": [
    {"type": "acción alternativa", "reasoning": "por qué esta alternativa"}
  ],
  "askUser": "pregunta al usuario si necesitas info",
  "giveUp": true/false,
  "giveUpReason": "razón para rendirse"
}`,
      },
      {
        role: 'user',
        content: `TAREA ORIGINAL: ${task}
URL ACTUAL: ${pageInfo.url}
TÍTULO: ${pageInfo.title}
RAZÓN DEL ESTANCAMIENTO: ${reason}

ACCIONES QUE YA FALLARON:
${failureHistory}

Necesito una estrategia COMPLETAMENTE NUEVA. No repitas nada de lo que ya intenté.`,
      },
    ];

    const response = await callBestModel('reasoning', messages, 1500);
    if (!response) return null;

    try {
      const jsonMatch = response.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const newPlan = JSON.parse(jsonMatch[0]);
        this.op.log(`  [Razonamiento] Nueva estrategia: ${newPlan.newStrategy || 'N/A'}`);
        if (newPlan.giveUp) {
          this.op.log(`  [Razonamiento] Rendición: ${newPlan.giveUpReason}`);
        }
        return newPlan;
      }
    } catch {}
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════
//  WEB OPERATOR — Con motor de razonamiento
// ═══════════════════════════════════════════════════════════════
export class WebOperator {
  constructor(options = {}) {
    this.browser = new BrowserManager({
      headless: options.headless !== false,
      userDataDir: options.userDataDir || null,
      viewport: options.viewport || { width: 1280, height: 800 },
    });
    this.maxIterations = options.maxIterations || 50;
    this.verbose = options.verbose !== false;
    this.actionHistory = [];
    this.task = null;
    this.onMessage = options.onMessage || null;
    this.siteMemory = null;
    this.currentDomain = null;
    this.takeoverMode = false;
    this.takeoverCallback = null;
    this.captchaDetected = false;
    this.reasoning = new ReasoningEngine(this);
  }

  // ── Detección de login ──
  async detectLoginPage() {
    if (!this.browser.page) return false;
    return await this.browser.page.evaluate(() => {
      const body = (document.body.innerText || '').toLowerCase();
      const html = (document.body.innerHTML || '').toLowerCase();
      const patterns = [/iniciar\s*sesi/i, /log\s*in/i, /sign\s*in/i, /acceder/i, /entrar/i];
      const hasPassInput = document.querySelector('input[type="password"], input[name*="pass"], input[name*="login"]');
      return hasPassInput || patterns.some(p => p.test(body) || p.test(html));
    });
  }

  // ── Detección de CAPTCHA ──
  async detectCaptcha() {
    if (!this.browser.page) return false;
    return await this.browser.page.evaluate(() => {
      const html = (document.body.innerHTML || '').toLowerCase();
      const patterns = [/recaptcha/i, /captcha/i, /verify.*human/i, /are you a robot/i, /turnstile/i, /hcaptcha/i];
      const hasFrame = document.querySelector('iframe[src*="recaptcha"], iframe[src*="captcha"], iframe[src*="hcaptcha"]');
      return patterns.some(p => p.test(html)) || !!hasFrame;
    });
  }

  // ── Takeover mode ──
  async enterTakeoverMode(reason) {
    this.takeoverMode = true;
    this.log(`  TAKEOVER: ${reason}`);
    this.onMessage?.({ type: 'takeover', reason });
    // En lugar de bloquear la ejecución permanentemente (lo cual causa el error 409 cuando se intenta reiniciar),
    // simplemente pausamos unos segundos para que el usuario pueda ver el estado, y luego dejamos
    // que el motor de razonamiento intente de nuevo. Si sigue bloqueado, el motor se dará por vencido.
    await this.browser.delay(5000);
    this.takeoverMode = false;
  }

  releaseTakeover() {
    if (this.takeoverCallback) { this.takeoverCallback(); this.takeoverCallback = null; }
  }

  log(msg) {
    if (this.verbose) console.log(msg);
    if (this.onMessage) this.onMessage({ type: 'log', text: msg });
  }

  logAction(action, result) {
    this.actionHistory.push({ action, result, timestamp: Date.now() });
    if (this.actionHistory.length > 50) this.actionHistory.shift();
  }

  parseAction(response) {
    if (!response) return null;

    // Extraer solo la línea de ACCIÓN del response
    const actionMatch = response.match(/ACCIÓN:\s*(.+)/i);
    const trimmed = (actionMatch ? actionMatch[1] : response).trim();

    if (trimmed.startsWith('TASK_COMPLETE')) return { type: 'TASK_COMPLETE' };
    if (trimmed.startsWith('TASK_FAILED')) {
      const reason = trimmed.replace('TASK_FAILED', '').replace(/^["\s]+|["\s]+$/g, '');
      return { type: 'TASK_FAILED', reason: reason || 'Unknown reason' };
    }

    const clickMatch = trimmed.match(/^CLICK\s+"([^"]+)"(?:\s+"([^"]+)")?/i);
    if (clickMatch) return { type: 'CLICK', target: clickMatch[1], context: clickMatch[2] || null };

    const typeMatch = trimmed.match(/^TYPE\s+"([^"]*)"\s+INTO\s+"([^"]+)"/i);
    if (typeMatch) return { type: 'TYPE', value: typeMatch[1], target: typeMatch[2] };

    const selectMatch = trimmed.match(/^SELECT\s+"([^"]+)"\s+FROM\s+"([^"]+)"/i);
    if (selectMatch) return { type: 'SELECT', value: selectMatch[1], target: selectMatch[2] };

    if (/^SCROLL_DOWN/i.test(trimmed)) return { type: 'SCROLL', direction: 'down' };
    if (/^SCROLL_UP/i.test(trimmed)) return { type: 'SCROLL', direction: 'up' };
    if (/^WAIT/i.test(trimmed)) return { type: 'WAIT' };

    const navMatch = trimmed.match(/^NAVIGATE\s+"([^"]+)"/i);
    if (navMatch) return { type: 'NAVIGATE', url: navMatch[1] };

    const extractMatch = trimmed.match(/^EXTRACT\s+"([^"]+)"/i);
    if (extractMatch) return { type: 'EXTRACT', description: extractMatch[1] };

    const refreshMatch = /^REFRESH|^RELOAD/i.test(trimmed);
    if (refreshMatch) return { type: 'NAVIGATE', url: this.lastUrl || '' };

    // Fallback: intentar extraer de lenguaje natural
    if (trimmed.toLowerCase().includes('click')) {
      const match = trimmed.match(/click\s+(?:on\s+)?["']?([^"'.]+)["']?/i);
      if (match) return { type: 'CLICK', target: match[1].trim(), context: null };
    }
    if (trimmed.toLowerCase().includes('type') || trimmed.toLowerCase().includes('enter')) {
      const textMatch = trimmed.match(/(?:type|enter)\s+["']([^"']+)["']/i);
      const fieldMatch = trimmed.match(/(?:into|in|on)\s+["']([^"']+)["']/i);
      if (textMatch) return { type: 'TYPE', value: textMatch[1], target: fieldMatch ? fieldMatch[1] : 'field' };
    }
    if (trimmed.toLowerCase().includes('scroll')) {
      return { type: 'SCROLL', direction: trimmed.toLowerCase().includes('up') ? 'up' : 'down' };
    }

    return { type: 'UNKNOWN', raw: trimmed };
  }

  async executeAction(action) {
    if (!action) return { success: false, message: 'No action' };

    this.log(`  [Operator] Ejecutando: ${action.type} ${JSON.stringify(action)}`);

    try {
      switch (action.type) {
        case 'CLICK': {
          const success = await this.browser.clickElement(action.target);
          this.log(`  [Operator] Click "${action.target}": ${success ? 'OK' : 'FAILED'}`);
          if (!success) {
            const fallbackSuccess = await this.browser.clickElement(action.target.split(' ').slice(0, 2).join(' '));
            if (fallbackSuccess) return { success: true, message: 'Clicked (fallback)' };
          }
          return { success, message: `Click "${action.target}"` };
        }
        case 'TYPE': {
          const success = await this.browser.typeText(action.value, action.target);
          this.log(`  [Operator] Type "${action.value.slice(0, 30)}..." into "${action.target}": ${success ? 'OK' : 'FAILED'}`);
          return { success, message: `Type into "${action.target}"` };
        }
        case 'SELECT': {
          const success = await this.browser.selectOption(action.value, action.target);
          this.log(`  [Operator] Select "${action.value}" from "${action.target}": ${success ? 'OK' : 'FAILED'}`);
          return { success, message: `Select "${action.value}"` };
        }
        case 'SCROLL': {
          await this.browser.scroll(action.direction);
          this.log(`  [Operator] Scrolled ${action.direction}`);
          return { success: true, message: `Scrolled ${action.direction}` };
        }
        case 'WAIT': {
          this.log('  [Operator] Esperando 3 segundos...');
          await this.browser.delay(3000);
          return { success: true, message: 'Waited 3s' };
        }
        case 'NAVIGATE': {
          await this.browser.navigate(action.url);
          this.lastUrl = action.url;
          return { success: true, message: `Navigated to ${action.url}` };
        }
        case 'EXTRACT': {
          const content = await this.browser.extractText();
          const screenshot = await this.browser.takeScreenshot();
          const extracted = await extractPageContent(screenshot, action.description);
          this.log(`  [Operator] Extracted: ${(extracted || content).slice(0, 200)}`);
          this.lastExtracted = extracted || content;
          return { success: true, message: 'Extracted data', data: extracted || content };
        }
        case 'TASK_COMPLETE':
        case 'TASK_FAILED':
          return { success: true, message: action.reason || action.type };
        default:
          this.log(`  [Operator] Acción desconocida: ${JSON.stringify(action)}`);
          return { success: false, message: 'Unknown action type' };
      }
    } catch (e) {
      this.log(`  [Operator] Error: ${e.message}`);
      return { success: false, message: e.message };
    }
  }

  // ═══════════════════════════════════════════════════════════
  //  LOOP PRINCIPAL — Con razonamiento real
  // ═══════════════════════════════════════════════════════════
  async run(task, startUrl = null, options = {}) {
    this.task = task;
    this.actionHistory = [];
    this.lastUrl = null;
    this.lastExtracted = null;
    this.siteInstructions = options.instructions || [];

    this.log('');
    this.log('========================================');
    this.log('  Web Operator — Con Razonamiento');
    this.log('========================================');
    this.log(`  Tarea: ${task}`);
    if (startUrl) this.log(`  URL: ${startUrl}`);
    this.log('');

    // ── FASE 1: LANZAR NAVEGADOR ──
    this.log('[1/5] Lanzando navegador...');
    const { page } = await this.browser.launch();
    this.log('[Browser listo]');

    // ── FASE 2: NAVEGAR ──
    if (startUrl) {
      this.log('[2/5] Navegando a URL inicial...');
      await this.browser.navigate(startUrl);
      this.lastUrl = startUrl;
      try {
        const url = new URL(startUrl);
        this.currentDomain = url.hostname;
        this.siteMemory = loadSiteMemory(this.currentDomain);
        this.log(`  Memoria: ${this.siteMemory.visitCount} visitas previas`);
      } catch {}
    }

    // ── FASE 3: RAZONAR Y PLANIFICAR ──
    this.log('[3/5] Razonando sobre la tarea...');
    const plan = await this.reasoning.analyzeAndPlan(task, startUrl);

    // Verificar si la tarea necesita intervención humana
    if (plan?.humanIntervention) {
      await this.enterTakeoverMode(plan.humanReason || 'La tarea requiere intervención humana.');
    }

    // Verificar si recomienda API
    if (plan?.strategy === 'api' && plan?.apiAlternative) {
      this.log(`  [Razonamiento] Recomendación: Usar API en lugar de navegador`);
      this.log(`  [Razonamiento] ${plan.apiAlternative}`);
      // Continuar con browser pero con la info de la API como contexto
    }

    this.log('');

    // ── FASE 4: EJECUTAR CON VERIFICACIÓN ──
    this.log('[4/5] Ejecutando con verificación...');
    this.log('');

    let consecutiveFails = 0;
    let noProgressCount = 0;
    let lastActionSummary = '';
    let screenshotBefore = null;

    for (let iteration = 0; iteration < this.maxIterations; iteration++) {
      this.log(`\n--- Iteración ${iteration + 1}/${this.maxIterations} ---`);

      // Capturar estado actual
      const pageInfo = await this.browser.getPageInfo();
      const screenshot = await this.browser.takeScreenshot();
      screenshotBefore = screenshot;

      if (!screenshot) {
        this.log('  Error: No se pudo tomar screenshot');
        break;
      }

      // 📡 Transmitir screenshot en vivo al frontend
      this.onMessage?.({
        type: 'screenshot',
        data: screenshot,
        url: pageInfo.url,
        title: pageInfo.title,
        iteration: iteration + 1,
        maxIterations: this.maxIterations,
      });

      // ── Detección de obstáculos ──
      if (await this.detectLoginPage()) {
        this.log('  Login detectado');
        if (!this.siteMemory?.loginSaved) {
          const hasLikelyCreds = /@[\w.-]+/.test(this.task) || /(?:password|contraseña|contrasena|clave|login)/i.test(this.task);
          
          if (!hasLikelyCreds) {
            this.log('  Se requiere inicio de sesión. Notificando al usuario...');
            // En vez de bloquear indefinidamente con enterTakeoverMode, dejamos que la IA pida ayuda y decida.
            // Esto permite que siga el bucle o que el LLM decida esperar.
            this.onMessage?.({ type: 'takeover', reason: 'Página de login detectada. Proporciona credenciales o inicia sesión manualmente.' });
          } else {
            this.log('  Posibles credenciales detectadas en la tarea. El agente intentará iniciar sesión automáticamente.');
          }
          if (this.siteMemory) { this.siteMemory.loginSaved = true; saveSiteMemory(this.currentDomain, this.siteMemory); }
        }
      }

      if (await this.detectCaptcha() && !this.captchaDetected) {
        this.captchaDetected = true;
        this.log('  CAPTCHA detectado');
        this.onMessage?.({ type: 'takeover', reason: 'CAPTCHA detectado. Resuélvelo manualmente si el agente se detiene.' });
      }

      if (this.currentDomain) this.siteMemory = loadSiteMemory(this.currentDomain);

      // ── PASO 1: PENSAR (análisis profundo) ──
      this.log('  [Pensando] Analizando pantalla...');
      const thinkingResponse = await this.reasoning.thinkBeforeAct(screenshot, task, pageInfo, this.actionHistory);

      if (!thinkingResponse) {
        this.log('  [AI] Sin respuesta, reintentando...');
        consecutiveFails++;
        if (consecutiveFails >= 3) {
          this.log('  [AI] 3 fallos consecutivos, abortando.');
          break;
        }
        await this.browser.delay(2000);
        continue;
      }
      consecutiveFails = 0;

      // Mostrar razonamiento al usuario
      const analysisMatch = thinkingResponse.match(/ANÁLISIS:\s*(.+)/i);
      const decisionMatch = thinkingResponse.match(/DECISIÓN:\s*(.+)/i);
      if (analysisMatch) this.log(`  [Análisis] ${analysisMatch[1].trim().slice(0, 200)}`);
      if (decisionMatch) this.log(`  [Decisión] ${decisionMatch[1].trim().slice(0, 200)}`);

      // ── PASO 2: EJECUTAR ──
      const action = this.parseAction(thinkingResponse);
      if (!action) {
        this.log(`  No se pudo parsear: ${thinkingResponse.slice(0, 100)}`);
        noProgressCount++;
        if (noProgressCount > 5) {
          this.log('  Demasiados fallos de parseo, replanificando...');
          const replan = await this.reasoning.replan(task, pageInfo, this.actionHistory, 'Parsing failures');
          if (replan?.giveUp) break;
          noProgressCount = 0;
        }
        continue;
      }

      if (action.type === 'TASK_COMPLETE') {
        this.log('');
        this.log('========================================');
        this.log('  TAREA COMPLETADA');
        this.log('========================================');
        const finalContent = await this.browser.extractText();
        const finalScreenshot = await this.browser.takeScreenshot();
        await this.browser.close();
        return {
          success: true,
          message: 'Task completed successfully',
          iterations: iteration + 1,
          extractedData: this.lastExtracted,
          pageContent: finalContent.slice(0, 5000),
          screenshot: finalScreenshot,
          history: this.actionHistory,
        };
      }

      if (action.type === 'TASK_FAILED') {
        this.log('');
        this.log('========================================');
        this.log(`  TAREA FALLÓ: ${action.reason}`);
        this.log('========================================');
        await this.browser.close();
        return {
          success: false,
          message: action.reason,
          iterations: iteration + 1,
          history: this.actionHistory,
        };
      }

      // Ejecutar acción
      const result = await this.executeAction(action);
      this.logAction(action, result);

      // ── PASO 3: VERIFICAR ──
      await this.browser.delay(1500); // Esperar que la página reaccione
      const screenshotAfter = await this.browser.takeScreenshot();
      const pageInfoAfter = await this.browser.getPageInfo();

      if (screenshotAfter) {
        this.log('  [Verificando] Comparando resultado...');
        const verification = await this.reasoning.verifyActionResult(
          action, screenshotBefore, screenshotAfter, task, pageInfoAfter
        );

        this.log(`  [Verificación] Éxito: ${verification.success}, Progreso: ${verification.progressMade}`);
        if (verification.whatChanged) this.log(`  [Verificación] Cambio: ${verification.whatChanged}`);
        this.log(`  [Verificación] Estado: ${verification.pageState || 'N/A'}`);

        if (verification.success && verification.progressMade) {
          noProgressCount = 0;
          lastActionSummary = action.type;
        } else if (!verification.progressMade) {
          noProgressCount++;
          this.log(`  ⚠️ Sin progreso (${noProgressCount}/5)`);

          if (noProgressCount >= 3) {
            // ── PASO 4: REPLANIFICAR ──
            const replan = await this.reasoning.replan(
              task, pageInfoAfter, this.actionHistory,
              verification.suggestion || 'Sin progreso detectado'
            );

            if (replan?.giveUp) {
              this.log(`  Rendiéndose: ${replan.giveUpReason}`);
              break;
            }

            if (replan?.askUser) {
              await this.enterTakeoverMode(replan.askUser);
            }

            noProgressCount = 0;
          }
        }
      } else {
        // Sin screenshot de verificación, confiar en el resultado de la acción
        if (result.success) {
          noProgressCount = 0;
          lastActionSummary = action.type;
        } else {
          noProgressCount++;
        }
      }

      await this.browser.delay(500);
    }

    // ── FASE 5: RESULTADO FINAL ──
    this.log('');
    this.log('========================================');
    this.log('  Límite de iteraciones alcanzado');
    this.log('========================================');
    const finalExtracted = await this.browser.extractText();
    await this.browser.close();
    return {
      success: false,
      message: `Max iterations (${this.maxIterations}) reached without completing task`,
      iterations: this.maxIterations,
      partialData: finalExtracted.slice(0, 5000),
      history: this.actionHistory,
    };
  }

  async runTask(task, startUrl = null) {
    return await this.run(task, startUrl);
  }
}

// CLI mode
async function main() {
  const args = process.argv.slice(2);
  const task = args.join(' ') || 'explora la página y dime qué contiene';

  const operator = new WebOperator({
    headless: false,
    verbose: true,
  });

  const result = await operator.runTask(task);
  console.log('\nResultado:', JSON.stringify(result, null, 2));
  process.exit(result.success ? 0 : 1);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main();
}
