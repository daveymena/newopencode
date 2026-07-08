@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title OpenCode Evolved - Windows

echo.
echo ============================================================
echo   OpenCode Evolved - MODO WINDOWS
echo ============================================================
echo.

:: ---- Directorio base
set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"
set "OC_EXE=%BASE_DIR%\bin\opencode.exe"
set "PROXY_JS=%BASE_DIR%\artifacts\opencode-ui\proxy.mjs"
set "OPERATOR_JS=%BASE_DIR%\web-operator\api-server.js"

:: ---- Puertos
set OPENCODE_PORT=21294
set OPERATOR_PORT=3001
set PROXY_PORT=21293

:: ---- Cargar .env
echo   Cargando configuracion...
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%BASE_DIR%\.env") do (
    if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
)

echo   OpenCode Engine  --^> :%OPENCODE_PORT%
echo   Web Operator     --^> :%OPERATOR_PORT%
echo   Proxy / Web UI   --^> :%PROXY_PORT%
echo.

:: ---- Limpiar procesos anteriores
echo   Limpiando procesos anteriores...
taskkill /f /im opencode.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr /c:":%OPENCODE_PORT% "') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr /c:":%OPERATOR_PORT% "') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr /c:":%PROXY_PORT% "') do taskkill /f /pid %%a >nul 2>&1
ping 127.0.0.1 -n 2 >nul

:: ---- 1. OpenCode Engine
echo [1/3] Iniciando OpenCode Engine...
start /b "" "%OC_EXE%" serve --port %OPENCODE_PORT% --hostname 0.0.0.0
echo   Esperando OpenCode...
ping 127.0.0.1 -n 6 >nul
echo   OK

:: ---- 2. Web Operator
echo [2/3] Iniciando Web Operator...
set PUPPETEER_SKIP_DOWNLOAD=1
set PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=1
start /b "" node "%OPERATOR_JS%"
ping 127.0.0.1 -n 3 >nul
echo   OK

:: ---- 3. Proxy
echo [3/3] Iniciando Proxy...
set PORT=%PROXY_PORT%
set OPENCODE_INTERNAL_PORT=%OPENCODE_PORT%
set OPERATOR_PORT=%OPERATOR_PORT%
set API_SERVER_PORT=%OPERATOR_PORT%
start /b "" node "%PROXY_JS%"
ping 127.0.0.1 -n 3 >nul
echo   OK

:: ---- Abrir navegador
echo.
start "" "http://localhost:%PROXY_PORT%"

echo.
echo ============================================================
echo   TODO LISTO
echo ============================================================
echo.
echo   Web UI:      http://localhost:%PROXY_PORT%
echo   Operator:    http://localhost:%OPERATOR_PORT%
echo   OpenCode:    http://localhost:%OPENCODE_PORT%
echo.
echo   Modelos: 10 (6 gratis + 4 Freemodel $300)
echo   Operator: Login, CAPTCHA, memoria, multi-task
echo.
echo   Minimiza esta ventana. Para detener, cierrala.
echo ============================================================

:: ---- Watchdog
:watchdog
ping 127.0.0.1 -n 15 >nul
curl -s -o nul "http://127.0.0.1:%OPENCODE_PORT%/" 2>nul
if errorlevel 1 (
    echo   [WATCHDOG] Reiniciando OpenCode...
    start /b "" "%OC_EXE%" serve --port %OPENCODE_PORT% --hostname 0.0.0.0
    ping 127.0.0.1 -n 5 >nul
)
goto watchdog
