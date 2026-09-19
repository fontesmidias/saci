"""
Catálogo de provedores e perfis de tarefa.

IMPORTANTE: todo par (provedor, modelo) listado aqui foi verificado com
uma chamada real de chat em 19/09/2026. Não adicione modelo sem testar:
catálogos publicados divergem bastante do que a API aceita de fato.

Para revalidar quando algo quebrar:
    py scripts/discover.py     # que modelos existem
    py ask.py --status         # quais respondem agora
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    env: str
    base_url: str
    models: list[str] = field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------
# PROVEDORES — models[] é a ordem de preferência genérica de cada um.
# ---------------------------------------------------------------------

PROVIDERS: dict[str, Provider] = {
    "groq": Provider(
        key="groq",
        label="Groq Cloud",
        env="GROQ_API_KEY",
        base_url="https://api.groq.com/openai/v1",
        models=["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"],
        notes="LPU: ~1s. O mais rápido e estável do conjunto. ~30 RPM / 1.000 RPD.",
    ),
    "google": Provider(
        key="google",
        label="Google AI Studio",
        env="GEMINI_API_KEY",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        models=["gemini-3.6-flash", "gemini-3.8-flash", "gemini-flash-latest"],
        notes="Contexto grande e cota alta (~1.500 RPD). 3.8-flash dá 503 em pico. 2.5-* foi descontinuado.",
    ),
    "mistral": Provider(
        key="mistral",
        label="Mistral AI",
        env="MISTRAL_API_KEY",
        base_url="https://api.mistral.ai/v1",
        models=["codestral-latest", "open-mistral-7b"],
        notes="codestral-latest é especializado em código (~2s). mistral-large-latest exige plano pago (403).",
    ),
    "nvidia": Provider(
        key="nvidia",
        label="NVIDIA NIM",
        env="NVIDIA_API_KEY",
        base_url="https://integrate.api.nvidia.com/v1",
        models=["z-ai/glm-5.3", "nvidia/nemotron-3.5-lightning-30b-a3b"],
        notes="Lento (15-70s) e instável: muitos IDs dão 404/410/503. Use como reserva.",
    ),
    "openrouter": Provider(
        key="openrouter",
        label="OpenRouter",
        env="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        models=["qwen/qwen3.8-27b:free", "z-ai/glm-5.2:free"],
        notes="Modelos :free são disputados; 429 é comum. Última rede de segurança.",
    ),
    # Cerebras fora da cascata: HTTP 402 (Payment Required) — sem free tier.
}

# ---------------------------------------------------------------------
# PERFIS POR TAREFA — cada item é (provedor, modelo), em ordem de queda.
#
# "code" e "plan" vêm primeiro na sua prioridade, então recebem os
# modelos de maior capacidade que ainda respondem rápido.
# ---------------------------------------------------------------------

PROFILES: dict[str, list[tuple[str, str]]] = {
    # Gerar/refatorar código. Verificados: gpt-oss-120b 0.98s, codestral 2.20s.
    "code": [
        ("groq", "openai/gpt-oss-120b"),
        ("mistral", "codestral-latest"),
        ("groq", "qwen/qwen3.8-27b"),
        ("google", "gemini-3.6-flash"),
        ("groq", "openai/gpt-oss-20b"),
        ("nvidia", "z-ai/glm-5.3"),
        ("openrouter", "qwen/qwen3.8-27b:free"),
    ],
    # Planejar arquitetura, quebrar tarefas, decidir trade-offs.
    # Prioriza capacidade de raciocínio e contexto sobre latência.
    "plan": [
        ("groq", "openai/gpt-oss-120b"),
        ("google", "gemini-3.6-flash"),
        ("google", "gemini-3.8-flash"),
        ("groq", "qwen/qwen3.8-27b"),
        ("nvidia", "z-ai/glm-5.3"),
        ("groq", "groq/compound"),
        ("openrouter", "z-ai/glm-5.2:free"),
    ],
    # Para agentes (Cline, Continue, Aider): prompts gigantes com system
    # prompt + arquivos + histórico. O Groq rejeita com HTTP 413
    # ("request too large"), então começamos por quem aguenta o volume.
    "agent": [
        ("mistral", "codestral-latest"),
        ("google", "gemini-3.6-flash"),
        ("google", "gemini-3.8-flash"),
        ("nvidia", "z-ai/glm-5.3"),
        ("groq", "openai/gpt-oss-120b"),
    ],
    # Perguntas rápidas do dia a dia. Latência acima de tudo.
    "fast": [
        ("groq", "openai/gpt-oss-20b"),
        ("groq", "qwen/qwen3.8-27b"),
        ("mistral", "open-mistral-7b"),
        ("google", "gemini-3.6-flash"),
    ],
    # Textos longos, documentos, contexto grande (relatórios, planilhas).
    "long": [
        ("google", "gemini-3.6-flash"),
        ("google", "gemini-3.8-flash"),
        ("groq", "openai/gpt-oss-120b"),
        ("nvidia", "z-ai/glm-5.3"),
    ],
    # Português do Brasil, texto corporativo, documentos formais.
    "pt": [
        ("google", "gemini-3.6-flash"),
        ("groq", "openai/gpt-oss-120b"),
        ("mistral", "open-mistral-7b"),
        ("nvidia", "z-ai/glm-5.3"),
    ],
}

DEFAULT_PROFILE = "fast"
DEFAULT_ORDER = ["groq", "google", "mistral", "nvidia", "openrouter"]
