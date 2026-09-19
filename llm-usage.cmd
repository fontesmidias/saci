@echo off
REM Mostra consumo e cota restante de cada provedor.
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" "%~dp0ask.py" --usage
