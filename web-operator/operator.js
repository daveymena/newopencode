import { BrowserManager } from './browser.js';
import { analyzeScreenshot, analyzeWithContext, extractPageContent, solveCaptchaVision } from './ai-client.js';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

export class WebOperator {
  constructor(options = {}) {
    this.browser = new BrowserManager({
      headless: options.headless || false,
      userDataDir: options.userDataDir || null,
      viewport: options.viewport || { width: 1280, height: 800 },
    });
    this.maxIterations = options.maxIterations || 50;
    this.verbose = options.verbose !== false;
    this.actionHistory = [];
    this.task = null;
    this.onMessage = options.onMessage || null;
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

    const trimmed = response.trim();

    if (trimmed.startsWith('TASK_COMPLETE')) {
      return { type: 'TASK_COMPLETE' };
    }

    if (trimmed.startsWith('TASK_FAILED')) {
      const reason = trimmed.replace('TASK_FAILED', '').replace(/^["\s]+|["\s]+$/g, '');
      return { type: 'TASK_FAILED', reason: reason || 'Unknown reason' };
    }

    const clickMatch = trimmed.match(/^CLICK\s+"([^"]+)"(?:\s+"([^"]+)")?/i);
    if (clickMatch) {
      return { type: 'CLICK', target: clickMatch[1], context: clickMatch[2] || null };
    }

