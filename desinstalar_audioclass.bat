@echo off
chcp 65001 >nul
title AudioClass v9.1 - Desinstalador
setlocal
echo.
echo  ============================================================
echo    AUDIOCLASS v9.1 - DESINSTALADOR
echo  ============================================================
echo.
set "DEST=%USERPROFILE%\AudioClass"
echo  Eliminando el acceso directo del escritorio...
del "%USERPROFILE%\Desktop\AudioClass.lnk" >nul 2>&1
echo  Eliminando la carpeta del programa...
rmdir /S /Q "%DEST%" >nul 2>&1
echo.
echo  Listo.
echo  NOTA: tus grabaciones y apuntes se conservan en:
echo    %USERPROFILE%\AudioClass_Recordings
echo  Borra esa carpeta manualmente solo si tambien quieres
echo  eliminar tus clases grabadas.
echo.
pause
