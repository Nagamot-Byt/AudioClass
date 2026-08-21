@echo off
title AudioClass - Reparador de Microfono
echo.
echo ============================================================
echo   AudioClass - Reparador de Microfono
echo ============================================================
echo.

:: Verificar si hay permisos de administrador
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Ejecutando como Administrador
    echo.
    powershell -ExecutionPolicy Bypass -File "%~dp0fix_audio_windows.ps1" -AutoFix
) else (
    echo [WARN] Sin permisos de Administrador
    echo        Solicitando elevacion...
    echo.
    powershell -Command "Start-Process cmd -ArgumentList '/c cd /d \"%~dp0\" && powershell -ExecutionPolicy Bypass -File fix_audio_windows.ps1 -AutoFix' -Verb RunAs"
)

echo.
echo ============================================================
echo   Presiona cualquier tecla para salir...
echo ============================================================
pause >nul
