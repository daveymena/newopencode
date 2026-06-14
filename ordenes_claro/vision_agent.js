const { solveCaptchaMultiRound } = require("./captcha_solver_final.js");

// ============================================================
// MÓDULO DE VISIÓN (Qwen3-VL via Ollama)
// ============================================================

async function askQwen(screenshotB64, prompt, timeoutMs = 120000) {
  try {
    const res = await fetch("http://127.0.0.1:11434/api/generate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        model: "qwen3-vl:235b-cloud",
        prompt,
        images: [screenshotB64],
        stream: false,
        options: {temperature: 0.05, num_predict: 256}
      }),
      signal: AbortSignal.timeout(timeoutMs)
    });
    const data = await res.json();
    return (data.response || "").trim().toLowerCase();
  } catch (e) {
    console.log(`  [VA] Qwen error: ${e.message.substring(0,60)}`);
    return "";
  }
}

// ============================================================
// AGENTE SUPERVISOR — Usa visión + lógica IA para decidir
// ============================================================

/**
 * supervisorAgent: Toma una captura de pantalla, la envía a Qwen3-VL,
 * y decide qué acción tomar. Retorna un objeto { action, detail }.
 * 
 * Acciones posibles:
 *   - "fill_fields"   → Hay campos por llenar
 *   - "click_next"    → Hay botón Siguiente
 *   - "click_submit"  → Hay botón Enviar
 *   - "solve_captcha" → Hay reCAPTCHA activo
 *   - "success"       → Formulario enviado exitosamente
 *   - "error"         → Hay errores visibles en rojo
 *   - "unknown"       → No se puede determinar
 */
async function supervisorAgent(page) {
  // Esperar un momento para que la página se estabilice
  await delay(1000);

  const ss = await page.screenshot({encoding: "base64", type: "jpeg", quality: 40});

  const prompt = `Eres un agente supervisor de calidad automatizando un formulario de Google Forms.
Analiza cuidadosamente esta captura de pantalla y responde con UNA SOLA de estas opciones:

- fill_fields: Hay campos de formulario vacíos que necesitan ser llenados (inputs de texto, dropdowns, radio buttons sin seleccionar)
- click_next: Hay un botón "Siguiente" visible para avanzar a la siguiente página del formulario
- click_submit: Hay un botón "Enviar" visible. Todo parece estar completo y listo para enviar
- solve_captcha: Hay un desafío reCAPTCHA visible (cuadrícula de imágenes o checkbox)
- success: El formulario YA fue enviado exitosamente. Se ve un mensaje de confirmación como "Tu respuesta ha sido registrada" o "Respuesta enviada"
- error: Hay mensajes de error visibles en rojo, como "Este campo es obligatorio" o similar
- unknown: No se puede determinar el estado

IMPORTANTE: Si ves un botón que dice "Enviar" y los campos parecen estar llenos, responde "click_submit".
Si ves un mensaje de éxito/confirmación, responde "success".

Tu respuesta (una sola palabra):`;

  const resp = await askQwen(ss, prompt);
  console.log(`  [SUPERVISOR] Decisión IA: "${resp || "(vacío)"}"`);

  // Normalizar la respuesta de la IA
  if (!resp) return { action: "unknown", detail: "Sin respuesta de IA" };
  
  if (resp.includes("fill_fields") || resp.includes("fill"))
    return { action: "fill_fields", detail: "Campos por llenar detectados por IA" };
  if (resp.includes("click_submit") || resp.includes("submit") || resp.includes("enviar"))
    return { action: "click_submit", detail: "Botón Enviar detectado por IA" };
  if (resp.includes("click_next") || resp.includes("next") || resp.includes("siguiente"))
    return { action: "click_next", detail: "Botón Siguiente detectado por IA" };
  if (resp.includes("solve_captcha") || resp.includes("captcha") || resp.includes("recaptcha"))
    return { action: "solve_captcha", detail: "Captcha detectado por IA" };
  if (resp.includes("success") || resp.includes("confirmado") || resp.includes("registrada") || resp.includes("enviada"))
    return { action: "success", detail: "Formulario enviado confirmado por IA" };
  if (resp.includes("error"))
    return { action: "error", detail: "Errores visibles detectados por IA" };

  return { action: "unknown", detail: resp };
}

/**
 * supervisorVerifyAndSubmit: El supervisor verifica visualmente que todo
 * está completo y realiza el envío final con confirmación doble.
 * Retorna true si el formulario fue enviado exitosamente.
 */
