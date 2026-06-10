# ============================================================
# OpenCode - Imagen Docker completa
# Soporta: Node.js, Python, Go, Rust, Java, Ruby, PHP,
#          .NET, Deno, Bun, C/C++, Bash y más
# Para EasyPanel / Docker / Servidor local
# ============================================================

FROM ubuntu:24.04

# Evitar prompts interactivos durante la instalación
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# ---- Herramientas base ---- #
RUN apt-get update && apt-get install -y \
    # Herramientas esenciales
    curl wget git unzip zip tar gzip \
    build-essential gcc g++ make cmake \
    # Para SSL/TLS
    ca-certificates gnupg \
    # Útiles
    jq tree htop nano vim less \
    # Para lenguajes
    libssl-dev libffi-dev zlib1g-dev \
    pkg-config libbz2-dev libreadline-dev \
    libsqlite3-dev libncurses5-dev \
    # Para Java
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# NODE.JS 22 (LTS)
# ============================================================
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest \
    && npm install -g pnpm yarn \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# BUN (Runtime JS/TS ultrarrápido - requerido por OpenCode)
# ============================================================
RUN curl -fsSL https://bun.sh/install | bash \
    && cp /root/.bun/bin/bun /usr/local/bin/bun \
    && ln -sf /usr/local/bin/bun /usr/local/bin/bunx

# ============================================================
# PYTHON 3.12 + pip + uv + poetry
# ============================================================
RUN apt-get update && apt-get install -y \
    python3 python3-dev python3-venv python3-pip \
    && pip3 install --no-cache-dir --break-system-packages uv poetry \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# GO 1.23
# ============================================================
RUN curl -fsSL https://go.dev/dl/go1.23.4.linux-amd64.tar.gz -o /tmp/go.tar.gz \
    && tar -C /usr/local -xzf /tmp/go.tar.gz \
    && rm /tmp/go.tar.gz
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOPATH="/root/go"
ENV PATH="${GOPATH}/bin:${PATH}"

# ============================================================
# RUST + CARGO (via rustup)
# ============================================================
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --no-modify-path --profile minimal
ENV PATH="/root/.cargo/bin:${PATH}"

# ============================================================
# JAVA 21 (JDK) + Maven + Gradle
# ============================================================
RUN apt-get update && apt-get install -y \
    openjdk-21-jdk maven \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME="/usr/lib/jvm/java-21-openjdk-amd64"
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Gradle
RUN curl -fsSL https://services.gradle.org/distributions/gradle-8.11.1-bin.zip -o /tmp/gradle.zip \
    && unzip -d /opt /tmp/gradle.zip \
    && mv /opt/gradle-8.11.1 /opt/gradle \
    && rm /tmp/gradle.zip
ENV PATH="/opt/gradle/bin:${PATH}"

# ============================================================
# RUBY 3.3
# ============================================================
RUN apt-get update && apt-get install -y \
    ruby ruby-dev ruby-bundler \
    && gem install rails --no-document \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# PHP 8.3 + Composer
# ============================================================
RUN apt-get update && apt-get install -y \
    php8.3 php8.3-cli php8.3-common \
    php8.3-curl php8.3-mbstring php8.3-xml \
    php8.3-zip php8.3-pgsql php8.3-mysql \
    && rm -rf /var/lib/apt/lists/*
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# ============================================================
# .NET 8 SDK
# ============================================================
RUN curl -fsSL https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb -o /tmp/packages-microsoft-prod.deb \
    && dpkg -i /tmp/packages-microsoft-prod.deb \
    && rm /tmp/packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get install -y dotnet-sdk-8.0 \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# DENO
# ============================================================
RUN curl -fsSL https://deno.land/install.sh | sh \
    && cp /root/.deno/bin/deno /usr/local/bin/deno

# ============================================================
# OPENCODE (binario oficial de SST)
# ============================================================
# Descargar OpenCode CLI oficial
ARG OPENCODE_VERSION=1.17.0
RUN curl -fsSL "https://github.com/anomalyco/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-x64.tar.gz" \
    -o /tmp/opencode.tar.gz \
    && tar -xzf /tmp/opencode.tar.gz -C /tmp \
    && mv /tmp/opencode /usr/local/bin/opencode \
    && chmod +x /usr/local/bin/opencode \
    && rm /tmp/opencode.tar.gz

# ============================================================
# CONFIGURACIÓN DEL WORKSPACE
# ============================================================
WORKDIR /workspace

# Copiar configuración de OpenCode
COPY .config/opencode/ /root/.config/opencode/
COPY .opencode/ /workspace/.opencode/
COPY .env.example /workspace/.env.example

# Crear estructura de directorios
RUN mkdir -p \
    /workspace/proyectos \
    /root/.local/share/opencode \
    /root/.cache/opencode \
    /root/.config/opencode

# Copiar proxy web y servicio de BD
COPY artifacts/opencode-ui/proxy.mjs /app/proxy.mjs
COPY artifacts/opencode-ui/public/ /app/public/
COPY db-sync.mjs /app/db-sync.mjs

# Instalar dependencias del proxy y sync
RUN mkdir -p /app && cd /app && npm init -y && \
    npm install express http-proxy-middleware pg --save

# Copiar script de inicio
COPY docker/start.sh /usr/local/bin/start-opencode.sh
RUN chmod +x /usr/local/bin/start-opencode.sh

# Puertos
EXPOSE 3000

# Variables de entorno por defecto
ENV PORT=3000
ENV OPENCODE_INTERNAL_PORT=3001
ENV SYNC_API_PORT=3002
ENV OPENCODE_WORKSPACE=/workspace
# ← Reemplaza con tu URL interna de EasyPanel al desplegar
ENV DATABASE_URL=postgres://postgres:6715320@tecnology_base-open:5432/davey?sslmode=disable

# Volúmenes para persistencia
VOLUME ["/workspace", "/root/.local/share/opencode"]

CMD ["/usr/local/bin/start-opencode.sh"]
