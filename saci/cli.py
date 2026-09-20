#!/usr/bin/env python
"""
CLI do Saci.

Exemplos:
    saci "explique herança em Python"
    saci -p code "funcao que valida CPF"
    saci -p plan "como estruturar um sistema de RH multi-empresa"
    saci -v -p code "refatore isso"      # mostra a cascata
    saci --status                        # testa todos os provedores
    saci --profiles                      # lista os perfis
    type arquivo.py | saci -p code "adicione testes:"
"""

from __future__ import annotations

import argparse
import sys

# Windows: força UTF-8 para não quebrar com emoji/acento vindos do modelo.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from saci import LLMRouter, RouterError  # noqa: E402
from saci.providers import PROFILES, PROVIDERS  # noqa: E402

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
    """Mostra consumo e cota restante por provedor e por modelo."""
    from saci import usage as usage_db

    rows = usage_db.report()
    total_calls = sum(r["calls_today"] for r in rows)
    total_tokens = sum(r["tokens_today"] for r in rows)

    agora = usage_db.local_now().strftime("%d/%m %H:%M")
    print(f"CONSUMO DE HOJE ({agora}): {total_calls} chamadas, {_mil(total_tokens)} tokens")
    print("  (cada provedor conta o dia pelo proprio ciclo de reset)\n")

    for r in rows:
        if not r["models"] and not r["calls_today"]:
            continue

        tag = "[oficial]" if r["source"] in ("headers", "endpoint") else "[estimado]"
        out = "  SEM COTA" if r["exhausted"] else ""
        cred = "  [GASTA CREDITO]" if r.get("cost") == "credits" else ""
        reset = f"  reseta as {r['daily_reset_at']}" if r.get("daily_reset_at") else ""
        print(f"{r['provider'].upper()}  {tag}{cred}{out}{reset}")

        if not r["models"]:
            if r["rpd_limit"]:
                pct = r["rpd_used_pct"] or 0
                print(f"  {_bar(pct)} {r['calls_today']}/{r['rpd_limit']} req/dia")
            print()
            continue

        for m in r["models"]:
            mark = " [sem cota]" if m["exhausted"] else ""
            stats = f"{m['calls']} chamadas, {_mil(m['tokens'])} tok"
            if m["avg_latency"]:
                stats += f", {m['avg_latency']}s"
            print(f"  {m['model']}{mark}  ({stats})")

            if m["limit_requests"]:
                used = m["limit_requests"] - (m["remaining_requests"] or 0)
                pct = 100 * used / m["limit_requests"]
                cd = _countdown(m["reset_requests_in"])
                print(f"    req  {_bar(pct)} {used}/{m['limit_requests']}{cd}")

            if m["limit_tokens"]:
                used = m["limit_tokens"] - (m["remaining_tokens"] or 0)
                pct = 100 * used / m["limit_tokens"]
                cd = _countdown(m["reset_tokens_in"])
                print(f"    tok  {_bar(pct)} {_mil(used)}/{_mil(m['limit_tokens'])}{cd}")
        print()

    if not total_calls:
        print("  (nenhuma chamada registrada hoje)\n")

    print("  [oficial]  = lido dos headers do provedor")
    print("  [estimado] = nossa contagem local (provedor nao informa)")
    print("\n  Painel visual: http://127.0.0.1:8000/dashboard")
    return 0


def _mil(n) -> str:
    """Formata numero com ponto de milhar (pt-BR)."""
    return f"{n:,}".replace(",", ".")


def _countdown(secs) -> str:
    """Formata o tempo que falta para a cota resetar."""
    if secs is None:
        return ""
    if secs <= 0.5:
        return "  reset: pronto"
    if secs < 60:
        return f"  reset em {secs:.0f}s"
    return f"  reset em {int(secs // 60)}m{int(secs % 60):02d}s"


def _bar(pct: float, width: int = 20) -> str:
    """Barra de progresso em texto."""
    pct = max(0.0, min(100.0, pct))
    filled = int(width * pct / 100)
    return f"[{'#' * filled}{'.' * (width - filled)}] {pct:5.1f}%"


def cmd_catalog() -> int:
    """Modelos descobertos automaticamente, com veredito."""
    from saci import catalog
    from saci.providers import PROVIDERS

    snap = catalog.snapshot()
    last = catalog.last_refresh_at()
    print(f"CATALOGO AUTOMATICO  (ultima verificacao: {last or 'nunca'})\n")
    label = {"ok": "OK", "paid": "pago", "gone": "removido", "ratelimited": "429",
             "error": "erro", "auth": "chave?", "new": "a verificar"}
    for pkey, models in snap["models"].items():
        prov = PROVIDERS.get(pkey)
        cost = "  [GASTA CREDITO]" if prov and prov.cost == "credits" else ""
        ok = sum(1 for m in models if m["status"] == "ok")
        print(f"{(prov.label if prov else pkey).upper()}{cost}  {ok} ok de {len(models)}")
        for m in sorted(models, key=lambda m: (m["status"] != "ok", m["latency_ms"] or 1e9)):
            lat = f"{m['latency_ms']/1000:.1f}s" if m["latency_ms"] else ""
            ctx = f"{m['context']//1000}k" if m["context"] else ""
            det = f"  ({m['detail']})" if m["detail"] and m["status"] != "ok" else ""
            print(f"  {label.get(m['status'], m['status']):11} {m['model']:44} {ctx:>5} {lat:>6}{det}")
        print()
    if not snap["models"]:
        print("  (vazio — rode: ask --refresh, ou suba o servidor, que verifica sozinho)")
    return 0


def cmd_events() -> int:
    """Histórico de mudança de veredito por modelo (ok -> pago, ok -> removido...)."""
    from saci import catalog

    rows = catalog.events(limit=50)
    if not rows:
        print("(nenhuma mudança registrada ainda — normal em instalação nova ou recente)")
        return 0
    print("HISTORICO DE MUDANCAS  (mais recente primeiro)\n")
    for r in rows:
        det = f"  ({r['detail']})" if r["detail"] else ""
        print(f"  {r['ts']}  {r['provider']:12} {r['model']:40} "
              f"{r['from_status']} -> {r['to_status']}{det}")
    return 0


def cmd_refresh() -> int:
    """Roda a descoberta + sondagem agora, no terminal."""
    from saci import catalog
    for s in catalog.refresh_all(on_event=print):
        print(f"  => {s['provider']}: {s['ok']} ok de {s['chat']} de chat"
              + (f"  ({s['error']})" if s.get("error") else ""))
    return 0


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
        prog="saci",
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
    parser.add_argument("--catalog", action="store_true", help="modelos descobertos e veredito")
    parser.add_argument("--refresh", action="store_true", help="descobre e sonda modelos agora")
    parser.add_argument("--events", action="store_true",
                         help="historico de mudanca de veredito (quando um modelo virou pago/sumiu)")
    args = parser.parse_args()

    if args.usage:
        return cmd_usage()
    if args.catalog:
        return cmd_catalog()
    if args.events:
        return cmd_events()
    if args.refresh:
        return cmd_refresh()
    if args.profiles:
        return cmd_profiles()
    if args.status:
        return cmd_status(args.timeout)

    prompt = " ".join(args.prompt).strip()

    # Permite encadear: type arquivo.py | saci -p code "adicione testes:"
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
