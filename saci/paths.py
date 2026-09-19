"""
Onde o Saci guarda seus dados: `.env`, `usage.db`, `prefs.json`, logs.

Dois modos:

    desenvolvimento  -> a pasta do repositório (comportamento de sempre)
    instalado (.exe) -> %APPDATA%\\Saci (a pasta do programa é só leitura
                        e some na atualização, então dados não podem morar lá)

`SACI_HOME` força um diretório específico (útil em testes: cada teste usa
uma pasta isolada, sem tocar nos dados reais do usuário).

Migração: se os arquivos existirem na pasta antiga (o repositório, para
quem já usava o Saci em modo desenvolvimento e depois instalou o .exe) e
ainda não existirem no destino, eles são COPIADOS uma vez — nunca movidos,
para que o original sobreviva a um erro de migração.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Arquivos que migram da pasta antiga (repositório) para a nova (%APPDATA%),
# na primeira vez que o Saci roda instalado.
_MIGRAVEIS = [".env", "usage.db", "prefs.json"]


def is_frozen() -> bool:
    """True quando rodando como executável empacotado (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def data_dir() -> Path:
    """
    A pasta onde ficam os dados do usuário.

    Resolvida uma vez por processo (cacheada), pois o resultado não muda
    em tempo de execução e é consultada com frequência.
    """
    if data_dir._cached is not None:  # type: ignore[attr-defined]
        return data_dir._cached  # type: ignore[attr-defined]

    override = os.getenv("SACI_HOME")
    if override:
        destino = Path(override).expanduser().resolve()
    elif is_frozen():
        appdata = os.getenv("APPDATA")
        destino = (Path(appdata) if appdata else Path.home() / "AppData" / "Roaming") / "Saci"
    else:
        destino = REPO_ROOT

    destino.mkdir(parents=True, exist_ok=True)
    (destino / "logs").mkdir(exist_ok=True)

    if destino != REPO_ROOT:
        _migrar_dados_antigos(destino)

    data_dir._cached = destino  # type: ignore[attr-defined]
    return destino


data_dir._cached = None  # type: ignore[attr-defined]


def _migrar_dados_antigos(destino: Path) -> None:
    """Copia (não move) arquivos do repositório para a pasta nova, se faltarem lá."""
    for nome in _MIGRAVEIS:
        origem = REPO_ROOT / nome
        alvo = destino / nome
        if origem.exists() and not alvo.exists():
            try:
                shutil.copy2(origem, alvo)
            except OSError:
                pass  # não trava a inicialização por causa disso


def env_path() -> Path:
    return data_dir() / ".env"


def db_path() -> Path:
    return data_dir() / "usage.db"


def prefs_path() -> Path:
    return data_dir() / "prefs.json"


def logs_dir() -> Path:
    return data_dir() / "logs"
