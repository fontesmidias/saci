"""
Leitura e escrita das configurações do usuário: chaves de API, ordem da
cascata, fuso e perfil padrão.

Isto é o que a Etapa 3 do PLAN.md substitui: hoje editar `.env` na mão.
Duas garantias que este módulo mantém:

    1. O VALOR de uma chave nunca é devolvido para fora do processo —
       só um booleano "tem chave" e um trecho mascarado (`gsk_••••4f2a`)
       para o usuário reconhecer qual chave é qual sem reexibi-la.
    2. A gravação usa `dotenv.set_key`, que escreve num arquivo
       temporário e substitui o original com `os.replace` (atômico) —
       uma queda no meio da escrita nunca deixa o `.env` corrompido, e
       os comentários/formatação do arquivo são preservados.
"""

from __future__ import annotations

import os

from dotenv import dotenv_values, set_key

from . import catalog, paths
from .providers import PROVIDERS

# Preferências que não são chave de provedor, mas moram no mesmo .env.
RUNTIME_KEYS = ("LLM_ROUTER_ORDER", "LLM_ROUTER_TZ", "LLM_ROUTER_PROFILE")


def _mask(value: str) -> str:
    """`gsk_abcdefgh1234` -> `gsk_••••1234`. Nunca devolve o meio da chave."""
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}{'•' * 4}{value[-4:]}"


def provider_status() -> list[dict]:
    """
    Uma linha por provedor, para a tela de configurações: rótulo, se tem
    chave (nunca o valor), prefixo/sufixo mascarados, onde conseguir uma,
    e se o provedor gasta crédito pré-pago em vez de ser gratuito.
    """
    valores = dotenv_values(paths.env_path())
    out = []
    for key, provider in PROVIDERS.items():
        valor = (valores.get(provider.env) or "").strip() if provider.env else ""
        out.append({
            "key": key,
            "label": provider.label,
            "env_var": provider.env or None,   # None = keyless (ex.: LLM7)
            "keyless": not provider.env,
            "has_key": bool(valor) or not provider.env,
            "masked": _mask(valor) if valor else None,
            "cost": provider.cost,
            "notes": provider.notes,
        })
    return out


def runtime_prefs() -> dict:
    """As preferências de execução gravadas no .env (não confundir com prefs.json)."""
    valores = dotenv_values(paths.env_path())
    return {
        "order": valores.get("LLM_ROUTER_ORDER") or "",
        "timezone": valores.get("LLM_ROUTER_TZ") or "-3",
        "default_profile": valores.get("LLM_ROUTER_PROFILE") or "",
        "available_providers": list(PROVIDERS.keys()),
    }


def set_provider_key(provider_key: str, value: str) -> None:
    """
    Grava (ou apaga, se `value` vier vazio) a chave de um provedor.

    Levanta ValueError para provedor desconhecido ou keyless — não faz
    sentido gravar chave onde não existe variável de ambiente.
    """
    provider = PROVIDERS.get(provider_key)
    if provider is None:
        raise ValueError(f"provedor desconhecido: {provider_key!r}")
    if not provider.env:
        raise ValueError(f"{provider.label} não usa chave (acesso direto)")

    set_key(str(paths.env_path()), provider.env, value.strip())
    # A chave só existe no processo atual depois de recarregada — quem
    # chama (o endpoint) decide se testa/sonda em seguida.
    os.environ[provider.env] = value.strip()


def set_runtime_prefs(*, order: str | None = None, timezone: str | None = None,
                      default_profile: str | None = None) -> None:
    """Grava as preferências de execução que ficam no .env."""
    path = str(paths.env_path())
    if order is not None:
        set_key(path, "LLM_ROUTER_ORDER", order.strip())
        os.environ["LLM_ROUTER_ORDER"] = order.strip()
    if timezone is not None:
        set_key(path, "LLM_ROUTER_TZ", timezone.strip())
        os.environ["LLM_ROUTER_TZ"] = timezone.strip()
    if default_profile is not None:
        set_key(path, "LLM_ROUTER_PROFILE", default_profile.strip())
        os.environ["LLM_ROUTER_PROFILE"] = default_profile.strip()


def test_key(provider_key: str, value: str) -> dict:
    """
    Testa uma chave SEM salvá-la — é o botão "testar" antes de "salvar".

    Usa o primeiro modelo já verificado pelo catálogo para esse provedor
    (o mais rápido); se ainda não há nenhum verificado, usa o primeiro
    da lista curada em providers.py como palpite razoável.
    """
    provider = PROVIDERS.get(provider_key)
    if provider is None:
        return {"ok": False, "error": "provedor desconhecido"}
    if not provider.env:
        return {"ok": False, "error": "este provedor não usa chave"}
    if not value.strip():
        return {"ok": False, "error": "cole uma chave antes de testar"}

    candidatos = catalog.verified_models(provider_key, limit=1) or provider.models[:1]
    if not candidatos:
        return {"ok": False, "error": "nenhum modelo conhecido para testar ainda"}

    status, detail, latency_ms = catalog.probe(provider, candidatos[0], key=value.strip())
    return {
        "ok": status == "ok",
        "status": status,
        "model": candidatos[0],
        "detail": detail or None,
        "latency_ms": latency_ms,
    }


def trigger_catalog_refresh(provider_key: str) -> None:
    """Dispara a sondagem do catálogo para um provedor específico, agora."""
    provider = PROVIDERS.get(provider_key)
    if provider is not None:
        catalog.refresh_provider(provider)
