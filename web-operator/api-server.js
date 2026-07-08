import express from 'express';
import cors from 'cors';
import morgan from 'morgan';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import { WebOperator } from './operator.js';
import { existsSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PORT = process.env.OPERATOR_PORT || process.env.PORT || 3001;

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ server });

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(morgan('dev'));

// Serve static frontend
app.use(express.static(resolve(__dirname, 'public')));

// Active task tracking
let activeTask = null;
let taskResult = null;
let wsClients = [];

function broadcast(data) {
  const msg = JSON.stringify(data);
  for (const ws of wsClients) {
    try { ws.send(msg); } catch {}
  }
}

// WebSocket for real-time streaming
wss.on('connection', (ws) => {
  wsClients.push(ws);
  ws.send(JSON.stringify({ type: 'connected', message: 'Web Operator Agent connected' }));

  if (activeTask) {
    ws.send(JSON.stringify({ type: 'task_status', running: true, task: activeTask }));
  }
  if (taskResult) {
    ws.send(JSON.stringify({ type: 'last_result', result: taskResult }));
  }

  ws.on('close', () => {
    wsClients = wsClients.filter(c => c !== ws);
  });
});

// API Routes

// Health check
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    taskRunning: !!activeTask,
    lastResult: !!taskResult,
  });
});

// Run a task
app.post('/api/run', async (req, res) => {
  if (activeTask) {
    return res.status(409).json({ error: 'A task is already running' });
  }

  const { task, url, headless } = req.body;
  if (!task) {
    return res.status(400).json({ error: 'Task description is required' });
  }

  activeTask = { task, url, startTime: Date.now() };
  broadcast({ type: 'task_started', task: activeTask });
  res.json({ message: 'Task started', task: activeTask });

  // Run in background (don't await)
  runTaskInBackground(task, url, headless).catch(err => {
    console.error('Task error:', err);
  });
});

async function runTaskInBackground(task, url, headless) {
  const operator = new WebOperator({
    headless: headless !== false,
    verbose: true,
    onMessage: (msg) => {
      broadcast(msg);
    },
  });

  try {
    const result = await operator.runTask(task, url || null);
    taskResult = {
      ...result,
      completedAt: Date.now(),
      task: activeTask?.task,
    };
    broadcast({ type: 'task_completed', result: taskResult });
  } catch (e) {
    taskResult = {
      success: false,
      message: e.message,
      completedAt: Date.now(),
      task: activeTask?.task,
    };
    broadcast({ type: 'task_error', error: e.message });
  } finally {
    activeTask = null;
  }
}

// Get task status
app.get('/api/status', (req, res) => {
  res.json({
    running: !!activeTask,
    task: activeTask,
    lastResult: taskResult,
  });
});

// Get task history
app.get('/api/history', (req, res) => {
  res.json({
    history: taskResult?.history || [],
    result: taskResult ? {
      success: taskResult.success,
      message: taskResult.message,
      iterations: taskResult.iterations,
    } : null,
  });
});

// Get latest screenshot
app.get('/api/screenshot', (req, res) => {
  if (taskResult?.screenshot) {
    const img = Buffer.from(taskResult.screenshot, 'base64');
    res.writeHead(200, {
      'Content-Type': 'image/png',
      'Content-Length': img.length,
    });
    res.end(img);
  } else {
    res.status(404).json({ error: 'No screenshot available' });
  }
});

// Get extracted data
app.get('/api/data', (req, res) => {
  res.json({
    extractedData: taskResult?.extractedData || null,
    pageContent: taskResult?.pageContent || null,
    partialData: taskResult?.partialData || null,
  });
});

// Chat with AI (non-browser tasks)
app.post('/api/chat', async (req, res) => {
  const { message } = req.body;
  if (!message) return res.status(400).json({ error: 'Message required' });

  try {
    // Intentar primero con callBestModel (OpenCode Zen + Copilot)
    const { callBestModel } = await import('./ai-client.js');
    const reply = await callBestModel('fast', [
      { role: 'user', content: message },
    ], 2048);
    if (reply) {
      return res.json({ reply, model: 'ai-agent' });
    }
  } catch (e) {
    console.log(`[Chat] callBestModel falló: ${e.message}`);
  }

  // Fallback 1: Freemodel API
  const freeKey = process.env.FREEMODEL_API_KEY;
  const freeBase = process.env.FREEMODEL_BASE_URL || 'https://api.freemodel.dev/v1';
  if (freeKey) {
    try {
      console.log('[Chat] Fallback: Freemodel API...');
      const resp = await fetch(`${freeBase}/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${freeKey}` },
        body: JSON.stringify({
          model: process.env.FREEMODEL_MODEL || 'gpt-4o',
          max_tokens: 2048,
          messages: [{ role: 'user', content: message }],
        }),
        signal: AbortSignal.timeout(30000),
      });
      const data = await resp.json();
      const content = data.choices?.[0]?.message?.content;
      if (content) {
        return res.json({ reply: content, model: 'freemodel' });
      }
    } catch (e) {
      console.log(`[Chat] Freemodel falló: ${e.message}`);
    }
  }

  // Fallback 2: OpenAI API directa
  const openaiKey = process.env.OPENAI_API_KEY;
  if (openaiKey) {
    try {
      console.log('[Chat] Fallback: OpenAI API...');
      const resp = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${openaiKey}` },
        body: JSON.stringify({
          model: 'gpt-4o-mini',
          max_tokens: 2048,
          messages: [{ role: 'user', content: message }],
        }),
        signal: AbortSignal.timeout(30000),
      });
      const data = await resp.json();
      const content = data.choices?.[0]?.message?.content;
      if (content) {
        return res.json({ reply: content, model: 'openai' });
      }
    } catch (e) {
      console.log(`[Chat] OpenAI falló: ${e.message}`);
    }
  }

  res.json({ reply: 'No hay APIs de IA disponibles. Verifica tus API keys en el archivo .env', model: 'none' });
});

// Cancel task
app.post('/api/cancel', (req, res) => {
  if (!activeTask) {
    return res.status(404).json({ error: 'No active task' });
  }
  activeTask = null;
  broadcast({ type: 'task_cancelled' });
  res.json({ message: 'Task cancelled' });
});

// Error handler
app.use((err, req, res, next) => {
  console.error('Server error:', err);
  res.status(500).json({ error: err.message });
});

server.listen(PORT, () => {
  console.log('');
  console.log('========================================');
  console.log('  Web Operator Agent - API Server');
  console.log('========================================');
  console.log(`  API:      http://localhost:${PORT}/api`);
  console.log(`  UI:       http://localhost:${PORT}`);
  console.log(`  WS:       ws://localhost:${PORT}`);
  console.log('========================================');
  console.log('');
});
