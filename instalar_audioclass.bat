@echo off
chcp 65001 >nul
title AudioClass v9.1 - Instalador (1 clic)
setlocal

echo.
echo  ============================================================
echo    AUDIOCLASS v9.1 - INSTALADOR AUTOMATICO
echo    (un solo clic: copia el programa y crea el acceso directo)
echo  ============================================================
echo.

set "EXE=%~dp0AudioClass.exe"
if not exist "%EXE%" (
    echo  ERROR: No se encuentra AudioClass.exe junto a este instalador.
    echo  Asegurate de que ambos archivos estan en la misma carpeta
    echo  (descomprime el .zip completo antes de instalar).
    echo.
    pause
    exit /b 1
)

set "DEST=%USERPROFILE%\AudioClass"
echo  [1/3] Copiando el programa a: %DEST%
if not exist "%DEST%" mkdir "%DEST%"
copy /Y "%EXE%" "%DEST%\AudioClass.exe" >nul
if errorlevel 1 (
    echo  ERROR: No se pudo copiar el programa. Cierra esta ventana,
    echo  abre la carpeta %DEST% y copia AudioClass.exe a mano.
    echo.
    pause
    exit /b 1
)

echo  [2/3] Creando acceso directo en el escritorio...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\AudioClass.lnk'); $s.TargetPath='%DEST%\AudioClass.exe'; $s.WorkingDirectory='%DEST%'; $s.IconLocation='%SystemRoot%\System32\SHELL32.dll,14'; $s.Description='AudioClass v9.1 - Grabador de clases'; $s.Save()" >nul 2>&1

echo  [3/3] Acceso directo "AudioClass" creado en el escritorio.
echo.
echo  LISTO. Las grabaciones se guardan en:
echo    %USERPROFILE%\AudioClass_Recordings
echo.
echo  La primera apertura tarda 30-60 segundos (descomprime la IA
echo  en segundo plano). Es normal; luego funciona con normalidad.
echo.
choice /C SN /M "Quieres ABRIR AudioClass ahora (S/N)"
if "%errorlevel%"=="1" start "" "%DEST%\AudioClass.exe"
echo.
echo  Para desinstalar: doble clic en "Desinstalar AudioClass.bat"
echo.
pause
