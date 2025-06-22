@echo off
:: ===================================================
:: == Script de Compilacion para Wordle Resolver GUI ==
:: ===================================================

echo.
echo [1/4] Comprobando entorno...

if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Entorno virtual 'venv' no encontrado.
    pause
    exit /b
)
if not exist "wordle_resolver_gui.py" (
    echo [ERROR] Script 'wordle_resolver_gui.py' no encontrado.
    pause
    exit /b
)

echo [2/4] Activando entorno virtual...
call venv\Scripts\activate

echo.
echo [3/4] Ejecutando PyInstaller...
pyinstaller --onefile --windowed ^
--icon="icon.ico" ^
--add-data "icon.ico;." ^
--add-data "palabras.json;." ^
--add-data "themes/azure.tcl;themes" ^
wordle_resolver_gui.py

echo.
echo [4/4] Proceso de compilacion finalizado.
echo El ejecutable se encuentra en la carpeta 'dist'.
echo.
pause