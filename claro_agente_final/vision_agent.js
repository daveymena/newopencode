
const { solveCaptchaMultiRound } = require("./captcha_solver_final.js");

function delay(ms) {
  return new Promise(r => setTimeout(r, ms + Math.random() * 100));
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

async function agentLoop(page, order, fillFieldsFn) {
  let noProgressCount = 0;
  
  for (let a = 0; a < 50; a++) {
    await delay(1500);
    
    // 1. DETECTAR CONFIRMACION
    const body = await page.evaluate(() => document.body.innerText.substring(0, 500)).catch(() => "");
    if (body.includes("registrada") || body.includes("Respuesta enviada") || body.includes("hemos registrado")) {
      console.log("  [VA] CONFIRMADO! Formulario enviado.");
      return true;
    }
    
    // 2. CAPTCHA
    const captchaVisible = await page.evaluate(() => {
      const iframe = document.querySelector('iframe[title*="recaptcha challenge"]');
      return iframe && iframe.offsetWidth > 0 && iframe.offsetHeight > 0 && window.getComputedStyle(iframe).visibility !== 'hidden';
    }).catch(() => false);
    
    if (captchaVisible) {
      console.log("  [VA] Captcha detectado (visible), intentando resolver...");
      const solved = await solveCaptchaMultiRound(page);
      if (solved) { noProgressCount = 0; continue; }
    }
    
    // 3. LLENAR CAMPOS
    const hasItems = await page.evaluate(() => document.querySelectorAll('[role="listitem"]').length > 0).catch(() => false);
    if (hasItems) {
      console.log("  [VA] Llenando campos...");
      await fillFieldsFn(page, order, false);
      noProgressCount = 0;
    }
    
    // 4. BOTON ENVIAR
    const envBtn = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('[role="button"], button, input[type="submit"], span'));
      return btns.some(b => {
        const txt = (b.innerText || b.value || "").trim().toLowerCase();
        return txt === "enviar" || txt === "submit" || txt.includes("enviar");
      });
    }).catch(() => false);
    if (envBtn) {
      console.log("  [VA] Click en Enviar...");
      await clickBtn(page, "Enviar");
      await delay(5000);
      const body2 = await page.evaluate(() => document.body.innerText.substring(0, 500)).catch(() => "");
      if (body2.includes("registrada") || body2.includes("Respuesta enviada") || body2.includes("hemos registrado")) {
        console.log("  [VA] ENVIADO!");
        return true;
      }
      noProgressCount = 0;
      continue;
    }
    
    // 5. BOTON SIGUIENTE
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
    
    // 6. SIN PROGRESO
    noProgressCount++;
    if (noProgressCount >= 5) {
      console.log("  [VA] Sin progreso, intentando recargar...");
      await page.goto("https://docs.google.com/forms/d/e/1FAIpQLSfd9f3bIBYdrMps4YlASFWr2Zsg81eiIsXF8wtq2bZ_xaSsYA/viewform", { waitUntil: "networkidle2", timeout: 30000 }).catch(() => {});
      await delay(3000);
      noProgressCount = 0;
    }
  }
  return false;
}

module.exports = { agentLoop };
