FROM node:22-slim

# ── Variables de entorno base ──────────────────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Bogota
ENV NODE_ENV=production
ENV DISPLAY=:99
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

# ── Dependencias del sistema (Chrome, Xvfb, VNC, noVNC) ───────────────────────
RUN apt-get update && apt-get install -y \
    # Chrome / Chromium deps
    ca-certificates curl gnupg wget \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libgbm1 libasound2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libpango-1.0-0 libcairo2 libx11-6 libx11-xcb1 \
    libxcb1 libxext6 libxss1 libxtst6 libxcb-dri3-0 fonts-liberation \
    fonts-ipafont-gothic fonts-wqy-zenhei \
    # Xvfb (pantalla virtual) + x11vnc + noVNC
    xvfb x11vnc novnc websockify \
    # Utilidades
    procps netcat-openbsd tzdata \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# ── Instalar Chromium via Playwright ──────────────────────────────────────────
RUN npx -y playwright install chromium --with-deps 2>/dev/null || true

# ── Directorio de trabajo ──────────────────────────────────────────────────────
WORKDIR /app

# ── Instalar dependencias Node (proxy + web-operator) ─────────────────────────
COPY artifacts/opencode-ui/package.json /app/artifacts/opencode-ui/
RUN cd /app/artifacts/opencode-ui && npm install --omit=dev

COPY web-operator/package.json /app/web-operator/
RUN cd /app/web-operator && npm install --omit=dev

# ── Copiar resto del proyecto ──────────────────────────────────────────────────
COPY . .

# ── Script de reset de tokens (por si se necesita dentro del contenedor) ───────
COPY scripts/reset-opencode.sh /usr/local/bin/reset-opencode
RUN chmod +x /usr/local/bin/reset-opencode

# ── Script de inicio (Xvfb + noVNC + servicios) ───────────────────────────────
COPY docker-start.sh /app/docker-start.sh
RUN chmod +x /app/docker-start.sh

# ── Puertos: Web UI, Web Operator, OpenCode Engine, noVNC (pantalla remota) ───
EXPOSE 21293 3001 21294 6080

# ── Volúmenes persistentes ─────────────────────────────────────────────────────
VOLUME ["/app/.chrome-session", "/app/web-operator/.site-memory", "/root/.config/opencode"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -sf http://localhost:21293/api/health || exit 1

CMD ["/app/docker-start.sh"]
