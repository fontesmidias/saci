@echo off
REM Liga o servidor do Saci (segundo plano, via PM2).
cd /d "%~dp0"
REM Se o daemon do PM2 caiu (reboot/logoff), restaura o que estava salvo.
call pm2 resurrect >nul 2>&1
call pm2 start ecosystem.config.js
call pm2 save >nul 2>&1
echo.
echo Servidor no ar: http://127.0.0.1:8000/v1
echo Painel: saci-panel     Desligar: saci-off
