@echo off
title OpenCode Evolved - WSL
color 0B
echo.
echo  ============================================================
echo   OpenCode Evolved - Iniciando en WSL Ubuntu
echo  ============================================================
echo.

:: Convertir ruta Windows a ruta WSL
set "WIN_PATH=%~dp0"
:: Quitar trailing backslash
set "WIN_PATH=%WIN_PATH:~0,-1%"

:: Convertir C:\ a /mnt/c/ para WSL
set "WSL_PATH=%WIN_PATH:\=/%"
set "WSL_PATH=%WSL_PATH:C:=/mnt/c%"
set "WSL_PATH=%WSL_PATH:c:=/mnt/c%"
set "WSL_PATH=%WSL_PATH:D:=/mnt/d%"
set "WSL_PATH=%WSL_PATH:d:=/mnt/d%"

echo  Workspace: %WIN_PATH%
echo  WSL Path:  %WSL_PATH%
echo.
echo  Iniciando Ubuntu WSL...
echo  (El navegador se abrira automaticamente en http://localhost:21293)
echo.

wsl -d Ubuntu -- bash -c "cd '%WSL_PATH%' && bash start-wsl.sh"

echo.
echo  OpenCode se ha detenido.
pause
