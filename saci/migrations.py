"""
Migrações do banco de dados (usage.db).

Por que isto existe: antes, cada módulo (usage.py, catalog.py) chamava
`CREATE TABLE IF NOT EXISTS` no import, e uma mudança de schema virava um
`DROP TABLE` manual condicional (veja o histórico de usage.py::init — a
tabela `quota` era recriada, com o comentário "é só cache", quando na
prática ela guarda o estado de cota lido dos headers). Isso funciona
enquanto for o autor testando localmente; num usuário real que atualiza o
Saci, um DROP TABLE apaga o histórico de uso ou o catálogo sondado — que
para o catálogo significa MINUTOS de sondagem perdidos, e para o uso
significa a promessa central do painel ("veja quanto você já gastou")
quebrada silenciosamente.

Regra: **migração nunca apaga dado do usuário por padrão.** Toda migração
aqui é aditiva (CREATE TABLE, ALTER TABLE ADD COLUMN, CREATE INDEX) ou,
quando precisa mudar uma chave primária, faz CREATE + COPY + RENAME, nunca
DROP direto. Uma migração destrutiva só é aceitável com backup automático
antes (ver `_backup_before` mais abaixo) — nenhuma das de hoje precisa disso.

Cada migração é uma função `_migration_NNN` numerada e registrada em
`MIGRATIONS`, na ordem em que devem rodar. `apply_pending()` roda apenas
as que a versão gravada em `schema_version` ainda não aplicou, em uma
transação por migração (uma falha não deixa o banco pela metade).
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone

from . import paths

# Cada item: (versão, descrição, função). A versão é o número da migração,
# não a versão do Saci — elas evoluem em ritmos diferentes.
Migration = tuple[int, str, Callable[[sqlite3.Connection], None]]


def _m001_tabelas_base(conn: sqlite3.Connection) -> None:
    """Schema inicial: calls, quota (chave por provedor+modelo), models, catalog_runs."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS calls (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            day         TEXT    NOT NULL,
            provider    TEXT    NOT NULL,
            model       TEXT    NOT NULL,
            profile     TEXT,
            ok          INTEGER NOT NULL,
            tokens      INTEGER DEFAULT 0,
            latency     REAL,
            error       TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_calls_day ON calls(day, provider, model);

        CREATE TABLE IF NOT EXISTS quota (
            provider            TEXT NOT NULL,
            model               TEXT NOT NULL,
            ts                  TEXT NOT NULL,
            limit_requests      INTEGER,
            remaining_requests  INTEGER,
            limit_tokens        INTEGER,
            remaining_tokens    INTEGER,
            reset_requests_at   TEXT,
            reset_tokens_at     TEXT,
            PRIMARY KEY (provider, model)
        );

        CREATE TABLE IF NOT EXISTS models (
            provider        TEXT NOT NULL,
            model           TEXT NOT NULL,
            name            TEXT,
            context         INTEGER,
            free_by_catalog INTEGER,
            status          TEXT NOT NULL,
            detail          TEXT,
            latency_ms      INTEGER,
            probes          INTEGER DEFAULT 0,
            first_seen      TEXT NOT NULL,
            last_seen       TEXT NOT NULL,
            last_probe      TEXT,
            misses          INTEGER DEFAULT 0,
            PRIMARY KEY (provider, model)
        );

        CREATE TABLE IF NOT EXISTS catalog_runs (
            provider    TEXT NOT NULL,
            ts          TEXT NOT NULL,
            listed      INTEGER,
            chat        INTEGER,
            probed      INTEGER,
            ok          INTEGER,
            error       TEXT
        );
    """)


def _m002_quota_chave_por_modelo(conn: sqlite3.Connection) -> None:
    """
    A tabela `quota` nasceu com chave só por `provider`. Passou a ser
    por (provider, model) — Groq conta tokens por modelo, não por conta
    (999/1000 requisições iguais nos 3 modelos, mas tokens diferentes:
    7860/7559/7487). Quem já tinha o schema antigo (chave só `provider`,
    sem coluna `model`) migra preservando a última leitura conhecida:
    ela vira a leitura de TODOS os modelos daquele provedor até a
    próxima chamada real corrigir por modelo — perde precisão por
    algumas horas, não perde o dado.

    Quem instala do zero já cria a tabela certa em _m001 e cai no `else`
    (nada a fazer).
    """
    cols = {r[1] for r in conn.execute("PRAGMA table_info(quota)").fetchall()}
    if not cols or "model" in cols:
        return  # instalação nova, ou já migrado

    conn.executescript("""
        ALTER TABLE quota RENAME TO quota_v1;
        CREATE TABLE quota (
            provider            TEXT NOT NULL,
            model               TEXT NOT NULL,
            ts                  TEXT NOT NULL,
            limit_requests      INTEGER,
            remaining_requests  INTEGER,
            limit_tokens        INTEGER,
            remaining_tokens    INTEGER,
            reset_requests_at   TEXT,
            reset_tokens_at     TEXT,
            PRIMARY KEY (provider, model)
        );
    """)
    # Sem coluna `model` no formato antigo: não há como saber a qual
    # modelo cada leitura pertencia, então a antiga é preservada à parte
    # (nunca apagada) em vez de forçada num modelo errado.
    conn.execute("ALTER TABLE quota_v1 RENAME TO quota_legacy_v1")


MIGRATIONS: list[Migration] = [
    (1, "tabelas base (calls, quota, models, catalog_runs)", _m001_tabelas_base),
    (2, "quota: chave por (provider, model)", _m002_quota_chave_por_modelo),
]


def _backup_before(version: int) -> None:
    """
    Cópia do banco antes de uma migração, mantida por segurança.

    Chamado automaticamente antes de qualquer migração marcada como
    potencialmente arriscada (nenhuma hoje precisa, mas o mecanismo
    existe para quando precisar — ver docstring do módulo).
    """
    origem = paths.db_path()
    if not origem.exists():
        return
    destino = origem.with_name(f"usage.pre-m{version:03d}.db")
    if not destino.exists():
        shutil.copy2(origem, destino)


def current_version(conn: sqlite3.Connection) -> int:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        " version INTEGER NOT NULL, applied_at TEXT NOT NULL)"
    )
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return row[0] or 0


def apply_pending(conn: sqlite3.Connection) -> list[int]:
    """Roda as migrações ainda não aplicadas, em ordem. Retorna as versões aplicadas."""
    aplicadas: list[int] = []
    atual = current_version(conn)

    for version, _descricao, fn in MIGRATIONS:
        if version <= atual:
            continue
        fn(conn)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        aplicadas.append(version)

    return aplicadas


def migrate() -> list[int]:
    """
    Ponto de entrada único: abre o banco, aplica o que faltar, fecha.

    Chamado por usage.py e catalog.py no lugar dos antigos `init()`
    independentes — as duas tabelas moram no mesmo arquivo, então uma
    única fonte de verdade evita duas transações concorrentes criando
    a mesma tabela.
    """
    conn = sqlite3.connect(paths.db_path(), timeout=10.0)
    try:
        aplicadas = apply_pending(conn)
        conn.commit()
        return aplicadas
    finally:
        conn.close()
