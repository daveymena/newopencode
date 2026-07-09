@echo off
title OpenCode - Prueba Local
echo.
echo  ========================================
echo   OpenCode - Prueba Local en Windows
echo  ========================================
echo.

:: Verificar Node.js
node -v >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js no esta instalado
    pause
    exit /b
)

:: Instalar dependencias si no existen
echo [1/4] Verificando dependencias del Web Operator...
if not exist "web-operator\node_modules\express" (
    echo     Instalando...
    cd web-operator && npm install && cd ..
) else (
    echo     OK
)

echo [2/4] Verificando dependencias del Proxy...
if not exist "artifacts\opencode-ui\node_modules\express" (
    echo     Instalando...
    cd artifacts\opencode-ui && npm install && cd ..\..
) else (
    echo     OK
)

echo.
echo [3/4] Iniciando Web Operator en puerto 3001...
start "Web Operator" cmd /k "cd web-operator && set PORT=3001 && set OPERATOR_PORT=3001 && node api-server.js"

:: Esperar a que inicie
timeout /t 3 /nobreak >nul

echo [4/4] Iniciando Proxy en puerto 21293...
start "OpenCode Proxy" cmd /k "cd artifacts\opencode-ui && set PORT=21293 && set OPENCODE_PORT=21294 && set API_SERVER_PORT=3001 && node proxy.mjs"

:: Esperar a que inicie
timeout /t 3 /nobreak >nul

echo.
echo  ========================================
echo   TODO LISTO - Abre en tu navegador:
echo.
echo   Frontend:  http://localhost:21293
echo   Diagnostico: http://localhost:21293/diag
echo   Web Operator: http://localhost:3001
echo  ========================================
echo.
echo  Presiona Ctrl+C en cada ventana para detener
echo.

:: Abrir navegador
start http://localhost:21293

pause
