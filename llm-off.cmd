@echo off
REM Desliga o servidor do LLM Router.
cd /d "%~dp0"
pm2 stop llm-router
pm2 delete llm-router
echo.
echo Servidor desligado.
