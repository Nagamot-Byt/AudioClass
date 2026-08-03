@echo off
chcp 65001 >nul
setlocal
title AudioClass v9.1 — Instalador de un clic
color 0B
cd /d "%~dp0"
cls

echo.
echo  ╔══════════════════════════════════════════════════════════════════════╗
echo  ║                                                                    ║
echo  ║        🎙️  AUDIOCLASS v9.1 — INSTALADOR AUTOMÁTICO               ║
echo  ║        Doble clic y listo: Python, dependencias, IA y la app       ║
echo  ║                                                                    ║
echo  ╚══════════════════════════════════════════════════════════════════════╝
echo.
echo  Este programa hará todo por ti, paso a paso:
echo.
echo    [1/6]  Buscar (o instalar) Python en tu equipo
echo    [2/6]  Crear un espacio aislado para AudioClass
echo    [3/6]  Instalar todas las librerías necesarias
echo    [4/6]  Descargar el modelo de voz (Whisper)
echo    [5/6]  Probar la conexión con Gemini (opcional)
echo    [6/6]  Crear acceso directo y abrir la app
echo.
echo  ⚠️  Necesitas internet y unos 2 GB de espacio libre.
echo  ⏳  La primera vez puede tardar 10-20 minutos. No cierres esta ventana.
echo.
pause
cls

REM ═══════════════════════════════════════════════════════════════════════════
REM PASO 1 — BUSCAR O INSTALAR PYTHON
REM ═══════════════════════════════════════════════════════════════════════════
echo.
echo  [1/6] 🔍 Buscando Python en tu equipo...
echo.
set "PYTHON_EXE="

REM Intentar 1: el lanzador "py" (el mas confiable, no es el alias de la tienda)
where py >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%i"
)

REM Intentar 2: "python" real (si el comando no es el alias vacio de Microsoft Store)
if not defined PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%i"
    )
)

REM Intentar 3: buscar instalaciones en la carpeta estandar de Python
if not defined PYTHON_EXE (
    for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%d\python.exe" set "PYTHON_EXE=%%d\python.exe"
    )
)

if not defined PYTHON_EXE (
    echo  ❌ No se encontro Python en tu equipo.
    echo.
    echo  ⬇️  Voy a instalarlo automáticamente con winget...
    echo.
    where winget >nul 2>&1
    if errorlevel 1 (
        echo  ❌ winget no esta disponible en este equipo.
        echo.
        echo  Puedes instalar Python manualmente desde:
        echo  https://www.python.org/downloads/
        echo.
        echo  ⚠️  IMPORTANTE: al instalar, marca la casilla:
        echo       [x] Add python.exe to PATH
        echo.
        echo  Después de instalarlo, cierra esta ventana y vuelve a
        echo  ejecutar "build.bat" con doble clic.
        echo.
        start https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo  Si Windows te pide permiso, pulsa "Sí" para continuar.
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo  ❌ No se pudo instalar Python con winget.
        echo     Instala Python manualmente desde https://www.python.org/downloads/
        echo     marcando [x] Add python.exe to PATH, y vuelve a ejecutar build.bat
        pause
        exit /b 1
    )
    echo.
    echo  ✅ Python instalado. Verificando...
    for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%d\python.exe" set "PYTHON_EXE=%%d\python.exe"
    )
    if defined PYTHON_EXE (
        REM Nota: el resto del script usa %PYTHON_EXE% directamente, sin depender del PATH
    )
)

if not defined PYTHON_EXE (
    echo  ❌ No se pudo localizar Python tras la instalacion.
    echo     Reinicia esta ventana y vuelve a ejecutar build.bat.
    pause
    exit /b 1
)

echo  ✅ Python encontrado: "%PYTHON_EXE%"
"%PYTHON_EXE%" --version
echo.

REM ═══════════════════════════════════════════════════════════════════════════
REM PASO 2 — CREAR ENTORNO VIRTUAL (espacio aislado y seguro)
REM ═══════════════════════════════════════════════════════════════════════════
echo.
echo  [2/6] 📦 Creando el espacio aislado de AudioClass...
echo.
if not exist "audioclass_env\Scripts\python.exe" (
    "%PYTHON_EXE%" -m venv audioclass_env
    if errorlevel 1 (
        echo  ❌ No se pudo crear el espacio aislado.
        pause
        exit /b 1
    )
    echo  ✅ Espacio aislado creado.
) else (
    echo  ℹ️  Ya existia un espacio aislado. Se reutiliza.
)
set "VENV_PY=audioclass_env\Scripts\python.exe"
"%VENV_PY%" -m pip install --upgrade pip >nul 2>&1
echo.

