"""
Log em arquivo, para quando não há PM2 guardando a saída do processo.

Hoje (modo desenvolvimento com PM2) o log vai para o stderr e o PM2 grava
em `logs/saci-err.log`. Isso não existe no app empacotado: sem PM2, sem
terminal, a saída simplesmente desaparece.

`setup_logging()` configura o logger raiz do Saci com dois destinos:

    console  -> stderr, só quando NÃO está empacotado (dev: continua
                aparecendo no terminal/PM2 como sempre)
    arquivo  -> logs/saci.log em paths.data_dir(), sempre, com rotação
                (2 MB x 3 arquivos, ~6 MB no total)

Nunca loga chave: quem chama já deve ter passado a mensagem por
`router._scrub` antes de logar; este módulo não faz higienização própria.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from . import paths

LOGGER_NAME = "saci"
_MAX_BYTES = 2 * 1024 * 1024  # 2 MB por arquivo
_BACKUPS = 3                   # + 3 arquivos antigos = ~8 MB no total

_configurado = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configura o logger do Saci. Idempotente — chamar de novo não duplica
    handlers (o servidor recarrega módulos em alguns cenários de dev).
    """
    global _configurado
    logger = logging.getLogger(LOGGER_NAME)

    if _configurado:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    formato = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    arquivo = RotatingFileHandler(
        paths.logs_dir() / "saci.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUPS,
        encoding="utf-8",
    )
    arquivo.setFormatter(formato)
    logger.addHandler(arquivo)

    # Empacotado (--windowed) não tem console; escrever nele derruba o
    # processo com OSError em alguns ambientes do Windows.
    if not paths.is_frozen():
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formato)
        logger.addHandler(console)

    _configurado = True
    return logger


def get_logger() -> logging.Logger:
    """Logger já configurado (chama setup_logging com os padrões se preciso)."""
    if not _configurado:
        return setup_logging()
    return logging.getLogger(LOGGER_NAME)
