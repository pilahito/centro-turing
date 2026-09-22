@echo off
rem Centro Turing - panel grafico de la mini pantalla USB (Windows)
rem Usa el venv del proyecto si existe; si no, el Python del sistema.
setlocal
set "ROOT=%~dp0"

set "PY=%ROOT%venv\Scripts\pythonw.exe"
if not exist "%PY%" set "PY=%ROOT%venv\Scripts\python.exe"
if not exist "%PY%" set "PY=pythonw"

start "" "%PY%" "%ROOT%tools\turing_center.py" %*
endlocal
