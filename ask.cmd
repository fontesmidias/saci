@echo off
REM Atalho: usa sempre o Python do .venv, sem precisar ativar o ambiente.
REM Uso:  ask -p code "sua pergunta"
"%~dp0.venv\Scripts\python.exe" "%~dp0ask.py" %*
