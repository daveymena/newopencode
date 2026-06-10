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
   - **Cómo hacerlo**: Si el usuario te pide "abre una página", "pon una canción en YouTube" o "abre un programa", ¡NO DIGAS QUE NO PUEDES! Eres capaz de abrir el navegador gráfico nativo del usuario ejecutando en bash: `cmd.exe /c start "URL_AQUI"`. 
   - **Ejemplos prácticos**:
     - Para abrir YouTube y buscar una canción: `cmd.exe /c start "https://www.youtube.com/results?search_query=tercer+cielo"`
     - Para abrir el explorador de archivos: `explorer.exe .`
     - Para interactuar con Windows, puedes ejecutar `powershell.exe -Command "..."`
   - **Tu rol**: Nunca te niegues a abrir cosas o controlar la PC. Cuando se te pida abrir algo visual, simplemente usa `cmd.exe /c start` para invocarlo en el sistema Windows anfitrión y confírmale al usuario que lo has ejecutado.
