"""
Contabilidade de consumo por (provedor, modelo).

Por que a granularidade é por MODELO, e não só por provedor — medido em
19/09/2026:

    Groq, requisições : 999/1000 nos 3 modelos, MESMO reset -> por CONTA
    Groq, tokens      : 7860 / 7559 / 7487 por modelo       -> por MODELO
    Mistral           : codestral 125 req/min, 7b 188       -> por MODELO

Ou seja, um modelo pode estar sem tokens enquanto outro do mesmo
provedor está livre. Tratar o provedor como unidade desperdiçaria cota.

Duas fontes de verdade, combinadas:

1. HEADERS DO PROVEDOR (oficial, quando existe)
   Groq e Mistral devolvem cota restante e tempo de reset a cada
   resposta. É o dado de quem cobra.

2. CONTAGEM LOCAL (nossa, sempre)
   Google e NVIDIA não informam nada. Somamos tokens no SQLite e
   comparamos com os limites conhecidos.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "usage.db"

_lock = threading.Lock()

# Limites do free tier. 'source' diz se o número vem do provedor ou é nosso.
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

-- Cota por (provedor, modelo). reset_*_at guarda o INSTANTE do reset,
-- para o painel mostrar contagem regressiva ao vivo.
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
        # A tabela quota mudou de chave (provider) para (provider, model).
        # Se existir no formato antigo, recria: é só cache, não histórico.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(quota)").fetchall()}
        if cols and "model" not in cols:
            conn.execute("DROP TABLE quota")
        conn.executescript(SCHEMA)


def parse_duration(text: str | None) -> float | None:
    """
    Converte o tempo de reset do provedor em segundos.

    Formatos vistos: '1m26.4s', '3.847s', '500ms', '1h2m3s'.
    """
    if not text:
        return None
    total = 0.0
    found = False
    for value, unit in re.findall(r"([\d.]+)\s*(ms|h|m|s)", str(text)):
        try:
            v = float(value)
        except ValueError:
            continue
        total += v * {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}[unit]
        found = True
    return round(total, 3) if found else None


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


def record_quota_headers(provider: str, model: str, headers) -> None:
    """
    Extrai cota dos headers da resposta, quando o provedor os envia.

    Groq:    x-ratelimit-{limit,remaining,reset}-{requests,tokens}
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

    def reset_at(*names) -> str | None:
        """Converte '1m26.4s' no instante absoluto do reset."""
        for n in names:
            secs = parse_duration(headers.get(n))
            if secs is not None:
                moment = datetime.now(timezone.utc) + timedelta(seconds=secs)
                return moment.isoformat(timespec="seconds")
        return None

    limit_req = num("x-ratelimit-limit-requests", "x-ratelimit-limit-req-minute")
    remain_req = num("x-ratelimit-remaining-requests", "x-ratelimit-remaining-req-minute")
    limit_tok = num("x-ratelimit-limit-tokens", "x-ratelimit-limit-tokens-minute")
    remain_tok = num("x-ratelimit-remaining-tokens", "x-ratelimit-remaining-tokens-minute")

    if limit_req is None and limit_tok is None:
        return  # provedor não informa cota

    with _lock, _db() as conn:
        conn.execute(
            "INSERT INTO quota (provider, model, ts, limit_requests, remaining_requests,"
            " limit_tokens, remaining_tokens, reset_requests_at, reset_tokens_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(provider, model) DO UPDATE SET"
            " ts=excluded.ts, limit_requests=excluded.limit_requests,"
            " remaining_requests=excluded.remaining_requests,"
            " limit_tokens=excluded.limit_tokens,"
            " remaining_tokens=excluded.remaining_tokens,"
            " reset_requests_at=excluded.reset_requests_at,"
            " reset_tokens_at=excluded.reset_tokens_at",
            (
                provider,
                model,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                limit_req,
                remain_req,
                limit_tok,
                remain_tok,
                reset_at("x-ratelimit-reset-requests"),
                reset_at("x-ratelimit-reset-tokens"),
            ),
        )


def _seconds_until(iso: str | None) -> float | None:
    """Segundos que faltam até um instante ISO. Negativo vira 0."""
    if not iso:
        return None
    try:
        moment = datetime.fromisoformat(iso)
    except ValueError:
        return None
    delta = (moment - datetime.now(timezone.utc)).total_seconds()
    return max(0.0, round(delta, 1))


