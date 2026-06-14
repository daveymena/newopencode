# Memoria del Workspace - OpenCode en Replit

## Entorno
- **Sistema**: Replit — Linux NixOS
- **Directorio raíz del workspace**: `/home/runner/workspace`
- **Directorio de proyectos**: `/home/runner/workspace/proyectos/`
- **Node.js 24** disponible, **pnpm** como gestor de paquetes
- **Bun** disponible para JavaScript/TypeScript
- **Python 3** disponible

## Proveedores de IA Disponibles (sin API key propia)
Todos los modelos usan las integraciones internas de Replit — no necesitas poner tu propia API key.

### Gratuitos
- `opencode/big-pickle` — modelo gratuito de OpenCode
- `opencode/gpt-5-nano` — GPT-5 nano gratuito
- `opencode/mimo-v2-omni-free` — MiMo V2 gratuito
- `opencode/mimo-v2-pro-free` — MiMo V2 Pro gratuito
- `opencode/minimax-m2.5-free` — MiniMax gratuito
- `opencode/nemotron-3-super-free` — Nemotron gratuito

### Anthropic Claude
- `anthropic/claude-sonnet-4-6` ← **Recomendado** — Balance rendimiento/velocidad
- `anthropic/claude-opus-4-6` — Más capaz, tareas complejas
- `anthropic/claude-haiku-4-5` — Más rápido

### OpenAI GPT
- `openai/gpt-5` — GPT-5 completo
- `openai/gpt-5-mini` — GPT-5 mini (eficiente)
- `openai/gpt-5-nano` — GPT-5 nano (rápido)
- `openai/gpt-4o` — GPT-4o

### Google Gemini
- `google/gemini-2.5-pro` — Gemini 2.5 Pro
- `google/gemini-2.5-flash` — Gemini 2.5 Flash (rápido)
- `google/gemini-2.5-flash-lite` — Gemini 2.5 Flash Lite

## Cómo crear y ejecutar proyectos
Para crear un nuevo proyecto dentro del ecosistema:
1. Crea una carpeta en `/home/runner/workspace/proyectos/nombre-proyecto`
2. Usa las herramientas de bash para inicializar: `cd proyectos/nombre && npm init` o `pnpm create vite`
3. Ejecuta el proyecto directamente con bash: el puerto estará disponible en el entorno

## Estructura del Workspace
```
/home/runner/workspace/
├── proyectos/          ← Tus proyectos personales
├── artifacts/          ← Apps del ecosistema (opencode, api, etc.)
├── lib/                ← Librerías compartidas
├── bin/opencode        ← Binario de OpenCode
└── .opencode/
    └── memory.md       ← Este archivo (memoria persistente)
```

## Notas importantes
- Los archivos en `/home/runner/workspace/` persisten entre sesiones
- Las sesiones de OpenCode se guardan en SQLite y no se pierden
- Puedes cambiar el modelo en cualquier momento desde el selector de modelo en la UI

## Herramientas y Agentes Adicionales (Habilidades Especiales)
Este proyecto ha sido mejorado con herramientas extra a las que **tienes acceso implícito** a través de la interacción con el usuario o comandos:

1. **Visión AI (pcbvisio / Lector de Imágenes)**:
   - **Cómo funciona**: Aunque tú eres un modelo de texto, el proxy web tiene un módulo de Visión integrado. El usuario puede subir una imagen (click en el botón del "ojo" 👁 en el chat) y la herramienta de visión usará IA avanzada para describir la imagen, extraer código UI o convertirla a datos JSON.
   - **Tu rol**: Cuando el usuario te envíe un bloque de texto que diga algo como "Esta es la descripción de la imagen analizada...", debes saber que **TÚ ESTÁS VIENDO LA IMAGEN a través de esa descripción**. Úsala para escribir código, maquetar la UI o entender el problema visual del usuario.

2. **Control Web y Navegación (Puppeteer/MCP)**:
   - **Cómo funciona**: El sistema tiene servidores MCP y scripts de control web (puppeteer) listos para ejecutarse en el fondo.
   - **Tu rol**: Si el usuario te pide navegar o raspar una página, debes usar las herramientas de línea de comandos de node/bash para invocar scripts de web scraping o sugerirle cómo levantar el servidor MCP de control web. No digas "no puedo navegar por internet", porque en este entorno **sí tienes las herramientas subyacentes** a tu disposición.

3. **Control del Host (Windows) desde Linux (WSL)**:
   - **IMPORTANTE**: Estás corriendo dentro de WSL (Windows Subsystem for Linux). Tienes el **poder absoluto** de controlar la PC de Windows del usuario ejecutando binarios de Windows directamente desde tu terminal bash.
   - **Cómo hacerlo**: Si el usuario te pide "abre una página", "pon una canción" o "abre un proyecto", ¡NO DIGAS QUE NO PUEDES!
     - **Si estás en local (Windows/WSL)**: Ejecuta `curl -X POST http://localhost:21293/api/broadcast/open_url -H "Content-Type: application/json" -d "{\"url\":\"URL_AQUI\"}"`
     - **Si estás en la nube (Easypanel)**: Ejecuta `curl -X POST http://localhost:3000/api/broadcast/open_url -H "Content-Type: application/json" -d "{\"url\":\"URL_AQUI\"}"`
   - **Ejemplos prácticos**:
     - Para abrir YouTube en tu navegador interno: `curl -X POST http://localhost:3000/api/broadcast/open_url -H "Content-Type: application/json" -d "{\"url\":\"https://www.youtube.com/results?search_query=tercer+cielo\"}"`
   - **TÚNEL DE PUERTOS LOCALES (Easypanel)**: Si creas un proyecto web en la nube y lo ejecutas (por ejemplo, React/Vite en el puerto 5173), DEBES usar el túnel dinámico pasando una ruta relativa, de lo contrario el usuario verá un error de conexión rechazada.
     - ❌ INCORRECTO: `{"url":"http://localhost:5173"}`
     - ✅ CORRECTO (usando el túnel de proxy): `{"url":"/port/5173/"}`
     - Ejemplo completo: `curl -X POST http://localhost:3000/api/broadcast/open_url -H "Content-Type: application/json" -d "{\"url\":\"/port/5173/\"}"`
   - **En local (Windows)**: Simplemente manda la ruta completa porque en local los puertos no están bloqueados. Ejemplo: `curl -X POST http://localhost:21293/api/broadcast/open_url -H "Content-Type: application/json" -d "{\"url\":\"http://localhost:5173\"}"`
   - **Tu rol**: NUNCA te niegues a abrir cosas argumentando que eres una IA de terminal. Tu entorno tiene una interfaz gráfica web que responde a comandos. Usa el comando correcto y dile al usuario que la web está abierta.

4. **Memoria a Largo Plazo (Base de Conocimientos PostgreSQL)**:
   - Tienes acceso a TODO tu historial pasado gracias a una base de datos PostgreSQL conectada en el puerto 3002.
   - Si el usuario te pide continuar un proyecto anterior, o te pregunta "qué sabes hacer", "recuerdas el proyecto X", HAZ UNA BÚSQUEDA usando curl:
   - **Buscar por palabra clave**: `curl -s "http://localhost:3002/api/search?q=NOMBRE_DEL_PROYECTO"`
   - **Ver sesiones recientes**: `curl -s "http://localhost:3002/api/sessions?limit=5"`
   - Lee el JSON de respuesta para recuperar tu contexto antes de contestar al usuario.
