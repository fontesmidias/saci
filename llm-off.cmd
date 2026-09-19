@echo off
REM Desliga o servidor do LLM Router.
cd /d "%~dp0"
call pm2 delete llm-router
call pm2 save >nul 2>&1
echo.
echo Servidor desligado.
