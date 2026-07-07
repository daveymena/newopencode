import { readFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

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
      if (!process.env[key]) process.env[key] = val;
    }
  }
}
loadEnv();

const CONFIG = {
  freemodel: {
    apiKey: process.env.FREEMODEL_API_KEY || 'fe_oa_db8434da9d092b657e26dba8e2cdbf5cc460848f7e3b490c',
    baseUrl: process.env.FREEMODEL_BASE_URL || 'https://api.freemodel.dev/v1',
    model: process.env.FREEMODEL_MODEL || 'gpt-4o',
  },
  puter: {
    token: process.env.PUTER_AUTH_TOKEN || '',
  },
  openai: {
    apiKey: process.env.OPENAI_API_KEY || '',
    model: process.env.OPENAI_MODEL || 'gpt-4o',
  },
};

function delay(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function callFreemodelVision(messages, maxTokens = 4096) {
  const url = `${CONFIG.freemodel.baseUrl}/chat/completions`;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${CONFIG.freemodel.apiKey}`,
        },
        body: JSON.stringify({
          model: CONFIG.freemodel.model,
          messages,
          max_tokens: maxTokens,
          temperature: 0.1,
        }),
        signal: AbortSignal.timeout(60000),
      });
      if (!resp.ok) {
        const text = await resp.text();
        console.error(`  [AI] HTTP ${resp.status}: ${text.slice(0, 100)}`);
        await delay(2000 * (attempt + 1));
        continue;
      }
      const data = await resp.json();
      return data.choices?.[0]?.message?.content || null;
    } catch (e) {
      console.error(`  [AI] Error: ${e.message.slice(0, 80)}`);
      await delay(2000 * (attempt + 1));
    }
  }
  return null;
}

async function callOpenAIVision(messages, maxTokens = 4096) {
  if (!CONFIG.openai.apiKey) return null;
  const url = 'https://api.openai.com/v1/chat/completions';
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${CONFIG.openai.apiKey}`,
      },
      body: JSON.stringify({
        model: CONFIG.openai.model,
        messages,
        max_tokens: maxTokens,
        temperature: 0.1,
      }),
      signal: AbortSignal.timeout(60000),
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    return data.choices?.[0]?.message?.content || null;
  } catch {
    return null;
  }
}

async function callVisionAI(messages, maxTokens = 4096) {
  let result = await callFreemodelVision(messages, maxTokens);
  if (result) return result;
  result = await callOpenAIVision(messages, maxTokens);
  if (result) return result;
  throw new Error('No AI provider available. Configure FREEMODEL_API_KEY or OPENAI_API_KEY in .env');
}

export async function analyzeScreenshot(screenshotBase64, task, pageInfo) {
  const messages = [
    {
      role: 'system',
      content: `You are a Computer-Using Agent (CUA) similar to ChatGPT Operator.
You control a web browser to complete tasks for the user.

CAPABILITIES:
- You see screenshots of the current browser page
- You can click buttons, links, and any clickable elements
- You can type text into input fields
- You can scroll the page
- You can navigate to URLs
- You can wait for page loads
- You can extract information from the page

RULES:
1. Always respond with EXACTLY ONE action in the exact format specified
2. If you see a captcha or challenge, try to solve it or find a bypass
3. If stuck after 3 attempts, try a different approach
4. If the task is complete, respond with TASK_COMPLETE
5. If the task cannot be completed, respond with TASK_FAILED and explain why
6. Be persistent - try different element selectors if one doesn't work
7. For dropdowns/selects, try clicking the element first, then clicking the option`,
    },
    {
      role: 'user',
      content: [
        {
          type: 'text',
          text: `TASK: ${task}

Current page URL: ${pageInfo.url || 'unknown'}
Page title: ${pageInfo.title || 'unknown'}

Analyze the screenshot and decide the NEXT action to make progress on the task.

RESPOND WITH EXACTLY ONE ACTION in one of these formats:

CLICK "element text"
  - Click a button, link, or element containing text
  - Example: CLICK "Sign In"
  - Example: CLICK "Submit"
  - Example: CLICK "Next"

TYPE "text" INTO "field label or placeholder"
  - Type text into an input field
  - Example: TYPE "john@email.com" INTO "Email"
  - Example: TYPE "password123" INTO "Password"

SELECT "option text" FROM "dropdown label"
  - Select an option from a dropdown/select
  - Example: SELECT "United States" FROM "Country"

SCROLL_DOWN
SCROLL_UP
  - Scroll the page

WAIT
  - Wait 3 seconds for page to load

NAVIGATE "url"
  - Navigate to a specific URL

EXTRACT "description of what to extract"
  - Extract information from the page (I will report back what I find)

TASK_COMPLETE
  - The task is done

TASK_FAILED "reason"
  - The task cannot be completed

NOW RESPOND WITH ONLY ONE ACTION LINE:`,
        },
        {
          type: 'image_url',
          image_url: { url: `data:image/png;base64,${screenshotBase64}`, detail: 'high' },
        },
      ],
    },
  ];

  return await callVisionAI(messages, 2048);
}

export async function analyzeWithContext(screenshotBase64, task, context, pageInfo) {
  const messages = [
    {
      role: 'system',
      content: `You are a Computer-Using Agent (CUA). You see screenshots and decide actions.`,
    },
    {
      role: 'user',
      content: [
        {
          type: 'text',
          text: `TASK: ${task}
PREVIOUS ACTIONS & RESULTS: ${context}

Current URL: ${pageInfo.url}
Title: ${pageInfo.title}

Analyze the screenshot. What happened after the last action? Is progress being made?
If the last action didn't work, try something different.
Respond with one action.`,
        },
        { type: 'image_url', image_url: { url: `data:image/png;base64,${screenshotBase64}`, detail: 'high' } },
      ],
    },
  ];

  return await callVisionAI(messages, 2048);
}

export async function extractPageContent(screenshotBase64, extractionDesc) {
  const messages = [
    {
      role: 'system',
      content: 'Extract the requested information from the screenshot. Return ONLY the extracted data, no explanation.',
    },
    {
      role: 'user',
      content: [
        { type: 'text', text: `Extract from this page: ${extractionDesc}` },
        { type: 'image_url', image_url: { url: `data:image/png;base64,${screenshotBase64}`, detail: 'high' } },
      ],
    },
  ];

  return await callVisionAI(messages, 4096);
}

export async function solveCaptchaVision(screenshotBase64) {
  const messages = [
    {
      role: 'system',
      content: 'You are a captcha solver. Analyze the image and determine the correct action to pass the challenge.',
    },
    {
      role: 'user',
      content: [
        { type: 'text', text: 'This page shows a captcha challenge. What should I do to pass it? Look carefully at what the captcha is asking for. If it\'s a reCAPTCHA checkbox, respond with CLICK. If it\'s an image grid challenge, describe which tiles to click. RESPOND WITH ONE ACTION.' },
        { type: 'image_url', image_url: { url: `data:image/png;base64,${screenshotBase64}`, detail: 'high' } },
      ],
    },
  ];

  return await callVisionAI(messages, 1024);
}