def today_usage() -> dict[tuple[str, str], dict]:
    """Consumo de hoje (UTC) por (provedor, modelo)."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _lock, _db() as conn:
        rows = conn.execute(
            "SELECT provider, model,"
            "       SUM(ok) AS ok_calls,"
            "       COUNT(*) - SUM(ok) AS failed,"
            "       SUM(tokens) AS tokens,"
            "       AVG(CASE WHEN ok=1 THEN latency END) AS avg_latency"
            " FROM calls WHERE day = ? GROUP BY provider, model",
            (day,),
        ).fetchall()
    return {
        (r["provider"], r["model"]): {
            "ok_calls": r["ok_calls"] or 0,
            "failed": r["failed"] or 0,
            "tokens": r["tokens"] or 0,
            "avg_latency": round(r["avg_latency"], 2) if r["avg_latency"] else None,
        }
        for r in rows
    }


def provider_usage() -> dict[str, dict]:
    """Consumo de hoje agregado por provedor."""
    out: dict[str, dict] = {}
    for (provider, _model), u in today_usage().items():
        acc = out.setdefault(provider, {"ok_calls": 0, "failed": 0, "tokens": 0})
        acc["ok_calls"] += u["ok_calls"]
        acc["failed"] += u["failed"]
        acc["tokens"] += u["tokens"]
    return out


def last_quota() -> dict[tuple[str, str], dict]:
    """Última cota lida dos headers, por (provedor, modelo)."""
    with _lock, _db() as conn:
        rows = conn.execute("SELECT * FROM quota").fetchall()
    return {(r["provider"], r["model"]): dict(r) for r in rows}


def is_exhausted(provider: str, model: str | None = None, threshold: float = 0.95) -> bool:
    """
    Diz se um MODELO específico está sem cota.

    Sem `model`, responde pelo provedor: só é considerado esgotado se
    TODOS os modelos conhecidos dele estiverem no limite — porque os
    tokens são contados por modelo.

    Na dúvida retorna False: é melhor tentar e falhar do que pular um
    modelo que estava disponível.
    """
    try:
        quota = last_quota()

        if model is None:
            entries = [(p, m) for (p, m) in quota if p == provider]
            if not entries:
                return _local_exhausted(provider, threshold)
            return all(is_exhausted(p, m, threshold) for p, m in entries)

        q = quota.get((provider, model))
        if q is None:
            return _local_exhausted(provider, threshold)

        # Se a janela de reset já passou, a cota voltou.
        rem_req, lim_req = q.get("remaining_requests"), q.get("limit_requests")
        if rem_req is not None and lim_req:
            if _seconds_until(q.get("reset_requests_at")) == 0:
                return False
            if rem_req <= 0 or 1 - (rem_req / lim_req) >= threshold:
                return True

        rem_tok, lim_tok = q.get("remaining_tokens"), q.get("limit_tokens")
        if rem_tok is not None and lim_tok:
            if _seconds_until(q.get("reset_tokens_at")) == 0:
                return False
            if rem_tok <= 0 or 1 - (rem_tok / lim_tok) >= threshold:
                return True
    except Exception:
        pass
    return False


def _local_exhausted(provider: str, threshold: float) -> bool:
    """Para provedores sem headers: compara nossa contagem com o limite diário."""
    limits = KNOWN_LIMITS.get(provider, {})
    rpd = limits.get("rpd")
    if rpd and limits.get("source") == "local":
        used = provider_usage().get(provider, {}).get("ok_calls", 0)
        return used / rpd >= threshold
    return False


def report() -> list[dict]:
    """
    Visão por provedor, com detalhe por modelo.

    `source` diz de onde veio o número: 'headers'/'endpoint' é dado do
    provedor; 'local' é estimativa nossa por contagem.
    """
    by_model = today_usage()
    quota = last_quota()
    prov_usage = provider_usage()
    out = []

    for provider, limits in KNOWN_LIMITS.items():
        pu = prov_usage.get(provider, {})
        rpd = limits.get("rpd")
        used = pu.get("ok_calls", 0)

        models = []
        seen = {m for (p, m) in by_model if p == provider} | {
            m for (p, m) in quota if p == provider
        }
        for model in sorted(seen):
            u = by_model.get((provider, model), {})
            q = quota.get((provider, model), {})
            models.append({
                "model": model,
                "calls": u.get("ok_calls", 0),
                "failed": u.get("failed", 0),
                "tokens": u.get("tokens", 0),
                "avg_latency": u.get("avg_latency"),
                "limit_requests": q.get("limit_requests"),
                "remaining_requests": q.get("remaining_requests"),
                "limit_tokens": q.get("limit_tokens"),
                "remaining_tokens": q.get("remaining_tokens"),
                "reset_requests_in": _seconds_until(q.get("reset_requests_at")),
                "reset_tokens_in": _seconds_until(q.get("reset_tokens_at")),
                "exhausted": is_exhausted(provider, model),
            })

        out.append({
            "provider": provider,
            "source": limits.get("source"),
            "calls_today": used,
            "failed_today": pu.get("failed", 0),
            "tokens_today": pu.get("tokens", 0),
            "rpd_limit": rpd,
            "rpd_used_pct": round(100 * used / rpd, 1) if rpd else None,
            "exhausted": is_exhausted(provider),
            "models": models,
        })

    return out


init()