REM ═══════════════════════════════════════════════════════════════════════════
REM PASO 3 — INSTALAR DEPENDENCIAS
REM ═══════════════════════════════════════════════════════════════════════════
REM Orden importante: primero el PyTorch ligero (CPU), luego el resto.
REM Si instalas requirements primero, pip descargaria el PyTorch CUDA enorme
REM (~2.5 GB) y lo reemplazaria despues por el ligero. Asi evitamos esa descarga.
echo.
echo  [3/6] ⬇️  Instalando las librerías necesarias (puede tardar)...
echo.
echo  🔧 Paso 1 de 2: PyTorch ligero para tu equipo (rapido, sin GPU)...
"%VENV_PY%" -m pip install torch --index-url https://download.pytorch.org/whl/cpu >nul 2>&1
if errorlevel 1 (
    echo  ⚠️  No se pudo instalar el PyTorch ligero. Se usará el estándar, tarda más.
) else (
    echo  ✅ PyTorch ligero listo.
)

echo.
echo  ⬇️  Paso 2 de 2: resto de librerías (Whisper, Gemini, interfaz)...
"%VENV_PY%" -m pip install -r requirements_v91.txt
if errorlevel 1 (
    echo.
    echo  ❌ Error instalando las librerías. Revisa tu conexión a internet.
    pause
    exit /b 1
)
echo  ✅ Librerías instaladas.
echo.

REM ═══════════════════════════════════════════════════════════════════════════
REM PASO 4 — DESCARGAR MODELO DE VOZ (Whisper tiny)
REM ═══════════════════════════════════════════════════════════════════════════
echo.
echo  [4/6] 🧠 Descargando el modelo de voz (primera vez, unos minutos)...
echo.
"%VENV_PY%" -c "import whisper; whisper.load_model('tiny')" >nul 2>&1
if errorlevel 1 (
    echo  ⚠️  No se pudo descargar el modelo de voz automáticamente.
    echo     La app lo descargará la primera vez que transcribas. No es un error grave.
) else (
    echo  ✅ Modelo de voz listo.
)
echo.

REM ═══════════════════════════════════════════════════════════════════════════
REM PASO 5 — PROBAR CONEXIÓN CON GEMINI (opcional)
REM ═══════════════════════════════════════════════════════════════════════════
echo.
echo  [5/6] ✨ Probando la conexión con Gemini...
echo  (Si no tienes API Key todavía, no te preocupes: se puede configurar después)
echo.
"%VENV_PY%" test_gemini_v91.py
echo.
echo  ℹ️  Si el paso anterior pidió una API Key, puedes añadirla después
echo     desde la app: Configuración → pegar tu clave → Probar Conexión.
echo.

REM ═══════════════════════════════════════════════════════════════════════════
REM PASO 6 — ACCESO DIRECTO Y ABRIR LA APP
REM ═══════════════════════════════════════════════════════════════════════════
echo.
echo  [6/6] 🚀 Creando acceso directo...
echo.
if not exist "Iniciar AudioClass.bat" (
    (
        echo @echo off
        echo cd /d "%~dp0"
        echo start "" "audioclass_env\Scripts\pythonw.exe" audioclass_v91.py
    ) > "Iniciar AudioClass.bat"
)

REM Acceso directo en el escritorio (via PowerShell, sin archivos temporales)
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $lnk = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\AudioClass.lnk'); $lnk.TargetPath = '%CD%\Iniciar AudioClass.bat'; $lnk.WorkingDirectory = '%CD%'; $lnk.IconLocation = '%SystemRoot%\System32\SHELL32.dll,14'; $lnk.Description = 'AudioClass v9.1 - Grabador de Clases'; $lnk.Save()" >nul 2>&1
echo  ✅ Acceso directo "AudioClass" creado en tu escritorio.

cls
echo.
echo  ╔══════════════════════════════════════════════════════════════════════╗
echo  ║  ✅ ¡TODO LISTO!                                                    ║
echo  ║                                                                    ║
echo  ║  La app se está abriendo... 🎙️                                      ║
echo  ║                                                                    ║
echo  ║  Para abrirla en el futuro:                                        ║
echo  ║    🖥️  Icono "AudioClass" en tu escritorio                         ║
echo  ║    🖥️  O "Iniciar AudioClass.bat" en esta carpeta                  ║
echo  ║                                                                    ║
echo  ║  📁 Tus grabaciones se guardan en:                                 ║
echo  ║     Documentos \ AudioClass_Recordings                             ║
echo  ║                                                                    ║
echo  ║  📖 Guía completa: abre el archivo GUIA_DE_USO.md                  ║
echo  ╚══════════════════════════════════════════════════════════════════════╝
echo.
start "" "audioclass_env\Scripts\pythonw.exe" audioclass_v91.py
echo  La app ya debería estar abierta. Si ves un error, avísale a la persona que te ayudó.
echo.
pause
endlocal
