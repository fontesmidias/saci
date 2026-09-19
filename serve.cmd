@echo off
REM Sobe o servidor local compativel com a API da OpenAI.
REM Deixe esta janela aberta enquanto usar a extensao do VSCode.
"%~dp0.venv\Scripts\python.exe" "%~dp0server.py" %*
