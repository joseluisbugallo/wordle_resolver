@echo off
echo.
echo Cerrando el Explorador de Windows...
taskkill /f /im explorer.exe

echo.
echo Limpiando la cache de iconos...
cd %localappdata%\Microsoft\Windows\Explorer
del iconcache* /a

echo.
echo Reiniciando el Explorador de Windows...
start explorer.exe

echo.
echo Cache limpiada.
pause