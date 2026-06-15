const puppeteer = require("puppeteer-extra");
const StealthPlugin = require("puppeteer-extra-plugin-stealth");
puppeteer.use(StealthPlugin());
const fs = require("fs");
const path = require("path");
const { solveCaptchaMultiRound } = require("./captcha_solver_final.js");
const { agentLoop } = require("./vision_agent.js");

const FORM_URL =
  "https://docs.google.com/forms/d/e/1FAIpQLSfd9f3bIBYdrMps4YlASFWr2Zsg81eiIsXF8wtq2bZ_xaSsYA/viewform";

const FIXED = {
  correo: "daveymena16@gmail.com",
  ciudad: "Cali",
  cedulaTecnico: "1077449318",
  nombreTecnico: "Duvier Davey Mena Mosquera",
  cedulaAuxiliar: "0",
  nombreAuxiliar: "X",
  tipoTrabajo: "MANTENIMIENTOS FTTH",
  tipoPostventa: "POSTVENTA FTTH",
  telefono: "3136174267",
};

const MAT = {
  "1057263-CBL DROP 100M TRAD OPTI/FAST/SLM SC/APC": "1",
  "1023342-CONECTOR 35400049 SC/APC FTTH FRKW": "3",
  "501115-CHAZO PLASTICO DE 3/8 X 2": "4",
  "501024-AMARRE PLASTICO 30 CM BLANCO": "5",
  "1059368-CONECTOR RJ45CAT6 INDOOR VEL SUP 500MBPS": "2",
  "501120-CINTA ADHESIVA AISLANTE COLOR NEGRO": "1",
  "1049591-ROSETA OPT 35250168 2P 4X2 FTTH FRKW": "1",
  "1025159-STICKER RED INTERNA OPERADOR": "1",
};

const FIELD_MAP = {
  correo: { value: FIXED.correo, type: "text" },
  ciudad: { value: FIXED.ciudad, type: "dropdown" },
  cuenta: { placeholder: true, type: "text" },
  nodo: { placeholder: true, type: "text" },
  orden: { placeholder: true, type: "text" },
  "tipo de trabajo": { value: FIXED.tipoTrabajo, type: "dropdown" },
  "cedula tecnico": { value: FIXED.cedulaTecnico, type: "text" },
  "nombre del tecnico": { value: FIXED.nombreTecnico, type: "text" },
  "cedula auxiliar": { value: FIXED.cedulaAuxiliar, type: "text" },
  "nombre del auxiliar": { value: FIXED.nombreAuxiliar, type: "text" },
  "aplica material": { placeholder: true, type: "radio" },
  telefono: { value: FIXED.telefono, type: "text" },
};

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

async function getFields(page) {
  return await page.evaluate(() =>
    Array.from(document.querySelectorAll('[role="listitem"]')).map(
      (item, idx) => {
        const h = item.querySelector('[role="heading"]');
        const title = h
          ? h.innerText.trim().replace(/\n/g, " ").trim().replace(/\s+/g, " ")
          : "";
        const cleanTitle = title.replace(/[*.]/g, "").trim().toLowerCase();
        const inp = item.querySelector(
          'input.whsOnd, input[type="text"], input[type="email"], input[type="number"]',
        );
        const radio = item.querySelector('[role="radio"]');
        return {
          idx,
          title: cleanTitle,
          rawTitle: title,
          hasInput: !!inp,
          hasSelect: !!item.querySelector('[role="listbox"]'),
          entryName: inp
            ? inp.getAttribute("name")
            : radio
              ? radio.getAttribute("name")
              : "",
          radios: Array.from(item.querySelectorAll('[role="radio"]')).map((r) =>
            r.getAttribute("data-value"),
          ),
        };
      },
    ),
  );
}

async function hasRequiredError(page) {
  return await page.evaluate(() =>
    Array.from(document.querySelectorAll('[role="alert"]')).some((a) =>
      a.innerText.includes("obligatoria"),
    ),
  );
}

