"""
Vigia o README do awesome-ai-free-tiers por mudanças, para avisar sobre
possíveis provedores/planos novos sem tentar adivinhar sozinho quem é
"genuinamente grátis" (sem cartão).

Por que isto NÃO tenta descobrir provedores automaticamente: não existe
forma confiável de saber, por scraping ou heurística, se um tier grátis
exige cartão de crédito, tem pegadinha de cobrança ou mudou de política
— isso é exatamente por que aquele repositório é mantido à mão por
humanos. Uma automação aqui daria falsos positivos (ou "grátis" que na
prática cobra) ou exigiria cadastro manual de qualquer forma, que já é
o fluxo existente (ver scripts/discover.py e a Regra R4 do CLAUDE.md:
nunca confiar na documentação do provedor, sempre testar com --refresh).

O que este script faz, e só isso: baixa o README, compara com a cópia
salva da última vez, e diz se mudou. Cabe ao humano ler o diff e decidir
se vale testar algo novo — nunca cadastra chave nem afirma "isto é
grátis" sozinho.

Uso:
    .venv/Scripts/python.exe scripts/watch_free_tiers.py
    (sai 0 se nada mudou ou na primeira execução; 2 se mudou -- útil
    para agendar e só notificar quando houver diferença real)
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = ROOT / "scripts" / ".free_tiers_snapshot.md"

README_URL = (
    "https://raw.githubusercontent.com/4pixeltechBR/awesome-ai-free-tiers"
    "/main/README.md"
)
TIMEOUT = 30.0


def fetch_readme() -> str:
    r = httpx.get(README_URL, timeout=TIMEOUT, follow_redirects=True)
    r.raise_for_status()
    return r.text


def main() -> int:
    try:
        atual = fetch_readme()
    except Exception as exc:
        print(f"Falha ao buscar o README: {type(exc).__name__}: {exc}")
        return 1

    if not SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.write_text(atual, encoding="utf-8")
        print("Primeira execução — snapshot salvo, nada para comparar ainda.")
        return 0

    anterior = SNAPSHOT_PATH.read_text(encoding="utf-8")
    if anterior == atual:
        print("Sem mudanças desde a última verificação.")
        return 0

    SNAPSHOT_PATH.write_text(atual, encoding="utf-8")
    print(
        "O README do awesome-ai-free-tiers mudou desde a última verificação.\n"
        "Isto NÃO significa que algo novo é grátis de verdade — só que o\n"
        "texto mudou. Compare manualmente e, se algo parecer promissor,\n"
        "teste com uma chave real antes de adicionar a saci/providers.py\n"
        "(Regra R4 do CLAUDE.md).\n\n"
        f"Veja o histórico completo em: {README_URL.replace('raw.githubusercontent.com', 'github.com').replace('/main/README.md', '/commits/main/README.md')}"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
