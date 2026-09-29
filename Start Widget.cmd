@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 scripts\launch-windows.py --widget
) else (
    where python >nul 2>nul
    if errorlevel 1 goto missing
    python scripts\launch-windows.py --widget
)
if errorlevel 1 (
    echo.
    echo If Python is missing, install Python 3.12 from python.org with Tcl/Tk and the launcher enabled.
    pause
    exit /b 1
)
exit /b 0
:missing
echo Install Python 3.12 from python.org with Tcl/Tk and the Python launcher enabled.
echo Then double-click this file again. No Ollama or GPU is needed.
pause
exit /b 1
