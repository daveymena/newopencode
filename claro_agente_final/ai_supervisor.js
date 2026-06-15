// Cargar variables de entorno del archivo .env del directorio raíz
try {
  const path = require("path");
  require("dotenv").config({ path: path.join(__dirname, "../.env") });
} catch (e) {}

const OLLAMA_ENDPOINT = "http://localhost:11434/api/generate";
const VISION_MODEL = "moondream:latest";
const REASON_MODEL = "gemma4:e2b-it-q4_K_M";
const FAST_MODEL = "llama-free:latest";

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

async function callOllama(model, prompt, imageBase64 = null) {
  const body = { model, prompt, stream: false };
  if (imageBase64) body.images = [imageBase64];
  try {
    const resp = await fetch(OLLAMA_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(60000),
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    return data.response || null;
  } catch (e) {
    return null;
  }
}

async function callVision(prompt, imageBase64) {
  const geminiKey = process.env.GOOGLE_GENERATIVE_AI_API_KEY;
  if (geminiKey) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${geminiKey}`;
    const body = {
      contents: [{
        parts: [
          { text: prompt },
          {
            inlineData: {
              mimeType: "image/png",
              data: imageBase64
            }
          }
        ]
      }]
    };
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      if (resp.ok) {
        const data = await resp.json();
        return data.candidates?.[0]?.content?.parts?.[0]?.text || null;
      }
    } catch (e) {}
  }
  
  // Fallback a Moondream local de Ollama si no hay API Key o falla
  return await callOllama(VISION_MODEL, prompt, imageBase64);
}

async function callReason(prompt) {
  return await callOllama(REASON_MODEL, prompt);
}

async function callFast(prompt) {
  return await callOllama(FAST_MODEL, prompt);
}

async function describeScreenshot(page) {
  const shot = await page.screenshot({ encoding: "base64" });
  const desc = await callVision(
    "Describe this webpage in detail. What do you see? What fields, buttons, text, and elements are visible? " +
    "Is there a form? A captcha? Error messages? What is the current state of the page? " +
    "List ALL visible text, buttons, and interactive elements.",
    shot
  );
  return { description: desc || "(no description)", screenshotBase64: shot };
}

async function analyzeCaptchaArea(page) {
  const shot = await page.screenshot({ encoding: "base64" });
  const analysis = await callVision(
    "I see a reCAPTCHA challenge on this page. " +
    "Look at the grid of images. What is the challenge asking for? " +
    "Describe EACH tile in the grid and what object/pattern it contains. " +
    "Then tell me EXACTLY which tile numbers (1-based, left-to-right, top-to-bottom) contain the requested object. " +
    "Format: CHALLENGE: <text> TILES: <numbers separated by commas>",
    shot
  );
  return analysis || "";
}

async function analyzeIndividualTile(tileImageBase64, challengeText) {
  const analysis = await callVision(
    "This is one tile from a reCAPTCHA challenge. The challenge asks to click images containing: \"" + challengeText + "\". " +
    "Does THIS tile contain the requested object? Answer ONLY: YES or NO. Then briefly explain why.",
    tileImageBase64
  );
  return analysis || "NO";
}

async function decideAction(pageState, context) {
  const prompt = `You are an AI supervisor for an automated form-filling bot. The bot is filling a Google Form.

CURRENT STATE:
${pageState}

CONTEXT: ${context}

TASK: Analyze the situation and decide what action the bot should take next.

Possible actions:
- CLICK "button text" - click a button with specific text
- FILL "field heading" = "value" - fill a field
- SCROLL - scroll down
- WAIT - wait and retry
- REFRESH - reload the page
- RELAUNCH - close and restart
- SOLVED - the form was submitted successfully

If there's a captcha challenge visible, describe what the captcha shows.

Respond with EXACTLY ONE action line, nothing else.`;
  
  return await callReason(prompt);
}

async function supervise(page, context = "Form filling progress") {
  console.log("\n🤖 [SUPERVISOR] Activando supervision IA...");
  
  const { description, screenshotBase64 } = await describeScreenshot(page);
  console.log("  [SUPERVISOR] Vision: " + (description ? description.substring(0, 200) + "..." : "sin descripcion"));
  
  const action = await decideAction(description, context);
  console.log("  [SUPERVISOR] Razonamiento: " + (action ? action.substring(0, 300) : "sin respuesta"));

  return { action, screenshotBase64, description };
}

async function executeAction(page, actionStr) {
  if (!actionStr) return false;
  
  const action = actionStr.trim();

  // CLICK action
  const clickMatch = action.match(/CLICK\s+"([^"]+)"/i);
  if (clickMatch) {
    const btnText = clickMatch[1];
    console.log("  [SUPERVISOR] Click en \"" + btnText + "\"...");
    for (let i = 0; i < 10; i++) {
      const ok = await page.evaluate((txt) => {
        const btns = document.querySelectorAll('[role="button"], button, input[type="submit"], span, a');
        for (const b of btns) {
          const t = (b.innerText || b.value || b.textContent || "").trim().toLowerCase();
          if (t === txt.toLowerCase() || t.includes(txt.toLowerCase())) {
            b.scrollIntoView({ block: "center" });
            b.click();
            return true;
          }
        }
        return false;
      }, btnText);
      if (ok) { await delay(500); return true; }
      await delay(300);
    }
    return false;
  }

  // FILL action
  const fillMatch = action.match(/FILL\s+"([^"]+)"\s*=\s*"([^"]*)"/i);
  if (fillMatch) {
    const [_, heading, value] = fillMatch;
    console.log("  [SUPERVISOR] Llenar \"" + heading.substring(0, 20) + "\" = \"" + value + "\"...");
    const ok = await page.evaluate(([h, v]) => {
      const items = document.querySelectorAll('[role="listitem"]');
      for (const item of items) {
        const hd = item.querySelector('[role="heading"]');
        if (hd && hd.textContent.trim().toLowerCase().includes(h.toLowerCase())) {
          const inp = item.querySelector('input.whsOnd, input[type="text"], input[type="email"], input[type="number"], textarea');
          if (inp) {
            inp.focus();
            inp.value = v;
            inp.dispatchEvent(new Event("input", { bubbles: true }));
            inp.dispatchEvent(new Event("change", { bubbles: true }));
            return true;
          }
        }
      }
      return false;
    }, [heading, value]);
    await delay(300);
    return ok;
  }

  if (action.includes("SCROLL")) {
    console.log("  [SUPERVISOR] Scroll...");
    await page.evaluate(() => window.scrollBy(0, 400));
    await delay(1000);
    return true;
  }

  if (action.includes("WAIT")) {
    console.log("  [SUPERVISOR] Esperando...");
    await delay(3000);
    return true;
  }

  if (action.includes("REFRESH")) {
    console.log("  [SUPERVISOR] Recargando pagina...");
    await page.reload({ waitUntil: "networkidle2" });
    await delay(3000);
    return true;
  }

  if (action.includes("SOLVED")) {
    console.log("  [SUPERVISOR] Detecta formulario completado!");
    return true;
  }

  console.log("  [SUPERVISOR] Accion no reconocida: " + action.substring(0, 100));
  return false;
}

module.exports = {
  callVision, callReason, callFast,
  describeScreenshot, analyzeCaptchaArea, analyzeIndividualTile,
  decideAction, supervise, executeAction
};
