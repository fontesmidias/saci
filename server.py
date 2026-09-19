#!/usr/bin/env python
"""
Servidor local compatível com a API da OpenAI.

Expõe a cascata de fallback como se fosse a API da OpenAI, para você
plugar em qualquer ferramenta que fale esse protocolo (Cline, Continue,
Aider, etc.). Cada PERFIL vira um "modelo":

    router-code   -> perfil code   (gerar/refatorar codigo)
    router-plan   -> perfil plan   (arquitetura, decisoes)
    router-agent  -> perfil agent  (Cline/Continue: prompts grandes)
    router-fast   -> perfil fast   (perguntas rapidas)
    router-long   -> perfil long   (contexto grande)
    router-pt     -> perfil pt     (portugues corporativo)

Subir:
    .venv\\Scripts\\python.exe server.py
    (ou: serve.cmd)

Configurar na extensão:
    Base URL: http://127.0.0.1:8000/v1
    API Key:  qualquer coisa (nao e verificada — o servidor e local)
    Model:    router-code

Atenção: o servidor escuta apenas em 127.0.0.1 (sua máquina). Ele não
exige autenticação, então NÃO o exponha na rede sem antes adicionar uma.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from llmrouter import LLMRouter, RouterError  # noqa: E402
from llmrouter.providers import PROFILES  # noqa: E402

app = FastAPI(title="LLM Router", version="0.1.0")

MODEL_PREFIX = "router-"


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool", "developer"]
    content: Any = ""


class ChatRequest(BaseModel):
    model: str = "router-fast"
    messages: list[ChatMessage]
    max_tokens: int | None = Field(default=None)
    max_completion_tokens: int | None = Field(default=None)
    temperature: float = 0.7
    stream: bool = False


# Acima deste tamanho (em caracteres) o Groq devolve HTTP 413, então
# trocamos para o perfil "agent", que começa por provedores que aguentam
# prompts grandes. ~24k chars ≈ 6k tokens, com folga sobre o limite real.
LARGE_PROMPT_CHARS = 24_000


def resolve_profile(model: str) -> str:
    """Converte o nome do 'modelo' pedido no perfil correspondente."""
    name = model[len(MODEL_PREFIX):] if model.startswith(MODEL_PREFIX) else model
    if name in PROFILES:
        return name
    # Nome desconhecido (a extensão pode mandar "gpt-4o") — usa um padrão útil.
    return "code"


def adjust_for_size(profile: str, messages: list[dict]) -> str:
    """
    Promove para o perfil 'agent' quando o prompt é grande demais.

    Extensões como o Cline mandam system prompt + arquivos + histórico, o
    que estoura o limite por requisição do Groq. Sem isso, toda chamada
    gastaria uma tentativa fadada ao 413 antes de cair para o próximo.
    """
    if profile in ("agent", "long"):
        return profile
    size = sum(len(m.get("content") or "") for m in messages)
    return "agent" if size > LARGE_PROMPT_CHARS else profile


def flatten(content: Any) -> str:
    """Achata content multimodal (lista de blocos) para texto puro."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(p for p in parts if p)
    return str(content or "")


@app.get("/v1/models")
def list_models() -> dict:
    """Lista os perfis como modelos — é o que a extensão mostra no seletor."""
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": f"{MODEL_PREFIX}{name}",
                "object": "model",
                "created": now,
                "owned_by": "llm-router",
            }
            for name in PROFILES
        ],
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "profiles": list(PROFILES)}


