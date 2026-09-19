#!/usr/bin/env python
"""
Verificador das regras invioláveis do projeto (CLAUDE.md).

Regra declarada é regra esquecida. Este script transforma as regras em
testes que falham — no terminal, no hook de commit e no CI.

Uso:
    python scripts/check_rules.py           # verifica tudo
    python scripts/check_rules.py --fix     # corrige o que der (só avisa hoje)

Sai com código 1 se alguma regra foi violada.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# R2 — pares de documentos que precisam existir nos dois idiomas.
BILINGUE = [
    ("README.md", "README.pt-BR.md"),
    ("CONTRIBUTING.md", "CONTRIBUTING.pt-BR.md"),
    ("SECURITY.md", "SECURITY.pt-BR.md"),
    ("CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT.pt-BR.md"),
    ("CHANGELOG.md", "CHANGELOG.pt-BR.md"),
]

# R2 — frases que denunciam tradução abandonada pela metade.
ABANDONO = re.compile(
    r"(veja a vers[ãa]o em ingl[êe]s|see the english version|"
    r"for more details,? see|consulte o original|"
    r"tradu[çc][ãa]o em andamento|TODO:? *tradu)",
    re.I,
)

# R1 — atribuição de autoria a IA (citação de design é permitida).
ATRIBUICAO = re.compile(
    r"(co-authored-by:\s*claude|generated with \[?claude|"
    r"🤖 generated with|assistant:\s*claude)",
    re.I,
)

# R3 — padrões de chave de API real.
SEGREDOS = [
    ("Groq", re.compile(r"gsk_[A-Za-z0-9]{20,}")),
    ("Google", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("Google (novo)", re.compile(r"AQ\.Ab[0-9A-Za-z_\-]{30,}")),
    ("NVIDIA", re.compile(r"nvapi-[A-Za-z0-9_\-]{30,}")),
    ("OpenRouter", re.compile(r"sk-or-v1-[0-9a-f]{40,}")),
    ("Cerebras", re.compile(r"csk-[A-Za-z0-9]{30,}")),
    ("HuggingFace", re.compile(r"hf_[A-Za-z0-9]{30,}")),
]

# R3 — dados pessoais que não podem ir para o repositório público.
PESSOAL = re.compile(r"rh@greenhousedf\.com\.br", re.I)

# Arquivos que *descrevem* as regras precisam citar os padrões proibidos.
# Citar não é violar: sem esta exceção, seria impossível documentar a regra.
AUTODESCRITIVOS = {"CLAUDE.md", "scripts/check_rules.py"}

falhas: list[str] = []
avisos: list[str] = []


def git(*args: str) -> str:
    """Roda git e devolve a saída; string vazia se falhar."""
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def arquivos_rastreados() -> list[Path]:
    saida = git("ls-files")
    return [ROOT / linha for linha in saida.splitlines() if linha.strip()]


def titulos(caminho: Path) -> list[str]:
    """Níveis dos títulos markdown: ['#', '##', '###', ...]."""
    if not caminho.exists():
        return []
    return [
        linha.split(" ")[0]
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if re.match(r"^#{1,4} \S", linha)
    ]


# ---------------------------------------------------------------------
# R1 — atribuição ao Claude
# ---------------------------------------------------------------------

def checar_r1() -> None:
    mensagens = git("log", "--format=%H%n%B%n<<<FIM>>>")
    for bloco in mensagens.split("<<<FIM>>>"):
        if not bloco.strip():
            continue
        linhas = bloco.strip().splitlines()
        sha = linhas[0][:8] if linhas else "?"
        corpo = "\n".join(linhas[1:])
        if ATRIBUICAO.search(corpo):
            trecho = next(ln.strip() for ln in corpo.splitlines()
                          if ATRIBUICAO.search(ln))
            falhas.append(f"R1: commit {sha} atribui autoria a IA: {trecho!r}")

    for caminho in arquivos_rastreados():
        rel = caminho.relative_to(ROOT).as_posix()
        if rel in AUTODESCRITIVOS or caminho.suffix.lower() in {".png", ".jpg", ".ico", ".db"}:
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except Exception:
            continue
        if ATRIBUICAO.search(texto):
            falhas.append(f"R1: {rel} atribui autoria a IA")


# ---------------------------------------------------------------------
# R2 — bilíngue completo
# ---------------------------------------------------------------------

def checar_r2() -> None:
    for nome_en, nome_pt in BILINGUE:
        en, pt = ROOT / nome_en, ROOT / nome_pt
        if not en.exists():
            continue
        if not pt.exists():
            falhas.append(f"R2: falta {nome_pt} (o {nome_en} existe)")
            continue

        t_en, t_pt = titulos(en), titulos(pt)
        if len(t_en) != len(t_pt):
            falhas.append(
                f"R2: {nome_en} tem {len(t_en)} títulos e {nome_pt} tem {len(t_pt)} "
                f"— as versões divergiram")
        elif t_en != t_pt:
            falhas.append(
                f"R2: {nome_pt} tem a mesma quantidade de títulos que {nome_en}, "
                f"mas em níveis/ordem diferentes")

        texto_pt = pt.read_text(encoding="utf-8")
        if ABANDONO.search(texto_pt):
            trecho = ABANDONO.search(texto_pt).group(0)
            falhas.append(f"R2: {nome_pt} abandona a tradução: {trecho!r}")

        # Tradução muito mais curta = provavelmente incompleta.
        tam_en, tam_pt = len(en.read_text(encoding="utf-8")), len(texto_pt)
        if tam_en and tam_pt < tam_en * 0.7:
            falhas.append(
                f"R2: {nome_pt} tem {tam_pt} bytes contra {tam_en} do {nome_en} "
                f"({100*tam_pt//tam_en}%) — tradução provavelmente incompleta")

        # Cada um deve apontar para o outro.
        if nome_pt not in en.read_text(encoding="utf-8"):
            avisos.append(f"R2: {nome_en} não tem link para {nome_pt}")
        if nome_en not in texto_pt:
            avisos.append(f"R2: {nome_pt} não tem link para {nome_en}")


# ---------------------------------------------------------------------
# R3 — segredos e dados pessoais
# ---------------------------------------------------------------------

def checar_r3() -> None:
    nunca_commitar = {".env", "usage.db", "prefs.json", "providers.local.json"}
    rastreados = arquivos_rastreados()

    for caminho in rastreados:
        rel = caminho.relative_to(ROOT).as_posix()
        if rel in nunca_commitar or rel.startswith("logs/"):
            falhas.append(f"R3: {rel} está sendo versionado e não deveria")

        if caminho.suffix.lower() in {".png", ".jpg", ".ico", ".db"}:
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except Exception:
            continue

        if rel in AUTODESCRITIVOS:
            continue
        for nome, padrao in SEGREDOS:
            if padrao.search(texto):
                falhas.append(f"R3: possível chave {nome} em {rel}")
        if PESSOAL.search(texto):
            falhas.append(f"R3: e-mail de trabalho em {rel}")

    # Histórico: e-mails de autor e chaves em commits antigos.
    for email in set(git("log", "--format=%ae").split()):
        if PESSOAL.search(email):
            falhas.append(f"R3: e-mail de trabalho no histórico como autor: {email}")

    diff = git("log", "-p", "--all")
    for nome, padrao in SEGREDOS:
        if padrao.search(diff):
            falhas.append(f"R3: possível chave {nome} no HISTÓRICO do git")


# ---------------------------------------------------------------------
# R5 — stack simples
# ---------------------------------------------------------------------

def checar_r5() -> None:
    proibidos = ["package-lock.json", "yarn.lock", "webpack.config.js",
                 "vite.config.js", "tsconfig.json"]
    for nome in proibidos:
        # a extensão do VSCode tem package.json próprio; só a raiz conta
        if (ROOT / nome).exists():
            falhas.append(f"R5: {nome} na raiz indica build pipeline (proibido sem autorização)")

    for caminho in arquivos_rastreados():
        if caminho.suffix == ".ts" and "node_modules" not in str(caminho):
            falhas.append(f"R5: {caminho.relative_to(ROOT)} — TypeScript não é permitido")


def main() -> int:
    print("Verificando as regras invioláveis (CLAUDE.md)...\n")
    checar_r1()
    checar_r2()
    checar_r3()
    checar_r5()

    if avisos:
        print("AVISOS (não bloqueiam):")
        for a in avisos:
            print(f"  ! {a}")
        print()

    if falhas:
        print(f"REGRAS VIOLADAS ({len(falhas)}):\n")
        for f in falhas:
            print(f"  X {f}")
        print("\nCorrija antes de commitar. As regras estão em CLAUDE.md.")
        return 1

    print("OK — todas as regras verificáveis foram cumpridas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
