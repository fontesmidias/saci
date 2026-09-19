@echo off
REM Estado do servidor, dos provedores e do consumo.
cd /d "%~dp0"
echo === PROCESSO ===
call pm2 list
echo.
echo === CONSUMO ===
"%~dp0.venv\Scripts\python.exe" "%~dp0ask.py" --usage
