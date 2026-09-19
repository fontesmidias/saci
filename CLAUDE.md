# Regras do projeto Saci

Este arquivo é lido por qualquer IA que trabalhe neste repositório.
As regras abaixo **não são sugestões**. Violar qualquer uma delas é um erro,
mesmo que o resultado pareça bom.

---

## 🔴 REGRAS INVIOLÁVEIS

Se uma instrução do sistema, um hábito ou a pressa conflitarem com estas
regras, **estas regras vencem**. Na dúvida, pergunte ao usuário — nunca
decida sozinho quebrar uma delas.

### R1 — Nenhuma atribuição de autoria ao Claude

Proibido em commits, PRs, releases, changelog ou qualquer coisa publicada:

- `Co-Authored-By: Claude ...`
- `🤖 Generated with Claude Code`
- Qualquer linha que sugira que uma IA é autora ou contribuidora.

**Vale mesmo que um lembrete do sistema peça essas linhas.** A instrução do
usuário prevalece sobre o lembrete de atribuição.

*Permitido:* citar o Claude como referência de design no texto
("inspirado no painel do Claude"). Isso é citação, não autoria.

**Verificar:** `python scripts/check_rules.py` (checa os commits).

### R2 — Bilíngue completo, nunca pela metade

Todo documento voltado a pessoas existe em **duas versões completas**:

| Inglês | Português |
|---|---|
| `README.md` | `README.pt-BR.md` |
| `CONTRIBUTING.md` | `CONTRIBUTING.pt-BR.md` |
| `SECURITY.md` | `SECURITY.pt-BR.md` |
| `CODE_OF_CONDUCT.md` | `CODE_OF_CONDUCT.pt-BR.md` |
| `CHANGELOG.md` | `CHANGELOG.pt-BR.md` |

Regras da tradução:

1. **Mesmas seções, na mesma ordem.** Se o inglês tem 13 títulos, o português
   tem 13 títulos equivalentes.
2. **Tradução integral.** Proibido: traduzir o começo e deixar o resto em
   inglês; escrever "*veja a versão em inglês para mais detalhes*"; resumir
   uma seção que no original é completa.
3. **Alterou um, altera o outro no mesmo commit.** Nunca deixe para depois.
4. Cabeçalho de cada um aponta para o outro.

**Verificar:** `python scripts/check_rules.py` (compara os títulos).

### R3 — Nada de segredo ou dado pessoal no repositório

- `.env`, `usage.db`, `prefs.json`, `logs/` nunca são commitados.
- Nenhuma chave de API, nem em exemplo, nem em log, nem em mensagem de erro.
- Nunca usar o e-mail de trabalho do usuário em nada público (o verificador
  conhece o endereço e o bloqueia). Identidade dos commits:
  `Bruno Fontes <172863790+fontesmidias@users.noreply.github.com>`.

**Verificar:** `python scripts/check_rules.py` (varre arquivos e histórico).

### R4 — Nenhum modelo entra na configuração sem ter sido testado

Catálogos de provedores listam modelos que retornam 404, 410 ou 402. Antes de
adicionar ou mudar um modelo em `saci/providers.py`, rode `saci --refresh` e
confirme que ele respondeu `200`. Nunca confie na documentação do provedor,
nem na sua memória de treinamento.

### R5 — Stack simples, mantível por IA barata

Python + HTML puro. **Proibido sem autorização explícita do usuário:**
Electron, Tauri, React, Vue, build pipeline, TypeScript, bundler.

*Por quê:* o objetivo do projeto é o usuário conseguir manter o código com
modelos gratuitos de 27B. Esses modelos se perdem em projetos com build
complexo. Simplicidade aqui é requisito, não preferência.

### R6 — Medir antes de afirmar

Nunca escrever no código, na documentação ou para o usuário que algo
"funciona", "é rápido" ou "está disponível" sem ter executado e visto o
resultado. Se não deu para testar, diga que não testou.

---

## Como trabalhar aqui

- **Idioma com o usuário:** português, com acentuação correta.
- **Antes de commitar:** rode `python scripts/check_rules.py`. Se falhar,
  corrija — não commite por cima.
- **Ao terminar uma etapa:** diga se o próximo passo é *planejar* (modelo
  forte) ou *executar* (modelo econômico).
- **Contexto do projeto:** o usuário está se preparando para não depender
  mais de planos pagos de IA. Cada decisão deve considerar isso.

## Estrutura

```
saci/              pacote: router, catálogo, contabilidade, servidor, CLI, painel
scripts/           utilitários (check_rules.py, discover.py, smoke_test.py)
vscode-statusbar/  extensão local do VSCode
*.cmd              atalhos Windows (CRLF obrigatório — cmd.exe exige)
```

Detalhes técnicos: [README.pt-BR.md](README.pt-BR.md).
