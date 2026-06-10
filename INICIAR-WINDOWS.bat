@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title OpenCode - Modo Windows Nativo

echo.
echo ============================================================
echo   ^^✦ OpenCode Evolved - MODO WINDOWS NATIVO
echo ============================================================
echo.

:: ---- Directorio base del proyecto
set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"
set "OC_EXE=%BASE_DIR%\bin\opencode.exe"
set "PROXY_JS=%BASE_DIR%\artifacts\opencode-ui\proxy.mjs"

:: ---- Puertos
set OPENCODE_PORT=21294
set PROXY_PORT=21293

:: ---- Cargar variables de .env
echo   Cargando configuracion...
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%BASE_DIR%\.env") do (
    if not "%%A"=="" if not "%%B"=="" (
        set "%%A=%%B"
    )
)

echo   Motor OpenCode  --^> puerto %OPENCODE_PORT% (interno)
echo   Shell / Proxy   --^> puerto %PROXY_PORT% (web)
echo   Workspace       --^> %BASE_DIR%
echo.

:: ---- Limpiar procesos anteriores
echo   Limpiando sesiones anteriores...
taskkill /f /im opencode.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr /c:":%OPENCODE_PORT% "') do (
    if not "%%a"=="0" taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr /c:":%PROXY_PORT% "') do (
    if not "%%a"=="0" taskkill /f /pid %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

:: ---- Iniciar OpenCode nativo de Windows (en background)
echo   Iniciando OpenCode (Windows nativo)...
start /b "" "%OC_EXE%" serve --port %OPENCODE_PORT% --hostname 0.0.0.0

:: ---- Esperar que OpenCode levante (hasta 30s)
echo   Esperando que OpenCode arranque...
set /a attempts=0
:wait_opencode
timeout /t 2 /nobreak >nul
set /a attempts+=1
curl -s -o nul -w "%%{http_code}" "http://localhost:%OPENCODE_PORT%/health" 2>nul | findstr /c:"200" >nul 2>&1
if not errorlevel 1 goto opencode_ready
if !attempts! lss 15 goto wait_opencode
echo.
echo   [ERROR] OpenCode no pudo arrancar en 30 segundos.
echo   Verifica que bin\opencode.exe este disponible.
pause
exit /b 1

:opencode_ready
echo   ✓ OpenCode listo en %attempts% x 2s
echo.

:: ---- Instalar dependencias del proxy si faltan
if not exist "%BASE_DIR%\artifacts\opencode-ui\node_modules" (
    echo   Instalando dependencias del proxy ^(primera vez^)...
    pushd "%BASE_DIR%\artifacts\opencode-ui"
    npm install --silent
    popd
    echo   ✓ Dependencias instaladas
)

:: ---- Iniciar Proxy Web (Node.js nativo de Windows)
echo   Iniciando proxy web...
set PORT=%PROXY_PORT%
set OPENCODE_INTERNAL_PORT=%OPENCODE_PORT%
start /b "" node "%PROXY_JS%"
timeout /t 3 /nobreak >nul
echo   ✓ Proxy listo
echo.

:: ---- Abrir navegador automaticamente
echo   Abriendo interfaz en el navegador...
start "" "http://localhost:%PROXY_PORT%"

echo.
echo ============================================================
echo   ^^✦ LISTO - OpenCode corriendo en: http://localhost:%PROXY_PORT%
echo ============================================================
echo.
echo   La IA ahora puede:
echo   ✓ Abrir tu navegador con: start https://...
echo   ✓ Ejecutar PowerShell nativamente
echo   ✓ Controlar archivos en C:\ directamente
echo   ✓ Abrir programas .exe sin restricciones
echo.
echo   Esta ventana mantiene vivos los servicios.
echo   Minimizala. Para detener, cierra esta ventana.
echo ============================================================
echo.

:: ---- Bucle de vigilancia (reinicia si OpenCode muere)
:watchdog
timeout /t 15 /nobreak >nul
curl -s -o nul -w "%%{http_code}" "http://localhost:%OPENCODE_PORT%/health" 2>nul | findstr /c:"200" >nul 2>&1
if errorlevel 1 (
    echo   [WATCHDOG] OpenCode se detuvo. Reiniciando...
    start /b "" "%OC_EXE%" serve --port %OPENCODE_PORT% --hostname 0.0.0.0
    timeout /t 5 /nobreak >nul
    echo   [WATCHDOG] OpenCode reiniciado.
)
goto watchdog
