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

# ── Instalar pnpm (requerido por el workspace) ───────────────────────────────
RUN corepack enable && corepack prepare pnpm@latest --activate

# ── Instalar OpenCode Engine via npm ──────────────────────────────────────────
RUN npm install -g opencode-ai@latest 2>/dev/null || \
    npm install -g opencode-ai || true
# ── Correr postinstall de opencode-ai (descarga binario) ─────────────────────
RUN cd /usr/lib/node_modules/opencode-ai && node postinstall.mjs 2>/dev/null || \
    cd /usr/local/lib/node_modules/opencode-ai && node postinstall.mjs 2>/dev/null || true

WORKDIR /app

# ── Copiar archivos de dependencias primero para mejor caché ──────────────────
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY artifacts/opencode-ui/package.json ./artifacts/opencode-ui/
COPY web-operator/package.json ./web-operator/

# ── Instalar dependencias con pnpm (respeta workspaces) ─────────────────────
RUN pnpm install --frozen-lockfile || pnpm install

# ── Instalar deps de web-operator con npm (si pnpm no los resolvió) ──────────
RUN cd /app/web-operator && npm install --omit=dev 2>/dev/null || true

# ── Copiar TODO el código ────────────────────────────────────────────────────
COPY . .

# ── Copiar UI pre-compilada si existe (sino proxy usa fallback de OpenCode) ──
RUN if [ -d "/app/artifacts/opencode-ui/dist/public" ]; then \
    mkdir -p /app/ui && cp -r /app/artifacts/opencode-ui/dist/public/* /app/ui/; fi

# ── Instalar Playwright Chromium DESPUÉS de instalar playwright via pnpm ──────
RUN cd /app/web-operator && pnpm exec playwright install chromium --with-deps 2>/dev/null || true

# ── Script de reset ────────────────────────────────────────────────────────────
RUN if [ -f /app/scripts/reset-opencode.sh ]; then \
    cp /app/scripts/reset-opencode.sh /usr/local/bin/reset-opencode && \
    chmod +x /usr/local/bin/reset-opencode; fi

RUN chmod +x /app/docker-start.sh

EXPOSE 21293 3001 21294 6080

VOLUME ["/app/.chrome-session", "/app/web-operator/.site-memory", "/root/.config/opencode"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:21293/api/health || exit 1

CMD ["/app/docker-start.sh"]
