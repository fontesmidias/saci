@echo off
REM Logs ao vivo (Ctrl+C para sair).
cd /d "%~dp0"
call pm2 logs saci
