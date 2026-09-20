"""
Iniciar o Saci com o Windows — sem privilégio de administrador.

Usa a chave de registro por-usuário
`HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`, que não exige
elevação (é gravada só para a conta atual, não para a máquina toda).

Dois cenários de comando de lançamento:

    empacotado (sys.frozen)   -> o próprio .exe, sem argumentos
    desenvolvimento           -> pythonw.exe -m saci.app
                                 (pythonw, não python: sem janela de
                                 console — o app já tem janela própria
                                 e ícone na bandeja)

`pythonw.exe` mora ao lado de `python.exe`/`python.exe` no mesmo venv;
resolvido a partir de `sys.executable`, não do PATH do sistema — assim
sempre aponta para o Python (e as dependências) certos.
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import paths

NOME_CHAVE = "Saci"
CAMINHO_REGISTRO = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _comando_de_lancamento() -> str:
    """O valor a gravar na chave: como o Windows deve iniciar o Saci."""
    if paths.is_frozen():
        return f'"{sys.executable}"'

    python_w = Path(sys.executable).with_name("pythonw.exe")
    interprete = str(python_w) if python_w.exists() else sys.executable
    return f'"{interprete}" -m saci.app'


def disponivel() -> bool:
    """False fora do Windows — o recurso simplesmente não existe lá."""
    return sys.platform == "win32"


def ligado() -> bool:
    """Existe uma entrada nossa na chave Run, e ela aponta para o comando atual?"""
    if not disponivel():
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CAMINHO_REGISTRO) as chave:
            valor, _tipo = winreg.QueryValueEx(chave, NOME_CHAVE)
            return bool(valor)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def ligar() -> None:
    """Grava a chave. Não exige administrador — é HKCU, por usuário."""
    if not disponivel():
        raise RuntimeError("iniciar com o sistema só está implementado no Windows")
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CAMINHO_REGISTRO) as chave:
        winreg.SetValueEx(chave, NOME_CHAVE, 0, winreg.REG_SZ, _comando_de_lancamento())


def desligar() -> None:
    """Remove a chave. Silencioso se já não existir (idempotente)."""
    if not disponivel():
        return
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, CAMINHO_REGISTRO, 0, winreg.KEY_SET_VALUE
        ) as chave:
            winreg.DeleteValue(chave, NOME_CHAVE)
    except FileNotFoundError:
        pass


def alternar() -> bool:
    """Liga se estiver desligado, desliga se estiver ligado. Retorna o novo estado."""
    if ligado():
        desligar()
        return False
    ligar()
    return True
