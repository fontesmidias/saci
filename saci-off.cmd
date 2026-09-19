@echo off
REM Desliga o servidor do Saci.
cd /d "%~dp0"
call pm2 delete saci
call pm2 save >nul 2>&1
echo.
echo Servidor desligado.
