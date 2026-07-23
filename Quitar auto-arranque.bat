@echo off
rem ============================================================
rem  Quita el auto-arranque de Cometa.
rem ============================================================
cd /d "%~dp0"

py cometa.py --remove-autostart
if errorlevel 1 python cometa.py --remove-autostart

echo.
echo   Nota: si Cometa esta corriendo ahora, cerralo con Ctrl + Shift + Q
echo   o con boton derecho en el icono del cometa, junto al reloj.
echo.
pause
