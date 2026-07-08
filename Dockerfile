FROM node:22-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Bogota
ENV NODE_ENV=production
ENV DISPLAY=:99
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

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

# ── Instalar deps del proxy ─────────────────────────────────────────────────
COPY artifacts/opencode-ui/package.json /app/artifacts/opencode-ui/package.json
RUN cd /app/artifacts/opencode-ui && npm install

# ── Instalar deps del web-operator ──────────────────────────────────────────
COPY web-operator/package.json /app/web-operator/package.json
RUN cd /app/web-operator && npm install

# ── Instalar Playwright Chromium (DESPUÉS de instalar playwright) ────────────
RUN cd /app/web-operator && npx playwright install chromium --with-deps 2>/dev/null || true

# ── Copiar TODO el código (node_modules excluidos por .dockerignore) ─────────
COPY . .

# ── Verificar y preparar el binario de OpenCode ─────────────────────────────
# El binario Linux viene en /app/bin/opencode (sin extensión)
RUN ls -la /app/bin/ 2>/dev/null && \
    if [ -f "/app/bin/opencode" ]; then chmod +x /app/bin/opencode; fi && \
    if [ -f "/app/bin/opencode-linux" ]; then chmod +x /app/bin/opencode-linux; fi

# ── Script de reset de tokens ───────────────────────────────────────────────
RUN if [ -f /app/scripts/reset-opencode.sh ]; then \
    cp /app/scripts/reset-opencode.sh /usr/local/bin/reset-opencode && \
    chmod +x /usr/local/bin/reset-opencode; fi

COPY docker-start.sh /app/docker-start.sh
RUN chmod +x /app/docker-start.sh

EXPOSE 21293 3001 21294 6080

VOLUME ["/app/.chrome-session", "/app/web-operator/.site-memory", "/root/.config/opencode"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -sf http://localhost:21293/api/health || exit 1

CMD ["/app/docker-start.sh"]