async function fillText(page, idx, val) {
  for (let n = 0; n < 4; n++) {
    const el = await page.evaluateHandle((i) => {
      const items = document.querySelectorAll('[role="listitem"]');
      if (!items[i]) return null;
      return items[i].querySelector(
        'input.whsOnd, input[type="text"], input[type="email"], input[type="number"], textarea',
      );
    }, idx);
    if (!el || el.asElement() === null) {
      await delay(300);
      continue;
    }
    try {
      // 1. Hacer foco en el campo
      await el.asElement().click();
      await delay(100);

      // 2. Seleccionar TODO el texto con Ctrl+A
      await page.keyboard.down('Control');
      await page.keyboard.press('a');
      await page.keyboard.up('Control');
      await delay(50);

      // 3. Borrar lo seleccionado
      await page.keyboard.press('Backspace');
      await delay(100);

      // 4. Limpiar el valor por JS también (doble seguridad)
      await page.evaluate((i) => {
        const items = document.querySelectorAll('[role="listitem"]');
        if (!items[i]) return;
        const inp = items[i].querySelector('input.whsOnd, input[type="text"], input[type="email"], input[type="number"], textarea');
        if (inp) {
          inp.value = '';
          inp.dispatchEvent(new Event('input', { bubbles: true }));
        }
      }, idx);
      await delay(100);

      // 5. Hacer clic de nuevo y escribir el valor nuevo
      await el.asElement().click();
      await delay(50);
      await el
        .asElement()
        .type(String(val), { delay: 25 + Math.random() * 15 });
    } catch (e) {
      /* continue */
    }
    try {
      await el.dispose();
    } catch (e) {}
    await delay(200);
    const cur = await page.evaluate((i) => {
      const items = document.querySelectorAll('[role="listitem"]');
      if (!items[i]) return "";
      const inp = items[i].querySelector("input.whsOnd");
      return inp ? inp.value : "";
    }, idx);
    if (String(cur) === String(val)) return true;
    await delay(300);
  }
  return false;
}

async function selectDropdown(page, idx, label) {
  for (let n = 0; n < 6; n++) {
    const listbox = await page.evaluateHandle((i) => {
      const items = document.querySelectorAll('[role="listitem"]');
      if (!items[i]) return null;
      return items[i].querySelector('[role="listbox"]');
    }, idx);
    if (!listbox || listbox.asElement() === null) {
      await delay(300);
      continue;
    }
    await listbox.asElement().scrollIntoView({ block: "center" });
    await delay(200);
    await listbox.asElement().click();
    await delay(1200);
    try {
      await listbox.dispose();
    } catch (e) {}
    const sel = await page.evaluate((lbl) => {
      const opts = document.querySelectorAll('[role="option"]');
      for (const o of opts) {
        if (o.textContent.trim().toLowerCase() === lbl.toLowerCase()) {
          o.scrollIntoView({ block: "center" });
          o.click();
          return o.textContent.trim();
        }
      }
      return null;
    }, label);
    if (sel) {
      await delay(500);
      const txt = await page.evaluate((i) => {
        const items = document.querySelectorAll('[role="listitem"]');
        if (!items[i]) return "";
        const lb = items[i].querySelector('[role="listbox"]');
        return lb ? lb.textContent.trim() : "";
      }, idx);
      if (txt.toLowerCase().includes(label.toLowerCase())) return true;
    }
    await delay(400);
  }
  return false;
}

async function selectRadio(page, idx, val) {
  for (let n = 0; n < 5; n++) {
    const radio = await page.evaluateHandle(
      (i, v) => {
        const items = document.querySelectorAll('[role="listitem"]');
        if (!items[i]) return null;
        const radios = items[i].querySelectorAll('[role="radio"]');
        for (const r of radios) {
          if (r.getAttribute("data-value") === v) return r;
        }
        return null;
      },
      idx,
      val,
    );
    if (!radio || radio.asElement() === null) {
      await delay(300);
      continue;
    }
    await radio.asElement().scrollIntoView({ block: "center" });
    await delay(200);
    await radio.asElement().click();
    await delay(500);
    try {
      await radio.dispose();
    } catch (e) {}
    const cur = await page.evaluate((i) => {
      const items = document.querySelectorAll('[role="listitem"]');
      if (!items[i]) return "";
      const radios = items[i].querySelectorAll('[role="radio"]');
      for (const r of radios) {
        if (r.getAttribute("aria-checked") === "true")
          return r.getAttribute("data-value");
      }
      return "";
    }, idx);
    if (cur === val) return true;
    await delay(300);
  }
  return false;
}

