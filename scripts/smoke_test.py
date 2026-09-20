"""
Teste de fumaça: faz uma chamada real de chat em cada provedor/modelo
candidato e mede a latência.

Serve para escolher a ordem da cascata com base em comportamento real,
não em promessa de documentação.

Uso:
    .venv/Scripts/python.exe scripts/smoke_test.py
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PROMPT = "Responda apenas com a palavra: OK"

# Candidatos por provedor, em ordem de preferência.
CANDIDATES = [
    ("google", "GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/",
     ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash"]),
    ("groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1",
     ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]),
    ("cerebras", "CEREBRAS_API_KEY", "https://api.cerebras.ai/v1",
     ["qwen-3.8-27b", "gpt-oss-120b"]),
    ("nvidia", "NVIDIA_API_KEY", "https://integrate.api.nvidia.com/v1",
     ["z-ai/glm-5.3-flash", "nvidia/nemotron-3.5-lightning-30b-a3b", "moonshotai/kimi-k3"]),
    ("mistral", "MISTRAL_API_KEY", "https://api.mistral.ai/v1",
     ["mistral-small-latest", "mistral-medium-latest"]),
    ("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1",
     ["qwen/qwen3.8-27b:free", "z-ai/glm-5.2:free"]),
]


def main() -> None:
    results: dict[str, list[dict]] = {}

    for pkey, env, base_url, models in CANDIDATES:
        api_key = (os.getenv(env) or "").strip()
        if not api_key:
            continue

        print(f"\n=== {pkey} ===")
        client = OpenAI(base_url=base_url, api_key=api_key, timeout=45.0, max_retries=0)
        ok_models = []

        for model in models:
            start = time.perf_counter()
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": PROMPT}],
                    max_tokens=2000,
                )
                elapsed = time.perf_counter() - start
                text = (resp.choices[0].message.content or "").strip()
                usage = resp.usage
                total = getattr(usage, "total_tokens", "?") if usage else "?"
                print(f"  [OK]  {model:45} {elapsed:5.2f}s  tok={total}  -> {text[:40]!r}")
                ok_models.append({"model": model, "latency": round(elapsed, 2)})
            except Exception as exc:
                msg = str(exc).replace(api_key, "***")[:110]
                print(f"  [!!]  {model:45} {type(exc).__name__}: {msg}")

        if ok_models:
            results[pkey] = ok_models

    print("\n\n===== RESUMO (provedores utilizáveis) =====")
    for pkey, models in results.items():
        best = min(models, key=lambda m: m["latency"])
        print(f"  {pkey:12} melhor={best['model']:40} {best['latency']:5.2f}s")


if __name__ == "__main__":
    main()
