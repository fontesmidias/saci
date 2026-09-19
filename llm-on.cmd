@echo off
REM Liga o servidor do LLM Router (fica rodando em segundo plano).
cd /d "%~dp0"
pm2 start ecosystem.config.js
echo.
echo Servidor no ar em http://127.0.0.1:8000/v1
echo Para desligar:  llm-off
