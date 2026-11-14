@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo BLAD: Nie znaleziono backend\.venv\Scripts\python.exe
    exit /b 2
)

".venv\Scripts\python.exe" -m automation.daily_runner --handle sandecjans --mode both --max-videos 3
exit /b %ERRORLEVEL%
