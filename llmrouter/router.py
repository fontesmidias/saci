"""
Cascata de fallback entre provedores de LLM.

Tenta cada provedor na ordem configurada; ao receber rate limit (429),
indisponibilidade (5xx), timeout ou modelo removido (404/410), passa
para o próximo modelo e depois para o próximo provedor.

Uso:
    from llmrouter import LLMRouter

    router = LLMRouter()
    r = router.ask("Explique o que é um índice em banco de dados.")
    print(r.content)
    print(r.provider, r.model, r.latency)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    NotFoundError,
    OpenAI,
    RateLimitError,
)

from . import catalog, prefs
from . import usage as usage_db
from .providers import DEFAULT_ORDER, DEFAULT_PROFILE, PROFILES, PROVIDERS, Provider

ROOT = Path(__file__).resolve().parent.parent

# Erros que significam "este modelo/provedor não vai servir AGORA" —
# vale a pena tentar o próximo em vez de abortar.
RETRYABLE = (
    RateLimitError,      # 429 — cota estourada
    APITimeoutError,     # demorou demais
    APIConnectionError,  # rede
    InternalServerError,  # 5xx — sobrecarga do provedor
    NotFoundError,       # 404 — modelo removido do catálogo
)


class RouterError(RuntimeError):
    """Todos os provedores falharam."""


@dataclass
class Attempt:
    provider: str
    model: str
    error: str
    latency: float


@dataclass
class Result:
    content: str
    provider: str
    model: str
    latency: float
    total_tokens: int | None = None
    attempts: list[Attempt] = field(default_factory=list)

    def __str__(self) -> str:  # pragma: no cover - conveniência
        return self.content


class LLMRouter:
    def __init__(
        self,
        profile: str | None = None,
        order: Iterable[str] | None = None,
        timeout: float | None = None,
        env_file: str | Path | None = None,
        on_event: Callable[[str], None] | None = None,
        skip_exhausted: bool = True,
        honor_pin: bool = True,
    ) -> None:
        load_dotenv(env_file or ROOT / ".env")
        self.skip_exhausted = skip_exhausted
        self.honor_pin = honor_pin

        # Perfil escolhido manualmente no seletor tem prioridade sobre o .env.
        self.profile = (
            profile
            or prefs.load().get("profile")
            or os.getenv("LLM_ROUTER_PROFILE")
            or DEFAULT_PROFILE
        )
        if self.profile not in PROFILES:
            raise RouterError(
                f"Perfil desconhecido: {self.profile!r}. "
                f"Disponíveis: {', '.join(PROFILES)}"
            )

        # `order` restringe a quais provedores usar (útil para --status).
        # Sem `order`, vale LLM_ROUTER_ORDER do .env; sem ele, o padrão.
        if order is None:
            raw = (os.getenv("LLM_ROUTER_ORDER") or "").strip()
            order = [x.strip() for x in raw.split(",") if x.strip()] or DEFAULT_ORDER
        self.order = [p for p in order if p in PROVIDERS]
        self.timeout = timeout or float(os.getenv("LLM_ROUTER_TIMEOUT") or 60.0)
        self.on_event = on_event or (lambda msg: None)

    # ---------------------------------------------------------------

    def plan(self) -> list[tuple[Provider, str]]:
        """
        A cascata efetiva: pares (provedor, modelo) com chave configurada.

        Provedores sem cota vão para o FIM da fila em vez de serem
        removidos — se todos estiverem no limite, ainda vale tentar (a
        cota pode ter resetado desde a última leitura).
        """
        # Trava manual: o usuário escolheu um modelo no seletor do VSCode.
        # Ele vai na frente, mas a cascata continua atrás como rede de
        # segurança — travar não deveria significar ficar sem resposta.
        forced: list[tuple[Provider, str]] = []
        pin = prefs.pinned()
        if pin and self.honor_pin:
            pkey, pmodel = pin
            if pkey in PROVIDERS and self._has_access(PROVIDERS[pkey]):
                forced.append((PROVIDERS[pkey], pmodel))

        ready: list[tuple[Provider, str]] = []
        exhausted: list[tuple[Provider, str]] = []

        for pkey, model in self._expanded_steps():
            if pkey not in self.order:
                continue
            provider = PROVIDERS[pkey]
            if not self._has_access(provider):
                continue

            # Por MODELO, nao por provedor: no Groq os tokens sao contados
            # por modelo, entao gpt-oss-20b pode estar livre enquanto o
            # 120b esta no limite. Pular o provedor inteiro desperdicaria cota.
            if self.skip_exhausted and usage_db.is_exhausted(pkey, model):
                exhausted.append((provider, model))
            else:
                ready.append((provider, model))

        if exhausted and ready:
            names = {f"{p.label}/{m.split('/')[-1]}" for p, m in exhausted}
            self.on_event(f"[cota] adiando: {', '.join(sorted(names))}")

        ordered = ready + exhausted
        if forced:
            rest = [(p, m) for (p, m) in ordered
                    if not (p.key == forced[0][0].key and m == forced[0][1])]
            self.on_event(f"[fixado] {forced[0][0].label} / {forced[0][1]}")
            return forced + rest
        return ordered

    def _expanded_steps(self) -> list[tuple[str, str]]:
        """
        Os passos do perfil, com duas expansões:

        1. (provedor, None) vira os 2 melhores modelos verificados desse
           provedor pelo catálogo automático (os mais rápidos primeiro).
        2. Todo provedor da ordem configurada que o perfil não cita entra
           no fim, também via catálogo. É o que faz um provedor recém
           configurado participar sem ninguém editar os perfis.
        """
        steps: list[tuple[str, str]] = []
        seen_prov: set[str] = set()

        def add(pkey: str, model: str | None) -> None:
            if model is not None:
                if (pkey, model) not in steps:
                    steps.append((pkey, model))
                return
            for m in catalog.verified_models(pkey, limit=2):
                if (pkey, m) not in steps:
                    steps.append((pkey, m))

        for pkey, model in PROFILES[self.profile]:
            seen_prov.add(pkey)
            add(pkey, model)

        for pkey in self.order:  # cauda genérica, na ordem do usuário
            if pkey in seen_prov or pkey not in PROVIDERS:
                continue
            add(pkey, None)
        return steps

    def available(self) -> list[Provider]:
        """Provedores com chave preenchida, na ordem configurada."""
        return [PROVIDERS[k] for k in self.order if self._has_access(PROVIDERS[k])]

    def _has_access(self, provider: Provider) -> bool:
        """Utilizável? Provedor sem `env` é keyless (ex.: LLM7)."""
        if not provider.env:
            return True
        return bool((os.getenv(provider.env) or "").strip())

    def _api_key(self, provider: Provider) -> str:
        # O SDK exige algo no lugar da chave; provedores keyless ignoram.
        return (os.getenv(provider.env) or "").strip() if provider.env else "unused"

    def _scrub(self, text: str, api_key: str) -> str:
        """Nunca deixa a chave aparecer em log ou exceção."""
        return text.replace(api_key, "***") if api_key else text

    def _log(
        self,
        provider: Provider,
        model: str,
        *,
        ok: bool,
        tokens: int = 0,
        latency: float | None = None,
        error: str | None = None,
    ) -> None:
        """Grava a chamada no histórico. Falha aqui nunca quebra a resposta."""
        try:
            usage_db.record_call(
                provider.key,
                model,
                ok=ok,
                tokens=tokens,
                latency=latency,
                profile=self.profile,
                error=error,
            )
        except Exception:
            pass

    # ---------------------------------------------------------------

    def ask(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> Result:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, max_tokens=max_tokens, temperature=temperature)

    def chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> Result:
        attempts: list[Attempt] = []
        steps = self.plan()

        if not steps:
            raise RouterError(
                "Nenhum provedor com chave configurada para o perfil "
                f"{self.profile!r}. Preencha o .env (veja .env.example)."
            )

        for provider, model in steps:
            api_key = self._api_key(provider)
            client = OpenAI(
                base_url=provider.base_url,
                api_key=api_key,
                timeout=self.timeout,
                max_retries=0,  # o retry é nosso, entre provedores
            )

            start = time.perf_counter()
            try:
                # with_raw_response dá acesso aos headers, onde Groq e
                # Mistral publicam a cota restante em tempo real.
                raw = client.chat.completions.with_raw_response.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                try:
                    usage_db.record_quota_headers(provider.key, model, raw.headers)
                except Exception:
                    pass  # contabilidade nunca derruba a chamada

                resp = raw.parse()
                elapsed = time.perf_counter() - start
                content = (resp.choices[0].message.content or "").strip()

                # Modelos de raciocínio podem gastar todo o orçamento de
                # tokens pensando e devolver conteúdo vazio: isso é falha.
                if not content:
                    raise ValueError("resposta vazia (orçamento de tokens esgotado?)")

                tokens = getattr(resp.usage, "total_tokens", None) if resp.usage else None
                self._log(provider, model, ok=True, tokens=tokens or 0, latency=elapsed)

                self.on_event(f"[OK] {provider.label} / {model} ({elapsed:.2f}s)")
                return Result(
                    content=content,
                    provider=provider.label,
                    model=model,
                    latency=round(elapsed, 2),
                    total_tokens=tokens,
                    attempts=attempts,
                )

            except APIStatusError as exc:
                # Cobre 402/403/410 e também 429/404 (subclasses) —
                # em todos os casos seguimos para o próximo candidato.
                elapsed = time.perf_counter() - start
                status = getattr(exc, "status_code", "?")
                msg = self._scrub(f"HTTP {status}: {exc}", api_key)[:200]
                attempts.append(Attempt(provider.label, model, msg, round(elapsed, 2)))
                self._log(provider, model, ok=False, latency=elapsed, error=msg)
                self.on_event(f"[falhou] {provider.label} / {model}: {msg[:90]}")

            except RETRYABLE as exc:
                elapsed = time.perf_counter() - start
                msg = self._scrub(f"{type(exc).__name__}: {exc}", api_key)[:200]
                attempts.append(Attempt(provider.label, model, msg, round(elapsed, 2)))
                self._log(provider, model, ok=False, latency=elapsed, error=msg)
                self.on_event(f"[falhou] {provider.label} / {model}: {msg[:90]}")

            except Exception as exc:  # inesperado — registra e segue
                elapsed = time.perf_counter() - start
                msg = self._scrub(f"{type(exc).__name__}: {exc}", api_key)[:200]
                attempts.append(Attempt(provider.label, model, msg, round(elapsed, 2)))
                self._log(provider, model, ok=False, latency=elapsed, error=msg)
                self.on_event(f"[falhou] {provider.label} / {model}: {msg[:90]}")

        detail = "\n".join(f"  - {a.provider}/{a.model}: {a.error}" for a in attempts)
        raise RouterError(
            f"Todos os provedores falharam (perfil {self.profile!r}):\n{detail}"
        )