async function supervisorVerifyAndSubmit(page) {
  console.log("\n  ┌──────────────────────────────────────────┐");
  console.log("  │  🤖 SUPERVISOR IA — Verificación final   │");
  console.log("  └──────────────────────────────────────────┘");

  for (let intento = 0; intento < 5; intento++) {
    console.log(`\n  [SUPERVISOR] Intento ${intento + 1}/5 — Analizando pantalla...`);
    
    const decision = await supervisorAgent(page);
    console.log(`  [SUPERVISOR] Acción: ${decision.action} — ${decision.detail}`);

    switch (decision.action) {
      case "success":
        console.log("  [SUPERVISOR] ✅ ÉXITO CONFIRMADO — Formulario enviado correctamente");
        return true;

      case "click_submit":
        console.log("  [SUPERVISOR] 📤 Procediendo a enviar...");
        const clicked = await clickBtn(page, "Enviar");
        if (clicked) {
          console.log("  [SUPERVISOR] ✓ Clic en Enviar realizado — Esperando confirmación...");
          await delay(6000);
          // Verificar que realmente se envió
          const postSubmit = await supervisorAgent(page);
          if (postSubmit.action === "success") {
            console.log("  [SUPERVISOR] ✅ ENVÍO CONFIRMADO POR IA");
            return true;
          }
          // Si no vemos éxito, puede haber errores o necesitar más tiempo
          console.log(`  [SUPERVISOR] Post-envío: ${postSubmit.action} — ${postSubmit.detail}`);
          if (postSubmit.action === "error") {
            console.log("  [SUPERVISOR] ⚠ Errores detectados post-envío, reintentando...");
          }
        } else {
          console.log("  [SUPERVISOR] ⚠ No se pudo hacer clic en Enviar con selector");
          // Intentar con visión: buscar el botón visualmente
          await clickBtnVisual(page, "enviar");
        }
        break;

      case "click_next":
        console.log("  [SUPERVISOR] ➡ Hay botón Siguiente, avanzando...");
        await clickBtn(page, "Siguiente");
        await delay(2000);
        break;

      case "fill_fields":
        console.log("  [SUPERVISOR] ⚠ Campos vacíos detectados — Abortando envío para rellenar");
        return false; // Devolver control al agentLoop para que llene

      case "solve_captcha":
        console.log("  [SUPERVISOR] 🔒 Captcha detectado, resolviendo...");
        await solveCaptchaMultiRound(page);
        await delay(2000);
        break;

      case "error":
        console.log("  [SUPERVISOR] ❌ Errores visibles. Intentando retroceder y corregir...");
        // Intentar hacer clic en "Atrás" para corregir
        const backClicked = await clickBtn(page, "Atrás");
        if (backClicked) {
          console.log("  [SUPERVISOR] ← Retrocedimos para corregir");
          await delay(2000);
        }
        return false; // Devolver control para rellenar

      default:
        console.log("  [SUPERVISOR] ❓ Estado desconocido, esperando y reintentando...");
        await delay(3000);
        break;
    }
  }

  console.log("  [SUPERVISOR] ⚠ Se agotaron los intentos del supervisor");
  // Último intento: verificar el texto del body directamente
  const body = await page.evaluate(() => document.body.innerText.substring(0, 500)).catch(() => "");
  if (body.includes("registrada") || body.includes("Respuesta enviada") || body.includes("hemos registrado")) {
    console.log("  [SUPERVISOR] ✅ Confirmado por texto del body");
    return true;
  }
  return false;
}

// ============================================================
// UTILIDADES DE CLIC
// ============================================================

