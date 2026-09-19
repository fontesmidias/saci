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
    cost: str = "free"   # "free" | "credits" (gasta saldo pré-pago)


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

    # --- Sem chave: funcionam na hora, sem cadastro -------------------
    "llm7": Provider(
        key="llm7",
        label="LLM7.io",
        env="",  # vazio = não precisa de chave
        base_url="https://api.llm7.io/v1",
        models=["codestral-latest", "GLM-5.3-Flash"],
        notes="Zero cadastro. Verificado: codestral 2.6s, GLM 3.9s. "
              "Nem todo modelo do catálogo responde (401), e a saída às vezes "
              "vem contaminada. Serve como último recurso, não como principal.",
    ),

    # --- Exigem cadastro (chave ainda não configurada) ----------------
    "cerebras": Provider(
        key="cerebras",
        label="Cerebras",
        env="CEREBRAS_API_KEY",
        base_url="https://api.cerebras.ai/v1",
        models=["gpt-oss-120b", "qwen-3.8-27b"],
        notes="Muito rápido, mas a conta testada retornou HTTP 402 "
              "(exige plano pago). Fora dos perfis até isso mudar.",
    ),
    "sambanova": Provider(
        key="sambanova",
        label="SambaNova",
        env="SAMBANOVA_API_KEY",
        base_url="https://api.sambanova.ai/v1",
        models=[],   # vem do catálogo automático
        notes="Free tier sem cartão (30 RPM). Chave: cloud.sambanova.ai",
    ),
    "hyperbolic": Provider(
        key="hyperbolic",
        label="Hyperbolic",
        env="HYPERBOLIC_API_KEY",
        base_url="https://api.hyperbolic.xyz/v1",
        models=[],   # vem do catálogo automático
        notes="US$ 1 de crédito na verificação do telefone — gasta saldo, não é free tier.",
        cost="credits",
    ),
    "huggingface": Provider(
        key="huggingface",
        label="HuggingFace",
        env="HF_API_KEY",
        base_url="https://router.huggingface.co/v1",
        models=[],   # vem do catálogo automático
        notes="Serverless em modelos abertos. Token: huggingface.co/settings/tokens",
    ),
}

# ---------------------------------------------------------------------
# PERFIS POR TAREFA — cada item é (provedor, modelo), em ordem de queda.
#
# "code" e "plan" vêm primeiro na sua prioridade, então recebem os
# modelos de maior capacidade que ainda respondem rápido.
# ---------------------------------------------------------------------

# Uma entrada (provedor, None) significa "os melhores modelos verificados
# desse provedor pelo catálogo automático". É assim que um provedor novo
# entra na cascata sem ninguém listar modelo nenhum à mão.
PROFILES: dict[str, list[tuple[str, str | None]]] = {
    # Gerar/refatorar código. Verificados: gpt-oss-120b 0.98s, codestral 2.20s.
    "code": [
        ("groq", "openai/gpt-oss-120b"),
        ("mistral", "codestral-latest"),
        ("groq", "qwen/qwen3.8-27b"),
        ("google", "gemini-3.6-flash"),
        ("groq", "openai/gpt-oss-20b"),
        ("nvidia", "z-ai/glm-5.3"),
        ("openrouter", "qwen/qwen3.8-27b:free"),
        ("llm7", "codestral-latest"),
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
        ("llm7", "GLM-5.3-Flash"),
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
        ("llm7", "codestral-latest"),
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
# Ordem da cauda genérica: grátis primeiro, depois quem gasta crédito,
# por último o keyless instável. Provedores sem chave são pulados.
DEFAULT_ORDER = ["groq", "google", "mistral", "nvidia", "sambanova",
                 "huggingface", "openrouter", "cerebras", "hyperbolic", "llm7"]
