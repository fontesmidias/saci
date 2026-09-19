@echo off
REM Mostra os logs ao vivo (Ctrl+C para sair).
cd /d "%~dp0"
pm2 logs llm-router