def _system_stats() -> dict:
    """RAM do servidor e da máquina — para você saber se pesa no PC."""
    stats: dict = {}
    try:
        import resource  # POSIX
        stats["server_ram_mb"] = round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1
        )
    except Exception:
        try:  # Windows
            import ctypes

            class MEM(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = MEM()
            counters.cb = ctypes.sizeof(MEM)
            ctypes.windll.psapi.GetProcessMemoryInfo(
                ctypes.windll.kernel32.GetCurrentProcess(),
                ctypes.byref(counters), counters.cb,
            )
            stats["server_ram_mb"] = round(counters.WorkingSetSize / 1048576, 1)

            class MEMSTAT(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            mem = MEMSTAT()
            mem.dwLength = ctypes.sizeof(MEMSTAT)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            stats["free_ram_mb"] = round(mem.ullAvailPhys / 1048576)
            stats["total_ram_mb"] = round(mem.ullTotalPhys / 1048576)
        except Exception:
            pass
    return stats


@app.get("/usage")
def usage_report() -> dict:
    """Consumo e cota por (provedor, modelo). JSON que alimenta o painel."""
    from llmrouter import usage as usage_db

    rows = usage_db.report()
    return {
        "providers": rows,
        "exhausted": [r["provider"] for r in rows if r["exhausted"]],
        "system": _system_stats(),
    }


@app.get("/status")
def status_line() -> dict:
    """
    Resumo enxuto para a barra de status do VSCode.

    Devolve o provedor em uso, quanto da cota foi gasta e quando reseta.
    """
    from llmrouter import usage as usage_db

    rows = usage_db.report()
    calls = sum(r["calls_today"] for r in rows)
    tokens = sum(r["tokens_today"] for r in rows)

    # O provedor "ativo" é o primeiro da cascata que ainda tem cota.
    active, pct, reset = None, None, None
    for r in rows:
        for m in r["models"]:
            if m["exhausted"]:
                continue
            if m["limit_tokens"] and m["remaining_tokens"] is not None:
                used_pct = 100 * (1 - m["remaining_tokens"] / m["limit_tokens"])
                if active is None or used_pct < pct:
                    active, pct = r["provider"], used_pct
                    reset = m["reset_tokens_in"]
        if active:
            break

    return {
        "active": active,
        "used_pct": round(pct, 1) if pct is not None else None,
        "reset_in": reset,
        "calls_today": calls,
        "tokens_today": tokens,
        "exhausted": [r["provider"] for r in rows if r["exhausted"]],
    }


class PrefsUpdate(BaseModel):
    profile: str | None = None
    pin_provider: str | None = None
    pin_model: str | None = None
    clear_pin: bool = False


@app.get("/prefs")
def get_prefs() -> dict:
    """Perfil ativo, trava manual e as opções disponíveis para o seletor."""
    from llmrouter import prefs
    from llmrouter.providers import PROVIDERS

    current = prefs.load()
    options = [
        {
            "profile": name,
            "steps": [
                {"provider": pkey, "label": PROVIDERS[pkey].label, "model": model}
                for pkey, model in steps
            ],
        }
        for name, steps in PROFILES.items()
    ]
    return {
        "profile": current.get("profile"),
        "pin": current.get("pin"),
        "profiles": options,
        "env_profile": os.getenv("LLM_ROUTER_PROFILE"),
    }


@app.post("/prefs")
def set_prefs(update: PrefsUpdate) -> dict:
    """Troca o perfil ativo ou trava um modelo. Vale na chamada seguinte."""
    from llmrouter import prefs

    changes: dict = {}
    if update.clear_pin:
        changes["pin"] = None
    elif update.pin_provider and update.pin_model:
        changes["pin"] = {"provider": update.pin_provider, "model": update.pin_model}

    if update.profile is not None:
        changes["profile"] = update.profile or None

    saved = prefs.save(**changes) if changes else prefs.load()
    print(f"\n-> prefs: {saved}", file=sys.stderr, flush=True)
    return saved


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    """Painel visual. Abra no navegador ou no Simple Browser do VSCode."""
    return (Path(__file__).parent / "llmrouter" / "dashboard.html").read_text(
        encoding="utf-8"
    )


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    profile = resolve_profile(req.model)
    messages = [
        {"role": m.role, "content": flatten(m.content)} for m in req.messages
    ]
    # Algumas extensões mandam "developer" em vez de "system".
    for m in messages:
        if m["role"] == "developer":
            m["role"] = "system"

    max_tokens = req.max_completion_tokens or req.max_tokens or 4096

    chars = sum(len(m.get("content") or "") for m in messages)
    routed = adjust_for_size(profile, messages)

    router = LLMRouter(
        profile=routed,
        on_event=lambda msg: print(f"  {msg}", file=sys.stderr, flush=True),
    )

    note = f" (prompt grande: {chars} chars -> {routed})" if routed != profile else ""
    print(
        f"\n-> {req.model} (perfil={routed}) stream={req.stream}{note}",
        file=sys.stderr,
        flush=True,
    )

    try:
        result = router.chat(
            messages, max_tokens=max_tokens, temperature=req.temperature
        )
    except RouterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    model_label = f"{MODEL_PREFIX}{routed}"

    if not req.stream:
        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": model_label,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result.content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": result.total_tokens or 0,
            },
            # Extra nosso: útil para depurar quem atendeu.
            "x_router": {
                "provider": result.provider,
                "model": result.model,
                "latency": result.latency,
                "failed_attempts": len(result.attempts),
            },
        }

    # Streaming: nossos provedores respondem inteiro, então emitimos a
    # resposta em pedaços para a extensão renderizar progressivamente.
    def event_stream():
        base = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_label,
        }

        first = {**base, "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]}
        yield f"data: {json.dumps(first)}\n\n"

        text = result.content
        size = 24
        for i in range(0, len(text), size):
            chunk = {
                **base,
                "choices": [
                    {"index": 0, "delta": {"content": text[i:i + size]}, "finish_reason": None}
                ],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

        last = {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
        yield f"data: {json.dumps(last)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    print("=" * 58, file=sys.stderr)
    print("  LLM Router — servidor local", file=sys.stderr)
    print("=" * 58, file=sys.stderr)
    print("  Base URL : http://127.0.0.1:8000/v1", file=sys.stderr)
    print("  API Key  : qualquer valor (nao e verificada)", file=sys.stderr)
    print(f"  Modelos  : {', '.join(MODEL_PREFIX + p for p in PROFILES)}", file=sys.stderr)
    print("=" * 58, file=sys.stderr)

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
