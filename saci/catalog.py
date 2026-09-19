"""
Catálogo automático de modelos por provedor.

O problema que isto resolve: cada provedor publica dezenas de modelos,
mas só um (OpenRouter) diz no catálogo quais são grátis. Para os outros
só se descobre testando. Ninguém quer manter essa lista à mão.

O ciclo, por provedor:

    1. DESCOBRIR  GET /models -> lista bruta
    2. FILTRAR    descarta o que não é chat (embedding, TTS, imagem,
                  guard, whisper...) por metadado ou nome
    3. SONDAR     uma chamada mínima em cada modelo NOVO, uma vez.
                  200 -> ok | 402/403 -> pago | 404/410 -> removido
                  429 -> sem cota agora | 5xx/timeout -> erro
    4. GUARDAR    veredito, latência, contexto, quando foi visto
    5. REVISAR    diariamente: modelos que sumiram do catálogo duas
                  vezes seguidas viram "gone"; erros são re-sondados
                  após 7 dias; "ok" após 14 (para pegar remoção
                  silenciosa).

A sondagem gasta cota — por isso é uma vez por modelo, com paralelismo
limitado ao RPM de cada provedor, e nunca em modelo já julgado "pago"
ou "gone" (esses só voltam a ser testados após 30 dias).

O router usa `verified_models(provider)` para expandir entradas de
perfil sem modelo fixo e para a cauda genérica: um provedor novo, com
a chave recém-colada, entra na cascata sozinho depois da primeira
sondagem.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Callable

import httpx
from dotenv import load_dotenv

from . import paths
from .providers import PROVIDERS, Provider

ROOT = paths.REPO_ROOT  # mantido por compatibilidade; prefira paths.data_dir()

_lock = threading.Lock()
_refresh_lock = threading.Lock()

PROBE_PROMPT = [{"role": "user", "content": "Responda apenas: OK"}]
PROBE_MAX_TOKENS = 64          # pequeno, mas suficiente p/ modelos que "pensam"
PROBE_TIMEOUT = 25.0

REPROBE_OK_DAYS = 14
REPROBE_ERROR_DAYS = 7
REPROBE_RATELIMIT_HOURS = 1    # 429 é transitório: tenta de novo na próxima hora
REPROBE_PAID_DAYS = 30
GONE_AFTER_MISSES = 2          # sumiu de 2 refreshes seguidos -> gone

# Paralelismo de sondagem por provedor (respeita o RPM do free tier).
PARALLEL = {"groq": 3, "google": 2, "mistral": 1, "nvidia": 4, "openrouter": 2}
DEFAULT_PARALLEL = 2
# Pausa entre sondagens por worker, derivada do RPM conhecido.
RPM_HINT = {"groq": 30, "google": 15, "mistral": 30, "nvidia": 40,
            "openrouter": 20, "llm7": 20, "sambanova": 30, "hyperbolic": 60,
            "huggingface": 30, "cerebras": 30}

# Qualquer coisa com estes termos no id não é chat de texto.
NOT_CHAT = re.compile(
    r"embed|rerank|guard|safety|moderat|whisper|tts|transcrib|speech|audio|"
    r"image|imagen|video|veo|lyria|music|live|robotic|parse|ocr|reward|"
    r"computer-use|deep-research|antigravity|orpheus|classif|vision-only|"
    r"omni-|translate|nano-banana|-vl-|chroma|krea|dark-beast",
    re.I,
)

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat(timespec="seconds")


@contextmanager
def _db():
    conn = sqlite3.connect(paths.db_path(), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    """Garante o schema atual. As tabelas vivem em saci/migrations.py."""
    from . import migrations
    with _lock:
        migrations.migrate()


# ---------------------------------------------------------------------
# 1. DESCOBRIR + 2. FILTRAR
# ---------------------------------------------------------------------

def _api_key(provider: Provider) -> str:
    import os
    load_dotenv(paths.env_path())
    if not provider.env:
        return "unused"
    return (os.getenv(provider.env) or "").strip()


def _is_chat(provider_key: str, item: dict) -> bool:
    """Decide se o item do catálogo é um modelo de chat de texto."""
    mid = str(item.get("id") or "")
    if not mid or NOT_CHAT.search(mid):
        return False

    if provider_key == "groq":
        if item.get("active") is False:
            return False
        out = item.get("output_modalities") or ["text"]
        return "text" in out

    if provider_key == "mistral":
        caps = item.get("capabilities") or {}
        if caps.get("completion_chat") is False:
            return False
        if item.get("deprecation"):
            return False
        return True

    if provider_key == "openrouter":
        exp = item.get("expiration_date")
        if exp and str(exp) < _now().strftime("%Y-%m-%d"):
            return False
        return True

    return True


def _free_by_catalog(provider_key: str, item: dict) -> int | None:
    """Só o OpenRouter publica preço. Para os outros, não sabemos."""
    if provider_key == "openrouter":
        pricing = item.get("pricing") or {}
        try:
            return 1 if float(pricing.get("prompt", 1)) == 0 else 0
        except (TypeError, ValueError):
            return None
    return None


def fetch_catalog(provider: Provider) -> tuple[list[dict], str | None]:
    """GET /models normalizado. Retorna (itens, erro)."""
    key = _api_key(provider)
    if provider.env and not key:
        return [], "sem chave"
    url = provider.base_url.rstrip("/") + "/models"
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=40)
    except Exception as exc:
        return [], f"{type(exc).__name__}"
    if r.status_code == 401:
        return [], "chave inválida (401)"
    if r.status_code != 200:
        return [], f"HTTP {r.status_code}"
    try:
        payload = r.json()
    except Exception:
        return [], "resposta não é JSON"
    items = payload.get("data") or payload.get("models") or payload
    out = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        mid = it.get("id") or it.get("name")
        if not mid:
            continue
        mid = str(mid)
        if mid.startswith("models/"):
            mid = mid.split("/", 1)[1]
        it = {**it, "id": mid}
        out.append(it)
    return out, None


# ---------------------------------------------------------------------
# 3. SONDAR
# ---------------------------------------------------------------------

def probe(provider: Provider, model: str, *, key: str | None = None) -> tuple[str, str, int | None]:
    """
    Uma chamada mínima. Retorna (status, detalhe, latência_ms).

    Só a saída é lida; a chave nunca entra no detalhe.

    `key` permite testar uma chave que ainda NÃO foi salva no .env — é o
    que a tela de configurações usa no botão "testar" antes de gravar.
    Sem ela, lê a chave já configurada (comportamento de sempre).
    """
    if key is None:
        key = _api_key(provider)
    url = provider.base_url.rstrip("/") + "/chat/completions"
    body = {"model": model, "messages": PROBE_PROMPT, "max_tokens": PROBE_MAX_TOKENS}
    t0 = time.perf_counter()
    try:
        r = httpx.post(url, json=body, headers={"Authorization": f"Bearer {key}"},
                       timeout=PROBE_TIMEOUT)
    except httpx.TimeoutException:
        return "error", "timeout", None
    except Exception as exc:
        return "error", type(exc).__name__, None
    ms = int((time.perf_counter() - t0) * 1000)

    if r.status_code == 200:
        try:
            content = r.json()["choices"][0]["message"].get("content") or ""
        except Exception:
            return "error", "resposta sem choices", ms
        return "ok", ("vazio" if not content.strip() else "")[:80], ms

    body_txt = r.text[:120].replace(key, "***") if key else r.text[:120]
    code = r.status_code
    if code == 401:
        return "auth", "chave inválida", ms
    if code in (402, 403):
        return "paid", f"HTTP {code}: exige plano/pagamento", ms
    if code in (404, 410):
        return "gone", f"HTTP {code}", ms
    if code == 429:
        return "ratelimited", "HTTP 429", ms
    if code == 400 and "unavailable" in body_txt.lower():
        return "error", "indisponível (400)", ms
    return "error", f"HTTP {code}: {body_txt[:60]}", ms


# ---------------------------------------------------------------------
# 4. GUARDAR + 5. REVISAR
# ---------------------------------------------------------------------

def _due_for_probe(row: sqlite3.Row) -> bool:
    st = row["status"]
    if st == "new":
        return True
    if st == "gone":
        return False
    last = row["last_probe"]
    if not last:
        return True
    age = _now() - datetime.fromisoformat(last)
    if st == "ok":
        return age > timedelta(days=REPROBE_OK_DAYS)
    if st == "ratelimited":
        return age > timedelta(hours=REPROBE_RATELIMIT_HOURS)
    if st in ("error", "auth"):
        return age > timedelta(days=REPROBE_ERROR_DAYS)
    if st == "paid":
        return age > timedelta(days=REPROBE_PAID_DAYS)
    return False


def refresh_provider(
    provider: Provider,
    *,
    do_probe: bool = True,
    on_event: Callable[[str], None] | None = None,
) -> dict:
    """Descobre, filtra, sonda o que for devido e grava. Retorna resumo."""
    say = on_event or (lambda m: None)
    items, err = fetch_catalog(provider)
    now = _iso()
    summary = {"provider": provider.key, "listed": len(items), "chat": 0,
               "probed": 0, "ok": 0, "error": err}

    if err:
        say(f"[catálogo] {provider.label}: {err}")
        with _lock, _db() as conn:
            conn.execute(
                "INSERT INTO catalog_runs (provider, ts, listed, chat, probed, ok, error)"
                " VALUES (?,?,?,?,?,?,?)",
                (provider.key, now, 0, 0, 0, 0, err))
        return summary

    chat = [it for it in items if _is_chat(provider.key, it)]
    summary["chat"] = len(chat)
    seen = {it["id"] for it in chat}

    with _lock, _db() as conn:
        for it in chat:
            mid = it["id"]
            free = _free_by_catalog(provider.key, it)
            ctx = it.get("context_length") or it.get("context_window") \
                or it.get("max_context_length")
            name = it.get("name") or it.get("display_name")
            row = conn.execute(
                "SELECT status FROM models WHERE provider=? AND model=?",
                (provider.key, mid)).fetchone()
            if row is None:
                # Pago pelo catálogo (OpenRouter) já nasce julgado: não gasta sonda.
                status = "paid" if free == 0 else "new"
                conn.execute(
                    "INSERT INTO models (provider, model, name, context, free_by_catalog,"
                    " status, first_seen, last_seen, misses)"
                    " VALUES (?,?,?,?,?,?,?,?,0)",
                    (provider.key, mid, name, ctx, free, status, now, now))
            else:
                conn.execute(
                    "UPDATE models SET name=COALESCE(?,name), context=COALESCE(?,context),"
                    " free_by_catalog=COALESCE(?,free_by_catalog), last_seen=?, misses=0,"
                    " status=CASE WHEN status='gone' THEN 'new' ELSE status END"
                    " WHERE provider=? AND model=?",
                    (name, ctx, free, now, provider.key, mid))

        # Quem não apareceu: conta a falta; duas seguidas -> gone.
        rows = conn.execute(
            "SELECT model, misses FROM models WHERE provider=? AND status!='gone'",
            (provider.key,)).fetchall()
        for r in rows:
            if r["model"] in seen:
                continue
            misses = (r["misses"] or 0) + 1
            st = "gone" if misses >= GONE_AFTER_MISSES else None
            if st:
                conn.execute("UPDATE models SET misses=?, status=?, detail='sumiu do catálogo'"
                             " WHERE provider=? AND model=?",
                             (misses, st, provider.key, r["model"]))
            else:
                conn.execute("UPDATE models SET misses=? WHERE provider=? AND model=?",
                             (misses, provider.key, r["model"]))

        due = [r["model"] for r in conn.execute(
            "SELECT * FROM models WHERE provider=? ORDER BY model", (provider.key,)
        ).fetchall() if do_probe and _due_for_probe(r)]

    say(f"[catálogo] {provider.label}: {len(items)} listados, {len(chat)} de chat, "
        f"{len(due)} a sondar")

    if due:
        workers = PARALLEL.get(provider.key, DEFAULT_PARALLEL)
        pause = 60.0 / RPM_HINT.get(provider.key, 20) * workers

        def work(mid: str) -> None:
            st, detail, ms = probe(provider, mid)
            with _lock, _db() as conn:
                conn.execute(
                    "UPDATE models SET status=?, detail=?, latency_ms=COALESCE(?,latency_ms),"
                    " probes=probes+1, last_probe=? WHERE provider=? AND model=?",
                    (st, detail or None, ms, _iso(), provider.key, mid))
            tag = {"ok": "OK", "paid": "pago", "gone": "removido",
                   "ratelimited": "429", "auth": "auth"}.get(st, "erro")
            say(f"[sonda] {provider.label} / {mid}: {tag}"
                + (f" {ms}ms" if ms and st == "ok" else "")
                + (f" ({detail})" if detail and st != "ok" else ""))
            time.sleep(pause)

        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, due))
        summary["probed"] = len(due)

    with _lock, _db() as conn:
        ok = conn.execute("SELECT COUNT(*) FROM models WHERE provider=? AND status='ok'",
                          (provider.key,)).fetchone()[0]
        conn.execute(
            "INSERT INTO catalog_runs (provider, ts, listed, chat, probed, ok, error)"
            " VALUES (?,?,?,?,?,?,NULL)",
            (provider.key, _iso(), len(items), len(chat), summary["probed"], ok))
    summary["ok"] = ok
    return summary


def refresh_all(
    *,
    only_with_access: bool = True,
    do_probe: bool = True,
    on_event: Callable[[str], None] | None = None,
) -> list[dict]:
    """Roda o ciclo em todos os provedores. Serializado: um refresh por vez."""
    import os
    load_dotenv(paths.env_path())
    if not _refresh_lock.acquire(blocking=False):
        (on_event or (lambda m: None))("[catálogo] refresh já em andamento")
        return []
    try:
        out = []
        for p in PROVIDERS.values():
            if only_with_access and p.env and not (os.getenv(p.env) or "").strip():
                continue
            out.append(refresh_provider(p, do_probe=do_probe, on_event=on_event))
        return out
    finally:
        _refresh_lock.release()


# ---------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------

def verified_models(provider_key: str, limit: int | None = None) -> list[str]:
    """Modelos julgados OK, os mais rápidos primeiro."""
    with _lock, _db() as conn:
        rows = conn.execute(
            "SELECT model FROM models WHERE provider=? AND status='ok'"
            " ORDER BY COALESCE(latency_ms, 999999), model",
            (provider_key,)).fetchall()
    ids = [r["model"] for r in rows]
    return ids[:limit] if limit else ids


def snapshot() -> dict:
    """Tudo que o painel precisa: modelos por provedor + última verificação."""
    with _lock, _db() as conn:
        rows = conn.execute("SELECT * FROM models ORDER BY provider, status, latency_ms").fetchall()
        runs = conn.execute(
            "SELECT provider, MAX(ts) AS ts, listed, chat, ok, error FROM catalog_runs"
            " GROUP BY provider").fetchall()
    by_prov: dict[str, list[dict]] = {}
    for r in rows:
        by_prov.setdefault(r["provider"], []).append(dict(r))
    last = {r["provider"]: dict(r) for r in runs}
    return {"models": by_prov, "last_run": last}


def last_refresh_at() -> str | None:
    with _lock, _db() as conn:
        r = conn.execute("SELECT MAX(ts) FROM catalog_runs").fetchone()
    return r[0] if r and r[0] else None


init()