function matchField(fieldTitle, order) {
  const ft = fieldTitle.toLowerCase();
  if (ft.includes("correo") || ft.includes("email"))
    return { type: "text", value: FIXED.correo };
  if (ft.includes("ciudad")) return { type: "dropdown", value: FIXED.ciudad };
  if (ft.includes("cuenta"))
    return { type: "text", value: String(order.cuenta) };
  if (ft.includes("nodo")) return { type: "text", value: String(order.nodo) };
  if (ft.includes("orden")) return { type: "text", value: String(order.ot) };
  if (ft.includes("tipo de trabajo") || ft.includes("tipo trabajo")) {
    const val =
      order.tipo === "POSTVENTA FTTH" ? FIXED.tipoPostventa : FIXED.tipoTrabajo;
    return { type: "dropdown", value: val };
  }
  if (ft.includes("cedula") && (ft.includes("tec") || ft.includes("tecnico")))
    return { type: "text", value: FIXED.cedulaTecnico };
  if (ft.includes("nombre") && (ft.includes("tec") || ft.includes("tecnico")))
    return { type: "text", value: FIXED.nombreTecnico };
  if (ft.includes("cedula") && (ft.includes("aux") || ft.includes("auxiliar")))
    return { type: "text", value: FIXED.cedulaAuxiliar };
  if (ft.includes("nombre") && (ft.includes("aux") || ft.includes("auxiliar")))
    return { type: "text", value: FIXED.nombreAuxiliar };
  if (ft.includes("aplica material"))
    return { type: "radio", value: order.aplicaMaterial || "Si" };
  if (
    ft.includes("telefono") ||
    ft.includes("teléfono") ||
    ft.includes("contacto") ||
    ft.includes("celular")
  )
    return { type: "text", value: FIXED.telefono };
  if (ft.includes("serial instalado") || ft.includes("serial")) {
    const match = ft.match(/serial\s*instalado\s*(\d+)/i);
    const idx = match ? parseInt(match[1]) : 1;
    const seriales = order.seriales || [];
    const val = seriales[idx - 1] || "";
    if (val) return { type: "text", value: val };
    return { type: "text", value: "" };
  }
  return null;
}