    const typeMatch = trimmed.match(/^TYPE\s+"([^"]*)"\s+INTO\s+"([^"]+)"/i);
    if (typeMatch) {
      return { type: 'TYPE', value: typeMatch[1], target: typeMatch[2] };
    }

    const selectMatch = trimmed.match(/^SELECT\s+"([^"]+)"\s+FROM\s+"([^"]+)"/i);
    if (selectMatch) {
      return { type: 'SELECT', value: selectMatch[1], target: selectMatch[2] };
    }

    if (/^SCROLL_DOWN/i.test(trimmed)) {
      return { type: 'SCROLL', direction: 'down' };
    }

    if (/^SCROLL_UP/i.test(trimmed)) {
      return { type: 'SCROLL', direction: 'up' };
    }

    if (/^WAIT/i.test(trimmed)) {
      return { type: 'WAIT' };
    }

    const navMatch = trimmed.match(/^NAVIGATE\s+"([^"]+)"/i);
    if (navMatch) {
      return { type: 'NAVIGATE', url: navMatch[1] };
    }

    const extractMatch = trimmed.match(/^EXTRACT\s+"([^"]+)"/i);
    if (extractMatch) {
      return { type: 'EXTRACT', description: extractMatch[1] };
    }

    const refreshMatch = /^REFRESH|^RELOAD/i.test(trimmed);
    if (refreshMatch) {
      return { type: 'NAVIGATE', url: this.lastUrl || '' };
    }

    // Fallback: try to extract action from natural language
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
    if (!action) {
      this.log('  [Operator] No action to execute');
      return { success: false, message: 'No action' };
    }

    this.log(`  [Operator] Executing: ${action.type} ${JSON.stringify(action)}`);

    try {
      switch (action.type) {
        case 'CLICK': {
          const success = await this.browser.clickElement(action.target);
          this.log(`  [Operator] Click "${action.target}": ${success ? 'OK' : 'FAILED'}`);
          if (!success) {
            // Try clicking by coordinates or position
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
          this.log('  [Operator] Waiting 3 seconds...');
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
          this.log(`  [Operator] Unknown action: ${JSON.stringify(action)}`);
          return { success: false, message: 'Unknown action type' };
      }
    } catch (e) {
      this.log(`  [Operator] Error executing action: ${e.message}`);
      return { success: false, message: e.message };
    }
  }

  async run(task, startUrl = null) {
    this.task = task;
    this.actionHistory = [];
    this.lastUrl = null;
    this.lastExtracted = null;

    this.log('');
    this.log('========================================');
    this.log('  Web Operator Agent - Iniciando');
    this.log('========================================');
    this.log(`  Task: ${task}`);
    if (startUrl) this.log(`  URL: ${startUrl}`);
    this.log('');

    // Launch browser
    this.log('[1/4] Lanzando navegador...');
    const { page } = await this.browser.launch();
    this.log('[Browser listo]');

    // Navigate to start URL
    if (startUrl) {
      this.log('[2/4] Navegando a URL inicial...');
      await this.browser.navigate(startUrl);
      this.lastUrl = startUrl;
    }

    this.log('[3/4] Ejecutando tarea...');
    this.log('');

    let consecutiveFails = 0;
    let noProgressCount = 0;
    let lastActionSummary = '';

    for (let iteration = 0; iteration < this.maxIterations; iteration++) {
      this.log(`\n--- Iteración ${iteration + 1}/${this.maxIterations} ---`);

      // Get page state
      const pageInfo = await this.browser.getPageInfo();
      const screenshot = await this.browser.takeScreenshot();

      if (!screenshot) {
        this.log('  Error: No se pudo tomar screenshot');
        break;
      }

      // Build context from history
      const recentHistory = this.actionHistory.slice(-5).map(h =>
        `${h.action.type}: ${h.action.target || h.action.value || ''} -> ${h.result.success ? 'OK' : 'FAIL'}`
      ).join('\n');

      // Ask AI for next action
      this.log('  Pensando...');
      let response;
      if (this.actionHistory.length > 0) {
        response = await analyzeWithContext(screenshot, task, recentHistory, pageInfo);
      } else {
        response = await analyzeScreenshot(screenshot, task, pageInfo);
      }

      if (!response) {
        this.log('  [AI] No response, retrying...');
        consecutiveFails++;
        if (consecutiveFails >= 3) {
          this.log('  [AI] 3 consecutive failures, aborting.');
          break;
        }
        await this.browser.delay(2000);
        continue;
      }
      consecutiveFails = 0;

      this.log(`  [AI Decisión]: ${response.slice(0, 150)}`);

      // Parse and execute action
      const action = this.parseAction(response);
      if (!action) {
        this.log(`  No se pudo parsear: ${response}`);
        noProgressCount++;
        if (noProgressCount > 5) {
          this.log('  Demasiados fallos de parseo, abortando.');
          break;
        }
        continue;
      }

      // Handle terminal actions
      if (action.type === 'TASK_COMPLETE') {
        this.log('');
        this.log('========================================');
        this.log('  ✅ TAREA COMPLETADA');
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
        this.log(`  ❌ TAREA FALLÓ: ${action.reason}`);
        this.log('========================================');
        await this.browser.close();
        return {
          success: false,
          message: action.reason,
          iterations: iteration + 1,
          history: this.actionHistory,
        };
      }

      // Execute normal action
      const result = await this.executeAction(action);
      this.logAction(action, result);

      if (result.success) {
        noProgressCount = 0;
        if (action.type !== lastActionSummary) {
          lastActionSummary = action.type;
        }
      } else {
        noProgressCount++;
        this.log(`  ⚠️ Progreso estancado (${noProgressCount}/8)`);

        if (noProgressCount >= 8) {
          // Try recovery strategies
          this.log('  🔄 Intentando estrategia de recuperación...');

          // Strategy 1: Scroll down
          await this.browser.scroll('down');
          await this.browser.delay(1000);

          // Strategy 2: Wait
          await this.browser.delay(3000);

          // Strategy 3: Try refreshing page
          if (this.lastUrl) {
            this.log('  🔄 Recargando página...');
            await this.browser.navigate(this.lastUrl);
          }

          noProgressCount = 0;
        }
      }

      await this.browser.delay(500);
    }

    // Hit max iterations
    this.log('');
    this.log('========================================');
    this.log('  ⏰ Límite de iteraciones alcanzado');
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
