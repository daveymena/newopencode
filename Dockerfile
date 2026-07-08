FROM node:22-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Bogota
ENV NODE_ENV=production
ENV DISPLAY=:99
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# ── Sistema: Chrome libs + Xvfb + VNC + noVNC ────────────────────────────────
RUN apt-get update && apt-get install -y \
    ca-certificates curl wget \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libgbm1 libasound2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libpango-1.0-0 libcairo2 libx11-6 libx11-xcb1 \
    libxcb1 libxext6 libxss1 libxtst6 libxcb-dri3-0 fonts-liberation \
    xvfb x11vnc novnc websockify \
    procps netcat-openbsd tzdata \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Copiar TODO el código ────────────────────────────────────────────────────
COPY . .

# ── Reemplazar package.json raíz con versión mínima (sin workspace ni preinstall) ─
RUN echo '{"name":"app","private":true}' > /app/package.json && \
    rm -f /app/pnpm-workspace.yaml /app/pnpm-lock.yaml /app/bun.lock

# ── Instalar OpenCode Engine (global) ────────────────────────────────────────
RUN npm install -g opencode-ai --ignore-scripts 2>/dev/null || true
RUN cd /usr/lib/node_modules/opencode-ai 2>/dev/null && node postinstall.mjs 2>/dev/null || \
    cd /usr/local/lib/node_modules/opencode-ai 2>/dev/null && node postinstall.mjs 2>/dev/null || true

# ── Instalar deps de web-operator ────────────────────────────────────────────
RUN cd /app/web-operator && npm install
# ── Asegurar que playwright esté accesible localmente ───────────────────────
RUN cd /app/web-operator && npm install playwright --no-save

# ── Instalar deps de proxy + frontend ────────────────────────────────────────
RUN cd /app/artifacts/opencode-ui && npm install

# ── Verificar dependencias críticas ──────────────────────────────────────────
RUN ls /app/web-operator/node_modules/express/index.js 2>/dev/null && echo "✓ express OK" || echo "✗ express MISSING"
RUN ls /app/web-operator/node_modules/playwright/index.mjs 2>/dev/null && echo "✓ playwright OK" || echo "✗ playwright MISSING"
RUN ls /app/artifacts/opencode-ui/node_modules/express/index.js 2>/dev/null && echo "✓ proxy-express OK" || echo "✗ proxy-express MISSING"

# ── Frontend UI (standalone, sin compilación) ────────────────────────────────
RUN mkdir -p /app/ui && cp /app/artifacts/opencode-ui/ui/index.html /app/ui/index.html && \
    echo "✓ Frontend standalone copiado a /app/ui/"

# ── Intentar compilar React como mejora (opcional) ───────────────────────────
RUN cd /app/artifacts/opencode-ui && npx --yes vite build 2>&1 | tail -5 || true
RUN if [ -f "/app/artifacts/opencode-ui/dist/public/index.html" ]; then \
    cp -r /app/artifacts/opencode-ui/dist/public/* /app/ui/ && \
    echo "✓ Frontend React compilado REEMPLAZANDO standalone en /app/ui/"; else \
    echo "ℹ Usando frontend standalone (React no compiló)"; fi

# ── Instalar Playwright Chromium ─────────────────────────────────────────────
RUN npx playwright install chromium --with-deps 2>/dev/null || true

# ── Scripts y permisos ───────────────────────────────────────────────────────
RUN if [ -f /app/scripts/reset-opencode.sh ]; then \
    cp /app/scripts/reset-opencode.sh /usr/local/bin/reset-opencode && \
    chmod +x /usr/local/bin/reset-opencode; fi

RUN chmod +x /app/docker-start.sh

EXPOSE 80 21293 3001 21294 6080

VOLUME ["/app/.chrome-session", "/app/web-operator/.site-memory", "/root/.config/opencode"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:21293/health || exit 1

CMD ["/app/docker-start.sh"]
