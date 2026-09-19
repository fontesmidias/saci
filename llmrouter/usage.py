"""
Contabilidade de consumo por provedor/modelo.

Duas fontes de verdade, combinadas:

1. HEADERS DO PROVEDOR (fonte oficial, quando existe)
   Groq e Mistral devolvem cota restante e quando reseta em cada
   resposta. É o dado mais confiável: vem de quem cobra.

2. CONTAGEM LOCAL (nossa, sempre)
   Google e NVIDIA não informam nada. Para eles, somamos os tokens de
   cada resposta num SQLite e comparamos com os limites conhecidos.

Guardamos tudo em um SQLite local (usage.db, fora do git) para que o
histórico sobreviva a reinícios do servidor.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "usage.db"

_lock = threading.Lock()

# Limites conhecidos do free tier, por provedor.
# Usados para os provedores que NÃO informam cota (Google, NVIDIA) e
# como referência na exibição. Verificados em 19/09/2026.
KNOWN_LIMITS: dict[str, dict] = {
    "groq": {"rpd": 1000, "rpm": 30, "source": "headers"},
    "google": {"rpd": 1500, "rpm": 15, "source": "local"},
    "mistral": {"rpm": 188, "source": "headers"},
    "nvidia": {"rpd": 1000, "rpm": 40, "source": "local"},
    "openrouter": {"rpd": 200, "rpm": 20, "source": "endpoint"},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,       -- ISO-8601 UTC
    day         TEXT    NOT NULL,       -- YYYY-MM-DD (UTC) para agregar por dia
    provider    TEXT    NOT NULL,       -- chave: groq, google, ...
    model       TEXT    NOT NULL,
    profile     TEXT,
    ok          INTEGER NOT NULL,       -- 1 sucesso, 0 falha
    tokens      INTEGER DEFAULT 0,
    latency     REAL,
    error       TEXT                    -- resumo quando ok=0
);
CREATE INDEX IF NOT EXISTS idx_calls_day ON calls(day, provider);

-- Último estado de cota lido dos headers do provedor.
CREATE TABLE IF NOT EXISTS quota (
    provider            TEXT PRIMARY KEY,
    ts                  TEXT NOT NULL,
    limit_requests      INTEGER,
    remaining_requests  INTEGER,
    limit_tokens        INTEGER,
    remaining_tokens    INTEGER,
    reset_requests      TEXT,
    reset_tokens        TEXT
);
"""


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with _lock, _db() as conn:
        conn.executescript(SCHEMA)


def record_call(
    provider: str,
    model: str,
    *,
    ok: bool,
    tokens: int = 0,
    latency: float | None = None,
    profile: str | None = None,
    error: str | None = None,
) -> None:
    """Registra uma chamada — bem-sucedida ou não."""
    now = datetime.now(timezone.utc)
    with _lock, _db() as conn:
        conn.execute(
            "INSERT INTO calls (ts, day, provider, model, profile, ok, tokens, latency, error)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                now.isoformat(timespec="seconds"),
                now.strftime("%Y-%m-%d"),
                provider,
                model,
                profile,
                1 if ok else 0,
                tokens or 0,
                latency,
                (error or "")[:300] or None,
            ),
        )


def record_quota_headers(provider: str, headers) -> None:
    """
    Extrai cota dos headers da resposta, quando o provedor os envia.

    Groq:    x-ratelimit-{limit,remaining}-{requests,tokens}
    Mistral: x-ratelimit-{limit,remaining}-{req,tokens}-minute
    """
    def num(*names) -> int | None:
        for n in names:
            v = headers.get(n)
            if v is not None:
                try:
                    return int(float(v))
                except (TypeError, ValueError):
                    pass
        return None

    def text(*names) -> str | None:
        for n in names:
            v = headers.get(n)
            if v:
                return str(v)
        return None

    limit_req = num("x-ratelimit-limit-requests", "x-ratelimit-limit-req-minute")
    remain_req = num("x-ratelimit-remaining-requests", "x-ratelimit-remaining-req-minute")
    limit_tok = num("x-ratelimit-limit-tokens", "x-ratelimit-limit-tokens-minute")
    remain_tok = num("x-ratelimit-remaining-tokens", "x-ratelimit-remaining-tokens-minute")

    if limit_req is None and limit_tok is None:
        return  # provedor não informa cota

    with _lock, _db() as conn:
        conn.execute(
            "INSERT INTO quota (provider, ts, limit_requests, remaining_requests,"
            " limit_tokens, remaining_tokens, reset_requests, reset_tokens)"
            " VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(provider) DO UPDATE SET"
            " ts=excluded.ts, limit_requests=excluded.limit_requests,"
            " remaining_requests=excluded.remaining_requests,"
            " limit_tokens=excluded.limit_tokens,"
            " remaining_tokens=excluded.remaining_tokens,"
            " reset_requests=excluded.reset_requests, reset_tokens=excluded.reset_tokens",
            (
                provider,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                limit_req,
                remain_req,
                limit_tok,
                remain_tok,
                text("x-ratelimit-reset-requests"),
                text("x-ratelimit-reset-tokens"),
            ),
        )


