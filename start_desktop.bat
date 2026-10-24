@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m pip install -r desktop\requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m desktop.app
if errorlevel 1 goto failed
exit /b 0
:failed
echo Snow Ball could not start. Read the error above.
pause
exit /b 1
