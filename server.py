#!/usr/bin/env python
"""
Servidor local compatível com a API da OpenAI.

Expõe a cascata de fallback como se fosse a API da OpenAI, para você
plugar em qualquer ferramenta que fale esse protocolo (Cline, Continue,
Aider, etc.). Cada PERFIL vira um "modelo":

    router-code   -> perfil code   (gerar/refatorar codigo)
    router-plan   -> perfil plan   (arquitetura, decisoes)
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
import sys
import time
import uuid
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
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


def resolve_profile(model: str) -> str:
    """Converte o nome do 'modelo' pedido no perfil correspondente."""
    name = model[len(MODEL_PREFIX):] if model.startswith(MODEL_PREFIX) else model
    if name in PROFILES:
        return name
    # Nome desconhecido (a extensão pode mandar "gpt-4o") — usa um padrão útil.
    return "code"


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

    router = LLMRouter(
        profile=profile,
        on_event=lambda msg: print(f"  {msg}", file=sys.stderr, flush=True),
    )

    print(f"\n-> {req.model} (perfil={profile}) stream={req.stream}", file=sys.stderr, flush=True)

    try:
        result = router.chat(
            messages, max_tokens=max_tokens, temperature=req.temperature
        )
    except RouterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    model_label = f"{MODEL_PREFIX}{profile}"

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
