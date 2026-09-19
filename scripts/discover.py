"""
Descoberta de modelos REAIS por provedor.

Consulta o endpoint /models de cada provedor com a sua chave e grava os
IDs efetivamente disponíveis em providers.local.json.

Por que isso existe: listas de "IA grátis" na internet (inclusive o repo
que originou este projeto) publicam nomes de modelo que não existem.
Só confiamos no que a própria API responde.

Uso:
    .venv/Scripts/python.exe scripts/discover.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

TIMEOUT = 30.0

# Cada provedor expõe um catálogo de modelos. A maioria segue o padrão
# OpenAI (/models + Bearer token); o Google usa um formato próprio.
PROVIDERS = [
    {
        "key": "google",
        "label": "Google AI Studio",
        "env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models_url": "https://generativelanguage.googleapis.com/v1beta/openai/models",
        "auth": "bearer",
    },
    {
        "key": "groq",
        "label": "Groq Cloud",
        "env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "models_url": "https://api.groq.com/openai/v1/models",
        "auth": "bearer",
    },
    {
        "key": "cerebras",
        "label": "Cerebras",
        "env": "CEREBRAS_API_KEY",
        "base_url": "https://api.cerebras.ai/v1",
        "models_url": "https://api.cerebras.ai/v1/models",
        "auth": "bearer",
    },
    {
        "key": "nvidia",
        "label": "NVIDIA NIM",
        "env": "NVIDIA_API_KEY",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "models_url": "https://integrate.api.nvidia.com/v1/models",
        "auth": "bearer",
    },
    {
        "key": "openrouter",
        "label": "OpenRouter",
        "env": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "models_url": "https://openrouter.ai/api/v1/models",
        "auth": "bearer",
    },
    {
        "key": "mistral",
        "label": "Mistral AI",
        "env": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
        "models_url": "https://api.mistral.ai/v1/models",
        "auth": "bearer",
    },
]


def fetch_models(provider: dict, api_key: str) -> tuple[list[str], str | None]:
    """Retorna (lista_de_ids, erro). Nunca inclui a chave na mensagem de erro."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = httpx.get(provider["models_url"], headers=headers, timeout=TIMEOUT)
    except Exception as exc:  # rede, DNS, timeout
        return [], f"{type(exc).__name__}: {exc}"

    if resp.status_code != 200:
        # Trunca o corpo para não vazar eco de credenciais em respostas verbosas.
        return [], f"HTTP {resp.status_code}: {resp.text[:160]}"

    try:
        payload = resp.json()
    except Exception:
        return [], "resposta não é JSON válido"

    items = payload.get("data") or payload.get("models") or []
    ids: list[str] = []
    for item in items:
        mid = item.get("id") or item.get("name")
        if mid:
            # Google devolve "models/gemini-..."; normalizamos para o ID puro.
            ids.append(mid.split("/", 1)[1] if mid.startswith("models/") else mid)
    return sorted(set(ids)), None


def main() -> int:
    catalog: dict[str, dict] = {}
    print("Consultando catálogos de modelos...\n")

    for provider in PROVIDERS:
        api_key = (os.getenv(provider["env"]) or "").strip()
        label = provider["label"]

        if not api_key:
            print(f"  [ ] {label:20} sem chave, pulando")
            continue

        ids, error = fetch_models(provider, api_key)
        if error:
            print(f"  [!] {label:20} FALHOU  -> {error}")
            continue

        print(f"  [OK] {label:20} {len(ids)} modelos")
        catalog[provider["key"]] = {
            "label": label,
            "env": provider["env"],
            "base_url": provider["base_url"],
            "models": ids,
        }

    out = ROOT / "providers.local.json"
    out.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nCatálogo salvo em {out.name} ({len(catalog)} provedores ativos)")
    return 0 if catalog else 1


if __name__ == "__main__":
    sys.exit(main())