async function fillFieldsByVision(page, order, isTest) {
  if (!page._serialOntFilled) page._serialOntFilled = false;
  if (!page._serialDecoFilled) page._serialDecoFilled = false;

  const fields = await getFields(page);
  if (isTest) {
    console.log("  📋 CAMPOS en esta pagina:");
    fields.forEach((f) =>
      console.log(
        "    [" +
          f.idx +
          '] "' +
          f.rawTitle +
          '" tipo=' +
          (f.hasSelect
            ? "dropdown"
            : f.hasInput
              ? "text"
              : f.radios.length
                ? "radio"
                : "?") +
          (f.radios.length ? " [" + f.radios.join(",") + "]" : ""),
      ),
    );
  }
  let filled = 0,
    total = 0;
  for (const f of fields) {
    if (f.hasSelect) {
      if (
        f.title.includes("ciudad") ||
        f.title.includes("tipo de trabajo") ||
        f.title.includes("tipo trabajo")
      ) {
        total++;
        const matched = matchField(f.title, order);
        if (matched && (await selectDropdown(page, f.idx, matched.value)))
          filled++;
      }
      continue;
    }
    if (f.hasInput) {
      if (!f.rawTitle || f.rawTitle.replace(/[*.]/g, "").trim() === "")
        continue;
      total++;
      const matched = matchField(f.title, order);
      if (matched) {
        // Verificar si el campo YA tiene el valor correcto (evitar sobreescritura)
        const currentVal = await page.evaluate((i) => {
          const items = document.querySelectorAll('[role="listitem"]');
          if (!items[i]) return "";
          const inp = items[i].querySelector("input.whsOnd, input[type='text'], input[type='email'], input[type='number'], textarea");
          return inp ? inp.value.trim() : "";
        }, f.idx);
        if (String(currentVal) === String(matched.value)) {
          filled++;
          continue; // Ya tiene el valor correcto, no tocar
        }
        if (await fillText(page, f.idx, matched.value)) {
          filled++;
          continue;
        }
      }
      // Búsqueda específica de Seriales (ONT/Deco)
      const rawLower = f.rawTitle.toLowerCase();
      if (rawLower.includes("serial") || rawLower.includes("mac") || rawLower.includes("deco") || rawLower.includes("ont")) {
        if (order.serial_ont && !page._serialOntFilled && (rawLower.includes("ont") || rawLower.includes("serial"))) {
          if (await fillText(page, f.idx, order.serial_ont)) { 
            filled++; 
            page._serialOntFilled = true;
            continue; 
          }
        }
        if (order.serial_deco && !page._serialDecoFilled && (rawLower.includes("deco") || rawLower.includes("mac") || rawLower.includes("serial"))) {
          if (await fillText(page, f.idx, order.serial_deco)) { 
            filled++; 
            page._serialDecoFilled = true;
            continue; 
          }
        }
      }

      // Intentar llenar como material (usando datos dinámicos del JSON si existen, o fallback)
      if (order.aplicaMaterial === "Si") {
        let matFilled = false;
        
        // Mapeo dinámico: si el JSON trae las llaves exactas, úsalas.
        const dynamicMaterials = {
          "conector": order.conectores_mecanicos || MAT["Conectores mecanicos"],
          "tensor": order.tensores || MAT["Tensores"],
          "fibra": order.fibra_drop || MAT["Fibra drop"],
          "cable": order.cable_utp || MAT["Cable UTP"]
        };

        for (const [matKey, qty] of Object.entries(dynamicMaterials)) {
          if (qty && rawLower.includes(matKey)) {
            if (await fillText(page, f.idx, qty)) {
              filled++;
              matFilled = true;
              break;
            }
          }
        }
        if (matFilled) continue;
      }
      continue;
    }
    if (f.radios.length > 0) {
      const cur = await page.evaluate((i) => {
        const items = document.querySelectorAll('[role="listitem"]');
        if (!items[i]) return "";
        const radios = items[i].querySelectorAll('[role="radio"]');
        for (const r of radios) {
          if (r.getAttribute("aria-checked") === "true")
            return r.getAttribute("data-value");
        }
        return "";
      }, f.idx);
      if (cur) continue;
      total++;
      const matched = matchField(f.title, order);
      const val = matched
        ? matched.value
        : f.radios.includes("Si")
          ? "Si"
          : f.radios[0];
      if (await selectRadio(page, f.idx, val)) filled++;
    }
  }
  return { filled, total, fields };
}

async function clickBtn(page, text) {
  for (let i = 0; i < 10; i++) {
    try {
      const ok = await page.evaluate((t) => {
        const btns = document.querySelectorAll('[role="button"]');
        for (const b of btns) {
          if (b.innerText.trim() === t) {
            b.scrollIntoView({ block: "center" });
            b.click();
            return true;
          }
        }
        return false;
      }, text);
      if (ok) {
        await delay(500);
        return true;
      }
    } catch (_) {}
    await delay(500);
  }
  return false;
}

async function getPageState(page) {
  const body = await page.evaluate(() => document.body.innerText);
  if (
    body.includes("Tu respuesta ha sido registrada") ||
    body.includes("Respuesta enviada") ||
    body.includes("hemos registrado")
  )
    return "CONFIRMADO";
  // Solo detectar desafio activo (bframe), no el widget permanente
  const frames = page.frames();
  const hasActiveChallenge = frames.some((f) => f.url().includes("bframe"));
  if (hasActiveChallenge) return "CAPTCHA";
  return (await page.evaluate(
    () => document.querySelectorAll('[role="listitem"]').length,
  )) > 0
    ? "FORMULARIO"
    : "DESCONOCIDO";
}

