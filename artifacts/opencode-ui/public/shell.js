/* ============================================================
   OpenCode Evolved — Shell JS v3
   • Modo oscuro forzado
   • Barra de branding + dots de estado
   • Visión universal: imagen → descripción de texto →
     se inyecta en el chat para que CUALQUIER modelo la "vea"
     (Llama, Groq, Mistral, Claude, GPT, Gemini, todos)
   ============================================================ */
(function () {
  "use strict";

  // ── 1. Forzar modo oscuro ──────────────────────────────────
  function forceDark() {
    try { localStorage.setItem("opencode-color-scheme", "dark"); } catch {}
    document.documentElement.dataset.colorScheme = "dark";
    document.documentElement.style.colorScheme = "dark";
  }
  new MutationObserver(() => {
    if (document.documentElement.dataset.colorScheme !== "dark") forceDark();
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-color-scheme"] });
  forceDark();

  // ── 2. Header de branding ──────────────────────────────────
  function injectHeader() {
    if (document.getElementById("oc-evolved-header")) return;
    const bar = document.createElement("div");
    bar.id = "oc-evolved-header";
    bar.innerHTML = `
      <div class="oc-logo">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M12 2L2 7L12 12L22 7Z" stroke="#8b5cf6" stroke-width="1.8" stroke-linejoin="round"/>
          <path d="M2 17L12 22L22 17" stroke="#8b5cf6" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M2 12L12 17L22 12" stroke="#6d28d9" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>OpenCode</span>
        <span class="oc-badge">EVOLVED</span>
      </div>
      <div class="oc-dots">
        <div class="oc-dot green"  title="Motor IA activo"></div>
        <div class="oc-dot purple" title="MCP Tools activos"></div>
        <div class="oc-dot blue"   title="Visión universal activa"></div>
      </div>
      <div class="oc-tools-info" title="Herramientas activas">
        🛠 SSH · PowerShell · Browser · Files · Memory · 👁 Visión Universal
      </div>
      <div class="oc-status" id="oc-status-text">listo</div>
    `;
    document.body.prepend(bar);
  }

  // ── 3. Panel de Visión Universal ───────────────────────────
  function injectVisionButton() {
    if (document.getElementById("oc-vision-btn")) return;

    const btn = document.createElement("div");
    btn.id = "oc-vision-btn";
    btn.title = "Visión Universal — cualquier modelo puede ver la imagen";
    btn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>
      <span>Visión</span>
    `;
    btn.addEventListener("click", () => togglePanel());
    document.body.appendChild(btn);

    // Panel
    const panel = document.createElement("div");
    panel.id = "oc-vision-panel";
    panel.innerHTML = `
      <div class="oc-vision-header">
        <div class="oc-vision-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="14" height="14">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
          <span>Visión Universal</span>
          <span class="oc-vision-badge">todos los modelos</span>
        </div>
        <button id="oc-vision-close">✕</button>
      </div>

      <div class="oc-vision-how">
        La imagen se convierte en texto descriptivo → <strong>cualquier modelo</strong> la puede "leer"
      </div>

      <div class="oc-vision-drop" id="oc-vision-drop">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="32" height="32">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
          <circle cx="8.5" cy="8.5" r="1.5"/>
          <path d="M21 15l-5-5L5 21"/>
        </svg>
        <p>Arrastra imagen aquí<br>
        o <label for="oc-file-input" class="oc-link">selecciona archivo</label><br>
        o <strong>Ctrl+V</strong> para pegar</p>
        <input type="file" id="oc-file-input" accept="image/*" style="display:none">
      </div>

      <div id="oc-vision-preview" style="display:none">
        <img id="oc-vision-img" alt="preview">
        <div class="oc-vision-actions">
          <input id="oc-vision-question" type="text"
            placeholder="¿Qué quieres saber? (deja vacío = descripción completa)">
          <div class="oc-vision-mode-row">
            <label class="oc-vision-mode-label">
              <input type="radio" name="oc-vision-mode" value="describe" checked>
              <span>📝 Describir imagen</span>
            </label>
            <label class="oc-vision-mode-label">
              <input type="radio" name="oc-vision-mode" value="code">
              <span>💻 Analizar código/error</span>
            </label>
            <label class="oc-vision-mode-label">
              <input type="radio" name="oc-vision-mode" value="data">
              <span>📊 Extraer datos</span>
            </label>
          </div>
          <button id="oc-vision-send" class="oc-btn-primary">
            <span id="oc-vision-btn-text">👁 Analizar e inyectar en chat →</span>
          </button>
        </div>
      </div>

      <div id="oc-vision-loading" style="display:none">
        <div class="oc-spinner"></div>
        <span id="oc-vision-loading-text">Analizando imagen con visión AI...</span>
      </div>

      <div id="oc-vision-result" style="display:none">
        <div class="oc-vision-result-header">
          <span>✅ Descripción generada</span>
          <span id="oc-vision-model-badge"></span>
        </div>
        <textarea id="oc-vision-result-text" readonly></textarea>
        <div class="oc-vision-result-actions">
          <button id="oc-vision-inject-btn" class="oc-btn-primary">💬 Insertar en chat</button>
          <button id="oc-vision-copy-btn" class="oc-btn-secondary">📋 Copiar</button>
          <button id="oc-vision-retry-btn" class="oc-btn-ghost">🔄 Nueva imagen</button>
        </div>
      </div>

      <div id="oc-vision-status"></div>
    `;
    document.body.appendChild(panel);
    setupVisionEvents(panel);
  }

  let currentBase64 = null;
  let currentMime   = "image/jpeg";
  let lastDescription = "";

  function togglePanel() {
    const p = document.getElementById("oc-vision-panel");
    p.classList.toggle("open");
  }

  function showStatus(msg, color = "#8b5cf6") {
    const el = document.getElementById("oc-status-text");
    if (el) { el.textContent = msg; el.style.color = color; }
    setTimeout(() => { if (el) { el.textContent = "listo"; el.style.color = ""; } }, 5000);
  }

  function setupVisionEvents(panel) {
    document.getElementById("oc-vision-close").onclick = () => panel.classList.remove("open");

    const drop    = document.getElementById("oc-vision-drop");
    const fileIn  = document.getElementById("oc-file-input");
    const preview = document.getElementById("oc-vision-preview");
    const img     = document.getElementById("oc-vision-img");
    const loading = document.getElementById("oc-vision-loading");
    const result  = document.getElementById("oc-vision-result");
    const status  = document.getElementById("oc-vision-status");

    function resetToUpload() {
      preview.style.display = "none";
      result.style.display  = "none";
      loading.style.display = "none";
      drop.style.display    = "flex";
      currentBase64 = null;
      fileIn.value  = "";
    }

    function loadImage(file) {
      if (!file || !file.type.startsWith("image/")) return;
      currentMime = file.type;
      const reader = new FileReader();
      reader.onload = e => {
        currentBase64 = e.target.result;
        img.src = currentBase64;
        drop.style.display    = "none";
        result.style.display  = "none";
        loading.style.display = "none";
        preview.style.display = "block";
        status.textContent = `✅ ${file.name} (${(file.size/1024).toFixed(1)}KB) lista`;
      };
      reader.readAsDataURL(file);
    }

    // Drag & drop
    drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("drag-over"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("drag-over"));
    drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("drag-over"); loadImage(e.dataTransfer.files[0]); });
    fileIn.addEventListener("change", () => loadImage(fileIn.files[0]));

    // Paste global (Ctrl+V)
    document.addEventListener("paste", e => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith("image/")) {
          e.preventDefault();
          const file = item.getAsFile();
          if (file) {
            if (!panel.classList.contains("open")) panel.classList.add("open");
            loadImage(file);
            return;
          }
        }
      }
    });

    // Botón Analizar
    document.getElementById("oc-vision-send").onclick = async () => {
      if (!currentBase64) return;

      const modeEl   = document.querySelector('input[name="oc-vision-mode"]:checked');
      const mode     = modeEl?.value || "describe";
      const userQ    = document.getElementById("oc-vision-question").value.trim();

      const questions = {
        describe: userQ || "Describe esta imagen en detalle completo en español. Incluye todo lo que ves: objetos, personas, texto, colores, disposición, cualquier detalle relevante.",
        code:     userQ || "Analiza este código o error en español. Identifica: lenguaje, qué hace el código, si hay errores explica cuáles son y cómo corregirlos, qué mejoras se pueden hacer.",
        data:     userQ || "Extrae y estructura todos los datos de esta imagen en español. Si hay tablas, convierte a formato estructurado. Si hay gráficos, describe los valores y tendencias. Si hay texto, transcríbelo todo."
      };

      const question = questions[mode];

      // Mostrar loading
      preview.style.display = "none";
      loading.style.display = "flex";
      document.getElementById("oc-vision-loading-text").textContent =
        mode === "code"   ? "🔍 Analizando código/error..." :
        mode === "data"   ? "📊 Extrayendo datos..." :
                           "👁 Describiendo imagen...";

      try {
        const base64 = currentBase64.includes(",") ? currentBase64.split(",")[1] : currentBase64;
        const response = await fetch("/__vision", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image: base64, mime: currentMime, question })
        });

        const data = await response.json();

        if (data.error) {
          loading.style.display = "none";
          preview.style.display = "block";
          status.textContent = `❌ ${data.error}. ${data.hint || ""}`;
          status.style.color = "#ef4444";
          return;
        }

        lastDescription = data.description;
        loading.style.display = "none";
        result.style.display  = "block";
        document.getElementById("oc-vision-result-text").value = data.description;
        document.getElementById("oc-vision-model-badge").textContent = data.model || "visión AI";
        status.textContent = "✅ Descripción lista — insértala en el chat";
        status.style.color = "#10b981";

      } catch(e) {
        loading.style.display = "none";
        preview.style.display = "block";
        status.textContent = `❌ Error: ${e.message}`;
        status.style.color = "#ef4444";
      }
    };

    // Inyectar descripción en el chat
    document.getElementById("oc-vision-inject-btn").onclick = () => {
      if (!lastDescription) return;
      injectTextToChat(lastDescription);
      panel.classList.remove("open");
      showStatus("👁 Descripción de imagen inyectada en el chat", "#10b981");
      setTimeout(resetToUpload, 500);
    };

    // Copiar al portapapeles
    document.getElementById("oc-vision-copy-btn").onclick = async () => {
      try {
        await navigator.clipboard.writeText(lastDescription);
        document.getElementById("oc-vision-copy-btn").textContent = "✅ Copiado";
        setTimeout(() => { document.getElementById("oc-vision-copy-btn").textContent = "📋 Copiar"; }, 2000);
      } catch {}
    };

    // Reintentar con otra imagen
    document.getElementById("oc-vision-retry-btn").onclick = resetToUpload;
  }

  // ── Inyectar texto en el input del chat de OpenCode ────────
  function injectTextToChat(text) {
    // Intentar varios selectores de OpenCode
    const selectors = [
      'textarea[placeholder]',
      'div[contenteditable="true"]',
      'textarea',
      'input[type="text"]:not(#oc-vision-question)',
    ];

    let input = null;
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el.id !== "oc-vision-question") { input = el; break; }
    }

    const prefix = "\n\n[ANÁLISIS DE IMAGEN]:\n";
    const fullText = prefix + text + "\n\n[FIN DE IMAGEN]\n\n";

    if (input) {
      input.focus();
      if (input.tagName === "TEXTAREA" || input.type === "text") {
        // Usar setter nativo para disparar eventos React
        const nativeSetter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set
                          || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
        if (nativeSetter) {
          nativeSetter.call(input, (input.value || "") + fullText);
          input.dispatchEvent(new Event("input", { bubbles: true }));
          input.dispatchEvent(new Event("change", { bubbles: true }));
        } else {
          input.value += fullText;
        }
        // Mover cursor al final
        input.selectionStart = input.selectionEnd = input.value.length;
      } else if (input.contentEditable === "true") {
        input.textContent += fullText;
        input.dispatchEvent(new InputEvent("input", { bubbles: true, data: fullText }));
      }
      // Scroll al final del textarea
      input.scrollTop = input.scrollHeight;
    } else {
      // Fallback: copiar al portapapeles
      navigator.clipboard?.writeText(fullText).then(() => {
        showStatus("📋 Descripción copiada al portapapeles (pega con Ctrl+V)", "#f59e0b");
      });
    }
  }


  // ── 7. Navegador Interno Integrado ───────────────────────
  function initInternalBrowser() {
    const panel = document.createElement("div");
    panel.id = "oc-internal-browser-panel";
    panel.innerHTML = `
      <div class="oc-ib-header">
        <div class="oc-ib-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="3" y1="9" x2="21" y2="9"></line>
            <line x1="9" y1="21" x2="9" y2="9"></line>
          </svg>
          Navegador
        </div>
        <div class="oc-ib-url" id="oc-ib-url-display">about:blank</div>
        <div class="oc-ib-actions">
          <button class="oc-ib-btn" id="oc-ib-btn-refresh" title="Recargar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 102.6-6.4L2 8"/></svg>
          </button>
          <button class="oc-ib-btn" id="oc-ib-btn-external" title="Abrir en pestaña externa">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          </button>
          <button class="oc-ib-btn" id="oc-ib-btn-close" title="Cerrar panel">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
      </div>
      <iframe id="oc-internal-iframe" src="about:blank" sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-modals"></iframe>
    `;
    document.body.appendChild(panel);

    const iframe = document.getElementById("oc-internal-iframe");
    const urlDisplay = document.getElementById("oc-ib-url-display");
    const btnClose = document.getElementById("oc-ib-btn-close");
    const btnRefresh = document.getElementById("oc-ib-btn-refresh");
    const btnExternal = document.getElementById("oc-ib-btn-external");

    btnClose.addEventListener("click", () => {
      panel.classList.remove("open");
      iframe.src = "about:blank";
    });

    btnRefresh.addEventListener("click", () => {
      const currentSrc = iframe.src;
      iframe.src = "about:blank";
      setTimeout(() => { iframe.src = currentSrc; }, 50);
    });

    btnExternal.addEventListener("click", () => {
      if (iframe.src && iframe.src !== "about:blank") {
        window.open(iframe.src, "_blank");
      }
    });

    // 2. Conectar por SSE al proxy para recibir comandos
    const sse = new EventSource("/api/ui-events");

    function openUrlInIframe(url) {
      if (!url) return;
      let targetUrl = url;
      if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://") && !targetUrl.startsWith("/")) {
        targetUrl = "https://" + targetUrl;
      }
      urlDisplay.textContent = targetUrl;
      iframe.src = targetUrl;
      panel.classList.add("open");
    }

    sse.onmessage = (e) => {
      try {
        if (e.event === "open_url" || e.data) {
          const data = JSON.parse(e.data);
          openUrlInIframe(data.url);
        }
      } catch (err) {
        console.error("Error parseando evento SSE:", err);
      }
    };
    sse.addEventListener("open_url", (e) => {
      try {
        const data = JSON.parse(e.data);
        openUrlInIframe(data.url);
      } catch (err) {}
    });
  }

  // Inicializar todo
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      injectHeader();
      injectVisionButton();
      initInternalBrowser();
    });
  } else {
    injectHeader();
    injectVisionButton();
    initInternalBrowser();
  }

})();
