@echo off
title AudioClass - Quick Start
echo ============================================================
echo   AudioClass v9.1 - Instalador y Lanzador Rapido
echo ============================================================
echo.

:: Detectar Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no encontrado en el PATH.
    echo.
    echo Instala Python 3.12 desde: https://www.python.org/downloads/
    echo IMPORTANTE: marca "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

:: Mostrar version de Python
python --version
echo.

:: Verificar si hay venv, si no crearlo
if not exist "venv" (
    echo [1/4] Creando entorno virtual...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo       Entorno virtual creado.
) else (
    echo [1/4] Entorno virtual existente encontrado.
)

:: Activar venv
echo [2/4] Activando entorno virtual...
call venv\Scripts\activate.bat

:: Instalar dependencias
echo [3/4] Instalando dependencias (puede tardar 2-5 min)...
pip install --upgrade pip --quiet
pip install -r requirements_v91.txt --quiet
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Fallo al instalar dependencias. Revisa el error arriba.
    pause
    exit /b 1
)
echo       Dependencias instaladas.

:: Lanzar la app
echo.
echo ============================================================
echo   AudioClass esta listo. Iniciando...
echo ============================================================
echo.
python audioclass_v91.py

:: Si la app cierra, mantener la ventana abierta
echo.
echo AudioClass se ha cerrado.
pause
