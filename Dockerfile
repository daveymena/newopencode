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

# ── Instalar OpenCode Engine (global) ────────────────────────────────────────
RUN npm install -g opencode-ai --ignore-scripts 2>/dev/null || true
RUN cd /usr/lib/node_modules/opencode-ai 2>/dev/null && node postinstall.mjs 2>/dev/null || \
    cd /usr/local/lib/node_modules/opencode-ai 2>/dev/null && node postinstall.mjs 2>/dev/null || true

# ── Instalar deps de web-operator (--ignore-scripts evita preinstall del root) ─
RUN cd /app/web-operator && npm install --ignore-scripts 2>/dev/null || true

# ── Instalar deps de proxy (--ignore-scripts evita preinstall del root) ─────
RUN cd /app/artifacts/opencode-ui && npm install --ignore-scripts 2>/dev/null || true

# ── Instalar Playwright Chromium ─────────────────────────────────────────────
RUN npx playwright install chromium --with-deps 2>/dev/null || true

# ── Copiar UI pre-compilada si existe ────────────────────────────────────────
RUN if [ -d "/app/artifacts/opencode-ui/dist/public" ]; then \
    mkdir -p /app/ui && cp -r /app/artifacts/opencode-ui/dist/public/* /app/ui/; fi

# ── Scripts y permisos ───────────────────────────────────────────────────────
RUN if [ -f /app/scripts/reset-opencode.sh ]; then \
    cp /app/scripts/reset-opencode.sh /usr/local/bin/reset-opencode && \
    chmod +x /usr/local/bin/reset-opencode; fi

RUN chmod +x /app/docker-start.sh

EXPOSE 21293 3001 21294 6080

VOLUME ["/app/.chrome-session", "/app/web-operator/.site-memory", "/root/.config/opencode"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:21293/api/health || exit 1

CMD ["/app/docker-start.sh"]
