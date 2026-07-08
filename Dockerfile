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

# ── Instalar pnpm (necesario para el workspace con catalog:) ─────────────────
RUN npm install -g pnpm

# ── Instalar Chromium via Playwright ──────────────────────────────────────────
RUN npx -y playwright install chromium --with-deps 2>/dev/null || true

# ── Directorio de trabajo ──────────────────────────────────────────────────────
WORKDIR /app

# ── Copiar config del workspace (para resolver catalog: y workspace:*) ─────────
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml /app/

# ── Copiar todos los package.json del workspace ────────────────────────────────
COPY artifacts/opencode-ui/package.json /app/artifacts/opencode-ui/
COPY artifacts/api-server/package.json /app/artifacts/api-server/
COPY artifacts/mockup-sandbox/package.json /app/artifacts/mockup-sandbox/
COPY lib/api-client-react/package.json /app/lib/api-client-react/
COPY lib/api-spec/package.json /app/lib/api-spec/
COPY lib/api-zod/package.json /app/lib/api-zod/
COPY lib/db/package.json /app/lib/db/
COPY lib/integrations-anthropic-ai/package.json /app/lib/integrations-anthropic-ai/
COPY scripts/package.json /app/scripts/
COPY web-operator/package.json /app/web-operator/

# ── Instalar dependencias de produccion con pnpm ───────────────────────────────
RUN pnpm install --no-frozen-lockfile --prod --ignore-scripts

# ── Copiar resto del proyecto ──────────────────────────────────────────────────
COPY . .

# ── web-operator no esta en el workspace, instalar aparte ──────────────────────
RUN cd /app/web-operator && npm install --omit=dev

# ── Script de reset de tokens (por si se necesita dentro del contenedor) ───────
COPY scripts/reset-opencode.sh /usr/local/bin/reset-opencode
RUN chmod +x /usr/local/bin/reset-opencode

# ── Script de inicio (Xvfb + noVNC + servicios) ───────────────────────────────
COPY docker-start.sh /app/docker-start.sh
RUN chmod +x /app/docker-start.sh

# ── Puertos: Web UI, Web Operator, OpenCode Engine, noVNC (pantalla remota) ───
EXPOSE 21293 3001 21294 6080

# ── Volumenes persistentes ──────────────────────────────────────────────────────
VOLUME ["/app/.chrome-session", "/app/web-operator/.site-memory", "/root/.config/opencode"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -sf http://localhost:21293/api/health || exit 1

CMD ["/app/docker-start.sh"]
