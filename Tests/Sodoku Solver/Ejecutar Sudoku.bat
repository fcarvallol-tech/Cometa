@echo off
REM ============================================================
REM  Lanzador de un click para el Sudoku (Windows)
REM  Detecta Python probando 'py', 'python' y 'python3'.
REM  Crea un .venv LOCAL en esta carpeta y ejecuta la app.
REM  No toca tu Python global. Tkinter viene con Python: no instala nada.
REM ============================================================

cd /d "%~dp0"

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

if not exist ".venv\Scripts\python.exe" (
    echo Preparando el entorno por primera vez...
    %PYCMD% -m venv .venv
)

set "RUNNER=.venv\Scripts\python.exe"
if not exist "%RUNNER%" set "RUNNER=%PYCMD%"

"%RUNNER%" sudoku_app.py

if errorlevel 1 pause
