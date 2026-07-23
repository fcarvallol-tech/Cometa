@echo off
rem ============================================================
rem  Instala Cometa para que arranque solo al prender el PC.
rem  Delega en Python: el sabe donde esta su propio ejecutable,
rem  asi no dependemos de que 'pyw' este en el PATH.
rem ============================================================
cd /d "%~dp0"

py cometa.py --install-autostart
if errorlevel 1 python cometa.py --install-autostart

echo.
echo   Listo. Probalo con tu atajo (por defecto Ctrl + Shift + S).
echo   Para salir en cualquier momento:  Ctrl + Shift + Q
echo   o boton derecho en el icono del cometa, junto al reloj.
echo.
pause