async function processOrder(browser, page, order, idx, isTest) {
  page._serialOntFilled = false;
  page._serialDecoFilled = false;

  const logMsg = `\n[${idx + 1}/30] OT ${order.ot} | ${order.ciudad} | Mat: ${order.aplicaMaterial} | Tipo: ${order.tipo_trabajo || 'N/A'} | Seriales: ${order.serial_ont||'N/A'}, ${order.serial_deco||'N/A'}`;
  console.log(logMsg);
  fs.appendFileSync(path.join(__dirname, "reporte_diario.txt"), logMsg + "\n");

  try {
    // ---- ABRIR FORMULARIO LIMPIO ---- #
    console.log("  🧹 Preparando formulario...");
    
    // (SE ELIMINÓ LA LIMPIEZA DE COOKIES PARA NO PERDER LA SESIÓN CONFIABLE Y EVITAR CAPTCHAS)

    // 3. Navegar al formulario con cache-buster para forzar carga limpia
    const cleanURL = FORM_URL + (FORM_URL.includes('?') ? '&' : '?') + '_t=' + Date.now();
    await page.goto(cleanURL, { waitUntil: "networkidle2", timeout: 60000 });
    await delay(3000);

    // 4. Verificar que el formulario está realmente vacío
    const formCheck = await page.evaluate(() => {
      const inputs = document.querySelectorAll('input.whsOnd, input[type="text"]');
      let filledCount = 0;
      for (const inp of inputs) {
        if (inp.value && inp.value.trim() !== '') filledCount++;
      }
      return { total: inputs.length, filled: filledCount };
    }).catch(() => ({ total: 0, filled: 0 }));

    if (formCheck.filled > 0) {
      console.log(`  ⚠ Formulario tiene ${formCheck.filled}/${formCheck.total} campos con datos. Limpiando...`);
      await page.evaluate(() => {
        document.querySelectorAll('input.whsOnd, input[type="text"]').forEach(inp => {
          inp.value = '';
          inp.dispatchEvent(new Event('input', { bubbles: true }));
        });
      }).catch(() => {});
      await delay(500);
    }
    console.log("  ✓ Formulario limpio cargado");

    // ---- EJECUTAR AGENTE ---- #
    console.log("  [VA] Iniciando agente con Supervisor IA...");
    const completado = await agentLoop(page, order, fillFieldsByVision);

    if (completado) {
      console.log("  ✅ ORDEN COMPLETADA Y ENVIADA!");
      fs.appendFileSync(path.join(__dirname, "reporte_diario.txt"), "  ✅ ORDEN COMPLETADA Y ENVIADA!\n");
    } else {
      // Verificar una última vez si se envió
      const body = await page.evaluate(() => document.body.innerText.substring(0, 500)).catch(() => "");
      if (body.includes("registrada") || body.includes("Respuesta enviada") || body.includes("hemos registrado")) {
        console.log("  ✅ ENVIADO (confirmado por texto)!");
        fs.appendFileSync(path.join(__dirname, "reporte_diario.txt"), "  ✅ ENVIADO (confirmado por texto)!\n");
      } else {
        console.log("  ❌ No se pudo completar esta orden");
        fs.appendFileSync(path.join(__dirname, "reporte_diario.txt"), "  ❌ No se pudo completar esta orden\n");
      }
    }

    if (isTest) await page.screenshot({ path: "test_result_" + idx + ".png" });
  } catch (e) {
    console.error("  ❌ ERROR: " + (e.message || e).substring(0, 200));
    fs.appendFileSync(path.join(__dirname, "reporte_diario.txt"), "  ❌ ERROR: " + (e.message || e).substring(0, 200) + "\n");
    if (isTest)
      await page.screenshot({ path: "error_" + idx + ".png" }).catch(() => {});
  }
}

