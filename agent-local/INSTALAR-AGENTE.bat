@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title OpenCode PC Agent - Instalador

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║     OpenCode PC Agent - Instalador Windows           ║
echo ║     Conecta tu PC a OpenCode en EasyPanel            ║
echo ╚══════════════════════════════════════════════════════╝
echo.

set "INSTALL_DIR=%LOCALAPPDATA%\OpenCodeAgent"
set "AGENT_DIR=%~dp0agent-local"
set "STARTUP_KEY=HKCU\Software\Microsoft\Windows\CurrentVersion\Run"

:: ── Verificar Node.js ────────────────────────────────────
echo [1/5] Verificando Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo   Node.js no encontrado. Descargando instalador...
    curl -fsSL "https://nodejs.org/dist/v22.12.0/node-v22.12.0-x64.msi" -o "%TEMP%\node-installer.msi"
    msiexec /i "%TEMP%\node-installer.msi" /quiet /norestart
    echo   ✓ Node.js instalado. Reinicia el instalador.
    pause
    exit /b 0
)
for /f %%v in ('node --version') do echo   ✓ Node.js %%v encontrado

:: ── Crear directorio de instalación ─────────────────────
echo.
echo [2/5] Creando directorio de instalacion...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
copy /y "%AGENT_DIR%\pc-agent.mjs" "%INSTALL_DIR%\pc-agent.mjs" >nul
echo   ✓ Archivos copiados a %INSTALL_DIR%

:: ── Instalar dependencia ws (WebSocket) ─────────────────
echo.
echo [3/5] Instalando dependencias...
cd /d "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\node_modules\ws" (
    npm init -y >nul 2>&1
    npm install ws --save --silent
    echo   ✓ Dependencias instaladas
) else (
    echo   ✓ Dependencias ya instaladas
)

:: ── Pedir URL de EasyPanel ───────────────────────────────
echo.
echo [4/5] Configuracion del servidor...
echo.

:: Leer configuracion existente si la hay
set "EXISTING_URL="
if exist "%USERPROFILE%\.opencode-agent\config.json" (
    for /f "tokens=*" %%a in ('powershell -Command "(Get-Content '%USERPROFILE%\.opencode-agent\config.json' | ConvertFrom-Json).serverUrl"') do set "EXISTING_URL=%%a"
)

if not "!EXISTING_URL!"=="" (
    echo   URL actual: !EXISTING_URL!
    set /p "CONFIRM=¿Usar esta URL? [S/n]: "
    if /i "!CONFIRM!"=="n" goto ask_url
    set "SERVER_URL=!EXISTING_URL!"
    goto save_config
)

:ask_url
echo   Ingresa la URL de tu OpenCode en EasyPanel
echo   Ejemplo: https://opencode.midominio.com
echo.
set /p "SERVER_URL=   URL del servidor: "
if "!SERVER_URL!"=="" (
    echo   [ERROR] La URL no puede estar vacía.
    goto ask_url
)

:save_config
:: Guardar configuración
if not exist "%USERPROFILE%\.opencode-agent" mkdir "%USERPROFILE%\.opencode-agent"
(
  echo {
  echo   "serverUrl": "!SERVER_URL!",
  echo   "agentName": "%COMPUTERNAME%",
  echo   "agentId": null,
  echo   "reconnectDelay": 5000
  echo }
) > "%USERPROFILE%\.opencode-agent\config.json"
echo   ✓ Configuracion guardada

:: ── Crear acceso directo y registro de inicio ────────────
echo.
echo [5/5] Configurando inicio automatico con Windows...

:: Script de inicio del agente
(
  echo @echo off
  echo title OpenCode PC Agent
  echo cd /d "%INSTALL_DIR%"
  echo :loop
  echo node pc-agent.mjs
  echo timeout /t 5 /nobreak ^>nul
  echo goto loop
) > "%INSTALL_DIR%\iniciar-agente.bat"

:: Registrar en inicio de Windows
reg add "%STARTUP_KEY%" /v "OpenCodeAgent" /t REG_SZ /d "\"%INSTALL_DIR%\iniciar-agente.bat\"" /f >nul
echo   ✓ Agente registrado para iniciar con Windows

:: Crear acceso directo en el Escritorio
powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%USERPROFILE%\Desktop\OpenCode Agent.lnk'); $s.TargetPath='%INSTALL_DIR%\iniciar-agente.bat'; $s.WorkingDirectory='%INSTALL_DIR%'; $s.IconLocation='%SystemRoot%\System32\SHELL32.dll,14'; $s.Description='OpenCode PC Agent - Control remoto'; $s.Save()"
echo   ✓ Acceso directo creado en el Escritorio

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║   ✅ INSTALACION COMPLETADA                          ║
echo ╠══════════════════════════════════════════════════════╣
echo ║   Servidor: !SERVER_URL!
echo ║   PC:       %COMPUTERNAME%
echo ╠══════════════════════════════════════════════════════╣
echo ║   El agente se iniciara automaticamente con Windows  ║
echo ║   Estado: http://localhost:21290/status              ║
echo ╚══════════════════════════════════════════════════════╝
echo.

set /p "INICIAR=¿Iniciar el agente ahora? [S/n]: "
if /i not "!INICIAR!"=="n" (
    echo.
    echo   Iniciando agente...
    start "OpenCode Agent" /min "%INSTALL_DIR%\iniciar-agente.bat"
    timeout /t 3 /nobreak >nul
    start "" "http://localhost:21290/status"
)

echo.
echo   El agente se esta ejecutando en segundo plano.
echo   Puedes cerrarlo desde la bandeja del sistema.
pause
