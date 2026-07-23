@echo off
REM ============================================================
REM  Lanzador de un click para Pac-Man (Windows)
REM  Detecta Python probando 'py', 'python' y 'python3'.
REM  Crea un .venv LOCAL en esta carpeta y ejecuta el juego.
REM  No toca tu Python global. Tkinter viene con Python: no instala nada.
REM ============================================================

cd /d "%~dp0"

REM --- Detectar un Python que funcione ---
set "PYCMD="
py --version >nul 2>&1 && set "PYCMD=py"
if not defined PYCMD ( python --version >nul 2>&1 && set "PYCMD=python" )
if not defined PYCMD ( python3 --version >nul 2>&1 && set "PYCMD=python3" )

if not defined PYCMD (
    echo No se encontro Python en el PATH.
    echo Instalalo desde https://www.python.org/downloads/ y marca
    echo "Add Python to PATH", o abre una consola y prueba escribir: py
    pause
    exit /b 1
)

echo Usando Python con el comando: %PYCMD%

REM --- Crear el entorno virtual local la primera vez ---
if not exist ".venv\Scripts\python.exe" (
    echo Preparando el entorno por primera vez...
    %PYCMD% -m venv .venv
)

REM --- Elegir con que ejecutar: el venv si existe, si no el Python detectado ---
set "RUNNER=.venv\Scripts\python.exe"
if not exist "%RUNNER%" set "RUNNER=%PYCMD%"

"%RUNNER%" pacman_app.py

if errorlevel 1 pause
