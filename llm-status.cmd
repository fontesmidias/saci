@echo off
REM Mostra o estado do servidor e testa os provedores.
cd /d "%~dp0"
pm2 list
echo.
"%~dp0.venv\Scripts\python.exe" "%~dp0ask.py" --status
