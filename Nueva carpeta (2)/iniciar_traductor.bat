@echo off
set "PYTHON_SCRIPT=vn_realtime_translator_overlay_fixed.py"

REM --- Verificación y ejecución del script ---

REM Intenta ejecutar con 'python'
python "%PYTHON_SCRIPT%"
if %errorlevel% equ 0 goto :end

REM Intenta ejecutar con 'python3'
python3 "%PYTHON_SCRIPT%"
if %errorlevel% equ 0 goto :end

REM Intenta ejecutar con 'py' (Windows)
py "%PYTHON_SCRIPT%"
if %errorlevel% equ 0 goto :end

REM Si no se encontró ningún intérprete, muestra un mensaje de error
echo.
echo ERROR: No se pudo encontrar un intérprete de Python para ejecutar el script.
echo Asegúrate de que Python está instalado y que su ruta está en la variable de entorno PATH.
echo.
pause

:end