def today_usage() -> dict[str, dict]:
    """Consumo de hoje (UTC) por provedor, da nossa contagem local."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _lock, _db() as conn:
        rows = conn.execute(
            "SELECT provider,"
            "       SUM(ok) AS ok_calls,"
            "       COUNT(*) - SUM(ok) AS failed,"
            "       SUM(tokens) AS tokens,"
            "       AVG(CASE WHEN ok=1 THEN latency END) AS avg_latency"
            " FROM calls WHERE day = ? GROUP BY provider",
            (day,),
        ).fetchall()
    return {
        r["provider"]: {
            "ok_calls": r["ok_calls"] or 0,
            "failed": r["failed"] or 0,
            "tokens": r["tokens"] or 0,
            "avg_latency": round(r["avg_latency"], 2) if r["avg_latency"] else None,
        }
        for r in rows
    }


def last_quota() -> dict[str, dict]:
    """Última cota lida dos headers, por provedor."""
    with _lock, _db() as conn:
        rows = conn.execute("SELECT * FROM quota").fetchall()
    return {r["provider"]: dict(r) for r in rows}


def is_exhausted(provider: str, threshold: float = 0.95) -> bool:
    """
    Diz se o provedor está sem cota (ou muito perto), para ser pulado.

    Usa o dado oficial dos headers quando existe; caso contrário, compara
    nossa contagem local com o limite diário conhecido. Na dúvida retorna
    False — é melhor tentar e falhar do que pular um provedor que estava
    disponível.
    """
    try:
        q = last_quota().get(provider, {})

        # Fonte oficial: o provedor disse quanto resta.
        rem_req, lim_req = q.get("remaining_requests"), q.get("limit_requests")
        if rem_req is not None and lim_req:
            if rem_req <= 0:
                return True
            if 1 - (rem_req / lim_req) >= threshold:
                return True

        rem_tok, lim_tok = q.get("remaining_tokens"), q.get("limit_tokens")
        if rem_tok is not None and lim_tok and rem_tok <= 0:
            return True

        # Sem dado oficial: compara nossa contagem com o limite diário.
        limits = KNOWN_LIMITS.get(provider, {})
        rpd = limits.get("rpd")
        if rpd and limits.get("source") == "local":
            used = today_usage().get(provider, {}).get("ok_calls", 0)
            return used / rpd >= threshold
    except Exception:
        pass
    return False


def report() -> list[dict]:
    """
    Visão unificada por provedor: o que sabemos de cota + uso de hoje.

    `source` diz de onde veio o número — 'headers'/'endpoint' é dado do
    provedor; 'local' é estimativa nossa por contagem.
    """
    usage = today_usage()
    quota = last_quota()
    out = []

    for provider, limits in KNOWN_LIMITS.items():
        u = usage.get(provider, {})
        q = quota.get(provider, {})
        rpd = limits.get("rpd")
        used = u.get("ok_calls", 0)

        out.append({
            "provider": provider,
            "source": limits.get("source"),
            "calls_today": used,
            "failed_today": u.get("failed", 0),
            "tokens_today": u.get("tokens", 0),
            "avg_latency": u.get("avg_latency"),
            "rpd_limit": rpd,
            "rpd_used_pct": round(100 * used / rpd, 1) if rpd else None,
            # Vindos dos headers (quando existem):
            "remaining_requests": q.get("remaining_requests"),
            "limit_requests": q.get("limit_requests"),
            "remaining_tokens": q.get("remaining_tokens"),
            "limit_tokens": q.get("limit_tokens"),
            "reset_requests": q.get("reset_requests"),
            "quota_read_at": q.get("ts"),
        })

    return out


init()