function delay(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function clickBtn(page, text) {
  for (let i = 0; i < 10; i++) {
    try {
      const ok = await page.evaluate((t) => {
        const btns = document.querySelectorAll('[role="button"], button, input[type="submit"]');
        for (const b of btns) {
          const btnText = (b.innerText || b.value || "").trim().toLowerCase();
          if (btnText === t.toLowerCase() || btnText.includes(t.toLowerCase())) {
            b.scrollIntoView({block: "center"});
            b.click();
            return true;
          }
        }
        // Buscar en spans y divs de Google Forms
        const spans = document.querySelectorAll('span, div.MocG8c, div.uArJ5e');
        for (const s of spans) {
          if ((s.innerText || "").trim().toLowerCase() === t.toLowerCase()) {
            s.click();
            return true;
          }
        }
        return false;
      }, text);
      if (ok) { await delay(500); return true; }
    } catch (_) {}
    await delay(500);
  }
  return false;
}

/**
 * clickBtnVisual: Cuando los selectores CSS fallan, usa la IA para
 * encontrar y hacer clic en un botón por coordenadas visuales.
 */
async function clickBtnVisual(page, buttonText) {
  console.log(`  [SUPERVISOR] Intentando clic visual en "${buttonText}"...`);
  
  const ss = await page.screenshot({encoding: "base64", type: "jpeg", quality: 50});
  const viewport = page.viewport();
  
  const prompt = `Mira esta captura de pantalla de un formulario de Google Forms.
Necesito encontrar el botón "${buttonText}".
Responde SOLO con las coordenadas X,Y del CENTRO del botón, en formato: X,Y
La pantalla tiene ${viewport.width}x${viewport.height} píxeles.
Si no ves el botón, responde: none

Tu respuesta (solo coordenadas o "none"):`;

  const resp = await askQwen(ss, prompt, 60000);
  
  if (!resp || resp.includes("none")) {
    console.log(`  [SUPERVISOR] No se encontró "${buttonText}" visualmente`);
    return false;
  }

  const coords = resp.match(/(\d+)\s*[,x]\s*(\d+)/);
  if (coords) {
    const x = parseInt(coords[1]);
    const y = parseInt(coords[2]);
    console.log(`  [SUPERVISOR] Clic visual en (${x}, ${y})...`);
    await page.mouse.click(x, y);
    await delay(1000);
    return true;
  }

  console.log(`  [SUPERVISOR] Coordenadas no válidas: "${resp}"`);
  return false;
}

// ============================================================
// BUCLE PRINCIPAL DEL AGENTE
// ============================================================

async function agentLoop(page, order, fillFieldsFn) {
  let noProgressCount = 0;

  for (let a = 0; a < 50; a++) {
    await delay(1500);
    
    // 1. CAPTCHA — Siempre verificar primero (más confiable que la IA)
    const bframe = page.frames().some(f => f.url().includes("bframe"));
    if (bframe) {
      console.log("  [VA] Captcha detectado, resolviendo...");
      await solveCaptchaMultiRound(page);
      noProgressCount = 0;
      continue;
    }

    // 2. CAMPOS — Si hay campos, llenarlos
    const hasItems = await page.evaluate(() => document.querySelectorAll('[role="listitem"]').length > 0).catch(() => false);
    if (hasItems) {
      console.log("  [VA] Llenando campos...");
      await fillFieldsFn(page, order, false);
      noProgressCount = 0;
      // No hacer continue — dejar que verifique botones después
    }

    // 3. BOTÓN ENVIAR — Verificar si existe
    const envBtn = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('[role="button"], button, input[type="submit"], span'));
      return btns.some(b => {
        const txt = (b.innerText || b.value || "").trim().toLowerCase();
        return txt === "enviar" || txt === "submit" || txt.includes("enviar");
      });
    }).catch(() => false);

    if (envBtn) {
      console.log("  [VA] Botón Enviar detectado — Delegando al SUPERVISOR IA...");
      const exito = await supervisorVerifyAndSubmit(page);
      if (exito) return true;
      // Si el supervisor retorna false, sigue intentando
      noProgressCount = 0;
      continue;
    }

    // 4. BOTÓN SIGUIENTE
    const sigBtn = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('[role="button"], button, input[type="submit"], span'));
      return btns.some(b => {
        const txt = (b.innerText || b.value || "").trim().toLowerCase();
        return txt === "siguiente" || txt === "next" || txt.includes("siguiente");
      });
    }).catch(() => false);
    if (sigBtn) {
      console.log("  [VA] Click Siguiente...");
      await clickBtn(page, "Siguiente");
      noProgressCount = 0;
      continue;
    }

    // 5. CONFIRMACIÓN POR TEXTO
    const body = await page.evaluate(() => document.body.innerText.substring(0, 500)).catch(() => "");
    if (body.includes("registrada") || body.includes("Respuesta enviada") || body.includes("hemos registrado")) {
      console.log("  [VA] ✅ CONFIRMADO! Formulario enviado.");
      return true;
    }

    // 6. ESTADO AMBIGUO — Delegar al Supervisor con IA
    noProgressCount++;
    if (noProgressCount >= 2) {
      console.log("  [VA] Sin progreso, consultando Supervisor IA...");
      const decision = await supervisorAgent(page);
      
      switch (decision.action) {
        case "success":
          console.log("  [VA] ✅ Supervisor confirma éxito!");
          return true;
        case "click_submit":
          console.log("  [VA] Supervisor dice enviar...");
          const ok = await supervisorVerifyAndSubmit(page);
          if (ok) return true;
          break;
        case "fill_fields":
        case "click_next":
        case "solve_captcha":
          noProgressCount = 0;
          continue; // Re-loop
        case "error":
          console.log("  [VA] Supervisor detectó errores, reintentando...");
          noProgressCount = 0;
          continue;
        default:
          if (noProgressCount >= 4) {
            console.log("  [VA] Demasiados ciclos sin progreso, saliendo...");
            break;
          }
          continue;
      }
    } else {
      continue; // Dar otra vuelta antes de invocar la IA
    }

    break;
  }
  return false;
}

module.exports = { agentLoop, supervisorAgent, supervisorVerifyAndSubmit, decideAction: supervisorAgent };