async function main() {
  // Inicializar reporte diario
  fs.writeFileSync(path.join(__dirname, "reporte_diario.txt"), "=== REPORTE DIARIO DE ORDENES ===\nFecha: " + new Date().toLocaleString() + "\n");

  const isTest = process.argv.includes("--test");
  let orders = JSON.parse(
    fs.readFileSync(require("path").join(__dirname, "ordenes_procesadas.json"), "utf8"),
  );
  if (isTest) orders = orders.slice(0, 1);
  console.log(isTest ? "TEST 1 orden" : orders.length + " ordenes");

  const chromePath =
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const profileDir = path.join(process.cwd(), "perfil_chrome");
  const { spawn } = require("child_process");

  // Try to connect to existing Chrome first (with Gmail session)
  let browser;
  console.log("🔍 Buscando Chrome existente con sesión...");
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      browser = await puppeteer.connect({
        browserURL: "http://127.0.0.1:9222",
      });
      console.log("✅ Conectado a Chrome existente (con sesión Gmail)");
      break;
    } catch (e) {
      if (attempt < 4) {
        console.log("  Chrome no encontrado, esperando...");
        await delay(2000);
      }
    }
  }

  // If no existing Chrome, launch new one
  if (!browser) {
    console.log("\n⚠️  Chrome no está corriendo. Lanzando nuevo...");
    console.log(
      "💡 Para evitar captchas: cierra esto, corre 'node setup_profile.js', loguéate en Gmail, y luego reinicia.",
    );
    console.log("Lanzando Chrome ahora...\n");

    // Kill existing Chrome gracefully
    try {
      require("child_process").execSync("taskkill /F /IM chrome.exe 2>nul", {
        stdio: "ignore",
      });
    } catch (e) {}
    await delay(2000);

    // Lanzar Chrome desde barra de tareas (start) para simular apertura natural
    const { exec } = require("child_process");
    const args = [
      `--remote-debugging-port=9222`,
      `--user-data-dir="${profileDir}"`,
      `--profile-directory=Profile`,
      `--start-maximized`,
      `--disable-blink-features=AutomationControlled`,
      `--no-first-run`,
      `--no-default-browser-check`,
    ].join(" ");

    exec(`start "" "${chromePath}" ${args}`, (err) => {
      if (err) console.log("  ⚠️ Error lanzando Chrome:", err.message);
    });

    console.log("Chrome lanzado desde barra de tareas (start)");
    console.log("Perfil: " + profileDir);
    console.log("Esperando que Chrome inicie...");

    // Wait for DevToolsActivePort to appear
    const devtoolsPortFile = path.join(profileDir, "DevToolsActivePort");
    for (let w = 0; w < 20; w++) {
      if (fs.existsSync(devtoolsPortFile)) {
        const content = fs.readFileSync(devtoolsPortFile, "utf8");
        console.log(
          "DevToolsActivePort encontrado: " + content.trim().split("\n")[0],
        );
        break;
      }
      await delay(1000);
    }

    // Connect to the real Chrome
    for (let attempt = 0; attempt < 10; attempt++) {
      try {
        browser = await puppeteer.connect({
          browserURL: "http://127.0.0.1:9222",
        });
        console.log("Conectado a Chrome real");
        break;
      } catch (e) {
        console.log("  Intento " + (attempt + 1) + " fallo, reintentando...");
        await delay(2000);
      }
    }
  }

  if (!browser) {
    console.log("No se pudo conectar a Chrome");
    process.exit(1);
  }

  const page = await browser.newPage();
  page.setDefaultTimeout(30000);
  await page.setViewport({ width: 1920, height: 1080 });

  await page.setRequestInterception(true);
  page.on("request", (req) => {
    try {
      const url = req.url();
      if (
        url.includes("google-analytics") ||
        url.includes("googlesyndication") ||
        url.includes("doubleclick") ||
        url.includes("googleadservices") ||
        url.includes("pagead2") ||
        url.includes("analytics")
      )
        req.abort();
      else req.continue();
    } catch (_) {}
  });

  for (let i = 0; i < orders.length; i++) {
    await processOrder(browser, page, orders[i], i, isTest);
    if (!isTest) await delay(1500);
  }

  console.log("\nCOMPLETADO!");
}

main().catch((e) => {
  console.error("FATAL:", e);
  process.exit(1);
});



