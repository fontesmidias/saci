#!/usr/bin/env python
"""
CLI do LLM Router.

Exemplos:
    py ask.py "explique herança em Python"
    py ask.py -p code "funcao que valida CPF"
    py ask.py -p plan "como estruturar um sistema de RH multi-empresa"
    py ask.py -v -p code "refatore isso"      # mostra a cascata
    py ask.py --status                        # testa todos os provedores
    py ask.py --profiles                      # lista os perfis
    type arquivo.py | py ask.py -p code "adicione testes:"
"""

from __future__ import annotations

import argparse
import sys

# Windows: força UTF-8 para não quebrar com emoji/acento vindos do modelo.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from llmrouter import LLMRouter, RouterError  # noqa: E402
from llmrouter.providers import PROFILES, PROVIDERS  # noqa: E402

# Instrução de sistema por perfil: molda o comportamento do modelo.
SYSTEM_PROMPTS = {
    "code": (
        "Você é um engenheiro de software sênior. Responda com código correto, "
        "idiomático e pronto para produção. Inclua tratamento de erro quando "
        "fizer sentido. Seja direto: código primeiro, explicação curta depois."
    ),
    "plan": (
        "Você é um arquiteto de software sênior. Analise trade-offs, aponte "
        "riscos e proponha um plano em etapas objetivas. Seja concreto e "
        "priorize o que entrega valor primeiro. Evite generalidades."
    ),
}


def cmd_usage() -> int:
    """Mostra consumo e cota restante por provedor."""
    from llmrouter import usage as usage_db

    rows = usage_db.report()
    print("CONSUMO DE HOJE (UTC)\n")
    print(f"  {'provedor':11} {'chamadas':>9} {'falhas':>7} {'tokens':>9} {'latencia':>9}  fonte")
    print(f"  {'-'*11} {'-'*9} {'-'*7} {'-'*9} {'-'*9}  {'-'*8}")

    any_use = False
    for r in rows:
        if r["calls_today"] or r["failed_today"]:
            any_use = True
        lat = f"{r['avg_latency']}s" if r["avg_latency"] else "-"
        print(
            f"  {r['provider']:11} {r['calls_today']:>9} {r['failed_today']:>7} "
            f"{r['tokens_today']:>9} {lat:>9}  {r['source']}"
        )

    if not any_use:
        print("\n  (nenhuma chamada registrada hoje)")

    print("\n\nCOTA RESTANTE\n")
    for r in rows:
        name = r["provider"]
        if r["remaining_requests"] is not None:
            # Dado oficial do provedor.
            used = (r["limit_requests"] or 0) - r["remaining_requests"]
            pct = 100 * used / r["limit_requests"] if r["limit_requests"] else 0
            bar = _bar(pct)
            reset = f" | reset em {r['reset_requests']}" if r["reset_requests"] else ""
            print(f"  {name:11} {bar} {used}/{r['limit_requests']} req  [oficial]{reset}")
            if r["remaining_tokens"] is not None and r["limit_tokens"]:
                tused = r["limit_tokens"] - r["remaining_tokens"]
                print(f"  {'':11} {_bar(100*tused/r['limit_tokens'])} "
                      f"{tused}/{r['limit_tokens']} tokens")
        elif r["rpd_limit"]:
            # Estimativa nossa, por contagem local.
            pct = r["rpd_used_pct"] or 0
            print(f"  {name:11} {_bar(pct)} {r['calls_today']}/{r['rpd_limit']} req/dia  [estimado]")
        else:
            print(f"  {name:11} (sem limite conhecido)")

    print("\n  [oficial]  = lido dos headers do provedor")
    print("  [estimado] = nossa contagem local (provedor nao informa)")
    return 0


def _bar(pct: float, width: int = 20) -> str:
    """Barra de progresso em texto."""
    pct = max(0.0, min(100.0, pct))
    filled = int(width * pct / 100)
    return f"[{'#' * filled}{'.' * (width - filled)}] {pct:5.1f}%"


def cmd_profiles() -> int:
    print("Perfis disponíveis:\n")
    for name, steps in PROFILES.items():
        print(f"  {name:6} -> {len(steps)} modelos na cascata")
        for pkey, model in steps[:3]:
            print(f"           {PROVIDERS[pkey].label} / {model}")
        if len(steps) > 3:
            print(f"           ... e mais {len(steps) - 3}")
        print()
    return 0


def cmd_status(timeout: float) -> int:
    """Faz uma chamada real em cada provedor e mostra quem está de pé."""
    print("Testando provedores configurados...\n")
    base = LLMRouter(profile="fast", timeout=timeout)
    ok = 0
    providers = base.available()

    for provider in providers:
        got = False
        for model in provider.models:
            try:
                single = LLMRouter(profile="fast", timeout=timeout)
                single.plan = lambda p=provider, m=model: [(p, m)]  # type: ignore[method-assign]
                r = single.ask("Responda apenas: OK", max_tokens=1500)
                print(f"  [OK]  {provider.label:20} {r.model:34} {r.latency:6.2f}s")
                ok += 1
                got = True
                break
            except RouterError:
                continue
        if not got:
            print(f"  [--]  {provider.label:20} indisponível agora")

    print(f"\n{ok}/{len(providers)} provedores respondendo.")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ask",
        description="Pergunta a uma cascata de LLMs gratuitos, com fallback automático.",
    )
    parser.add_argument("prompt", nargs="*", help="a pergunta")
    parser.add_argument(
        "-p", "--profile", choices=list(PROFILES), default=None,
        help="perfil de tarefa (code, plan, fast, long, pt)",
    )
    parser.add_argument("-s", "--system", help="instrução de sistema customizada")
    parser.add_argument("-m", "--max-tokens", type=int, default=4096)
    parser.add_argument("-t", "--temperature", type=float, default=0.7)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("-v", "--verbose", action="store_true", help="mostra a cascata")
    parser.add_argument("--status", action="store_true", help="testa todos os provedores")
    parser.add_argument("--profiles", action="store_true", help="lista os perfis")
    parser.add_argument("--usage", action="store_true", help="consumo e cota por provedor")
    args = parser.parse_args()

    if args.usage:
        return cmd_usage()
    if args.profiles:
        return cmd_profiles()
    if args.status:
        return cmd_status(args.timeout)

    prompt = " ".join(args.prompt).strip()

    # Permite encadear: type arquivo.py | py ask.py -p code "adicione testes:"
    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            prompt = f"{prompt}\n\n{piped}" if prompt else piped

    if not prompt:
        parser.print_help()
        return 1

    profile = args.profile or "fast"
    system = args.system or SYSTEM_PROMPTS.get(profile)

    try:
        router = LLMRouter(
            profile=profile,
            timeout=args.timeout,
            on_event=(lambda m: print(m, file=sys.stderr)) if args.verbose else None,
        )
        result = router.ask(
            prompt,
            system=system,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
    except RouterError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    print(result.content)

    if args.verbose:
        tok = result.total_tokens if result.total_tokens is not None else "?"
        print(
            f"\n--- {result.provider} / {result.model} | "
            f"{result.latency}s | {tok} tokens | perfil={profile} ---",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
